"""Download the NYC DOT Traffic Speeds feed into ``data/raw/`` — immutably.

Primary (and, for Phases 1-9, only) source:
    NYC DOT Traffic Speeds NBE, Socrata dataset ``i4gi-tjb9``
    https://data.cityofnewyork.us/Transportation/DOT-Traffic-Speeds-NBE/i4gi-tjb9

Strategy
--------
The full dataset is > 100M rows, so we pull it **one calendar month at a time**,
filtered on ``data_as_of``. Each month is written to its own parquet part:

    data/raw/dot_speeds/dot_speeds_YYYY-MM.parquet

Re-running only fetches months that are missing (``--force`` re-fetches all).
For every month we also ask Socrata for the exact row count and store it in the
manifest, so a short download is detectable later.

Raw parts are never edited. ``data/raw/manifest.json`` records, per part:
query window, row count, expected row count, byte size, SHA-256, pull timestamp.

Usage
-----
    python -m src.data.download --start 2023-01-01 [--end 2025-09-01]
    python -m src.data.download --start 2023-01-01 --force
    NYC_OPENDATA_APP_TOKEN=xxxx python -m src.data.download --start 2023-01-01
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import (
    DOT_SPEEDS_DATASET_ID,
    RAW_DIR,
    RAW_MANIFEST_PATH,
    RAW_TIME_COL,
    SOCRATA_APP_TOKEN,
    SOCRATA_DOMAIN,
    STUDY_START,
)

log = logging.getLogger(__name__)

PARTS_DIR = RAW_DIR / "dot_speeds"
BASE_URL = f"https://{SOCRATA_DOMAIN}/resource/{DOT_SPEEDS_DATASET_ID}"
PAGE_SIZE = 50_000
HTTP_TIMEOUT = 180


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "nyc-congestion-pricing/0.1 (research)"
    if SOCRATA_APP_TOKEN:
        s.headers["X-App-Token"] = SOCRATA_APP_TOKEN
        log.info("using Socrata app token")
    else:
        log.warning("no NYC_OPENDATA_APP_TOKEN set - anonymous rate limits apply")
    return s


def _month_bounds(d: date) -> tuple[str, str]:
    """SoQL half-open window [start, next-month-start) as floating timestamps."""
    start = d.replace(day=1)
    nxt = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return f"{start:%Y-%m-%d}T00:00:00", f"{nxt:%Y-%m-%d}T00:00:00"


def _iter_months(start: date, end: date):
    cur = start.replace(day=1)
    while cur <= end:
        yield cur
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _get(session: requests.Session, params: dict) -> requests.Response:
    resp = session.get(BASE_URL + ".csv", params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _count(session: requests.Session, where: str) -> int:
    resp = session.get(
        BASE_URL + ".json",
        params={"$select": "count(1) as n", "$where": where},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return int(resp.json()[0]["n"])


@dataclass
class PartRecord:
    part: str
    month: str
    where: str
    rows: int
    rows_expected: int
    bytes: int
    sha256: str
    pulled_at: str
    complete: bool


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_month(session: requests.Session, month: date, *, force: bool) -> PartRecord:
    dest = PARTS_DIR / f"dot_speeds_{month:%Y-%m}.parquet"
    lo, hi = _month_bounds(month)
    where = f"{RAW_TIME_COL} >= '{lo}' AND {RAW_TIME_COL} < '{hi}'"

    if dest.exists() and not force:
        log.info("skip %s (exists)", dest.name)
        rows = int(pd.read_parquet(dest, columns=[RAW_TIME_COL]).shape[0])
        return PartRecord(
            part=dest.name,
            month=f"{month:%Y-%m}",
            where=where,
            rows=rows,
            rows_expected=rows,
            bytes=dest.stat().st_size,
            sha256=_sha256(dest),
            pulled_at="(pre-existing)",
            complete=True,
        )

    expected = _count(session, where)
    log.info("GET %s  (expected %s rows)", f"{month:%Y-%m}", f"{expected:,}")

    frames: list[pd.DataFrame] = []
    offset = 0
    while True:
        params = {
            "$where": where,
            "$order": f"{RAW_TIME_COL},id",  # stable order for offset paging
            "$limit": PAGE_SIZE,
            "$offset": offset,
        }
        resp = _get(session, params)
        page = pd.read_csv(io.BytesIO(resp.content), dtype=str)
        if page.empty:
            break
        frames.append(page)
        offset += len(page)
        if len(page) < PAGE_SIZE:
            break
        if offset % (PAGE_SIZE * 10) == 0:
            log.info("  %s: %s / %s rows", f"{month:%Y-%m}", f"{offset:,}", f"{expected:,}")

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
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


def write_manifest(records: list[PartRecord], start: date, end: date) -> None:
    manifest = {
        "dataset_id": DOT_SPEEDS_DATASET_ID,
        "source_url": f"https://{SOCRATA_DOMAIN}/Transportation/x/{DOT_SPEEDS_DATASET_ID}",
        "time_column": RAW_TIME_COL,
        "requested_window": {"start": f"{start:%Y-%m-%d}", "end": f"{end:%Y-%m-%d}"},
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_rows": sum(r.rows for r in records),
        "total_rows_expected": sum(r.rows_expected for r in records),
        "all_parts_complete": all(r.complete for r in records),
        "parts": [asdict(r) for r in records],
    }
    RAW_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    log.info(
        "wrote %s (%s rows across %d parts)",
        RAW_MANIFEST_PATH.name,
        f"{manifest['total_rows']:,}",
        len(records),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=STUDY_START,
        help="first month to pull (YYYY-MM-DD); default from config.STUDY_START",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="last month to pull (YYYY-MM-DD); default = current month",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-download months that already exist"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    end = args.end or date.today().replace(day=1)
    session = _session()

    records: list[PartRecord] = []
    failures: list[str] = []
    for month in _iter_months(args.start, end):
        try:
            records.append(download_month(session, month, force=args.force))
        except Exception:  # noqa: BLE001 - record and continue
            log.exception("failed month: %s", f"{month:%Y-%m}")
            failures.append(f"{month:%Y-%m}")

    if records:
        write_manifest(records, args.start, end)
    if failures:
        raise SystemExit(f"download failed for months: {', '.join(failures)}")


if __name__ == "__main__":
    main()
