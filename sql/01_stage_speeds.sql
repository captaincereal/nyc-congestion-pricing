-- 01_stage_speeds.sql   (DuckDB)
-- Type + normalize the raw DOT Traffic Speeds parts into stg_dot_highway_readings.
--
-- SECONDARY source. This feed carries only ~123 links city-wide, all highways,
-- crossings and toll-EXEMPT roads (FDR Drive, West Side Hwy) — it has no links
-- on tolled CRZ surface streets, so it cannot serve the primary specification.
-- It is retained for the spillover/diversion analysis: those exempt roads are
-- exactly where displaced traffic would go. The primary staging table
-- (stg_speed_readings) is built from the EZ Pass local-street feeds by
-- sql/01_stage_ezpass.sql. See the 2026-09-08 decision record in
-- docs/methodology.md.
--
-- NO value cleaning: implausible speeds, zeros, duplicates and outages are
-- reported by 02_quality_checks.sql / quality_report.py and handled later,
-- only after they are documented.
--
-- Parameters (bind before executing, see src/data/build_staging.py):
--   $parts_glob : path glob for data/raw/dot_speeds/*.parquet
--
-- Confirmed (probe, 2026-09-07): data_as_of is naive America/New_York wall
-- clock (spring-forward hour 2025-03-09 02:00-02:59 is empty). No timezone
-- conversion is applied. If this is ever revisited, do it here and nowhere else.

CREATE OR REPLACE TABLE stg_dot_highway_readings AS
WITH raw AS (
    SELECT * FROM read_parquet($parts_glob, union_by_name => true)
),
typed AS (
    SELECT
        CAST(link_id AS VARCHAR)                       AS link_id,
        try_cast(data_as_of AS TIMESTAMP)             AS ts,
        try_cast(speed AS DOUBLE)                     AS speed_mph,
        try_cast(travel_time AS DOUBLE)              AS travel_time_s,
        CAST(status AS VARCHAR)                       AS status,
        -- borough label casing/spacing varies in the feed
        nullif(trim(lower(CAST(borough AS VARCHAR))), '') AS borough,
        CAST(link_name AS VARCHAR)                    AS link_name,
        CAST(id AS VARCHAR)                           AS reading_id
    FROM raw
),
deduped AS (
    -- Keep one row per (link_id, ts). Duplicate rate is reported separately;
    -- here we take the last-written reading_id deterministically so staging is
    -- stable. Revisit if inspect_schema shows duplicates carry real variation.
    SELECT * EXCLUDE (rn) FROM (
        SELECT *,
               row_number() OVER (PARTITION BY link_id, ts ORDER BY reading_id DESC) AS rn
        FROM typed
        WHERE link_id IS NOT NULL AND ts IS NOT NULL
    ) WHERE rn = 1
)
SELECT
    link_id,
    ts,
    date_trunc('hour', ts)          AS ts_hour,
    speed_mph,
    travel_time_s,
    status,
    borough,
    link_name
FROM deduped;
