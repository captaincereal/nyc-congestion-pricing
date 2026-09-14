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
Every explanation that would have rescued it — too little pre-period, an
atypical holiday window, a poorly chosen comparison group — has now been tested
and none survives.

**Updated 2026-09-13.** Two things changed, and neither rescued the design.

The frozen archive is now **complete** — all 44 months, 2023-01 through 2026-08,
every one verified. The "too little pre-period" explanation is therefore
exhausted rather than merely unlikely: the design has the full two years it asked
for, and the joint pre-trend test rejects in all four samples on it, harder than
it did on half the data.

And the diversion half of the finding is now checked directly rather than
inferred. The secondary highway feed does carry the toll-exempt roads traffic
would divert onto, and it stops reporting speeds on three of the nine across the
toll date, so it cannot measure diversion either. That failure is
instrumentation rather than identification, which is a different problem with a
different fix.

**One thing the study can now show.** Drivers demonstrably respond to the toll's
*price schedule*: entries collapse as the peak rate begins and rise as it ends,
against a control of vehicles on exempt roads who are never charged and who move
the opposite way. That is a behavioural response, cleanly identified off a price
discontinuity rather than a parallel-trends assumption. It is reported under
Evidence with the caveat it deserves — neither record cleared its own
pre-registered bar — and it says nothing about congestion or speeds. Retiming an
entry is not avoiding one.
Owner decisions are laid out in [the decision memo](docs/owner_decisions.md).

---

## Question

What was the effect of congestion pricing on traffic speeds inside the
Congestion Relief Zone (CRZ), and is there evidence that congestion shifted to
areas just outside the zone boundary?

Secondary: do effects differ peak vs off-peak and weekday vs weekend? Do MTA
entry and TLC data support the mechanism? The MTA entry counts cannot say
whether the toll reduced entries — the series begins on the tolling date — but
their own peak/overnight price structure supports a separate question, **do
drivers retime entries to avoid the peak rate**, which is answered below.

## Result

**Speeds inside the Congestion Relief Zone rose relative to comparison streets
after tolling began, by around 1.05 mph on the full sample, roughly 11% of the
pre-tolling treated mean. That association is real and survives every robustness
check applied to it. It cannot be attributed to the toll.**

Four separate lines of attack, each pre-registered before it ran, converge on
the same conclusion: the comparison group does not support a causal reading.
Pre-period leads reject decisively in all four samples. The estimate's reported
precision survives neither an honest null nor a collapse to one observation per
link. And controls selected on pre-treatment behaviour, judged on a window the
selection never saw, reject *more* decisively than the naive pool.

Nearby diversion is likewise unidentified, now on both available feeds and for
two different reasons. In the primary panel the five links labelled `boundary`
straddle 60th Street rather than sitting wholly outside it, and no control link
lies within 500 m of the line, so it contains no units where diversion would
show up most clearly. The secondary DOT highway feed does carry those units —
the nine toll-exempt in-zone links traffic would divert onto — and it stops
measuring three of them across the toll date. Neither is evidence that diversion
did not occur.

## Evidence

The frozen archive is **complete**: 44 contiguous months, 2023-01 through
2026-08, **all 44 verified** against live source counts with deterministic
replay of the retained sample. That is 24 pre-treatment months and 20
post-treatment, or 104 pre-treatment weeks. Effect magnitudes appear below
because the verification gate has passed.

Evidence is labelled by the panel it was computed on, and the labels matter.
The association, the pre-trend test and the robustness table are current, rebuilt
from the complete archive on 2026-09-13. The hypothesis records are **not**
rebuilt with it: each cites the artefacts it was answered on, and rerunning one
against the longer panel would be a fresh draw needing its own registration. So
H001 through H004 stand on an earlier 12-month panel, H005 and H006 on 96
pre-treatment weeks, and H007 on the secondary feed.

**The association** (44-month panel). Two-way fixed effects on link and time,
standard errors clustered by link, 334 clusters, 7.95M link-hours
([did_estimates.csv](outputs/tables/did_estimates.csv)):

| Sample | ATT (mph) | SE | 95% CI | % of pre-treated mean |
|---|---:|---:|---|---:|
| all | +1.05 | 0.27 | [0.53, 1.57] | 10.6 |
| weekday peak | +0.98 | 0.25 | [0.50, 1.47] | 12.2 |
| weekday off-peak | +0.95 | 0.26 | [0.43, 1.47] | 9.3 |
| weekend | +1.28 | 0.30 | [0.69, 1.86] | 12.2 |

