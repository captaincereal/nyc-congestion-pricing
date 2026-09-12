# NYC Congestion Pricing — Effect on Traffic Speeds

Estimating the causal effect of NYC's Congestion Relief Zone toll (tolling began
**2025-01-05**) on traffic speeds inside the zone, and testing whether congestion
shifted to nearby areas.

**Research finding, 2026-09-12:** the current comparison design cannot support
a causal claim about the toll's effect on speed or nearby diversion. The
positive speed association survives several sensitivities, but corrected
pre-period tests reject in every sample. This is not evidence of zero effect.
The full frozen study remains incomplete; owner decisions are laid out in
[the decision memo](docs/owner_decisions.md).

---

## Question

What was the effect of congestion pricing on traffic speeds inside the
Congestion Relief Zone (CRZ), and is there evidence that congestion shifted to
areas just outside the zone boundary?

Secondary: do effects differ peak vs off-peak and weekday vs weekend? Do MTA
entry and TLC data support the mechanism? (Phase 10.)

## Result

Observed speeds improved relative to the candidate control streets, but this
study cannot presently attribute that change to congestion pricing. The
comparison groups already differ in their pre-treatment evolution, the
required 2023–24 archive is incomplete, and primary source verification is
pending. A larger archive or a validated control design could change this
assessment; the current result does not establish a causal benefit or a null.

Nearby diversion is also unidentified. The five primary links labelled
`boundary` straddle 60th Street, so they do not directly measure streets wholly
outside the zone. Secondary highway/crossing speeds are summarized
descriptively, without assigning their changes to diverted traffic.

## Evidence

The contiguous October 2024–April 2025 diagnostic window and the expanded
archive including June both produce positive two-way fixed-effects
coefficients. The output tables preserve link-clustered standard errors and
confidence intervals for reproducibility, but **effect magnitudes are withheld
from this report until the primary archive completes live verification**.
These outputs are exploratory computations, not validated effect estimates.

The corrected joint pre-period tests reject on the contiguous window, so
adding June does not explain the failure. On all available months, every
sample rejects: overall, peak, off-peak and weekend.
The earlier “peak and weekend pass” claim used an invalid joint test and an
incorrect event-week boundary and is superseded.

See the [corrected pre-trend results](outputs/tables/pretrend_tests.csv),
[contiguous-window test](outputs/tables/robustness_pretrend_contiguous.csv),
[event-study figure](outputs/figures/event_study_all.png), and
[input/code provenance](outputs/tables/analysis_provenance.json).

## Robustness

The [12-specification comparison](outputs/tables/robustness_comparison.csv)
includes control geography, alternative windows, a common link roster,
transition exclusion, probe-depth and extreme-speed filters, an hourly mean
outcome, two placebo dates, and the four 11th Avenue links as a separate
treatment sensitivity. Non-placebo coefficients remain positive, while their
magnitude is sensitive to the control pool and quality filters.

The November 17 and December 1, 2024 placebos, using only actual pre-tolling
observations, do not reject a zero coefficient. These null placebos do not
repair the joint lead rejection. Weather interactions have little effect on
the all-hours coefficient. None of these
exploratory comparisons validates D2 or demonstrates parallel trends. Daily
aggregation, held-out trend matching and a full-year placebo remain unfinished.

## Limitations

- Only eight of 44 complete target months are held: June 2024 and October
  2024–April 2025. July–September are missing; the longest contiguous
  pre-treatment run is three full months, versus the frozen 24-month design.
- Default event-study endpoints pool weeks earlier/later than ±12. A longer
  download alone does not yield a week-by-week year-long test. Holidays are
  an untested explanation for the lead rejection, and passing a test would
  not prove parallel trends.
- All primary parts remain unverified. Probe quality, sensor turnover, uneven
  coverage and the nearly twofold pre-treatment level gap limit interpretation.
  The [quality report](docs/data_quality_report.md) documents the current archive.
