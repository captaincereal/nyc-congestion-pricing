# Future data sources (Phase 10 — do not add yet)

The core analysis uses **only** the NYC DOT Traffic Speeds feed (`i4gi-tjb9`).
These sources are deferred until the speed-based DiD / event study is stable and
has passed its diagnostics. Each is added only to answer a *specific* question.

| Source | Socrata / access | Question it would answer |
|---|---|---|
| MTA Congestion Relief Zone vehicle entries | `data.ny.gov` resource `t6yz-b64h` | Did *volume* entering the zone fall? Does it corroborate the speed change (mechanism check)? |
| NYC DOT Traffic Volume Counts | `data.cityofnewyork.us` resource `7ym2-wayt` | Segment-level volume near the boundary — spillover in counts, not just speeds. |
| NYC TLC trip records (yellow / green / FHV) | TLC monthly parquet files | Trip times, fares, pickup/dropoff shifts across the cordon. |
| Weather (Open-Meteo / NOAA, Central Park) | API | Confounder control if descriptive analysis shows weather imbalance across the treatment date. |

The earlier scaffold wired all of these into `download.py` and the SQL at once.
That was rolled back on 2026-09-07 to keep Phases 1–9 to a single, well-understood
source. The dataset ids above are recorded here so the work isn't lost.