The estimate has drifted down as the archive grew — 1.17 mph on 27 months, 1.19
on 39, 1.05 on the full 44 — while staying positive and comfortably bounded away
from zero in every cut. The pre-treatment treated mean is 9.88 mph.

**Why it is not causal.** The joint test that pre-tolling leads are zero rejects
in every sample ([pretrend_tests.csv](outputs/tables/pretrend_tests.csv)):
chi-squared 97.9 overall, 69.7 peak, 102.2 off-peak and 46.7 weekend, all on 11
degrees of freedom, the weakest of them at p = 2.4e-06. Treated and comparison
streets were already moving apart before the toll existed.

The pre-period is now the full two years the design asked for, and lengthening
it never rescued the test. Against the same four samples: 84.8, 63.9, 87.1 and
43.6 on 36 pre-treatment weeks; 97.0, 70.7, 100.4 and 45.6 on 96; and 97.9,
69.7, 102.2 and 46.7 on 104. Three of the four rise monotonically and weekday
peak is the exception, easing from 70.7 to 69.7 at the last step while remaining
far beyond rejection. Every earlier caveat leaned on the pre-period being short
and holiday-dominated, and predicted the opposite. **That explanation is now
exhausted rather than merely unlikely**: there is no more pre-period to add.

An earlier version of that test summed squared individual t-statistics and
ignored the covariance between leads, and an off-by-one event-week boundary put
1-4 January into event week zero. Both were corrected on 2026-09-12. The earlier
"peak and weekend pass" claim came from the broken test and is superseded.

An earlier version of that test summed squared individual t-statistics and
ignored the covariance between leads, and an off-by-one event-week boundary put
1-4 January into event week zero. Both were corrected on 2026-09-12. The earlier
"peak and weekend pass" claim came from the broken test and is superseded.

**How little violation it takes to overturn.** Rambachan & Roth (2023)
sensitivity bounds post-treatment violations as a multiple of those observed
pre-treatment, and reports the breakdown value: the smallest violation at which
the robust confidence set stops excluding zero.
[H005](docs/hypotheses/H005-honest-did-long-preperiod.md) on 96 pre-treatment
weeks, at three event-study horizons:

| Sample | ±12 weeks | ±26 weeks | ±52 weeks |
|---|---:|---:|---:|
| all | 0.093 | 0.063 | 0.044 |
| peak | 0.044 | 0.015 | **0.005** |
| off-peak | 0.054 | 0.034 | 0.034 |
| weekend | 0.171 | 0.112 | 0.093 |

The estimate holds only if post-tolling differential drift stays below a few
percent of the largest drift already visible beforehand. The pre-period
violations are large, so that is a demand the data give no reason to grant. At
M = 0.5 the robust intervals already run two to five mph either side of zero,
an order of magnitude wider than the estimate they bound.

Two things about this table matter beyond the headline. At a matched horizon,
tripling the pre-period barely moved the values — H002 on 36 weeks gave 0.083,
0.044, 0.054 and 0.151. And the values fall monotonically as the restriction is
allowed to see more of the pre-period, because the largest observed first
difference grows with the window. **The more of this pre-period the analysis
looks at, the less the estimate survives** — the opposite of what a design
limited by short data would show.

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

**Two attempts to fix the comparison group failed.**
[H004](docs/hypotheses/H004-control-construction.md) built controls from
pre-treatment trajectory shape and judged them on a window the matching never
saw. Nearest-neighbour selection made held-out flatness *worse* in all four
samples. Synthetic weights roughly halved the test statistic and still rejected
at p = 4.4e-07, after fitting the matching window to a squared loss of exactly
zero. Judged in-sample it would have looked like a complete success.

[H006](docs/hypotheses/H006-control-construction-clean-holdout.md) repeated it
on the long archive: seventy weeks of matching, judged on a clean July-September
holdout **and** on H004's October-December one, under a single specification.
Every control set rejects on the clean window — best result p = 0.0014.

That two-holdout contrast settles the holiday question. Every set rejects about
twice as hard on October-December as on the clean window, so holidays are real
and H004's caveat was legitimate. But the clean window still rejects decisively.
**Holidays were aggravating a failure, not causing one.**

Against seventy weeks the synthetic weights could no longer fit exactly, landing
at a loss of 2.67 on 31 donors. They remain the best rule at both holdouts and
still reject. H004's perfect in-sample fit was degeneracy, not skill.

