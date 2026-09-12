# NYC Congestion Pricing — Effect on Traffic Speeds

Estimating the causal effect of NYC's Congestion Relief Zone toll (tolling began
**2025-01-05**) on traffic speeds inside the zone, and testing whether congestion
shifted to nearby areas.

**Research finding, 2026-09-12:** this design cannot identify the toll's effect
on speed or on nearby diversion. Speeds inside the zone did rise relative to
comparison streets, and that association is robust. Its *causal* interpretation
is not: pre-period tests reject in every sample, the estimate tolerates only a
fraction of the differential drift already visible in the data, and a
pre-registered attempt to build a better comparison group failed out of sample.
This is a finding about the design, not evidence that the toll did nothing.
Owner decisions are laid out in [the decision memo](docs/owner_decisions.md).

---

## Question

What was the effect of congestion pricing on traffic speeds inside the
Congestion Relief Zone (CRZ), and is there evidence that congestion shifted to
areas just outside the zone boundary?

Secondary: do effects differ peak vs off-peak and weekday vs weekend? Do MTA
entry and TLC data support the mechanism? (Phase 10.)

## Result

**Speeds inside the Congestion Relief Zone rose relative to comparison streets
after tolling began, by around 0.77 mph on the full sample, roughly 8% of the
pre-tolling treated mean. That association is real and survives every robustness
check applied to it. It cannot be attributed to the toll.**

Four separate lines of attack, each pre-registered before it ran, converge on
the same conclusion: the comparison group does not support a causal reading.
Pre-period leads reject decisively in all four samples. The estimate's reported
precision survives neither an honest null nor a collapse to one observation per
link. And controls selected on pre-treatment behaviour, judged on a window the
selection never saw, reject *more* decisively than the naive pool.

Nearby diversion is likewise unidentified. The five links labelled `boundary`
straddle 60th Street rather than sitting wholly outside it, and no control link
lies within 500 m of the line, so the panel contains no units where diversion
would show up most clearly. That is a coverage limitation of the feed, not
evidence that diversion did not occur.

## Evidence

The source archive is complete for the window it covers: **12 contiguous months,
2024-05 through 2025-04, all 12 verified** against live source counts with
deterministic replay of the retained sample. Effect magnitudes appear below
because that verification has now completed.

**The association.** Two-way fixed effects on link and time, standard errors
clustered by link, 331 clusters, 2.36M link-hours
([did_estimates.csv](outputs/tables/did_estimates.csv)):

| Sample | ATT (mph) | SE | 95% CI | % of pre-treated mean |
|---|---:|---:|---|---:|
| all | +0.77 | 0.22 | [0.34, 1.20] | 7.9 |
| weekday peak | +0.81 | 0.22 | [0.37, 1.24] | 10.1 |
| weekday off-peak | +0.67 | 0.21 | [0.24, 1.09] | 6.7 |
| weekend | +0.95 | 0.25 | [0.46, 1.45] | 9.2 |

**Why it is not causal.** The joint test that pre-tolling leads are zero rejects
in every sample ([pretrend_tests.csv](outputs/tables/pretrend_tests.csv)):
chi-squared 84.8 overall, 63.9 peak, 87.1 off-peak, 43.6 weekend, all on 11
degrees of freedom, all p below 1e-05. Treated and comparison streets were
already moving apart before the toll existed.

An earlier version of that test summed squared individual t-statistics and
ignored the covariance between leads, and an off-by-one event-week boundary put
1-4 January into event week zero. Both were corrected on 2026-09-12. The earlier
"peak and weekend pass" claim came from the broken test and is superseded.

**How little violation it takes to overturn.** Rambachan & Roth (2023)
sensitivity, bounding post-treatment violations as a multiple of those observed
pre-treatment ([H002](docs/hypotheses/H002-honest-did-sensitivity.md)):

| Sample | breakdown value | robust CI at M = 0.5 |
|---|---:|---|
| all | 0.083 | [-2.42, 4.57] |
| peak | 0.044 | [-2.10, 3.97] |
| off-peak | 0.054 | [-2.93, 4.76] |
| weekend | 0.151 | [-2.08, 5.07] |

The estimate holds only if post-tolling differential drift stays below roughly
4 to 15 percent of the largest drift already visible beforehand. The pre-period
violations are large, so that is a demand the data give no reason to grant.

**The precision is not defensible either.** Two independent checks:

