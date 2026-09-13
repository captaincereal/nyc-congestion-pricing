"""Download the NYC DOT E-Z Pass **local street** speed feeds into ``data/raw/``.

This is the PRIMARY source from 2026-09-08 onward. See the decision record in
``docs/methodology.md`` for why it replaced ``i4gi-tjb9`` (that feed carries only
~123 links city-wide and none on tolled CRZ surface streets).

Two Socrata datasets with identical schemas and the same 351 ``sid``s, joining
with no gap:

    erdf-2akx   2021-04-08 .. 2024-07-07
    6a2s-2t65   2024-07-08 .. present

The split is handled transparently: each calendar month is routed to whichever
dataset covers it (``EZPASS_SPLIT_DATE``). July 2024 straddles the boundary and
is fetched from both, then concatenated.

Strategy mirrors ``src.data.download`` — one parquet part per calendar month,
resumable, with optional raw-page counts and deterministic sample replay, and
a manifest rewritten after every month:

    data/raw/ezpass_speeds/ezpass_speeds_YYYY-MM.parquet
    data/raw/ezpass_manifest.json

Server-side filters cut ~190M raw rows to the study window:
``aggregation_period_sec = 900`` (the feed also emits 0) and the requested
month. Raw parts are never edited; speed stays in feet/second here and is
converted to mph in staging.

Usage
-----
    python -m src.data.download_ezpass --start 2023-01-01
    python -m src.data.download_ezpass --start 2023-01-01 --verify
    python -m src.data.download_ezpass --start 2023-01-01 --force
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import time
from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from urllib3.util import Timeout

from src.config import (
    EZPASS_AGG_PERIOD_SEC,
    EZPASS_CHUNK_DAYS,
    EZPASS_DATASET_IDS,
    EZPASS_DAYS_DIR,
    EZPASS_MANIFEST_PATH,
    EZPASS_PARTS_DIR,
    EZPASS_READING_COLS,
    EZPASS_SEGMENTS_PATH,
    EZPASS_SPLIT_DATE,
    EZPASS_TIME_COL,
    EZPASS_WINDOW_MINUTES,
    SOCRATA_DOMAIN,
    STUDY_START,
)
from src.data.download import (
    HTTP_TIMEOUT,
    PAGE_SIZE,
    PartRecord,
    _iter_months,
    _load_existing_parts,
    _month_bounds,
    _session,
    _sha256,
    write_manifest,
)

log = logging.getLogger(__name__)

DATASET_BEFORE_SPLIT = "erdf-2akx"
DATASET_AFTER_SPLIT = "6a2s-2t65"

# A single day of readings is ~320-375k rows (measured 2026-09-10), so a page
# this size normally fetches a whole day in ONE request instead of the ~7 that
# PAGE_SIZE=50_000 (src.data.download's default, tuned for the secondary feed)
# would need. Fewer requests per day means less exposure to Socrata's
# per-request throttling; it does NOT lift the underlying throughput ceiling
# (measured: the server resets the connection after 2-3 consecutive big
# requests regardless of size), which is why retries below are now logged
# rather than silent - a stall now shows as visible backoff, not a hang.
EZPASS_PAGE_SIZE = 400_000

# Bump this when replay or sampling semantics change. Receipts bind this
# algorithm to an immutable parquet hash; they are evidence at their recorded
# check times, not a guarantee that the upstream feed can never be revised.
VERIFICATION_METHOD = "raw-count-and-deterministic-replay-v1"


@dataclass
class EzpassPartRecord(PartRecord):
    verified: bool = False
    verification_method: str | None = None
    verified_at: str | None = None
    source_rows: int | None = None
    verification_error: str | None = None


_EZPASS_PART_FIELDS = frozenset(f.name for f in fields(EzpassPartRecord))


class VerificationError(RuntimeError):
    """Raw paging or the retained sample disagrees with its independent check."""


def _datasets_for_month(month: date) -> list[str]:
    """Which dataset(s) cover ``month``.

    July 2024 straddles the handover (erdf-2akx ends 2024-07-07, 6a2s-2t65
    starts 2024-07-08), so that month alone needs both.
    """
    split = EZPASS_SPLIT_DATE
    month_start = month.replace(day=1)
    next_month = (
        date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    )
    if next_month <= split:
        return [DATASET_BEFORE_SPLIT]
    if month_start >= split:
        return [DATASET_AFTER_SPLIT]
    return [DATASET_BEFORE_SPLIT, DATASET_AFTER_SPLIT]


def _where(month: date) -> str:
    """SoQL filter for a whole month (used for counts and the manifest record).

    Kept index-friendly: plain range predicates only. An earlier version added
    ``date_extract_mm(...) IN (...)`` to downsample server-side, which put a
    function on the indexed timestamp column and made deep paging collapse -- a
    50k page at offset 500,000 took 255.8s versus 3.7s without it. The
    downsample now happens client-side in :func:`_downsample`.
    """
    lo, hi = _month_bounds(month)
    return (
        f"{EZPASS_TIME_COL} >= '{lo}' AND {EZPASS_TIME_COL} < '{hi}'"
        f" AND aggregation_period_sec = {EZPASS_AGG_PERIOD_SEC}"
    )


def _day_where(day: date) -> str:
    """SoQL filter for a single day."""
    nxt = day + timedelta(days=EZPASS_CHUNK_DAYS)
    return (
        f"{EZPASS_TIME_COL} >= '{day:%Y-%m-%d}T00:00:00'"
        f" AND {EZPASS_TIME_COL} < '{nxt:%Y-%m-%d}T00:00:00'"
        f" AND aggregation_period_sec = {EZPASS_AGG_PERIOD_SEC}"
    )


def _days_in_month(month: date):
    cur = month.replace(day=1)
    nxt = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    while cur < nxt:
        yield cur
        cur += timedelta(days=EZPASS_CHUNK_DAYS)


class TimeBudgetExceeded(RuntimeError):
    """The wall-clock budget ran out mid-month.

    Not an error: day checkpoints are on disk, so the next run resumes from
    them. Raised so the caller stops cleanly instead of being hard-killed
    partway through writing a part.
    """


def _day_part_path(day: date) -> Path:
    return EZPASS_DAYS_DIR / f"ezpass_day_{day:%Y-%m-%d}.parquet"


def _day_receipt_path(day: date) -> Path:
    return EZPASS_DAYS_DIR / f"ezpass_day_{day:%Y-%m-%d}.receipt.json"


def _valid_day_evidence(evidence: object, sample_rows: int) -> bool:
    """Validate cached counts and check time before trusting a matching hash."""
    if not isinstance(evidence, dict):
        return False
    source_rows = evidence.get("source_rows")
    retained_rows = evidence.get("sample_rows")
    if (
        type(source_rows) is not int
        or type(retained_rows) is not int
        or source_rows < retained_rows
        or retained_rows != sample_rows
        or retained_rows < 0
    ):
        return False
    try:
        checked_at = datetime.fromisoformat(evidence["checked_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return checked_at.utcoffset() is not None


def _checkpoint_evidence(day: date, path: Path, sample_rows: int) -> dict | None:
    try:
        evidence = json.loads(_day_receipt_path(day).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if (
        _valid_day_evidence(evidence, sample_rows)
        and evidence.get("day") == str(day)
        and evidence.get("verification_method") == VERIFICATION_METHOD
        and evidence.get("checkpoint_sha256") == _sha256(path)
    ):
        return evidence
    return None


def _record_checked_day(day: date, path: Path, replay: pd.DataFrame, source_rows: int) -> dict:
    # Verify what was persisted, so the receipt binds source-checked sample
    # values to the actual checkpoint bytes used by a later month assembly.
    _assert_same_sample(pd.read_parquet(path), replay, str(day))
    evidence = {
        "day": str(day),
        "checkpoint_sha256": _sha256(path),
        "verification_method": VERIFICATION_METHOD,
        "source_rows": source_rows,
        "sample_rows": len(replay),
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if not _valid_day_evidence(evidence, len(replay)):
        raise VerificationError(f"{day}: invalid raw-count evidence for the retained sample")
    _save_receipt(_day_receipt_path(day), evidence)
    return evidence


def _write_parquet_atomic(df: pd.DataFrame, dest: Path) -> None:
    """Write via a temp file and rename, so a kill never leaves a torn parquet."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    df.to_parquet(tmp, engine="pyarrow", index=False)
    tmp.replace(dest)