**The spillover feed cannot measure diversion, and the reason is measurement.**
[H007](docs/hypotheses/H007-secondary-feed-diversion.md) put the question to the
secondary DOT highway feed (`i4gi-tjb9`), which carries the nine toll-exempt
in-zone links — FDR Drive, 12th/11th Ave, West St, the Brooklyn Battery Tunnel
approaches — that displaced traffic would use. Three of the nine produce no
usable speed after tolling began. One has never emitted a positive reading in
41 months; the two 12th Avenue links report at full availability through March
2024 and go permanently dark from May 2024, eight months before the toll
existed. The treated group is eight contributing links before and six after,
and the three lost are the entire West Side Highway arm.

The pre-registered availability gate measures that as a **−21.2 percentage
point** differential change in usable-hour availability against a 5-point bar,
in every hour-of-week cut. Pre-trends also reject (χ² = 86.0 on 11 monthly
leads, p = 1e-13) and the Rambachan–Roth breakdown value is 0.000 to 0.034, so
all three refutation conditions fire — but the availability gate is the one the
verdict rests on, because it is a count of hours rather than an asymptotic
argument about nine treated clusters.

The estimate, which is not quotable: **+0.354 mph** on all hours, positive where
diversion predicts negative, randomization p = 0.804 on 500 draws reassigning
nine control links. The design's 80%-power minimum detectable effect is 4.85
mph. Even with clean diagnostics it could not have seen a diversion effect the
size of the in-zone association above.

This is a different kind of failure from the four above. Those are
identification failures — the comparison cannot separate the effect from
pre-existing drift. This one is instrumentation: sensors stopped reporting on
the roads the question is about, for reasons that have nothing to do with the
toll. What would fix it is a feed with working sensors on that corridor, not a
better control group.

