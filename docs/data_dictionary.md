# Data dictionary

## Primary source — NYC DOT Traffic Speeds NBE

- **Portal**: NYC Open Data (Socrata), dataset id `i4gi-tjb9`
- **URL**: https://data.cityofnewyork.us/Transportation/DOT-Traffic-Speeds-NBE/i4gi-tjb9
- **What it is**: Average speed and travel time for defined roadway *links*,
  derived from TRANSCOM probe / E-ZPass-reader data.
- **Cadence**: sub-hourly (roughly every 1–5 minutes per link, irregular).
- **History**: from 2017-04-17; continuously appended.
- **Known bias**: coverage is concentrated on highways, parkways, bridges and
  tunnels, and major arterials. Surface-street coverage inside the Congestion
  Relief Zone is thinner — quantified in `data_quality_report.md`.
- **Coverage concern (open)**: a 4-hour sample in March 2025 returned only 121
  distinct `link_id` city-wide. If active-link counts are really this low, the
  treated group inside the CRZ may be too small for a clean design. First thing
  to quantify once the full pull is in (Phase 3).

### Raw fields (verified against the live API, 2026-09-07)

| Field | Example | Type (raw) | Notes |
|---|---|---|---|
| `id` | `318` | string | In short windows `id` is 1:1 with `link_id` (not per-reading as first assumed). Confirm over the full pull in Phase 2; treat `link_id` as the key regardless. |
| `speed` | `48.46` | string→float | Average speed over the link. Units assumed **mph** — confirm in Phase 2. |
| `travel_time` | `81` | string→float | Seconds to traverse the link. |
| `status` | `0` | string | Not officially documented. Observed values include `0` and `-101`; `-101` (~28% of a March-2025 sample) coincides with `speed = 0` → likely a stale / no-data flag. Full value counts in Phase 2. |
| `data_as_of` | `2026-09-07T13:46:06.000` | string→timestamp | Observation time. **Confirmed naive `America/New_York`**: the 02:00–02:59 local hour is empty on spring-forward day 2025-03-09, and the surrounding hours each carry equal row counts. No timezone conversion applied. |
| `link_id` | `4362249` | string | **Stable segment identifier — the analysis unit.** |
| `transcom_id` | `4362249` | string | Usually equals `link_id`. |
| `link_points` | `40.744,-73.77 40.745,-73.769 …` | string | Space-separated `lat,lon` pairs tracing the link. Only geometry available. |
| `encoded_poly_line` | `kztwFzogaM…` | string | Google-encoded polyline of the same geometry. |
| `encoded_poly_line_lvls` | `BBBB…` | string | Polyline zoom levels. |
| `owner` | `NYC-DOT-Region 10` | string | Operating region/agency. |
| `borough` | `Queens` | string | Borough label (free text; casing varies). |
| `link_name` | `LIE WB LITTLE NECK PKWY - NB CIP` | string | Human-readable segment description. |

No latitude/longitude columns — segment location must be derived from
`link_points` (Phase 5, treatment geography).

## `data/raw/`

Immutable source extracts, written by `python -m src.data.download`. Named
`dot_speeds_<window>_<pull-date>.parquet`. Never edited. Each pull appends an
entry to `data/raw/manifest.json` recording query params, row count, byte size,
SHA-256, and pull timestamp.

## `data/interim/` — `stg_speed_readings`

Typed, de-duplicated staging of the raw feed. **No cleaning of values** beyond
type casting; problems are documented in the data-quality report, not fixed
here. Built by `sql/01_stage_speeds.sql` (DuckDB).

| Column | Type | Description |
|---|---|---|
| `link_id` | VARCHAR | Segment identifier |
| `ts` | TIMESTAMP | `data_as_of` parsed, `America/New_York` |
| `speed_mph` | DOUBLE | `speed` cast to float (not range-filtered) |
| `travel_time_s` | DOUBLE | `travel_time` cast to float |
| `status` | VARCHAR | Raw status flag |
| `borough` | VARCHAR | Normalized borough label |
| `link_name` | VARCHAR | Segment description |

## `data/processed/` — `hourly_panel`

Analysis-ready. One row per `link_id` × hour. Built by `sql/03_hourly_panel.sql`
in **Phase 4** — schema below is the current plan and may change once the
staging data is inspected.

| Column | Type | Description |
|---|---|---|
| `link_id` | string | Segment |
| `ts_hour` | timestamp | Hour start, `America/New_York` |
| `date` | date | Calendar date |
| `hour` | int | 0–23 |
| `dow` | int | Day of week, 0 = Monday |
| `is_weekend` | bool | Saturday/Sunday |
| `is_peak` | bool | Within AM (07–09) or PM (16–18) peak |
| `median_speed_mph` | float | **Primary outcome** — hourly median of link speed |
| `mean_speed_mph` | float | Secondary |
| `n_obs` | int | Sub-hourly readings aggregated into the cell |
| `borough` | string | Borough label |
| `treated` | bool | Segment inside the Congestion Relief Zone (Phase 5) |
| `is_boundary` | bool | Near-boundary / spillover segment (Phase 5) |
| `post` | bool | `ts_hour >= 2025-01-05` |
| `treated_post` | bool | `treated & post` — the DiD interaction |
| `event_time` | int | Weeks relative to 2025-01-05 |

## Secondary sources (Phase 10 only — not yet used)

See `docs/future_data_sources.md`. MTA Congestion Relief Zone vehicle-entry
data and NYC TLC trip records are added only after the speed analysis is stable.

## Conventions

- All timestamps stored/interpreted in `America/New_York`; DST-aware.
- Missing numeric values are `NaN`, never `0` or `-999`.
- Treatment date constant: `TREATMENT_DATE = 2025-01-05` (`src/config.py`).
- Row counts are tracked through every transformation (raw → staged → panel).
