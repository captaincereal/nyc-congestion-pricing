-- 02_quality_checks.sql   (DuckDB)
-- Data-quality assertions + descriptive metrics on stg_speed_readings.
-- Consumed by src/data/quality_report.py, which runs each named block and
-- writes docs/data_quality_report.md. "HARD" checks should return 0 rows;
-- a non-zero result is documented as an exception, not silently dropped.
--
-- Each statement is separated by a line beginning with "-- name: <key>".

-- name: total_rows
SELECT count(*) AS total_rows,
       count(DISTINCT link_id) AS distinct_links,
       min(ts) AS ts_min, max(ts) AS ts_max
FROM stg_speed_readings;

-- name: null_rates
SELECT
  round(100.0 * avg(CASE WHEN link_id      IS NULL THEN 1 ELSE 0 END), 4) AS link_id_null_pct,
  round(100.0 * avg(CASE WHEN ts           IS NULL THEN 1 ELSE 0 END), 4) AS ts_null_pct,
  round(100.0 * avg(CASE WHEN speed_mph    IS NULL THEN 1 ELSE 0 END), 4) AS speed_null_pct,
  round(100.0 * avg(CASE WHEN travel_time_s IS NULL THEN 1 ELSE 0 END), 4) AS travel_time_null_pct,
  round(100.0 * avg(CASE WHEN borough      IS NULL THEN 1 ELSE 0 END), 4) AS borough_null_pct
FROM stg_speed_readings;

-- name: hard_duplicate_key
-- HARD: staging must be unique on (link_id, ts).
SELECT link_id, ts, count(*) AS n
FROM stg_speed_readings
GROUP BY 1, 2
HAVING count(*) > 1;

-- name: implausible_speed
SELECT
  count(*) FILTER (WHERE speed_mph = 0)              AS zero_speed,
  count(*) FILTER (WHERE speed_mph < 0)              AS negative_speed,
  count(*) FILTER (WHERE speed_mph > 80)             AS over_80,
  count(*) FILTER (WHERE speed_mph > 100)            AS over_100,
  round(100.0 * avg(CASE WHEN speed_mph = 0 THEN 1 ELSE 0 END), 3) AS zero_speed_pct
FROM stg_speed_readings;

-- name: status_values
SELECT status, count(*) AS n, count(DISTINCT link_id) AS links
FROM stg_speed_readings
GROUP BY 1 ORDER BY n DESC;

-- name: readings_per_link_hour
-- Sub-hourly cadence sanity: how many raw readings land in a link-hour cell.
WITH c AS (
  SELECT link_id, ts_hour, count(*) AS n
  FROM stg_speed_readings GROUP BY 1, 2
)
SELECT
  round(avg(n), 2)  AS mean_readings_per_link_hour,
  min(n) AS min_n, quantile_cont(n, 0.5) AS p50_n,
  quantile_cont(n, 0.95) AS p95_n, max(n) AS max_n,
  count(*) AS link_hours
FROM c;

-- name: link_coverage_span
-- First/last day each link is seen and how many distinct days it reports.
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
  count(*) FILTER (WHERE observed_hours >= 0.90 * (SELECT expected_hours FROM expected)) AS ge_90pct_hours,
  count(*) FILTER (WHERE observed_hours <  0.50 * (SELECT expected_hours FROM expected)) AS lt_50pct_hours,
  round(avg(observed_hours * 100.0 / (SELECT expected_hours FROM expected)), 1) AS mean_coverage_pct
FROM win;

-- name: ts_bounds
-- HARD: no readings before the study start or in the future.
SELECT count(*) AS n
FROM stg_speed_readings
WHERE ts < DATE '2023-01-01' OR ts > now()
HAVING count(*) > 0;
