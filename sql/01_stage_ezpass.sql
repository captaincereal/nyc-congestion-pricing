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
--   $parts_glob    : path glob for data/raw/ezpass_speeds/*.parquet
--   $segments_path : data/raw/ezpass_segments.parquet
--
-- The raw parts carry only the per-reading columns; link_name, borough,
-- polyline and link_length_ft are per-segment constants held once in the
-- segments table and joined here. An INNER join would silently drop readings
-- for a segment missing from that table, so this LEFT joins and the quality
-- report counts unmatched sids.
--
-- Units: the feed reports median_speed_fps in FEET PER SECOND. Converted to mph
-- here (x 3600/5280) and nowhere else, so speed_mph is directly comparable to
-- the secondary DOT highway feed.
--
-- Timezone: median_calculation_timestamp is naive America/New_York wall clock.
-- VERIFIED 2026-09-09 against the raw feed: on the fall-back date 2024-11-03,
-- sid 1004 has 103 readings stamped in hour 01 versus 51 in every neighbouring
-- hour and 51 in that hour on the control Sunday 2024-10-27 -- exactly the
-- doubling expected when 01:00-01:59 runs twice and both passes carry the same
-- wall-clock stamp. Under UTC no hour would double. No timezone conversion is
-- applied anywhere; if this is ever revisited, do it here and nowhere else.
--
-- CONSEQUENCE - ambiguous fall-back hour: because both passes of 01:00-01:59
-- floor to the same 15-minute windows, the de-dup below keeps one reading per
-- window and silently discards the other. On fall-back dates that hour is
-- therefore ambiguous (it is unknowable which real hour a kept reading came
-- from) and under-counted. It is flagged here as `is_dst_ambiguous_hour` so the
-- panel build can exclude it rather than quietly averaging two different hours
-- together. Cost of excluding: one hour per year per link.
--
-- Window semantics: each row is a median over a preceding `aggregation_period_sec`
-- window (900s). A reading is attributed to the hour of its timestamp, so a
-- window may straddle an hour boundary by up to 15 minutes. Documented rather
-- than corrected; revisit only if the quality report shows it matters.
--
-- Sampling: the raw feed republishes a ROLLING 900s median about every 61s, so
-- neighbouring rows overlap ~93% and are often identical. Ingestion already
-- reduces this to one reading per (segment, 15-minute window) client-side, so
-- the de-dup below is normally a no-op. It is kept because it is the guarantee
-- the rest of the pipeline relies on, and it still applies when parts were
-- fetched by an older ingest or re-fetched across a chunk boundary. The result
-- is the independent series the frozen "hourly median" is computed from.

CREATE OR REPLACE TABLE stg_speed_readings AS
WITH raw AS (
    SELECT * FROM read_parquet($parts_glob, union_by_name => true)
),
segments AS (
    SELECT
        CAST(sid AS VARCHAR)                              AS link_id,
        CAST(link_name AS VARCHAR)                        AS link_name,
        -- borough label casing/spacing varies in the feed
        nullif(trim(lower(CAST(borough AS VARCHAR))), '') AS borough,
        CAST(polyline AS VARCHAR)                         AS polyline,
        try_cast(link_length_ft AS DOUBLE)                AS link_length_ft
    FROM read_parquet($segments_path)
),
typed AS (
    SELECT
        CAST(r.sid AS VARCHAR)                                    AS link_id,
        try_cast(r.median_calculation_timestamp AS TIMESTAMP)     AS ts,
        try_cast(r.median_speed_fps AS DOUBLE) * (3600.0/5280.0)  AS speed_mph,
        try_cast(r.median_tt_sec AS DOUBLE)                       AS travel_time_s,
        try_cast(r.n_samples AS INTEGER)                          AS n_samples,
        s.link_length_ft                                          AS link_length_ft,
        s.borough                                                 AS borough,
        s.link_name                                               AS link_name,
        s.polyline                                                AS polyline
    FROM raw r
    LEFT JOIN segments s ON CAST(r.sid AS VARCHAR) = s.link_id
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
    -- The 01:00-01:59 hour on a US fall-back date runs twice under naive local
    -- time; both passes collapse into the same windows above, so this hour is
    -- ambiguous and under-counted. Flagged, not dropped: staging does not
    -- remove data, the panel build decides.
    (date_part('hour', ts) = 1
     AND CAST(ts AS DATE) IN (
        DATE '2023-11-05', DATE '2024-11-03', DATE '2025-11-02', DATE '2026-11-01'
     ))                             AS is_dst_ambiguous_hour,
    speed_mph,
    travel_time_s,
    n_samples,
    link_length_ft,
    borough,
    link_name,
    polyline
FROM deduped;