def _month_has_checkpoints(month: date) -> bool:
    """Whether an interrupted run left day checkpoints for this month."""
    return any(_day_part_path(day).exists() for day in _days_in_month(month))


def _downsample(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one reading per (sid, non-overlapping N-minute window).

    The feed publishes a rolling 900s median about every 61s, so neighbouring
    rows overlap ~93% and are frequently identical. Prefer the median built
    from the most probe samples; ties break on the earliest timestamp so the
    result is deterministic across re-runs.
    """
    if df.empty:
        return df
    out = df.copy()
    ts = pd.to_datetime(out[EZPASS_TIME_COL], errors="coerce")
    out = out[ts.notna()]
    ts = ts[ts.notna()]
    freq = f"{EZPASS_WINDOW_MINUTES}min"
    out["_window"] = ts.dt.floor(freq)
    out["_n"] = pd.to_numeric(out["n_samples"], errors="coerce").fillna(-1)
    out["_ts"] = ts
    out = (
        out.sort_values(["sid", "_window", "_n", "_ts"], ascending=[True, True, False, True])
        .drop_duplicates(["sid", "_window"], keep="first")
        .drop(columns=["_window", "_n", "_ts"])
        .reset_index(drop=True)
    )
    return out


def _base(dataset_id: str) -> str:
    return f"https://{SOCRATA_DOMAIN}/resource/{dataset_id}"


def _time_left(deadline: float | None) -> float:
    """Bound one HTTP attempt by the shared job budget, including its retries."""
    if deadline is None:
        return float(HTTP_TIMEOUT)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeBudgetExceeded("budget spent before the next HTTP request or retry")
    return remaining


def _request(
    session: requests.Session,
    url: str,
    params: dict,
    *,
    deadline: float | None = None,
    max_attempts: int = 5,
) -> requests.Response:
    """Retry transport failures without restarting the caller's time budget.

    The total timeout shares a limit across connection and socket reads. Like
    all Requests timeouts it is not a process watchdog; check the clock again
    after each response and before every backoff or retry.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    for attempt in range(max_attempts):
        request_budget = min(float(HTTP_TIMEOUT), _time_left(deadline))
        response = None
        try:
            response = session.get(url, params=params, timeout=Timeout(total=request_budget))
            response.raise_for_status()
        except requests.RequestException as exc:
            if response is not None:
                response.close()
            remaining = _time_left(deadline)
            if attempt + 1 == max_attempts:
                raise
            backoff = min(60.0, 2.0 ** (attempt + 1))
            if deadline is not None and backoff >= remaining:
                raise TimeBudgetExceeded("insufficient budget for the next HTTP retry") from exc
            log.warning(
                "HTTP attempt %d/%d failed (%s); retrying in %.0fs",
                attempt + 1,
                max_attempts,
                type(exc).__name__,
                backoff,
            )
            time.sleep(backoff)
        else:
            if deadline is not None and time.monotonic() >= deadline:
                response.close()
                raise TimeBudgetExceeded("budget spent while waiting for the HTTP response")
            return response
    raise AssertionError("HTTP retry loop ended without a response or exception")


def _count(
    session: requests.Session, dataset_id: str, where: str, *, deadline: float | None = None
) -> int:
    resp = _request(
        session,
        _base(dataset_id) + ".json",
        params={"$select": "count(1) as n", "$where": where},
        deadline=deadline,
    )
    return int(resp.json()[0]["n"])


def _get_page(
    session: requests.Session,
    dataset_id: str,
    params: dict,
    *,
    deadline: float | None = None,
    max_attempts: int = 5,
) -> requests.Response:
    return _request(
        session,
        _base(dataset_id) + ".csv",
        params=params,
        deadline=deadline,
        max_attempts=max_attempts,
    )


def _fetch_pages(
    session: requests.Session,
    dataset_id: str,
    where: str,
    *,
    select: str | None = None,
    page_size: int = PAGE_SIZE,
    deadline: float | None = None,
) -> list[pd.DataFrame]:
    """Page through one dataset for one filter, ordered for stable offset paging."""
    frames: list[pd.DataFrame] = []
    offset = 0
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeBudgetExceeded("budget spent before the next API page")
        params = {
            "$where": where,
            "$order": f"{EZPASS_TIME_COL},sid",
            "$limit": page_size,
            "$offset": offset,
        }
        if select:
            params["$select"] = select
        try:
            resp = _get_page(
                session,
                dataset_id,
                params,
                deadline=deadline,
                max_attempts=1 if page_size > PAGE_SIZE else 5,
            )
        except (
            requests.Timeout,
            requests.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ):
            if page_size <= PAGE_SIZE:
                raise
            log.warning(
                "large CSV page failed at offset %d; reducing %d -> %d rows "
                "and retrying that offset",
                offset,
                page_size,
                PAGE_SIZE,
            )
            page_size = PAGE_SIZE
            continue
        try:
            page = pd.read_csv(io.BytesIO(resp.content), dtype=str)
        finally:
            resp.close()
        if page.empty:
            break
        frames.append(page)
        offset += len(page)
        if len(page) < page_size:
            break
    return frames


def _fetch_day(
    session: requests.Session, day: date, datasets: list[str], *, deadline: float | None = None
) -> pd.DataFrame:
    """Fetch and downsample one day across the dataset(s) covering it.

    Downsampling per day (rather than per month) keeps peak memory to one day of
    raw readings — ~335k rows — instead of the ~10.4M a month would hold. Using
    EZPASS_PAGE_SIZE (~a day's worth of rows) means the common case is ONE
    request per dataset per day rather than ~7 offset pages.
    """
    return _read_day(session, day, datasets, deadline=deadline)[0]


def _read_day(
    session: requests.Session,
    day: date,
    datasets: list[str],
    *,
    check_count: bool = False,
    deadline: float | None = None,
) -> tuple[pd.DataFrame, int]:
    """Count raw pages before sampling; compare like units when requested."""
    where = _day_where(day)
    select = ",".join(EZPASS_READING_COLS)
    frames: list[pd.DataFrame] = []
    raw_rows = 0
    for ds in datasets:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeBudgetExceeded("budget spent before the next dataset")
        expected = _count(session, ds, where, deadline=deadline) if check_count else None
        if expected == 0:
            log.info("  %s %s: live count is zero; no CSV fetch needed", day, ds)
            continue
        pages = _fetch_pages(
            session, ds, where, select=select, page_size=EZPASS_PAGE_SIZE, deadline=deadline
        )
        seen = sum(len(page) for page in pages)
        if expected is not None and seen != expected:
            raise VerificationError(f"{day} {ds}: {seen} raw rows fetched; expected {expected}")
        frames.extend(pages)
        raw_rows += seen
    if not frames:
        return pd.DataFrame(columns=list(EZPASS_READING_COLS)), raw_rows
    sampled = _downsample(pd.concat(frames, ignore_index=True))
    log.info("  %s: %s raw -> %s sampled rows (one per sid/window)", day, raw_rows, len(sampled))
    return sampled, raw_rows


def _canonical_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Compare typed retained values, independently of row order or CSV spelling."""
    out = df.loc[:, list(EZPASS_READING_COLS)].copy()
    out["sid"] = out["sid"].astype("string")
    out[EZPASS_TIME_COL] = pd.to_datetime(out[EZPASS_TIME_COL], errors="raise")
    if out["sid"].isna().any() or out[EZPASS_TIME_COL].isna().any():
        raise VerificationError("sample contains a missing sid or timestamp")
    for col in ("median_speed_fps", "median_tt_sec", "n_samples"):
        out[col] = pd.to_numeric(out[col], errors="raise").astype("float64")
    return out.sort_values(list(EZPASS_READING_COLS)).reset_index(drop=True)


def _assert_same_sample(disk: pd.DataFrame, replay: pd.DataFrame, label: str) -> None:
    if not _canonical_sample(disk).equals(_canonical_sample(replay)):
        raise VerificationError(
            f"{label}: retained sample differs from counted raw replay "
            f"(disk={len(disk)}, replay={len(replay)}); raw part left unchanged"
        )


def download_month(
    session: requests.Session,
    month: date,
    *,
    force: bool,
    prior: dict | None = None,
    do_count: bool = False,
    deadline: float | None = None,
) -> EzpassPartRecord:
    if month.replace(day=1) >= date.today().replace(day=1):
        raise ValueError("only completed calendar months can be downloaded or verified")
    dest = EZPASS_PARTS_DIR / f"ezpass_speeds_{month:%Y-%m}.parquet"
    where = _where(month)
    datasets = _datasets_for_month(month)

    if dest.exists() and not force:
        if do_count:
            return _verify_part(session, month, prior=prior, deadline=deadline)
        log.info("skip %s (exists)", dest.name)
        sha = _sha256(dest)
        if prior and prior.get("sha256") == sha:
            rec = EzpassPartRecord(**{k: prior[k] for k in _EZPASS_PART_FIELDS if k in prior})
            # Older flags came from incomparable raw/sample counts, or from
            # PartRecord's default True. Neither establishes replay verification.
            rec.verified = bool(rec.verified and rec.verification_method == VERIFICATION_METHOD)
            return rec
        rows = int(pd.read_parquet(dest, columns=[EZPASS_TIME_COL]).shape[0])
        expected = prior["rows_expected"] if prior and "rows_expected" in prior else rows
        return EzpassPartRecord(
            part=dest.name,
            month=f"{month:%Y-%m}",
            where=where,
            rows=rows,
            rows_expected=expected,
            bytes=dest.stat().st_size,
            sha256=sha,
            pulled_at=prior.get("pulled_at", "(pre-existing)") if prior else "(pre-existing)",
            complete=rows == expected,
        )

    log.info(
        "GET %s from %s (%s)",
        f"{month:%Y-%m}",
        "+".join(datasets),
        "daily raw counts enabled" if do_count else "row count not pre-checked",
    )

    # Each day is checkpointed to disk as it lands. Before this, a month was
    # held in memory and written only on completion, so a kill at minute 35 of
    # 40 discarded all 35 -- which is how partial 2024-07 and 2023-11 pulls
    # were lost. Now an interruption costs one day.
    day_paths: list[Path] = []
    resumed = 0
    raw_seen = 0
    source_rows = 0
    checked_days: dict[str, dict] = {}
    for day in _days_in_month(month):
        dpath = _day_part_path(day)
        if dpath.exists() and not force:
            held = pd.read_parquet(dpath)
            if do_count:
                evidence = _checkpoint_evidence(day, dpath, len(held))
                if evidence is None:
                    if deadline is not None and time.monotonic() >= deadline:
                        raise TimeBudgetExceeded(f"{month:%Y-%m}: budget spent; checkpoints kept")
                    replay, seen = _read_day(
                        session, day, datasets, check_count=True, deadline=deadline
                    )
                    evidence = _record_checked_day(day, dpath, replay, seen)
                checked_days[str(day)] = evidence
                source_rows += evidence["source_rows"]
            day_paths.append(dpath)
            raw_seen += len(held)
            resumed += 1
            continue
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeBudgetExceeded(
                f"{month:%Y-%m}: budget spent after {len(day_paths)} day(s); "
                "checkpoints kept, resuming next run"
            )
        if do_count:
            chunk, seen = _read_day(session, day, datasets, check_count=True, deadline=deadline)
            source_rows += seen
        else:
            chunk = _fetch_day(session, day, datasets, deadline=deadline)
        _write_parquet_atomic(chunk, dpath)
        if do_count:
            checked_days[str(day)] = _record_checked_day(day, dpath, chunk, seen)
        day_paths.append(dpath)
        raw_seen += len(chunk)
        log.info("  %s: %s kept rows so far", f"{month:%Y-%m}", f"{raw_seen:,}")
    if resumed:
        log.info("  %s: resumed %d day(s) from checkpoints", f"{month:%Y-%m}", resumed)

    frames = [pd.read_parquet(p) for p in day_paths]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    _write_parquet_atomic(df, dest)

    rows = len(df)
    part_sha256 = _sha256(dest)
    if do_count:
        _assert_same_sample(pd.read_parquet(dest), df, f"{month:%Y-%m}")
        # Every day was counted before deterministic sampling and compared to
        # persisted checkpoint bytes. Bind those same checks to the assembled
        # month before publishing its verified manifest flag or deleting days.
        receipt = {
            "part_sha256": part_sha256,
            "verification_method": VERIFICATION_METHOD,
            "month": f"{month:%Y-%m}",
            "days": {
                tag: {key: evidence[key] for key in ("source_rows", "sample_rows", "checked_at")}
                for tag, evidence in checked_days.items()
            },
        }
        _save_receipt(_receipt_path(month), receipt)
    log.info("wrote %s (%s rows, %.1f MB)", dest.name, f"{rows:,}", dest.stat().st_size / 1e6)

    # The month part is durable now, so the day checkpoints have done their job.
    for p in day_paths:
        p.unlink(missing_ok=True)
        p.with_suffix(".receipt.json").unlink(missing_ok=True)

    return EzpassPartRecord(
        part=dest.name,
        month=f"{month:%Y-%m}",
        where=where,
        rows=rows,
        rows_expected=rows,
        bytes=dest.stat().st_size,
        sha256=part_sha256,
        pulled_at=datetime.now(UTC).isoformat(timespec="seconds"),
        complete=True,
        verified=do_count,
        verification_method=VERIFICATION_METHOD if do_count else None,
        verified_at=datetime.now(UTC).isoformat(timespec="seconds") if do_count else None,
        source_rows=source_rows if do_count else None,
    )


# One sample day per period. The active segment roster CHANGES over time, so a
# single day is not enough: building the table from 2025-01-06 alone left 32
# sids (7.9% of October 2024 readings) with no borough or geometry, and so no
# treatment group. These span both datasets and the whole study window.
SEGMENT_SAMPLE_DAYS = (
    date(2023, 1, 10),
    date(2023, 7, 11),
    date(2024, 1, 10),
    date(2024, 6, 11),
    date(2024, 10, 9),
    date(2025, 1, 6),
    date(2025, 7, 9),
    date(2026, 1, 7),
    date(2026, 6, 10),
    # Added 2026-09-13. The archive now runs to 2026-08-31, and sampling only to
    # 2026-06 left a segment in the readings with no attribute row: the panel
    # build put 586 link-hours in an `unassigned` group and `hard_unmatched_segments`
    # stopped the analysis. Extend this whenever the window extends.
    date(2026, 8, 12),
)


def fetch_segments(
    session: requests.Session,
    sample_days: tuple[date, ...] = SEGMENT_SAMPLE_DAYS,
    *,
    deadline: float | None = None,
) -> pd.DataFrame:
    """Fetch the per-segment attribute table (sid -> name, borough, geometry).

    These columns are constant per segment, so they are pulled once here rather
    than repeated on all ~450M readings. Sampling a day is far cheaper than a
    GROUP BY over the full table (that query timed out repeatedly during
    development), but it must be several days spread across the study window --
    see SEGMENT_SAMPLE_DAYS for why one is not enough.
    """
    cols = "sid,link_name,borough,polyline,link_length_ft"
    frames: list[pd.DataFrame] = []
    for day in sample_days:
        for ds in _datasets_for_month(day):
            try:
                frames.extend(
                    _fetch_pages(session, ds, _day_where(day), select=cols, deadline=deadline)
                )
            except TimeBudgetExceeded:
                raise
            except Exception:  # noqa: BLE001 - one bad sample day must not lose the rest
                log.exception("segment sample failed for %s on %s", day, ds)
        log.info("  segments: %s sampled", day)
    if not frames:
        raise SystemExit("no segment rows returned for any sample day")
    seg = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["sid"])
        .sort_values("sid")
        .reset_index(drop=True)
    )
    EZPASS_SEGMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    seg.to_parquet(EZPASS_SEGMENTS_PATH, engine="pyarrow", index=False)
    log.info("wrote %s (%d segments)", EZPASS_SEGMENTS_PATH.name, len(seg))
    return seg


def _write(parts_by_month: dict[str, dict]) -> None:
    write_manifest(
        parts_by_month,
        path=EZPASS_MANIFEST_PATH,
        dataset_id="+".join(EZPASS_DATASET_IDS),
        time_col=EZPASS_TIME_COL,
    )


def _receipt_path(month: date) -> Path:
    return EZPASS_MANIFEST_PATH.parent / "ezpass_verification" / f"ezpass_verify_{month:%Y-%m}.json"


def _save_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(receipt, indent=2))
    tmp.replace(path)


def _verify_part(
    session: requests.Session,
    month: date,
    *,
    prior: dict | None = None,
    deadline: float | None = None,
) -> EzpassPartRecord:
    """Replay a part day by day, resuming receipts bound to its hash and method.

    A receipt establishes equivalence at its ``checked_at`` time. Historical
    revisions after that time require removing the receipt and clearing the
    manifest's verified flag before a fresh audit. Raw parquet is never changed.
    """
    rec = download_month(session, month, force=False, prior=prior)
    dest = EZPASS_PARTS_DIR / rec.part
    disk = pd.read_parquet(dest, columns=list(EZPASS_READING_COLS))
    ts = pd.to_datetime(disk[EZPASS_TIME_COL], errors="raise")
    lo, hi = _month_bounds(month)
    if ts.isna().any() or not ((ts >= lo) & (ts < hi)).all():
        raise VerificationError(f"{rec.month}: part contains missing or out-of-month timestamps")
    path = _receipt_path(month)
    identity = {
        "part_sha256": rec.sha256,
        "verification_method": VERIFICATION_METHOD,
        "month": rec.month,
    }
    try:
        receipt = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        receipt = {}
    if (
        not isinstance(receipt, dict)
        or any(receipt.get(k) != v for k, v in identity.items())
        or not isinstance(receipt.get("days"), dict)
    ):
        receipt = {**identity, "days": {}}
    days = list(_days_in_month(month))
    day_tags = {str(day) for day in days}
    receipt["days"] = {tag: value for tag, value in receipt["days"].items() if tag in day_tags}
    source_rows = 0
    replayed = 0
    for day in days:
        tag = str(day)
        held = disk.loc[(ts >= str(day)) & (ts < str(day + timedelta(days=EZPASS_CHUNK_DAYS)))]
        cached = receipt["days"].get(tag)
        if _valid_day_evidence(cached, len(held)):
            source_rows += cached["source_rows"]
            continue
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeBudgetExceeded(
                f"verify {rec.month}: budget spent after {len(receipt['days'])}/{len(days)} "
                "checked days; receipts kept"
            )
        replay, seen = _read_day(
            session, day, _datasets_for_month(month), check_count=True, deadline=deadline
        )
        _assert_same_sample(held, replay, tag)
        receipt["days"][tag] = {
            "source_rows": seen,
            "sample_rows": len(replay),
            "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        _save_receipt(path, receipt)
        replayed += 1
        source_rows += seen
        log.info("verify %s: %d/%d days checked", rec.month, len(receipt["days"]), len(days))
    # Even a manifest already marked verified needs its complete day receipt:
    # older counted downloads set the flag without publishing this evidence.
    _save_receipt(path, receipt)
    if not rec.verified or replayed:
        rec.verified_at = datetime.now(UTC).isoformat(timespec="seconds")
    rec.rows_expected = rec.rows
    rec.complete = True
    rec.verified = True
    rec.verification_method = VERIFICATION_METHOD
    rec.source_rows = source_rows
    rec.verification_error = None
    return rec


def verify(
    session: requests.Session,
    start: date,
    end: date,
    *,
    deadline: float | None = None,
    existing_only: bool = False,
) -> None:
    """Count raw pages and replay the immutable sample, saving monthly results.

    Existing verified hashes and successful day receipts resume earlier audits.
    A budget exit is clean; mismatches, missing parts and network errors fail.
    """
    problems: list[str] = []
    budget_spent = False
    parts = _load_existing_parts(EZPASS_MANIFEST_PATH)
    for month in _iter_months(start, end):
        tag = f"{month:%Y-%m}"
        dest = EZPASS_PARTS_DIR / f"ezpass_speeds_{tag}.parquet"
        if not dest.exists():
            if existing_only:
                continue
            log.warning("%s  MISSING on disk", tag)
            problems.append(tag)
            if tag in parts:
                parts[tag].update(complete=False, verified=False, verification_error="missing part")
                _write(parts)
            continue
        prior = parts.get(tag, {})
        try:
            # Persist an honest state before a replay that may be interrupted.
            rec = download_month(session, month, force=False, prior=prior)
            parts[tag] = {**prior, **asdict(rec)}
            _write(parts)
            rec = _verify_part(session, month, prior=parts[tag], deadline=deadline)
            parts[tag].update(asdict(rec))
            _write(parts)
        except TimeBudgetExceeded as exc:
            log.info("%s", exc)
            budget_spent = True
            break
        except Exception as exc:  # noqa: BLE001 - downgrade stale verification on failure
            log.exception("verify failed for %s", tag)
            if tag in parts:
                parts[tag].update(
                    complete=False, verified=False, verified_at=None, verification_error=str(exc)
                )
                _write(parts)
            problems.append(tag)
    if problems:
        raise SystemExit(f"verify: {len(problems)} problem month(s): {', '.join(problems)}")
    if not budget_spent:
        log.info("verify: checked all requested parts (or resumed prior verified hashes)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, default=STUDY_START)
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="exclusive upper bound on month starts; capped at the current month (default)",
    )
    parser.add_argument("--force", action="store_true", help="re-download existing months")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="count raw pages and replay retained samples; resume prior verified hashes/days",
    )
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="with --verify, check only present parts; archive coverage remains a separate check",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="check fetched raw day counts before sampling; replay existing samples; "
        "adds count queries and is off by default",
    )
    parser.add_argument(
        "--segments",
        action="store_true",
        help="fetch only the per-segment attribute table and exit",
    )
    parser.add_argument(
        "--max-runtime",
        type=float,
        default=None,
        metavar="MINUTES",
        help="stop cleanly after this long, leaving day checkpoints for the "
        "next run. Set it below the CI job limit so the job exits rather than "
        "being killed mid-write.",
    )
    parser.add_argument(
        "--month-budget",
        type=float,
        default=50.0,
        metavar="MINUTES",
        help="don't start a fresh month with less than this much budget left "
        "(default: 50, a slow month). Clean exits then land on month "
        "boundaries, where nothing is in flight.",
    )
    args = parser.parse_args()
    if args.verify_existing and not args.verify:
        parser.error("--verify-existing requires --verify")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Shared secondary-feed iteration is inclusive. Primary callers and the
    # priority script use an exclusive end; never freeze an in-progress month
    # into a supposedly complete immutable part that future runs would skip.
    exclusive_end = min(args.end or date.today().replace(day=1), date.today().replace(day=1))
    end = exclusive_end - timedelta(days=1)
    session = _session()
    deadline = time.monotonic() + args.max_runtime * 60 if args.max_runtime else None

    if args.segments:
        try:
            fetch_segments(session, deadline=deadline)
        except TimeBudgetExceeded as exc:
            log.info("%s", exc)
        return

    if args.verify:
        verify(session, args.start, end, deadline=deadline, existing_only=args.verify_existing)
        return

    if not EZPASS_SEGMENTS_PATH.exists():
        log.info("segment table missing - fetching it first")
        try:
            fetch_segments(session, deadline=deadline)
        except TimeBudgetExceeded as exc:
            log.info("%s", exc)
            return

    parts_by_month = _load_existing_parts(EZPASS_MANIFEST_PATH)
    failures: list[str] = []
    remaining: list[str] = []
    months = list(_iter_months(args.start, end))
    for i, month in enumerate(months):
        tag = f"{month:%Y-%m}"
        if deadline is not None and not _month_has_checkpoints(month):
            left = (deadline - time.monotonic()) / 60
            if left < args.month_budget:
                log.info(
                    "stopping before %s: %.0f min left, under the %.0f min a month needs",
                    tag,
                    max(left, 0),
                    args.month_budget,
                )
                remaining = [f"{m:%Y-%m}" for m in months[i:]]
                break
        try:
            rec = download_month(
                session,
                month,
                force=args.force,
                prior=parts_by_month.get(tag),
                do_count=args.count,
                deadline=deadline,
            )
            parts_by_month[rec.month] = asdict(rec)
            _write(parts_by_month)
        except TimeBudgetExceeded as exc:
            log.info("%s", exc)
            remaining = [f"{m:%Y-%m}" for m in months[i:]]
            break
        except Exception:  # noqa: BLE001 - record and continue
            log.exception("failed month: %s", tag)
            failures.append(tag)

    if remaining:
        log.info("%d month(s) still to pull, next run starts at %s", len(remaining), remaining[0])

    if failures:
        raise SystemExit(f"download failed for months: {', '.join(failures)}")


if __name__ == "__main__":
    main()
