-- 02_quality_checks.sql   (DuckDB)
-- Data-quality assertions + descriptive metrics on stg_speed_readings, which is
-- built from the PRIMARY source (EZ Pass local-street speeds) by
-- sql/01_stage_ezpass.sql. Consumed by src/data/quality_report.py, which runs
-- each named block and writes docs/data_quality_report.md. "HARD" checks should
-- return 0 rows; a non-zero result is documented as an exception, not silently
-- dropped.
--
-- Each statement is separated by a line beginning with "-- name: <key>".

-- name: total_rows
SELECT count(*) AS total_rows,
       count(DISTINCT link_id) AS distinct_links,
       min(ts) AS ts_min, max(ts) AS ts_max
FROM stg_speed_readings;

-- name: null_rates
SELECT
  round(100.0 * avg(CASE WHEN link_id       IS NULL THEN 1 ELSE 0 END), 4) AS link_id_null_pct,
  round(100.0 * avg(CASE WHEN ts            IS NULL THEN 1 ELSE 0 END), 4) AS ts_null_pct,
  round(100.0 * avg(CASE WHEN speed_mph     IS NULL THEN 1 ELSE 0 END), 4) AS speed_null_pct,
  round(100.0 * avg(CASE WHEN travel_time_s IS NULL THEN 1 ELSE 0 END), 4) AS travel_time_null_pct,
  round(100.0 * avg(CASE WHEN n_samples     IS NULL THEN 1 ELSE 0 END), 4) AS n_samples_null_pct,
  round(100.0 * avg(CASE WHEN borough       IS NULL THEN 1 ELSE 0 END), 4) AS borough_null_pct
FROM stg_speed_readings;

-- name: hard_duplicate_key
-- HARD: staging must be unique on (link_id, ts_window). The window, not the raw
-- timestamp, is the key: the feed republishes a rolling 900s median about every
-- 61s and ingestion reduces that to one reading per 15-minute window.
SELECT link_id, ts_window, count(*) AS n
FROM stg_speed_readings
GROUP BY 1, 2
HAVING count(*) > 1;

-- name: hard_unmatched_segments
-- HARD: every reading's sid should join to the segment attribute table. A
-- non-zero count means data/raw/ezpass_segments.parquet is stale relative to the
-- readings, and those links carry no borough or geometry, so they cannot be
-- assigned to a treatment group.
SELECT link_id, count(*) AS readings
FROM stg_speed_readings
WHERE borough IS NULL AND link_name IS NULL
GROUP BY 1 ORDER BY readings DESC;

-- name: implausible_speed
-- The raw feed emits median_speed_fps up to ~20,662 (~14,000 mph). Nothing is
-- cleaned in staging; the cut points are decided from this table and applied in
-- the panel build, so they are documented before they are used.
SELECT
  count(*) FILTER (WHERE speed_mph = 0)   AS zero_speed,
  count(*) FILTER (WHERE speed_mph < 0)   AS negative_speed,
  count(*) FILTER (WHERE speed_mph > 60)  AS over_60,
  count(*) FILTER (WHERE speed_mph > 80)  AS over_80,
  count(*) FILTER (WHERE speed_mph > 100) AS over_100,
  round(100.0 * avg(CASE WHEN speed_mph = 0 THEN 1 ELSE 0 END), 3)   AS zero_speed_pct,
  round(100.0 * avg(CASE WHEN speed_mph > 80 THEN 1 ELSE 0 END), 4)  AS over_80_pct,
  round(max(speed_mph), 1) AS max_speed_mph
FROM stg_speed_readings;

-- name: sample_depth
-- n_samples is how many probe vehicles the median was computed from. Thin
-- medians are noisy; this sets the minimum-samples threshold for the panel.
SELECT
  round(avg(n_samples), 2) AS mean_samples,
  min(n_samples) AS min_samples,
  quantile_cont(n_samples, 0.05) AS p05,
  quantile_cont(n_samples, 0.50) AS p50,
  quantile_cont(n_samples, 0.95) AS p95,
  max(n_samples) AS max_samples,
  count(*) FILTER (WHERE n_samples <= 1) AS readings_with_le_1_sample,
  round(100.0 * avg(CASE WHEN n_samples <= 3 THEN 1 ELSE 0 END), 2) AS le_3_samples_pct
FROM stg_speed_readings;

-- name: speed_vs_travel_time
-- Independent consistency check: speed should equal link_length_ft /
-- median_tt_sec. A large disagreement means one of the two fields is unreliable.
WITH c AS (
  SELECT speed_mph,
         (link_length_ft / nullif(travel_time_s, 0)) * (3600.0/5280.0) AS implied_mph
  FROM stg_speed_readings
  WHERE link_length_ft IS NOT NULL AND travel_time_s > 0 AND speed_mph > 0
)
SELECT
  count(*) AS comparable_rows,
  round(quantile_cont(abs(speed_mph - implied_mph), 0.50), 3) AS p50_abs_diff_mph,
  round(quantile_cont(abs(speed_mph - implied_mph), 0.95), 3) AS p95_abs_diff_mph,
  round(100.0 * avg(CASE WHEN abs(speed_mph - implied_mph) > 5 THEN 1 ELSE 0 END), 2)
    AS pct_disagree_gt_5mph
