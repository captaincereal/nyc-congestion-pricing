# Data dictionary

## Primary source — NYC DOT E-Z Pass local-street speeds

- **Portal**: NYC Open Data (Socrata), dataset ids `erdf-2akx` + `6a2s-2t65`
- **What it is**: median speed and travel time over named **local street**
  segments, from E-Z Pass readers installed across the city (the Midtown in
  Motion programme and its successors).
- **Coverage**: `erdf-2akx` 2021-04-08 .. 2024-07-07; `6a2s-2t65` 2024-07-08 ..
  present. Identical schemas, same `sid` space, joining with no gap.
- **Segments**: ~346 across Manhattan, Queens, Brooklyn and Staten Island
  (no Bronx), including the tolled Manhattan grid the secondary feed lacks.
- **Cadence**: a **rolling** 900-second median re-published about every 61
  seconds, so consecutive rows overlap ~93%. Ingestion reduces this to one
  reading per non-overlapping 15-minute window.

| Field | Example | Type (raw) | Notes |
|---|---|---|---|
| `sid` | `1004` | string | **Stable segment identifier — the analysis unit** (`link_id` downstream). |
| `link_name` | `42nd Street - Eastbound - Lexington Ave to 3rd Ave` | string | Free text. The roadway *subject* is the part before the first delimiter; endpoints name cross streets. Delimiters are inconsistent (` - `, en dash, mojibaked en dash, `Street- westbound`). |
| `borough` | `Manhattan` | string | Casing/spacing varies; folded to lowercase in staging. |
| `polyline` | `agvwFxmobMfCeI` | string | Google-encoded polyline. **The basis for treatment assignment** — decoded in `src/data/geo.py`, never string-matched on `link_name`. |
| `link_length_ft` | `3781.98` | string→float | Segment length. |
| `aggregation_period_sec` | `900` | string→int | Window the median covers. The feed also emits `0`; ingestion keeps only `900`. |
| `n_samples` | `25` | string→int | Probe vehicles behind the median. 10.2% of readings rest on ≤3. |
| `median_calculation_timestamp` | `2025-01-06T08:00:10.000` | string→timestamp | **Naive `America/New_York`, verified both directions**: hour 01 doubles on fall-back 2024-11-03 (103 vs 51), and hour 02 is empty on spring-forward 2025-03-09 (0 vs 1,063). No conversion applied. |
| `median_tt_sec` | `228.0` | string→float | Median seconds to traverse. Agrees with the reported speed to a median 0.002 mph. |
| `median_speed_fps` | `20.57` | string→float | **Primary outcome input.** FEET PER SECOND — converted to mph (×3600/5280) in staging and nowhere else. Contains impossible values (observed max ~20,662 fps); not cleaned in staging. |

## Secondary source — NYC DOT Traffic Speeds NBE

Demoted from primary on 2026-09-08: it carries only ~121–125 links city-wide and
**none** on tolled CRZ surface streets. Retained for the spillover/diversion
analysis, because FDR Drive and the West Side Highway are precisely the
toll-exempt roads displaced traffic can move to. See `docs/methodology.md`.

- **Portal**: NYC Open Data (Socrata), dataset id `i4gi-tjb9`
- **URL**: https://data.cityofnewyork.us/Transportation/DOT-Traffic-Speeds-NBE/i4gi-tjb9
- **What it is**: Average speed and travel time for defined roadway *links*,
  derived from TRANSCOM probe / E-ZPass-reader data.
- **Cadence**: sub-hourly (roughly every 1–5 minutes per link, irregular).
- **History**: from 2017-04-17; continuously appended.
- **Known bias**: coverage is concentrated on highways, parkways, bridges and
  tunnels, and major arterials. Surface-street coverage inside the Congestion
  Relief Zone is thinner — quantified in `data_quality_report.md`.
- **Coverage concern — RESOLVED, and fatal for primary use**: a census of 40
  ingested months confirms ~121–125 distinct `link_id` city-wide in every month.
  Of the 18 whose geometry lies inside the CRZ, every one is toll-exempt or a
  crossing. The treated group under the frozen design was empty, which is why
  this source was demoted.

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

