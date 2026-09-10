# Project brief — frozen definitions

This is the canonical statement of the research design. The items under
**Frozen** do not change without a written justification in
`docs/methodology.md` and a note in the git history.

## Background

On **2025-01-05**, New York City began tolling vehicles entering the Congestion
Relief Zone (CRZ) — Manhattan at and below 60th Street, excluding the FDR Drive,
the West Side Highway / Route 9A, and the surface roadways connecting to the
Hugh L. Carey and Queens–Midtown tunnels. It is the first cordon congestion
pricing program in the United States.

## Research question

**What was the effect of congestion pricing on traffic speeds inside the
Congestion Relief Zone, and is there evidence that congestion shifted to nearby
areas (spillover near the zone boundary)?**

Secondary questions:

1. Do effects differ during peak vs off-peak hours?
2. Do effects differ on weekdays vs weekends?
3. Are there spillover effects near the zone boundary?
4. Do MTA vehicle-entry and TLC taxi data support the mechanism suggested by the
   speed analysis? (Phase 10 only.)

## Frozen

| Item | Definition |
|---|---|
| **Intervention date** | 2025-01-05 (`TREATMENT_DATE` in `src/config.py`) |
| **Primary outcome** | Hourly **median** traffic speed (mph) on a road segment (link) |
| **Treatment units** | Links physically inside the CRZ |
| **Control units** | Comparable links outside the CRZ, evaluated on pre-treatment trends — **not** chosen for geographic convenience |
| **Near-boundary units** | Links just outside the CRZ boundary, analysed separately for spillover; excluded from the control group |
| **Primary method** | Difference-in-differences with a two-way fixed-effects estimator, plus an event-study specification |
| **Standard errors** | Clustered by link (`CLUSTER_VAR`) |
| **Study period** | 2023-01-01 through the latest complete data (≥ 24 months pre-treatment) |
| **Unit of analysis** | link × hour |
| **Primary data source** | NYC DOT E-Z Pass local-street speeds (`erdf-2akx` + `6a2s-2t65`) — changed 2026-09-08, see the decision record in `docs/methodology.md` |
| **Secondary data source** | NYC DOT Traffic Speeds NBE (`i4gi-tjb9`) — highways, crossings and toll-exempt roads only; used for the spillover/diversion analysis |

## Scope

- **Geography**: CRZ (treated); comparable Manhattan-above-60th and outer-borough
  links (control); boundary approaches (spillover). Final assignment in Phase 5.
- **Not in scope for the core analysis**: volume, travel time as a primary
  outcome, mode shift, revenue, air quality. Volume enters in Phase 10 as a
  mechanism check.

## Deliverables

- Reproducible repo + clean README (Question → Result → Evidence → Robustness →
  Limitations → Recommendation).
- Data-quality report — `docs/data_quality_report.md`.
- Cleaned hourly panel — `data/processed/`.
- Descriptive report — `outputs/`.
- DiD estimates with clustered SEs — `outputs/tables/`.
- Event-study figure — `outputs/figures/`.
- Methodology writeup — `docs/methodology.md`.
- Robustness comparison table + limitations section.

## Key assumptions & risks

- **Parallel trends** between treated and control links absent treatment
  (tested via pre-period event-study coefficients, not assumed proven).
- **No anticipation** before 2025-01-05 (tested with leads).
- **SUTVA / interference**: traffic diverted to boundary links violates SUTVA;
  handled by excluding boundary links from controls and modelling spillover
  separately.
- **Sensor stability**: link coverage and the probe panel are stable across the
  treatment date (checked in the data-quality report).
- Confounders: weather, fuel prices, transit service changes, remote-work
  trends, major events, construction.

## Research integrity

Report effect sizes and confidence intervals. Document missing data. Track row
counts through every transformation. Preserve null / inconvenient findings.
Distinguish exploratory from confirmatory analysis. Do not describe an
association as causal without defending the assumptions above.

## Stakeholders

- Analyst / owner: Hanu Varma Pinaramaju (`hanu.p098@gmail.com`)
- Audience: data-science portfolio; potential public writeup.
