# Data-quality report — E-Z Pass local-street staging

Generated: 2026-09-14T00:00:45+00:00
Source DB: `nyc_cp.duckdb`  ·  raw manifest: `ezpass_manifest.json` (present; presence alone does not establish verification)

> Observed problems only. Handling decisions are in the last section and are applied elsewhere, never by this script.

## `total_rows`

|   total_rows |   distinct_links | ts_min              | ts_max              |
|-------------:|-----------------:|:--------------------|:--------------------|
|     31271925 |              347 | 2023-01-01 00:00:19 | 2026-08-31 23:59:24 |

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
|         8708 |                0 |    260539 |     61782 |       6212 |            0.028 |        0.1976 |         11674.7 |

## `sample_depth`

|   mean_samples |   min_samples |   p05 |   p50 |   p95 |   max_samples |   readings_with_le_1_sample |   le_3_samples_pct |
|---------------:|--------------:|------:|------:|------:|--------------:|----------------------------:|-------------------:|
|          38.39 |             2 |     2 |    19 |   137 |           782 |                           0 |              10.88 |

## `speed_vs_travel_time`

|   comparable_rows |   p50_abs_diff_mph |   p95_abs_diff_mph |   pct_disagree_gt_5mph |
|------------------:|-------------------:|-------------------:|-----------------------:|
|       3.12632e+07 |              0.002 |              0.003 |                      0 |

## `dst_spring_forward`

| label                |   readings_in_missing_hour |   readings_hour_01 |   readings_hour_03 |
|:---------------------|---------------------------:|-------------------:|-------------------:|
| control week earlier |                       1063 |               1087 |               1010 |
| spring forward 2024  |                          0 |               1130 |               1071 |
| spring forward 2025  |                          0 |               1026 |                990 |

## `readings_per_link_hour`

|   mean_readings_per_link_hour |   min_n |   p50_n |   p95_n |   max_n |   link_hours |   link_hours_over_4 |
|------------------------------:|--------:|--------:|--------:|--------:|-------------:|--------------------:|
|                          3.77 |       1 |       4 |       4 |       4 |  8.28455e+06 |                   0 |

## `link_coverage_span`

|   links |   links_gone_before_treatment |   links_new_after_treatment |   mean_active_days |
|--------:|------------------------------:|----------------------------:|-------------------:|
|     347 |                             3 |                           1 |             1085.7 |

## `daily_link_count`

1,288 rows (series; not inlined — plot separately).

Head / tail:

| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2023-01-01 00:00:00 |     331 |      29295 |
| 2023-01-02 00:00:00 |     335 |      29372 |
| 2023-01-03 00:00:00 |     334 |      29519 |
…
| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2026-08-29 00:00:00 |     291 |      23970 |
| 2026-08-30 00:00:00 |     290 |      23637 |
| 2026-08-31 00:00:00 |     294 |      23681 |

## `link_hour_gaps`

|   links_in_window |   ge_90pct_hours |   lt_50pct_hours |   mean_coverage_pct |
|------------------:|-----------------:|-----------------:|--------------------:|
|               336 |              179 |               43 |                  81 |

## `ts_bounds`

_(no rows)_

## Handling decisions

D1 in `docs/decision_register.md` remains open. The primary panel applies no
speed ceiling or probe-depth threshold. Separate robustness specifications
exclude low-depth hours and hours containing readings above 80 mph; they do not
alter the raw data or the primary outcome. A zero speed alone is not evidence
of an invalid reading. See `outputs/tables/robustness_comparison.csv`.
