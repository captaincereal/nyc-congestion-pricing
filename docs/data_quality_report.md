# Data-quality report — DOT Traffic Speeds staging

Generated: 2026-09-09T18:31:42+00:00
Source DB: `nyc_cp.duckdb`  ·  raw manifest: `present`

> Observed problems only. Handling decisions are in the last section and are applied elsewhere, never by this script.

## `total_rows`

|   total_rows |   distinct_links | ts_min              | ts_max              |
|-------------:|-----------------:|:--------------------|:--------------------|
|      3008183 |              330 | 2024-10-01 00:00:48 | 2025-01-31 23:59:06 |

## `null_rates`

|   link_id_null_pct |   ts_null_pct |   speed_null_pct |   travel_time_null_pct |   n_samples_null_pct |   borough_null_pct |
|-------------------:|--------------:|-----------------:|-----------------------:|---------------------:|-------------------:|
|                  0 |             0 |                0 |                      0 |                    0 |             3.4873 |

## `hard_duplicate_key`  ✅ pass

_(no rows)_

## `hard_unmatched_segments`  ❌ **FAIL**

|   link_id |   readings |
|----------:|-----------:|
|     57061 |       7589 |
|     57053 |       7391 |
|     96095 |       4865 |
|     95096 |       4806 |
|     76045 |       4756 |
|     97096 |       4750 |
|     96097 |       4686 |
|     60057 |       4484 |
|     57060 |       4344 |
|    106050 |       4139 |
|     50057 |       4128 |
|     82050 |       4116 |
|     50082 |       4009 |
|     76083 |       3872 |
|    165164 |       3515 |
|     61057 |       3514 |
|     50106 |       3478 |
|    164165 |       2809 |
|     83076 |       2507 |
|    158165 |       2483 |
|    172173 |       2274 |
|    173172 |       2264 |
|    171172 |       2136 |
|    172171 |       2116 |
|      8118 |       1591 |
|    118023 |       1590 |
|     23118 |       1587 |
|    118008 |       1586 |
|     14118 |       1495 |
|     24026 |       1031 |
|    165158 |        960 |
|    169166 |         28 |
|     26034 |          6 |

## `implausible_speed`

|   zero_speed |   negative_speed |   over_60 |   over_80 |   over_100 |   zero_speed_pct |   over_80_pct |   max_speed_mph |
|-------------:|-----------------:|----------:|----------:|-----------:|-----------------:|--------------:|----------------:|
|          147 |                0 |     11397 |       986 |        549 |            0.005 |        0.0328 |          7019.4 |

## `sample_depth`

|   mean_samples |   min_samples |   p05 |   p50 |   p95 |   max_samples |   readings_with_le_1_sample |   le_3_samples_pct |
|---------------:|--------------:|------:|------:|------:|--------------:|----------------------------:|-------------------:|
|          34.62 |             2 |     2 |    18 |   121 |           706 |                           0 |              11.26 |

## `speed_vs_travel_time`

|   comparable_rows |   p50_abs_diff_mph |   p95_abs_diff_mph |   pct_disagree_gt_5mph |
|------------------:|-------------------:|-------------------:|-----------------------:|
|       2.90315e+06 |              0.002 |              0.003 |                      0 |

## `dst_spring_forward`

| label                |   readings_in_missing_hour |   readings_hour_01 |   readings_hour_03 |
|:---------------------|---------------------------:|-------------------:|-------------------:|
| control week earlier |                          0 |                  0 |                  0 |
| spring forward 2024  |                          0 |                  0 |                  0 |
| spring forward 2025  |                          0 |                  0 |                  0 |

## `readings_per_link_hour`

|   mean_readings_per_link_hour |   min_n |   p50_n |   p95_n |   max_n |   link_hours |   link_hours_over_4 |
|------------------------------:|--------:|--------:|--------:|--------:|-------------:|--------------------:|
|                          3.75 |       1 |       4 |       4 |       4 |       802228 |                   0 |

## `link_coverage_span`

|   links |   links_gone_before_treatment |   links_new_after_treatment |   mean_active_days |
|--------:|------------------------------:|----------------------------:|-------------------:|
|     330 |                            25 |                           0 |                110 |

## `daily_link_count`

123 rows (series; not inlined — plot separately).

Head / tail:

| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2024-10-01 00:00:00 |     320 |      26452 |
| 2024-10-02 00:00:00 |     310 |      26598 |
| 2024-10-03 00:00:00 |     310 |      26574 |
…
| day                 |   links |   readings |
|:--------------------|--------:|-----------:|
| 2025-01-29 00:00:00 |     291 |      24309 |
| 2025-01-30 00:00:00 |     283 |      23969 |
| 2025-01-31 00:00:00 |     286 |      24284 |

## `link_hour_gaps`

|   links_in_window |   ge_90pct_hours |   lt_50pct_hours |   mean_coverage_pct |
|------------------:|-----------------:|-----------------:|--------------------:|
|               330 |                0 |              209 |                42.2 |

## `ts_bounds`

_(no rows)_

## Proposed handling (human-edited — not yet applied)

_Fill in after reviewing the observed problems above. Each row: problem →
proposed rule → why → where it will be applied. Nothing here is applied until
it is written down and reviewed._

| Problem | Proposed rule | Rationale | Applied in |
|---|---|---|---|
| _e.g._ zero speeds | treat as missing | 0 mph is an artifact | `sql/03_hourly_panel.sql` |