Immutable source extracts, one calendar month per file. Primary:
`data/raw/ezpass_speeds/ezpass_speeds_YYYY-MM.parquet` written by
`python -m src.data.download_ezpass`, with per-segment attributes held once in
`data/raw/ezpass_segments.parquet`. Secondary:
`data/raw/dot_speeds/dot_speeds_YYYY-MM.parquet` written by
`python -m src.data.download`.
Never edited. `data/raw/manifest.json` records, per month: SoQL window, row
count, expected row count (from a live `count(1)` query), byte size, SHA-256,
and pull timestamp. The manifest is merged across runs and rewritten after
every month, so an interrupted pull still leaves an accurate manifest.
`python -m src.data.download --verify` re-checks every on-disk part against the
live API row count.

## `data/interim/` — `stg_speed_readings`

Typed, de-duplicated staging of the **primary** feed. **No cleaning of values**
beyond type casting; problems are documented in the data-quality report, not
fixed here. Built by `sql/01_stage_ezpass.sql` (DuckDB), which also joins the
per-segment attributes. One row per `(link_id, 15-minute window)`.

The secondary feed stages separately to `stg_dot_highway_readings` via
`sql/01_stage_speeds.sql`; use `python -m src.data.build_staging --source dot`.

| Column | Type | Description |
|---|---|---|
| `link_id` | VARCHAR | Segment identifier (`sid`) |
| `ts` | TIMESTAMP | Reading time, naive `America/New_York` |
| `ts_window` | TIMESTAMP | The non-overlapping 15-minute window it belongs to |
| `ts_hour` | TIMESTAMP | Hour start |
| `is_dst_ambiguous_hour` | BOOLEAN | True for 01:00–01:59 on a fall-back date, where the hour runs twice and de-dup kept only one pass. Flagged, not dropped |
| `speed_mph` | DOUBLE | `median_speed_fps` × 3600/5280 (not range-filtered) |
| `travel_time_s` | DOUBLE | `median_tt_sec` |
| `n_samples` | INTEGER | Probe vehicles behind the median |
| `link_length_ft` | DOUBLE | From the segment table |
| `borough` | VARCHAR | Normalized borough label |
| `link_name` | VARCHAR | Segment description |
| `polyline` | VARCHAR | Encoded geometry, for treatment assignment |

## `data/processed/` — `hourly_panel`

Analysis-ready. One row per `link_id` × hour, built by `sql/03_hourly_panel.sql`
(`python -m src.data.build_panel`). Excludes only the DST-ambiguous hour and
null speeds; carries the diagnostics a cleaning rule would need
(`n_probe_samples`, `min_n_samples`, `n_zero_speed`, `n_over_80`) rather than
applying thresholds, so exclusions stay documented and reversible. Treatment
groups come from `data/interim/segment_treatment.parquet`
(`python -m src.data.geo`, geometric — decoded polylines vs the 60th St line):
`treated`, `control`, `exempt_in_zone`, `boundary`, `crossing`, and
`unassigned` for links absent from the segment attribute table.

| Column | Type | Description |
|---|---|---|
| `link_id` | string | Segment (`sid`) |
| `ts_hour` | timestamp | Hour start, `America/New_York` |
| `date` | date | Calendar date |
| `hour` | int | 0–23 |
| `dow` | int | Day of week, 0 = Sunday (DuckDB `date_part('dow', …)`) |
| `is_weekend` | bool | `dow IN (0, 6)` — Saturday/Sunday |
| `is_am_peak` / `is_pm_peak` | bool | Hour in 07–09 / 16–18 |
| `is_peak` | bool | `is_am_peak OR is_pm_peak` |
| `median_speed_mph` | float | **Primary outcome** — hourly median of link speed |
| `mean_speed_mph` | float | Secondary |
| `min_speed_mph` / `max_speed_mph` | float | Diagnostic range within the hour |
| `n_obs` | int | Sub-hourly (15-min-window) readings aggregated into the cell |
| `n_probe_samples` | int | Sum of `n_samples` behind the hour |
| `min_n_samples` | int | Thinnest reading behind the hour |
| `n_zero_speed` / `n_over_80` | int | Readings at 0 mph / above 80 mph — for coverage filters |
| `borough` | string | Borough label |
| `link_name` | string | Segment description |
| `roadway` | string | Roadway the segment runs along (name subject, from the treatment table) |
| `treatment_group` | string | `treated` · `control` · `exempt_in_zone` · `boundary` · `crossing` · `unassigned` |
| `treated` | bool | `treatment_group = 'treated'` |
| `post` | bool | `ts_hour >= 2025-01-05` |
| `treated_post` | bool | `treated & post` — the DiD interaction |
| `event_week` | int | Floor of elapsed local calendar days since 2025-01-05 divided by 7; Sunday–Saturday weeks, including negative weeks |

