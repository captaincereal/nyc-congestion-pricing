"""Descriptive spillover coverage; no diversion effect is identified here.

The current primary 'boundary' links straddle the cordon. They are not a
sample of wholly outside streets. Secondary corridor speeds describe the
available toll-exempt/crossing feed without choosing a causal comparison pool.
"""

from __future__ import annotations

import argparse
import logging

import duckdb

from src.config import HOURLY_PANEL_PATH, RAW_DIR, TABLES_DIR

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secondary-parts", default=str(RAW_DIR / "dot_speeds" / "*.parquet"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect(config={"memory_limit": "2GB", "threads": "2"})
    try:
        primary = con.execute(
            "SELECT treatment_group, post, count(*) AS link_hours, "
            "count(DISTINCT link_id) AS links, min(ts_hour) AS first_hour, "
            "max(ts_hour) AS last_hour, avg(median_speed_mph) AS mean_hourly_median_mph "
            "FROM read_parquet(?) GROUP BY 1, 2 ORDER BY 1, 2",
            [str(HOURLY_PANEL_PATH)],
        ).df()
        primary["interpretation"] = "descriptive levels; unverified primary parts; no causal claim"
        primary.to_csv(TABLES_DIR / "spillover_primary_descriptive.csv", index=False)
        raw_count = con.execute(
            "SELECT count(*) FROM read_parquet(?)", [args.secondary_parts]
        ).fetchone()[0]
        # Preserve the secondary staging convention: naive local timestamps,
        # and latest reading_id for duplicate link/timestamp pairs.
        monthly = con.execute(
            """
            WITH typed AS (
                SELECT link_id, try_cast(data_as_of AS TIMESTAMP) AS ts,
                       try_cast(speed AS DOUBLE) AS speed_mph, id, link_name, borough
                FROM read_parquet(?)
            ), dedup AS (
                SELECT * FROM typed WHERE link_id IS NOT NULL AND ts IS NOT NULL
                QUALIFY row_number() OVER (PARTITION BY link_id, ts ORDER BY id DESC) = 1
            ), valid AS (
                SELECT *, date_trunc('hour', ts) AS ts_hour FROM dedup
                WHERE speed_mph IS NOT NULL
                  AND NOT (month(ts) = 11 AND day(ts) <= 7 AND dayofweek(ts) = 0 AND hour(ts) = 1)
            ), hourly AS (
                SELECT link_id, ts_hour, median(speed_mph) AS speed_mph,
                       min(link_name) AS link_name, min(borough) AS borough,
                       count(*) AS readings
                FROM valid GROUP BY 1, 2
            )
            SELECT link_id, date_trunc('month', ts_hour) AS month,
                   min(link_name) AS link_name, min(borough) AS borough,
                   count(*) AS link_hours, sum(readings) AS readings,
                   avg(speed_mph) AS mean_hourly_median_mph,
                   median(speed_mph) AS median_hourly_median_mph
            FROM hourly GROUP BY 1, 2 ORDER BY 1, 2
            """,
            [args.secondary_parts],
        ).df()
        monthly["interpretation"] = "secondary feed descriptive coverage; no diversion attribution"
        monthly.to_csv(TABLES_DIR / "spillover_secondary_monthly.csv", index=False)
        log.info(
            "%s raw secondary readings -> %s eligible deduplicated readings -> %s link-hours "
            "-> %s link-months (drops: null keys/speed, duplicates, ambiguous DST hour)",
            f"{raw_count:,}",
            f"{int(monthly.readings.sum()):,}",
            f"{int(monthly.link_hours.sum()):,}",
            f"{len(monthly):,}",
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