- *Placebo-in-space* ([H001](docs/hypotheses/H001-placebo-in-space.md)):
  reassigning treatment at random among control links, 500 draws. The clustered
  standard errors run up to 1.5 times too tight, and the weekday peak estimate
  fails outright, with chance reassignment producing a peak-sized effect about
  one time in eleven (p = 0.092).
- *Temporal aggregation* ([H003](docs/hypotheses/H003-temporal-aggregation.md)):
  daily aggregation is stable, within 0.14 mph everywhere. Collapsing to one pre
  and one post observation per link, the Bertrand-Duflo-Mullainathan remedy for
  serial correlation, inflates standard errors 3.8 to 6.2 times, puts zero inside
  every interval, and flips the off-peak sign. Much of the apparent precision
  comes from treating serially correlated link-hours as independent evidence.

**A direct attempt to fix the comparison group failed.**
[H004](docs/hypotheses/H004-control-construction.md) built controls from
pre-treatment trajectory shape on event weeks -36 to -13 and judged them on
-12 to -2, a window the matching never saw. Nearest-neighbour selection made
held-out flatness *worse* in all four samples. Synthetic weights roughly halved
the test statistic and still rejected at p = 4.4e-07, after fitting the matching
window to a squared loss of exactly zero. Judged in-sample it would have looked
like a complete success.

Every hypothesis run against this study, including those that failed, is in the
[hypothesis register](docs/hypotheses/REGISTER.md), each with its prediction
fixed before the result existed.

## Robustness

The [12-specification comparison](outputs/tables/robustness_comparison.csv)
covers control geography, alternative windows, a common link roster, transition
exclusion, probe-depth and extreme-speed filters, an hourly mean outcome, two
placebo dates, and the four 11th Avenue links as a treatment sensitivity.
Non-placebo coefficients stay positive; their magnitude is sensitive to the
control pool and to quality filters.

The 2024-11-17 and 2024-12-01 placebos, using only pre-tolling observations, do
not reject zero. Weather interactions move the all-hours coefficient by under
5%. None of this repairs the rejected leads: a specification can be stable and
still be measuring the wrong thing.

The pattern across all of it is consistent. **The point estimate is robust and
its causal interpretation is not.** Those are different claims, and only the
first is supported.

## Limitations

- **Coverage.** Twelve of 44 target months are held. The pre-treatment side is
  eight months where the frozen design asks for 24, so nothing here has been
  tested on the window the design actually calls for.
- **The held-out window is holiday-dominated.** H004 validates on October to
  December 2024. That makes it a demanding test, but a failure there is
  confounded with holiday dynamics and cannot on its own establish that trend
  matching is hopeless. Repeat it on a clean window once the backfill reaches
  2023-01.
- **Endpoint pooling.** Event-study bins beyond 12 weeks either side pool more
  distant weeks. The diagnostics record which bins are genuine weekly estimates.
- **No units where diversion would show.** No control link lies within 500 m of
  the boundary; the nearest is about 808 m. The spillover question is
  unanswerable on this roster rather than answered in the negative.
- **Treatment classification.** D3 remains open. The blanket 11th Avenue
  exemption probably misclassifies four local-street segments, though the
  sensitivity moves the coefficient only slightly.
- **What the outcome is.** Hourly median speed on selected links, weighting a
  quiet link the same as a heavy corridor. Not network congestion, not volume,
  not door-to-door travel time, not welfare. MTA entry and TLC mechanism checks
  have not been run.

## Recommendation

**Report this as a documented failure to identify, and do not soften it.** The
positive coefficients must not be used to claim the toll improved speeds, and
the absent spillover estimate must not be used to claim no diversion occurred.
A design that cannot separate an effect from pre-existing drift tells you
nothing about that effect's sign or size.

This is still a usable result. "Here is what the available data can and cannot
support, and here is the evidence for both" is a more honest deliverable than a
confident number resting on an assumption the data reject.

To move past it: complete the frozen archive to 2023-01 on the hosted backfill,
then repeat H004's held-out matching on a non-holiday window with the
pre-treatment span the design specifies. If flat held-out leads emerge there,
re-run the Rambachan-Roth sensitivity on the new control set before writing any
causal sentence. If they do not, the conclusion above is the finding.

[D1, D2, D3, D5, D6 and D7](docs/owner_decisions.md) await owner approval. No
open decision has been silently adopted.

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
