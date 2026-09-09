"""Phase 3 — build the typed staging table(s) from the raw parts.

Two sources, each with its own SQL and its own output table:

``ezpass`` (default, PRIMARY)
    ``sql/01_stage_ezpass.sql`` over ``data/raw/ezpass_speeds/*.parquet`` ->
    ``stg_speed_readings``, the canonical analysis staging table. Speed is
    converted fps -> mph and readings are reduced to one per 15-minute window.

``dot`` (SECONDARY, spillover/diversion analysis)
    ``sql/01_stage_speeds.sql`` over ``data/raw/dot_speeds/*.parquet`` ->
    ``stg_dot_highway_readings``. Highways only; see the 2026-09-08 decision
    record in docs/methodology.md for why this is no longer primary.

Both persist into ``data/nyc_cp.duckdb``, export a parquet copy to
``data/interim/``, and log the row-count funnel. No value cleaning happens
here — see the data-quality report.

Usage:
    python -m src.data.build_staging                 # primary (ezpass)
    python -m src.data.build_staging --source dot    # secondary
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb

from src.config import (
    DUCKDB_PATH,
    EZPASS_PARTS_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    STAGED_DOT_HIGHWAY_PATH,
    STAGED_SPEEDS_PATH,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    sql_path: Path
    parts_glob: str
    table: str
    out_path: Path


SOURCES = {
    "ezpass": Source(
        sql_path=PROJECT_ROOT / "sql" / "01_stage_ezpass.sql",
        parts_glob=str(EZPASS_PARTS_DIR / "*.parquet"),
        table="stg_speed_readings",
        out_path=STAGED_SPEEDS_PATH,
    ),
    "dot": Source(
        sql_path=PROJECT_ROOT / "sql" / "01_stage_speeds.sql",
        parts_glob=str(RAW_DIR / "dot_speeds" / "*.parquet"),
        table="stg_dot_highway_readings",
        out_path=STAGED_DOT_HIGHWAY_PATH,
    ),
}


def build(con: duckdb.DuckDBPyConnection, source: Source) -> None:
    raw_rows = con.execute(
        f"SELECT count(*) FROM read_parquet('{source.parts_glob}', union_by_name => true)"
    ).fetchone()[0]
    log.info("raw parts: %s rows", f"{raw_rows:,}")

    con.execute(source.sql_path.read_text(), {"parts_glob": source.parts_glob})

    staged_rows = con.execute(f"SELECT count(*) FROM {source.table}").fetchone()[0]
    dropped = raw_rows - staged_rows
    log.info(
        "staged %s: %s rows  (dropped %s: null key + de-dup)",
        source.table,
        f"{staged_rows:,}",
        f"{dropped:,}",
    )

    source.out_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY {source.table} TO '{source.out_path.as_posix()}' (FORMAT parquet)")
    log.info("wrote %s", source.out_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="ezpass",
        help="which raw source to stage (default: ezpass, the primary source)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        build(con, SOURCES[args.source])
    finally:
        con.close()


if __name__ == "__main__":
    main()
