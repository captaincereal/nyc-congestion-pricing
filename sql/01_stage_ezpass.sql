-- 01_stage_ezpass.sql   (DuckDB)
-- Type + normalize the raw EZ Pass local-street speed parts into the canonical
-- staging table `stg_speed_readings`. This is the PRIMARY source; see the
-- 2026-09-08 decision record in docs/methodology.md.
--
-- NO value cleaning: implausible speeds (the feed emits values up to ~20,662
-- fps ≈ 14,000 mph), zero speeds, thin-sample medians, duplicates and outages
-- are reported by 02_quality_checks.sql / quality_report.py and handled later,
-- only after they are documented.
--
-- Parameters (bind before executing, see src/data/build_staging.py):
--   $parts_glob : path glob for data/raw/ezpass_speeds/*.parquet
--
-- Units: the feed reports median_speed_fps in FEET PER SECOND. Converted to mph
-- here (x 3600/5280) and nowhere else, so speed_mph is directly comparable to
-- the secondary DOT highway feed.
--
-- Timezone: median_calculation_timestamp is assumed naive America/New_York wall
-- clock, matching the DOT feed. VERIFY before Phase 4 by checking that the
-- spring-forward hour (2025-03-09 02:00-02:59) is empty; if it is not, fix the
-- interpretation here and nowhere else.
--
-- Window semantics: each row is a median over a preceding `aggregation_period_sec`
-- window (900s). A reading is attributed to the hour of its timestamp, so a
-- window may straddle an hour boundary by up to 15 minutes. Documented rather
-- than corrected; revisit only if the quality report shows it matters.
--
-- Sampling: the raw feed republishes a ROLLING 900s median about every 61s, so
-- neighbouring rows overlap ~93% and are often identical. Ingestion samples the
-- minutes opening each non-overlapping 15-minute window plus a backup minute
-- (EZPASS_SAMPLE_MINUTES), so up to two rows can land in the same window. This
-- keeps exactly ONE reading per (link, 15-minute window) -- preferring the one
-- built from more probe samples -- which is the independent series the frozen
-- "hourly median" is meant to be computed from.

CREATE OR REPLACE TABLE stg_speed_readings AS
WITH raw AS (
    SELECT * FROM read_parquet($parts_glob, union_by_name => true)
),
typed AS (
    SELECT
        CAST(sid AS VARCHAR)                                  AS link_id,
        try_cast(median_calculation_timestamp AS TIMESTAMP)   AS ts,
        try_cast(median_speed_fps AS DOUBLE) * (3600.0/5280.0) AS speed_mph,
        try_cast(median_tt_sec AS DOUBLE)                     AS travel_time_s,
        try_cast(n_samples AS INTEGER)                        AS n_samples,
        try_cast(link_length_ft AS DOUBLE)                    AS link_length_ft,
        try_cast(aggregation_period_sec AS INTEGER)           AS agg_period_s,
        -- borough label casing/spacing varies in the feed
        nullif(trim(lower(CAST(borough AS VARCHAR))), '')     AS borough,
        CAST(link_name AS VARCHAR)                            AS link_name,
        CAST(polyline AS VARCHAR)                             AS polyline
    FROM raw
),
windowed AS (
    -- Floor each reading to its non-overlapping 15-minute window.
    SELECT *,
           date_trunc('hour', ts)
               + INTERVAL (floor(date_part('minute', ts) / 15) * 15) MINUTE AS ts_window
    FROM typed
    WHERE link_id IS NOT NULL AND ts IS NOT NULL
),
deduped AS (
    -- One row per (link_id, 15-minute window). Ingestion samples a primary and
    -- a backup minute per window, so up to two rows can arrive; prefer the
    -- median built from more probe samples, then break remaining ties
    -- deterministically so staging is stable across rebuilds. The duplicate
    -- rate is reported separately rather than silently assumed to be zero.
    SELECT * EXCLUDE (rn) FROM (
        SELECT *,
               row_number() OVER (
                   PARTITION BY link_id, ts_window
                   ORDER BY n_samples DESC, ts ASC, speed_mph DESC
               ) AS rn
        FROM windowed
    ) WHERE rn = 1
)
SELECT
    link_id,
    ts,
    ts_window,
    date_trunc('hour', ts)          AS ts_hour,
    speed_mph,
    travel_time_s,
    n_samples,
    link_length_ft,
    agg_period_s,
    borough,
    link_name,
    polyline
FROM deduped;
