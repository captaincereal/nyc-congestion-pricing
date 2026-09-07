"""Phase 3 — build the typed staging table from the raw DOT speeds parts.

Runs ``sql/01_stage_speeds.sql`` in DuckDB against ``data/raw/dot_speeds/*.parquet``,
persists ``stg_speed_readings`` into ``data/nyc_cp.duckdb``, exports a parquet
copy to ``data/interim/``, and logs the row-count funnel.

No value cleaning happens here — see the data-quality report.

Usage:
    python -m src.data.build_staging
"""

from __future__ import annotations

import logging

import duckdb

from src.config import DUCKDB_PATH, PROJECT_ROOT, RAW_DIR, STAGED_SPEEDS_PATH

log = logging.getLogger(__name__)

SQL_PATH = PROJECT_ROOT / "sql" / "01_stage_speeds.sql"
PARTS_GLOB = str(RAW_DIR / "dot_speeds" / "*.parquet")


def build(con: duckdb.DuckDBPyConnection) -> None:
    raw_rows = con.execute(
        f"SELECT count(*) FROM read_parquet('{PARTS_GLOB}', union_by_name => true)"
    ).fetchone()[0]
    log.info("raw parts: %s rows", f"{raw_rows:,}")

    sql = SQL_PATH.read_text()
    con.execute(sql, {"parts_glob": PARTS_GLOB})

    staged_rows = con.execute("SELECT count(*) FROM stg_speed_readings").fetchone()[0]
    dropped = raw_rows - staged_rows
    log.info(
        "staged: %s rows  (dropped %s: null key + de-dup on (link_id, ts))",
        f"{staged_rows:,}",
        f"{dropped:,}",
    )

    STAGED_SPEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY stg_speed_readings TO '{STAGED_SPEEDS_PATH.as_posix()}' (FORMAT parquet)")
    log.info("wrote %s", STAGED_SPEEDS_PATH)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        build(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
