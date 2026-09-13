# Data-quality report — E-Z Pass local-street staging

Generated: 2026-09-13T05:47:51+00:00
Source DB: `nyc_cp.duckdb`  ·  raw manifest: `ezpass_manifest.json` (present; presence alone does not establish verification)

> Observed problems only. Handling decisions are in the last section and are applied elsewhere, never by this script.

## `total_rows`

|   total_rows |   distinct_links | ts_min              | ts_max              |
|-------------:|-----------------:|:--------------------|:--------------------|
|     16334079 |              346 | 2023-08-01 00:00:57 | 2025-04-30 23:59:03 |

## `null_rates`

|   link_id_null_pct |   ts_null_pct |   speed_null_pct |   travel_time_null_pct |   n_samples_null_pct |   borough_null_pct |
|-------------------:|--------------:|-----------------:|-----------------------:|---------------------:|-------------------:|
|                  0 |             0 |                0 |                      0 |                    0 |                  0 |

## `hard_duplicate_key`  ✅ pass

_(no rows)_

## `hard_unmatched_segments`  ✅ pass

_(no rows)_

## `implausible_speed`

|   zero_speed |   negative_speed |   over_60 |   over_80 |   over_100 |   zero_speed_pct |   over_80_pct |   max_speed_mph |
|-------------:|-----------------:|----------:|----------:|-----------:|-----------------:|--------------:|----------------:|
|         1189 |                0 |    125808 |     29318 |       3192 |            0.007 |        0.1795 |          7043.9 |

## `sample_depth`

|   mean_samples |   min_samples |   p05 |   p50 |   p95 |   max_samples |   readings_with_le_1_sample |   le_3_samples_pct |
|---------------:|--------------:|------:|------:|------:|--------------:|----------------------------:|-------------------:|
|          39.74 |             2 |     2 |    21 |   140 |           782 |                           0 |              10.12 |

## `speed_vs_travel_time`

|   comparable_rows |   p50_abs_diff_mph |   p95_abs_diff_mph |   pct_disagree_gt_5mph |
|------------------:|-------------------:|-------------------:|-----------------------:|
|       1.63329e+07 |              0.002 |              0.003 |                      0 |

## `dst_spring_forward`

| label                |   readings_in_missing_hour |   readings_hour_01 |   readings_hour_03 |
|:---------------------|---------------------------:|-------------------:|-------------------:|
| control week earlier |                       1063 |               1087 |               1010 |
| spring forward 2024  |                          0 |               1130 |               1071 |
| spring forward 2025  |                          0 |               1026 |                990 |

## `readings_per_link_hour`

|   mean_readings_per_link_hour |   min_n |   p50_n |   p95_n |   max_n |   link_hours |   link_hours_over_4 |
|------------------------------:|--------:|--------:|--------:|--------:|-------------:|--------------------:|
|                          3.79 |       1 |       4 |       4 |       4 |  4.30739e+06 |                   0 |

## `link_coverage_span`

|   links |   links_gone_before_treatment |   links_new_after_treatment |   mean_active_days |
|--------:|------------------------------:|----------------------------:|-------------------:|
|     346 |                            21 |                           0 |              558.6 |

## `daily_link_count`

639 rows (series; not inlined — plot separately).

Head / tail:

| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2023-08-01 00:00:00 |     293 |      25787 |
| 2023-08-02 00:00:00 |     294 |      25815 |
| 2023-08-03 00:00:00 |     290 |      25238 |
…
| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2025-04-28 00:00:00 |     288 |      23295 |
| 2025-04-29 00:00:00 |     301 |      24428 |
| 2025-04-30 00:00:00 |     295 |      24481 |

## `link_hour_gaps`

|   links_in_window |   ge_90pct_hours |   lt_50pct_hours |   mean_coverage_pct |
|------------------:|-----------------:|-----------------:|--------------------:|
|               336 |              159 |               43 |                79.7 |

## `ts_bounds`

_(no rows)_

## Handling decisions

D1 in `docs/decision_register.md` remains open. The primary panel applies no
speed ceiling or probe-depth threshold. Separate robustness specifications
exclude low-depth hours and hours containing readings above 80 mph; they do not
alter the raw data or the primary outcome. A zero speed alone is not evidence
of an invalid reading. See `outputs/tables/robustness_comparison.csv`.
