"""Phase 4 — build the link x hour analysis panel from staging.

Runs ``sql/03_hourly_panel.sql`` in DuckDB against ``stg_speed_readings``,
joins the geometric CRZ treatment assignment, persists ``hourly_panel`` into
``data/nyc_cp.duckdb`` and exports a parquet copy to ``data/processed/``.

No value cleaning happens here; see the header of the SQL for what is excluded
and why.

Usage:
    python -m src.data.build_panel
"""

from __future__ import annotations

import logging

import duckdb

from src.config import DUCKDB_PATH, HOURLY_PANEL_PATH, INTERIM_DIR, PROJECT_ROOT

log = logging.getLogger(__name__)

SQL_PATH = PROJECT_ROOT / "sql" / "03_hourly_panel.sql"
TREATMENT_PATH = INTERIM_DIR / "segment_treatment.parquet"


def build(con: duckdb.DuckDBPyConnection) -> None:
    if not TREATMENT_PATH.exists():
        raise SystemExit(f"missing {TREATMENT_PATH} - run `python -m src.data.geo` first")

    staged = con.execute("SELECT count(*) FROM stg_speed_readings").fetchone()[0]
    log.info("staging: %s readings", f"{staged:,}")

    con.execute(SQL_PATH.read_text(), {"treatment_path": str(TREATMENT_PATH)})

    rows = con.execute("SELECT count(*) FROM hourly_panel").fetchone()[0]
    log.info("panel: %s link-hours", f"{rows:,}")

    groups = con.execute(
        "SELECT treatment_group, count(*) AS link_hours, count(DISTINCT link_id) AS links "
        "FROM hourly_panel GROUP BY 1 ORDER BY link_hours DESC"
    ).df()
    log.info("treatment groups:\n%s", groups.to_string(index=False))

    HOURLY_PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY hourly_panel TO '{HOURLY_PANEL_PATH.as_posix()}' (FORMAT parquet)")
    log.info("wrote %s", HOURLY_PANEL_PATH)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        build(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
