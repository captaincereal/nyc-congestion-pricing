-- 03_hourly_panel.sql   (DuckDB)
-- Build the analysis panel: one row per link_id x hour, carrying the primary
-- outcome (hourly median speed) and the DiD / event-time flags.
--
-- Parameters (bind before executing, see src/data/build_panel.py):
--   $treatment_path : data/interim/segment_treatment.parquet
--
-- Blockers cleared:
--   * Timezone CONFIRMED naive America/New_York (2026-09-09, see
--     sql/01_stage_ezpass.sql). Hour-of-day cuts below are therefore correct.
--   * Treatment geography built geometrically from `polyline` by src/data/geo.py;
--     joined here, never hard-coded.
--
-- Deliberately NO value cleaning. Staging does not clean and neither does this;
-- the frozen primary outcome is a MEDIAN precisely so that sparse extreme
-- readings do not drive it. Instead every diagnostic a filter would need is
-- carried on the row (n_obs, sample depth, extreme counts) so that exclusion
-- rules can be applied as documented robustness variants rather than baked
-- irreversibly into the panel. See docs/methodology.md.
--
-- Rows EXCLUDED here, and only these:
--   * the ambiguous fall-back hour (is_dst_ambiguous_hour) - that hour runs
--     twice under naive local time and de-dup already discarded one pass, so
--     the cell would average two different real hours. 0.07% of readings.
--   * readings with a null speed, which carry no outcome.
-- Links with no treatment group (sid missing from the segment table) are KEPT
-- with treatment_group = 'unassigned' so they are visible and countable rather
-- than silently absent; the models select the groups they need.

CREATE OR REPLACE TABLE hourly_panel AS
WITH agg AS (
    SELECT
        link_id,
        ts_hour,
        median(speed_mph)                                      AS median_speed_mph,
        avg(speed_mph)                                         AS mean_speed_mph,
        min(speed_mph)                                         AS min_speed_mph,
        max(speed_mph)                                         AS max_speed_mph,
        count(*)                                               AS n_obs,
        -- Sample depth behind the hour's median, for coverage filtering later.
        sum(n_samples)                                         AS n_probe_samples,
        min(n_samples)                                         AS min_n_samples,
        -- Diagnostics a cleaning rule would need, computed once here.
        count(*) FILTER (WHERE speed_mph = 0)                  AS n_zero_speed,
        count(*) FILTER (WHERE speed_mph > 80)                 AS n_over_80,
        any_value(borough)                                     AS borough,
        any_value(link_name)                                   AS link_name
    FROM stg_speed_readings
    WHERE speed_mph IS NOT NULL
      AND NOT is_dst_ambiguous_hour
    GROUP BY link_id, ts_hour
),
flagged AS (
    SELECT
        a.*,
        CAST(a.ts_hour AS DATE)                                AS date,
        CAST(date_part('hour', a.ts_hour) AS INTEGER)          AS hour,
        CAST(date_part('dow',  a.ts_hour) AS INTEGER)          AS dow,
        date_part('dow', a.ts_hour) IN (0, 6)                  AS is_weekend,
        -- Peak windows from src/config.py: AM 07:00-09:59, PM 16:00-18:59.
        (date_part('hour', a.ts_hour) BETWEEN 7 AND 9)         AS is_am_peak,
        (date_part('hour', a.ts_hour) BETWEEN 16 AND 18)       AS is_pm_peak,
        (date_part('hour', a.ts_hour) BETWEEN 7 AND 9
         OR date_part('hour', a.ts_hour) BETWEEN 16 AND 18)    AS is_peak,
        -- Tolling began 2025-01-05. `post` is the DiD period indicator.
        (a.ts_hour >= TIMESTAMP '2025-01-05 00:00:00')         AS post,
        -- Event time in weeks relative to the treatment week; 0 is the week
        -- tolling started. Reference period k = -1 is set in the model, not here.
        CAST(date_diff('week', DATE '2025-01-05',
                       CAST(a.ts_hour AS DATE)) AS INTEGER)    AS event_week
    FROM agg a
)
SELECT
    f.*,
    coalesce(t.treatment_group, 'unassigned')                  AS treatment_group,
    (coalesce(t.treatment_group, '') = 'treated')              AS treated,
    (coalesce(t.treatment_group, '') = 'treated' AND f.post)   AS treated_post,
    t.roadway
FROM flagged f
LEFT JOIN read_parquet($treatment_path) t
       ON f.link_id = CAST(t.sid AS VARCHAR);
