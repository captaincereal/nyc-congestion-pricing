# Data-quality report — DOT Traffic Speeds staging

Generated: 2026-09-09T22:25:13+00:00
Source DB: `nyc_cp.duckdb`  ·  raw manifest: `present`

> Observed problems only. Handling decisions are in the last section and are applied elsewhere, never by this script.

## `total_rows`

|   total_rows |   distinct_links | ts_min              | ts_max              |
|-------------:|-----------------:|:--------------------|:--------------------|
|      5162965 |              336 | 2024-10-01 00:00:48 | 2025-04-30 23:59:03 |

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
|          301 |                0 |     25677 |      4679 |       1041 |            0.006 |        0.0906 |          7043.9 |

## `sample_depth`

|   mean_samples |   min_samples |   p05 |   p50 |   p95 |   max_samples |   readings_with_le_1_sample |   le_3_samples_pct |
|---------------:|--------------:|------:|------:|------:|--------------:|----------------------------:|-------------------:|
|          35.02 |             2 |     2 |    18 |   120 |           707 |                           0 |              11.17 |

## `speed_vs_travel_time`

|   comparable_rows |   p50_abs_diff_mph |   p95_abs_diff_mph |   pct_disagree_gt_5mph |
|------------------:|-------------------:|-------------------:|-----------------------:|
|       5.16266e+06 |              0.002 |              0.003 |                      0 |

## `dst_spring_forward`

| label                |   readings_in_missing_hour |   readings_hour_01 |   readings_hour_03 |
|:---------------------|---------------------------:|-------------------:|-------------------:|
| control week earlier |                       1063 |               1087 |               1010 |
| spring forward 2024  |                          0 |                  0 |                  0 |
| spring forward 2025  |                          0 |               1026 |                990 |

## `readings_per_link_hour`

|   mean_readings_per_link_hour |   min_n |   p50_n |   p95_n |   max_n |   link_hours |   link_hours_over_4 |
|------------------------------:|--------:|--------:|--------:|--------:|-------------:|--------------------:|
|                          3.76 |       1 |       4 |       4 |       4 |  1.37378e+06 |                   0 |

## `link_coverage_span`

|   links |   links_gone_before_treatment |   links_new_after_treatment |   mean_active_days |
|--------:|------------------------------:|----------------------------:|-------------------:|
|     336 |                            11 |                           6 |              185.7 |

## `daily_link_count`

212 rows (series; not inlined — plot separately).

Head / tail:

| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2024-10-01 00:00:00 |     320 |      26452 |
| 2024-10-02 00:00:00 |     310 |      26598 |
| 2024-10-03 00:00:00 |     310 |      26574 |
…
| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2025-04-28 00:00:00 |     288 |      23295 |
| 2025-04-29 00:00:00 |     301 |      24428 |
| 2025-04-30 00:00:00 |     295 |      24481 |

## `link_hour_gaps`

|   links_in_window |   ge_90pct_hours |   lt_50pct_hours |   mean_coverage_pct |
|------------------:|-----------------:|-----------------:|--------------------:|
|               336 |                0 |               57 |                  71 |

## `ts_bounds`

_(no rows)_

## Proposed handling (human-edited — not yet applied)

_Fill in after reviewing the observed problems above. Each row: problem →
proposed rule → why → where it will be applied. Nothing here is applied until
it is written down and reviewed._

| Problem | Proposed rule | Rationale | Applied in |
|---|---|---|---|
| _e.g._ zero speeds | treat as missing | 0 mph is an artifact | `sql/03_hourly_panel.sql` |
