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
from datetime import UTC, date, datetime

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import (
    EZPASS_AGG_PERIOD_SEC,
    EZPASS_DATASET_IDS,
    EZPASS_MANIFEST_PATH,
    EZPASS_PARTS_DIR,
    EZPASS_SPLIT_DATE,
    EZPASS_TIME_COL,
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
    lo, hi = _month_bounds(month)
    return (
        f"{EZPASS_TIME_COL} >= '{lo}' AND {EZPASS_TIME_COL} < '{hi}'"
        f" AND aggregation_period_sec = {EZPASS_AGG_PERIOD_SEC}"
    )


def _base(dataset_id: str) -> str:
    return f"https://{SOCRATA_DOMAIN}/resource/{dataset_id}"


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _count(session: requests.Session, dataset_id: str, where: str) -> int:
    resp = session.get(
        _base(dataset_id) + ".json",
        params={"$select": "count(1) as n", "$where": where},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return int(resp.json()[0]["n"])


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _get_page(session: requests.Session, dataset_id: str, params: dict) -> requests.Response:
    resp = session.get(_base(dataset_id) + ".csv", params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp


def _fetch_pages(session: requests.Session, dataset_id: str, where: str) -> list[pd.DataFrame]:
    """Page through one dataset for one month, ordered for stable offset paging."""
    frames: list[pd.DataFrame] = []
    offset = 0
    while True:
        resp = _get_page(
            session,
            dataset_id,
            {
                "$where": where,
                "$order": f"{EZPASS_TIME_COL},sid",
                "$limit": PAGE_SIZE,
                "$offset": offset,
            },
        )
        page = pd.read_csv(io.BytesIO(resp.content), dtype=str)
        if page.empty:
            break
        frames.append(page)
        offset += len(page)
        if len(page) < PAGE_SIZE:
            break
        if offset % (PAGE_SIZE * 10) == 0:
            log.info("  %s: %s rows so far", dataset_id, f"{offset:,}")
    return frames


def download_month(
    session: requests.Session, month: date, *, force: bool, prior: dict | None = None
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

    expected = sum(_count(session, ds, where) for ds in datasets)
    log.info(
        "GET %s from %s (expected %s rows)",
        f"{month:%Y-%m}",
        "+".join(datasets),
        f"{expected:,}",
    )

    frames: list[pd.DataFrame] = []
    for ds in datasets:
        frames.extend(_fetch_pages(session, ds, where))

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    EZPASS_PARTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".parquet.part")
    df.to_parquet(tmp, engine="pyarrow", index=False)
    tmp.replace(dest)

    rows = len(df)
    complete = rows == expected
    if not complete:
        log.warning("%s: got %s rows, expected %s", dest.name, f"{rows:,}", f"{expected:,}")
    log.info("wrote %s (%s rows, %.1f MB)", dest.name, f"{rows:,}", dest.stat().st_size / 1e6)

    return PartRecord(
        part=dest.name,
        month=f"{month:%Y-%m}",
        where=where,
        rows=rows,
        rows_expected=expected,
        bytes=dest.stat().st_size,
        sha256=_sha256(dest),
        pulled_at=datetime.now(UTC).isoformat(timespec="seconds"),
        complete=complete,
    )


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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    end = args.end or date.today().replace(day=1)
    session = _session()

    if args.verify:
        verify(session, args.start, end)
        return

    parts_by_month = _load_existing_parts(EZPASS_MANIFEST_PATH)
    failures: list[str] = []
    for month in _iter_months(args.start, end):
        tag = f"{month:%Y-%m}"
        try:
            rec = download_month(session, month, force=args.force, prior=parts_by_month.get(tag))
            parts_by_month[rec.month] = asdict(rec)
            _write(parts_by_month)
        except Exception:  # noqa: BLE001 - record and continue
            log.exception("failed month: %s", tag)
            failures.append(tag)

    if failures:
        raise SystemExit(f"download failed for months: {', '.join(failures)}")


if __name__ == "__main__":
    main()