**The mechanism checks cannot be run on the obvious source.** The study has
always listed MTA entry counts as the way to corroborate the mechanism: if the
toll worked, fewer vehicles entered the zone, and that should be visible
directly rather than inferred from speed. The MTA publishes exactly that, as
hourly vehicle entries by detection point and vehicle class
([`t6yz-b64h`](https://data.ny.gov/d/t6yz-b64h), NYC Open Data on data.ny.gov).
Its title is the problem: *Congestion Relief Zone Vehicle Entries: **Beginning
2025***. The series starts on 2025-01-05 and runs to 2026-09-05, checked
2026-09-13.

That is the tolling date. There is no pre-treatment period, because the
detection infrastructure that produces the counts was installed to operate the
toll. The feed can describe how many vehicles entered after tolling and how that
varies by hour, class and entry point, and it cannot support a before-and-after
comparison of any kind, because the "before" was never measured. No estimator
recovers a counterfactual that was never instrumented. This is a structural
limit of the source rather than a gap that a longer wait fills.

**But the same source answers a different question, and this one does not need
parallel trends.** The toll is not a single price. It is higher in a peak window
and discounted overnight, and the switch happens at a fixed clock time — 05:00
and 21:00 on weekdays, 09:00 and 21:00 at weekends, derived from the feed's own
`time_period` rather than assumed. That is a price discontinuity *within* the
post-period, so the counterfactual is the minutes on the other side of it, and
the assumption that defeated H001 through H006 is not required.

[H008](docs/hypotheses/H008-toll-timing-bunching.md) and
[H009](docs/hypotheses/H009-toll-timing-exempt-control.md) test it. **Neither
cleared its own pre-registered bar, and the reasons are recorded in full**; what
follows is reported as strong suggestive evidence, not as a positive finding.

The sharpest result comes from a control the speed study never had.
`excluded_roadway_entries` counts vehicles on the toll-exempt roadways — the
FDR, the West Side Highway, the Carey Tunnel — crossing the same detection
points, on the same sensors, in the same ten-minute blocks. They are never
charged, so no price changes for them. **At 05:00, as the peak rate begins,
tolled entries fall 69 log points while exempt entries rise 7**, a difference of
−0.759 (95% CI −0.795 to −0.723), consistent at all four points that record
both. No clock, sensor artefact or curvature explains that, because each would
move both series together.

At 21:00 both rise, and the design separates a shared evening rhythm of 5.6 log
points from a price-attributable difference of **+7.1** (CI 4.8 to 9.4). Both
results hold across 2025 and 2026.

The response is confined to the vehicles with discretion over departure time.
Cars and motorcycles carry all of it; single-unit trucks, multi-unit trucks,
taxis and buses are flat or wrong-signed. Taxis pay a per-trip surcharge and
drive to a passenger's schedule, freight runs to contracted windows, buses to a
timetable. **That pattern was predicted backwards** — the record expected trucks
to respond hardest — and is the most economically legible part of the result.

Why neither record passed: H008 compared its estimate to a *maximum* over
twenty-one placebo boundaries, a set contaminated by the morning ramp where
entries rise fivefold within the hour; H009 required its control series to show
no *significant* movement, which 609 days and 125M entries can never deliver.
Both are gates built on the wrong scale, drafted by the same author within an
hour, and that pattern should discount the pre-registration value of both.
Deliberately not repaired by a third attempt: rewriting the criterion would move
the label and not the estimate.

**What this does not show.** That the toll reduced congestion, reduced total
entries, or changed speeds. Retiming an entry is not avoiding one, and nothing
here bears on the speed finding above.

TLC trip records remain the only untried source with a genuine pre-period — the
per-year archives on NYC Open Data reach back to at least 2014. Ingesting them
has not been attempted and would need its own registered hypothesis. The honest
note is that the current trip records are distributed as monthly files outside
the Socrata endpoints this project already uses; that exact source has not been
verified here and should be confirmed rather than assumed.

Every hypothesis run against this study, including those that failed, is in the
[hypothesis register](docs/hypotheses/REGISTER.md), each with its prediction
fixed before the result existed.

## Robustness

The [12-specification comparison](outputs/tables/robustness_comparison.csv)
covers control geography, alternative windows, a common link roster, transition
exclusion, probe-depth and extreme-speed filters, an hourly mean outcome, two
placebo dates, and the four 11th Avenue links as a treatment sensitivity. Ten of
the twelve hold the October 2024 – April 2025 comparison window fixed so they
vary one thing at a time; `all_available` is the full-archive fit reported above.

Non-placebo coefficients stay positive, from +0.48 to +1.05 mph, and their
magnitude is sensitive to the control pool above all. Restricting controls to
Manhattan more than halves the estimate, to +0.48 mph and barely distinguishable
from zero (p = 0.049), while outer-borough controls give +0.88. That spread is
itself part of the identification problem: the answer depends on which streets
are chosen for comparison.

The two placebo dates, using only pre-tolling observations, do not reject zero —
2024-11-17 gives +0.15 mph (p = 0.46) and 2024-12-01 gives −0.11 mph (p = 0.59).
Weather interactions move the all-hours coefficient from 1.048 to 1.041, under
1%. The D3 sensitivity that reassigns the four 11th Avenue links to treated
gives +0.85 against the +0.85 baseline on the same window, so that open decision
barely moves the number. None of this repairs the rejected leads: a
specification can be stable and still be measuring the wrong thing.

The pattern across all of it is consistent. **The point estimate is robust and
its causal interpretation is not.** Those are different claims, and only the
first is supported.

## Limitations

- **Coverage is no longer a limitation.** All 44 target months are held and
  verified, 2023-01 to 2026-08: the full 24-month pre-period the frozen design
  asks for, and 20 post-treatment months. This entry is kept because the
  identification failure was once attributed to short coverage, and completing
  the archive did not repair it.
- **Rule B's donor count is thin.** H006's best control set retains 31 donors
  against a pre-registered minimum of 30, with the top five weights carrying 46%
  of the mass. It clears the bar as written, but its clustered inference should
  be read as thin, and the threshold would have been worth setting higher.
- **Endpoint pooling.** Event-study bins beyond 12 weeks either side pool more
  distant weeks. The diagnostics record which bins are genuine weekly estimates.
- **No units where diversion would show.** No control link lies within 500 m of
  the boundary; the nearest is about 808 m. The spillover question is
  unanswerable on this roster rather than answered in the negative.
- **The secondary feed stops measuring the exempt roads.** H007: three of the
  nine toll-exempt in-zone links yield no usable speed after tolling, the break
  landing in May 2024. Usable-hour availability diverges by 21.2 points against
  a 5-point bar. Its committed diagnostic table
  `outputs/tables/spillover_secondary_monthly.csv` is superseded — it averages
  8.8M zero-speed **outages** in as 0 mph, so its speed levels are biased toward
  zero. Use `data/processed/secondary_hourly_panel.parquet` instead. The primary
  panel is unaffected: zero-speed readings are at most 0.014% of any
  `treatment_group × post` cell there.
- **Treatment classification.** D3 remains open. The blanket 11th Avenue
  exemption probably misclassifies four local-street segments, though the
  sensitivity moves the coefficient only slightly.
- **What the outcome is.** Hourly median speed on selected links, weighting a
  quiet link the same as a heavy corridor. Not network congestion, not volume,
  not door-to-door travel time, not welfare.
- **No before-and-after on entry counts.** The MTA's vehicle-entry series begins
  on the tolling date itself, so it cannot say whether the toll reduced entries.
  H008 and H009 use its internal price variation instead, which answers a
  narrower question — timing, not volume. TLC trip records do have a pre-period
  and have not been ingested.
- **The timing result did not clear its own bar, twice.** H008's placebo set was
  contaminated by the morning ramp and summarised by a maximum; H009 required a
  control series to show no significant movement, which its sample size makes
  impossible. The underlying estimates are stable and precise, but two
  consecutive flawed criteria by the same author should discount how much the
  pre-registration is worth on this thread specifically.

## Recommendation

**Report this as a documented failure to identify, and do not soften it.** The
positive coefficients must not be used to claim the toll improved speeds, and
the absent spillover estimate must not be used to claim no diversion occurred.
A design that cannot separate an effect from pre-existing drift tells you
nothing about that effect's sign or size.

This is still a usable result. "Here is what the available data can and cannot
support, and here is the evidence for both" is a more honest deliverable than a
confident number resting on an assumption the data reject.

The live test has now run. H006 was the cleanest remaining shot at a usable
comparison group and it failed, on a holdout with no holiday confound and a
seventy-week matching window. The conclusion above is the finding.

**Stop searching for a control set that passes.** Every further attempt is
another draw against the same fixed data, and the register would have to carry
the count. The spillover check has now run, on the one feed that covers the
exempt routes, and it is reported above.

**The productive direction is a different question on different data, not a
better specification on this one.** The MTA entry counts cannot say whether the
toll reduced entries, because they begin on the tolling date — but their
internal peak/overnight price variation supports a design that needs no parallel
trends, and H008 and H009 show it detects a large, precisely estimated
behavioural response. That is where a usable positive finding is most likely to
come from. TLC trip records are the only untried source with a genuine
pre-period, and need their own registered hypothesis before anyone starts.

What could still change the answer is different data, not a different
specification: links nearer the cordon than the current 808 m nearest control,
an outcome other than link speed, or — for the spillover question specifically —
working speed sensors on the 11th/12th Avenue corridor across the toll date.
None of the three is available in what these feeds provide.

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
was retained for the spillover/diversion analysis, since those exempt roads are
exactly where displaced traffic would go. Full reasoning in the 2026-09-08
decision record in `docs/methodology.md`.

H007 has now used it, and it does not deliver. 42 months are held, 2023-01 to
2026-07 with 2026-06 missing, and 42.2M readings — a longer post-period than the
primary archive has. But 21.6% of those readings are outages coded `speed = 0`
with `travel_time = 0` and `status = -101`, their rate peaking overnight rather
than at rush hour, and on the exempt in-zone links that rate climbs from 16% in
2023 to 49% in 2026 while the controls hold flat. Treat zeros as missing, never
as 0 mph, and start from `data/processed/secondary_hourly_panel.parquet` rather
than the superseded `spillover_diagnostics.py` table.

**Mechanism — MTA Congestion Relief Zone Vehicle Entries** (`t6yz-b64h`,
data.ny.gov). Hourly entries by detection point and vehicle class, 2025-01-05
onward. Held for completeness only: it starts on the tolling date, so it carries
no pre-treatment period and cannot support a before-and-after comparison. Not
ingested.

Schema and conventions in `docs/data_dictionary.md`; open questions in
`docs/decision_register.md`; further sources in `docs/future_data_sources.md`.

## Project structure

```
data/         raw/ (immutable) · interim/ (typed staging) · processed/ (panels)
docs/         brief · data dictionary · methodology · reproducibility · data-quality report
sql/          DuckDB: 01 staging · 02 quality checks · 03 hourly panel
src/
  data/       download · inspect_schema · build_staging · build_panel · build_secondary_panel
  analysis/   descriptive · did · event_study · robustness · honest_did · placebo_space ·
              h007_diversion (spillover) · provenance
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