## `data/processed/` — `secondary_hourly_panel`

The spillover panel, built from the **secondary** feed by
`python -m src.data.build_secondary_panel` for H007. Same shape as
`hourly_panel` so the Phase 7–9 estimators run against it unchanged, with three
differences of meaning that a reader has to hold on to.

**`treated` means toll-EXEMPT, not tolled.** This feed carries no tolled CRZ
surface street, so there is no treated group in the frozen sense. The nine
`exempt_in_zone` links — FDR Drive, 12th/11th Ave, West St, the Brooklyn Battery
Tunnel Manhattan approaches — are flagged `treated` here because the question is
whether traffic diverted *onto* them.

**Zero-speed readings are outages and never enter an average.** They carry
`travel_time = 0` and `status = -101`, and their frequency peaks overnight. The
hourly median is taken over readings with `speed > 0`; an hour with readings but
no positive one keeps a **null** `median_speed_mph` and is retained, because the
share of present link-hours that yield a speed is the quantity H007's
availability criterion is written on. Every estimator drops null outcomes, so
retaining them changes no estimate. This supersedes
`outputs/tables/spillover_secondary_monthly.csv`, which averaged those zeros in
as 0 mph.

**Window 2023-01-01 .. 2026-05-31.** The feed holds 2023-01 … 2026-07 but
2026-06 is missing, so the window stops short rather than spanning a hole.

Columns are `hourly_panel`'s, minus the E-Z Pass-only `n_probe_samples` and
`min_n_samples`, plus:

| Column | Type | Description |
|---|---|---|
| `n_readings` | int | Deduplicated readings present in the hour, positive or not — the availability denominator |
| `n_positive` | int | Readings with `speed > 0`; the hourly median is taken over exactly these |
| `n_unparsed_speed` | int | Readings whose `speed` did not cast to a number |
| `has_speed` | bool | `median_speed_mph` is not null |
| `event_month` | int | Calendar months from 2025-01; `k = 0` is January 2025, `k = -1` December 2024. H007's event study bins on this, not on `event_week` |
| `analysis_group` | string | `treated_exempt` · `control` · `boundary` · `crossing` · `held_out_geo` |
| `hold_out_reason` | string | Why a link is in neither estimation group; empty for the two that are |
| `treated` | bool | `analysis_group = 'treated_exempt'` — **not** `treatment_group = 'treated'` |

`treatment_group` still carries the raw `classify_segment` output, so the two
columns disagree on link_ids `4616339` and `4616340`: the classifier calls them
`treated` because it trusts their `borough = Manhattan` label, their geometry is
in Brooklyn, and `analysis_group` holds them out of both estimation groups.

## Secondary sources (Phase 10 only — not yet used)

See `docs/future_data_sources.md`. MTA Congestion Relief Zone vehicle-entry
data and NYC TLC trip records are added only after the speed analysis is stable.

## Conventions

- All timestamps stored/interpreted in `America/New_York`; DST-aware.
- Missing numeric values are `NaN`, never `0` or `-999`.
- Treatment date constant: `TREATMENT_DATE = 2025-01-05` (`src/config.py`).
- Row counts are tracked through every transformation (raw → staged → panel).