- Treatment classification still reserves D3 for the owner. The generic
  11th Avenue exemption likely misclassifies four local-street segments;
  the corresponding sensitivity changes the contiguous coefficient only slightly.
- The feed measures selected link speeds, not network-wide congestion,
  vehicle volumes, welfare or mode shift. MTA entries and TLC mechanism checks
  have not been run. The secondary link-month series supports coverage review,
  not a causal spillover estimate.

## Recommendation

Report this as a documented failure of the current design to identify a causal
effect. Do not use its positive coefficients to claim the toll improved speed,
or its lack of spillover identification to claim no diversion occurred.

Complete and verify the frozen archive on the free hosted backfill, then
develop trend-based controls with a held-out pre-treatment validation period.
Resolve the near-boundary definition and the 11th Avenue assignment before
re-estimation. [D1, D2, D3, D5, D6 and D7 recommendations](docs/owner_decisions.md)
await owner approval; no open decision was silently adopted.

---

## Method

- **Difference-in-differences**: CRZ links (treated) vs. comparable links
  outside the zone (control), before vs. after 2025-01-05, with link and
  time fixed effects and SEs clustered by link.
- **Event study**: dynamic coefficients around the tolling date to check
  pre-trends and trace the adjustment path.
- **Placebo / robustness**: separate specifications, not tweaks to the primary
  model.

See `docs/methodology.md` for the full specification and identifying
assumptions, and `docs/project_brief.md` for frozen definitions.

## Data

**Primary — NYC DOT E-Z Pass local-street speeds** (`erdf-2akx` +
`6a2s-2t65`, NYC Open Data). Two datasets with identical schemas that join with
no gap, covering 2021-04-08 to the present. `median_speed_fps` on ~346 named
street segments, including the tolled Manhattan grid.

**Secondary — NYC DOT Traffic Speeds NBE** (`i4gi-tjb9`). This was the original
primary source. It carries only ~123 links city-wide and **none** on tolled CRZ
surface streets — every in-zone link is a toll-exempt highway (FDR Drive, West
Side Highway) or a crossing — so it cannot support the primary specification. It
is retained for the spillover/diversion analysis, since those exempt roads are
exactly where displaced traffic would go. Full reasoning in the 2026-09-08
decision record in `docs/methodology.md`.

Schema and conventions in `docs/data_dictionary.md`; open questions in
`docs/decision_register.md`; further sources in `docs/future_data_sources.md`.

## Project structure

```
data/         raw/ (immutable) · interim/ (typed staging) · processed/ (panels)
docs/         brief · data dictionary · methodology · reproducibility · data-quality report
sql/          DuckDB: 01 staging · 02 quality checks · 03 hourly panel
src/
  data/       download · inspect_schema · build_staging · quality_report
  analysis/   descriptive · did · event_study · robustness · spillover_diagnostics · provenance
  visualization/
notebooks/    exploratory analysis (orchestrate + narrate only)
tests/        unit tests for src/ transformations
outputs/      figures/ · tables/ — tracked; the results are the deliverable
scripts/      priority_backfill.sh (range order) · data_release.sh (CI storage)
.github/      backfill · analysis · tests workflows
```

## Getting started

```bash
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows
pip install -e ".[dev]"

python -m src.data.coverage_report    # how far the backfill is, and whether the
                                      # pre-trend test clears yet
```

Ingestion runs on a schedule in GitHub Actions rather than locally — the
backfill is ~21 hours against a feed that throttles, and it resumes itself
across passes. To pull months locally anyway:

```bash
python -m src.data.download_ezpass --start 2023-01-01   # primary; needs NYC_OPENDATA_APP_TOKEN
python -m src.data.download        --start 2023-01-01   # secondary (DOT highways, spillover)
```

Full pipeline, workflows and environment variables: `docs/reproducibility.md`.

## License

MIT (see `pyproject.toml`).
