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
The manifest is **merged** across runs (a partial run augments it, never
replaces it) and rewritten after every month, so an interrupted run still
leaves an accurate manifest for the months it did fetch.

Usage
-----
    python -m src.data.download --start 2023-01-01 [--end 2025-09-01]
    python -m src.data.download --start 2023-01-01 --force
    python -m src.data.download --start 2023-01-01 --verify   # no download; check disk vs live API
    NYC_OPENDATA_APP_TOKEN=xxxx python -m src.data.download --start 2023-01-01
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
from dataclasses import asdict, dataclass, fields
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


_PART_FIELDS = frozenset(f.name for f in fields(PartRecord))


def _load_existing_parts(path=None) -> dict[str, dict]:
    """Existing manifest parts keyed by ``YYYY-MM``, or ``{}`` if none/unreadable.

    ``path`` defaults to :data:`RAW_MANIFEST_PATH`, resolved at call time so
    tests (and the EZ Pass ingest) can point it elsewhere.
    """
    path = path or RAW_MANIFEST_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        log.warning("existing manifest is unreadable - starting a fresh one")
        return {}
    return {p["month"]: p for p in data.get("parts", []) if "month" in p}


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_month(
    session: requests.Session, month: date, *, force: bool, prior: dict | None = None
) -> PartRecord:
    dest = PARTS_DIR / f"dot_speeds_{month:%Y-%m}.parquet"
    lo, hi = _month_bounds(month)
    where = f"{RAW_TIME_COL} >= '{lo}' AND {RAW_TIME_COL} < '{hi}'"

    if dest.exists() and not force:
        log.info("skip %s (exists)", dest.name)
        sha = _sha256(dest)
        if prior and prior.get("sha256") == sha:
            # Untouched since the recorded pull - keep its original provenance
            # (real pulled_at, expected count) instead of overwriting with a stub.
            return PartRecord(**{k: prior[k] for k in _PART_FIELDS if k in prior})
        rows = int(pd.read_parquet(dest, columns=[RAW_TIME_COL]).shape[0])
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


def write_manifest(
    parts_by_month: dict[str, dict],
    *,
    path=None,
    dataset_id: str | None = None,
    time_col: str | None = None,
) -> None:
    """Rewrite the manifest from ``parts_by_month`` (month -> part dict).

    ``coverage`` is derived from the parts actually present, not from any single
    run's ``--start``/``--end``, because the manifest is merged across runs.
    ``path`` / ``dataset_id`` / ``time_col`` default to the DOT speeds feed and
    are resolved at call time so the EZ Pass ingest can reuse this.
    """
    path = path or RAW_MANIFEST_PATH
    dataset_id = dataset_id or DOT_SPEEDS_DATASET_ID
    time_col = time_col or RAW_TIME_COL
    months = sorted(parts_by_month)
    parts = [parts_by_month[m] for m in months]
    manifest = {
        "dataset_id": dataset_id,
        "source_url": f"https://{SOCRATA_DOMAIN}/d/{dataset_id}",
        "time_column": time_col,
        "coverage": {"first_month": months[0], "last_month": months[-1]} if months else {},
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_rows": sum(p["rows"] for p in parts),
        "total_rows_expected": sum(p["rows_expected"] for p in parts),
        "all_parts_complete": all(p["complete"] for p in parts),
        "parts": parts,
    }
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(manifest, indent=2))
    tmp.replace(path)
    log.info(
        "wrote %s (%s rows across %d parts, %s..%s)",
        path.name,
        f"{manifest['total_rows']:,}",
        len(parts),
        months[0] if months else "-",
        months[-1] if months else "-",
    )


def verify(session: requests.Session, start: date, end: date) -> None:
    """Check each on-disk part in ``[start, end]`` against the live API count."""
    problems: list[str] = []
    for month in _iter_months(start, end):
        tag = f"{month:%Y-%m}"
        dest = PARTS_DIR / f"dot_speeds_{tag}.parquet"
        if not dest.exists():
            log.warning("%s  MISSING on disk", tag)
            problems.append(tag)
            continue
        lo, hi = _month_bounds(month)
        where = f"{RAW_TIME_COL} >= '{lo}' AND {RAW_TIME_COL} < '{hi}'"
        disk = int(pd.read_parquet(dest, columns=[RAW_TIME_COL]).shape[0])
        api = _count(session, where)
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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="don't download; check each on-disk part's row count against the live API",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    end = args.end or date.today().replace(day=1)
    session = _session()

    if args.verify:
        verify(session, args.start, end)
        return

    # Merge into whatever the manifest already records; rewrite it after every
    # month so an interrupted run still leaves an accurate manifest.
    parts_by_month = _load_existing_parts()
    failures: list[str] = []
    for month in _iter_months(args.start, end):
        tag = f"{month:%Y-%m}"
        try:
            rec = download_month(session, month, force=args.force, prior=parts_by_month.get(tag))
            parts_by_month[rec.month] = asdict(rec)
            write_manifest(parts_by_month)
        except Exception:  # noqa: BLE001 - record and continue
            log.exception("failed month: %s", tag)
            failures.append(tag)

    if failures:
        raise SystemExit(f"download failed for months: {', '.join(failures)}")


if __name__ == "__main__":
    main()
