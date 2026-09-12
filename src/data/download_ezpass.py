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
resumable, with a per-month row-count check against a live ``count(1)`` and a
manifest rewritten after every month:

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
import logging
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import requests
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from src.config import (
    EZPASS_AGG_PERIOD_SEC,
    EZPASS_CHUNK_DAYS,
    EZPASS_DATASET_IDS,
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
    _PART_FIELDS,
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
    nxt = (
        date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    )
    while cur < nxt:
        yield cur
        cur += timedelta(days=EZPASS_CHUNK_DAYS)


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


_retry_logged = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    before_sleep=before_sleep_log(log, logging.WARNING),
)


@_retry_logged
def _count(session: requests.Session, dataset_id: str, where: str) -> int:
    resp = session.get(
        _base(dataset_id) + ".json",
        params={"$select": "count(1) as n", "$where": where},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return int(resp.json()[0]["n"])


@_retry_logged
def _get_page(session: requests.Session, dataset_id: str, params: dict) -> requests.Response:
    resp = session.get(_base(dataset_id) + ".csv", params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp


def _fetch_pages(
    session: requests.Session,
    dataset_id: str,
    where: str,
    *,
    select: str | None = None,
    page_size: int = PAGE_SIZE,
) -> list[pd.DataFrame]:
    """Page through one dataset for one filter, ordered for stable offset paging."""
    frames: list[pd.DataFrame] = []
    offset = 0
    while True:
        params = {
            "$where": where,
            "$order": f"{EZPASS_TIME_COL},sid",
            "$limit": page_size,
            "$offset": offset,
        }
        if select:
            params["$select"] = select
        resp = _get_page(session, dataset_id, params)
        page = pd.read_csv(io.BytesIO(resp.content), dtype=str)
        if page.empty:
            break
        frames.append(page)
        offset += len(page)
        if len(page) < page_size:
            break
    return frames


def _fetch_day(session: requests.Session, day: date, datasets: list[str]) -> pd.DataFrame:
    """Fetch and downsample one day across the dataset(s) covering it.

    Downsampling per day (rather than per month) keeps peak memory to one day of
    raw readings — ~335k rows — instead of the ~10.4M a month would hold. Using
    EZPASS_PAGE_SIZE (~a day's worth of rows) means the common case is ONE
    request per dataset per day rather than ~7 offset pages.
    """
    where = _day_where(day)
    select = ",".join(EZPASS_READING_COLS)
    frames: list[pd.DataFrame] = []
    for ds in datasets:
        frames.extend(_fetch_pages(session, ds, where, select=select, page_size=EZPASS_PAGE_SIZE))
    if not frames:
        return pd.DataFrame(columns=list(EZPASS_READING_COLS))
    return _downsample(pd.concat(frames, ignore_index=True))


def download_month(
    session: requests.Session,
    month: date,
    *,
    force: bool,
    prior: dict | None = None,
    do_count: bool = False,
) -> PartRecord:
    dest = EZPASS_PARTS_DIR / f"ezpass_speeds_{month:%Y-%m}.parquet"
    where = _where(month)
    datasets = _datasets_for_month(month)

    if dest.exists() and not force:
        log.info("skip %s (exists)", dest.name)
        sha = _sha256(dest)
        if prior and prior.get("sha256") == sha:
            return PartRecord(**{k: prior[k] for k in _PART_FIELDS if k in prior})
        rows = int(pd.read_parquet(dest, columns=[EZPASS_TIME_COL]).shape[0])
        expected = prior["rows_expected"] if prior and "rows_expected" in prior else rows
        return PartRecord(
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

    # The minute filter puts a function on the timestamp column, which stops
    # Socrata using its index: a whole-month count(1) then runs for many minutes
    # and can time out. The count only verifies completeness, so it is off by
    # default here and available on demand via --count / --verify.
    expected = sum(_count(session, ds, where) for ds in datasets) if do_count else None
    log.info(
        "GET %s from %s (%s)",
        f"{month:%Y-%m}",
        "+".join(datasets),
        f"expected {expected:,} rows" if expected is not None else "row count not pre-checked",
    )

    days: list[pd.DataFrame] = []
    raw_seen = 0
    for day in _days_in_month(month):
        chunk = _fetch_day(session, day, datasets)
        days.append(chunk)
        raw_seen += len(chunk)
        log.info("  %s: %s kept rows so far", f"{month:%Y-%m}", f"{raw_seen:,}")

    df = pd.concat(days, ignore_index=True) if days else pd.DataFrame()
    EZPASS_PARTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".parquet.part")
    df.to_parquet(tmp, engine="pyarrow", index=False)
    tmp.replace(dest)

    rows = len(df)
    if expected is None:
        # Paging ran to a short page, so the month is as complete as the feed
        # will give us — but unverified against a live count.
        complete, verified = True, False
    else:
        complete, verified = rows == expected, True
        if not complete:
            log.warning("%s: got %s rows, expected %s", dest.name, f"{rows:,}", f"{expected:,}")
    log.info("wrote %s (%s rows, %.1f MB)", dest.name, f"{rows:,}", dest.stat().st_size / 1e6)

    return PartRecord(
        part=dest.name,
        month=f"{month:%Y-%m}",
        where=where,
        rows=rows,
        rows_expected=expected if expected is not None else rows,
        bytes=dest.stat().st_size,
        sha256=_sha256(dest),
        pulled_at=datetime.now(UTC).isoformat(timespec="seconds"),
        complete=complete,
        verified=verified,
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
)


def fetch_segments(
    session: requests.Session, sample_days: tuple[date, ...] = SEGMENT_SAMPLE_DAYS
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
                frames.extend(_fetch_pages(session, ds, _day_where(day), select=cols))
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


def verify(session: requests.Session, start: date, end: date) -> None:
    """Check each on-disk part in ``[start, end]`` against the live API count."""
    problems: list[str] = []
    for month in _iter_months(start, end):
        tag = f"{month:%Y-%m}"
        dest = EZPASS_PARTS_DIR / f"ezpass_speeds_{tag}.parquet"
        if not dest.exists():
            log.warning("%s  MISSING on disk", tag)
            problems.append(tag)
            continue
        where = _where(month)
        disk = int(pd.read_parquet(dest, columns=[EZPASS_TIME_COL]).shape[0])
        api = sum(_count(session, ds, where) for ds in _datasets_for_month(month))
        ok = disk == api
        log.info(
            "%s  disk=%s  api=%s  %s", tag, f"{disk:,}", f"{api:,}", "OK" if ok else "MISMATCH"
        )
        if not ok:
            problems.append(tag)
    if problems:
        raise SystemExit(f"verify: {len(problems)} problem month(s): {', '.join(problems)}")
    log.info("verify OK - every part matches the live API")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, default=STUDY_START)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--force", action="store_true", help="re-download existing months")
    parser.add_argument("--verify", action="store_true", help="check disk vs live API, no download")
    parser.add_argument(
        "--count",
        action="store_true",
        help="pre-check each month against a live count(1); adds a slow "
        "aggregate query per month and is off by default",
    )
    parser.add_argument(
        "--segments",
        action="store_true",
        help="fetch only the per-segment attribute table and exit",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    end = args.end or date.today().replace(day=1)
    session = _session()

    if args.segments:
        fetch_segments(session)
        return

    if args.verify:
        verify(session, args.start, end)
        return

    if not EZPASS_SEGMENTS_PATH.exists():
        log.info("segment table missing - fetching it first")
        fetch_segments(session)

    parts_by_month = _load_existing_parts(EZPASS_MANIFEST_PATH)
    failures: list[str] = []
    for month in _iter_months(args.start, end):
        tag = f"{month:%Y-%m}"
        try:
            rec = download_month(
                session,
                month,
                force=args.force,
                prior=parts_by_month.get(tag),
                do_count=args.count,
            )
            parts_by_month[rec.month] = asdict(rec)
            _write(parts_by_month)
        except Exception:  # noqa: BLE001 - record and continue
            log.exception("failed month: %s", tag)
            failures.append(tag)

    if failures:
        raise SystemExit(f"download failed for months: {', '.join(failures)}")


if __name__ == "__main__":
    main()