FROM c;

-- name: dst_spring_forward
-- TIMEZONE VERIFICATION. Timestamps are assumed to be naive America/New_York
-- wall clock. If so, the 02:00-02:59 hour on a spring-forward date does not
-- exist and must be EMPTY, while the same hour a week earlier is populated.
-- A non-zero readings_in_missing_hour means the feed is UTC (or something
-- else), and every hour-of-day cut in the analysis would be shifted.
--
-- Read it with the neighbouring-hour columns: all three zero means that date has
-- no data at all and the row proves nothing. The check is only informative when
-- readings_hour_01 and readings_hour_03 are populated.
SELECT
  d.label,
  count(*) FILTER (WHERE date_part('hour', s.ts) = 2) AS readings_in_missing_hour,
  count(*) FILTER (WHERE date_part('hour', s.ts) = 1) AS readings_hour_01,
  count(*) FILTER (WHERE date_part('hour', s.ts) = 3) AS readings_hour_03
FROM (VALUES
        (DATE '2025-03-09', 'spring forward 2025'),
        (DATE '2025-03-02', 'control week earlier'),
        (DATE '2024-03-10', 'spring forward 2024')
     ) AS d(day, label)
LEFT JOIN stg_speed_readings s ON CAST(s.ts AS DATE) = d.day
GROUP BY d.label ORDER BY d.label;

-- name: readings_per_link_hour
-- Cadence sanity. After the 15-minute downsample this should be ~4 per
-- link-hour; materially more means the de-dup is not doing its job, materially
-- fewer means the feed has gaps.
WITH c AS (
  SELECT link_id, ts_hour, count(*) AS n
  FROM stg_speed_readings GROUP BY 1, 2
)
SELECT
  round(avg(n), 2)  AS mean_readings_per_link_hour,
  min(n) AS min_n, quantile_cont(n, 0.5) AS p50_n,
  quantile_cont(n, 0.95) AS p95_n, max(n) AS max_n,
  count(*) AS link_hours,
  count(*) FILTER (WHERE n > 4) AS link_hours_over_4
FROM c;

-- name: link_coverage_span
-- First/last day each link is seen and how many distinct days it reports.
-- Links that vanish before, or appear after, the treatment date break the
-- balanced-panel assumption and are candidates for exclusion.
WITH s AS (
  SELECT link_id,
         min(CAST(ts AS DATE)) AS first_day,
         max(CAST(ts AS DATE)) AS last_day,
         count(DISTINCT CAST(ts AS DATE)) AS active_days
  FROM stg_speed_readings GROUP BY 1
)
SELECT
  count(*) AS links,
  count(*) FILTER (WHERE last_day  < DATE '2025-01-05') AS links_gone_before_treatment,
  count(*) FILTER (WHERE first_day > DATE '2025-01-05') AS links_new_after_treatment,
  round(avg(active_days), 1) AS mean_active_days
FROM s;

-- name: daily_link_count
-- Coverage over time: distinct links reporting each day (feed into a plot).
-- A discontinuity at 2025-01-05 would confound the estimate.
SELECT CAST(ts AS DATE) AS day,
       count(DISTINCT link_id) AS links,
       count(*) AS readings
FROM stg_speed_readings
GROUP BY 1 ORDER BY 1;

-- name: link_hour_gaps
-- Missingness: for links active in the +/-120 day window around treatment,
-- share of expected hours actually observed.
WITH win AS (
  SELECT link_id, count(DISTINCT ts_hour) AS observed_hours
  FROM stg_speed_readings
  WHERE ts >= DATE '2024-09-07' AND ts < DATE '2025-05-05'
  GROUP BY 1
),
expected AS (SELECT 24 * (DATE '2025-05-05' - DATE '2024-09-07') AS expected_hours)
SELECT
  count(*) AS links_in_window,
  count(*) FILTER (WHERE observed_hours >= 0.90 * (SELECT expected_hours FROM expected))
    AS ge_90pct_hours,
  count(*) FILTER (WHERE observed_hours <  0.50 * (SELECT expected_hours FROM expected))
    AS lt_50pct_hours,
  round(avg(observed_hours * 100.0 / (SELECT expected_hours FROM expected)), 1)
    AS mean_coverage_pct
FROM win;

-- name: ts_bounds
-- HARD: no readings before the study start or in the future.
SELECT count(*) AS n
FROM stg_speed_readings
WHERE ts < DATE '2023-01-01' OR ts > now()
HAVING count(*) > 0;
