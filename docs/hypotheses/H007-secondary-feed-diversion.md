# H007 — Can the secondary highway feed identify diversion onto toll-exempt in-zone routes?

| | |
|---|---|
| **Status** | answered — **refutes** |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5, session picking up `docs/agent_handoff.md` |
| **Answered by** | Claude Opus 5, fresh session, 2026-09-13 |
| **Supersedes / superseded by** | none |

## Question

The primary E-ZPass panel contains no units where diversion would show: the five
`boundary` links straddle 60th Street, and the nearest control link is about
808 m from the cordon. The secondary DOT Traffic Speeds feed (`i4gi-tjb9`) does
contain them — nine links on the FDR Drive, the West Side Highway / 12th Avenue
and West Street, all inside the zone and all exempt from the toll. Those are the
roads a driver uses to cross Manhattan without paying.

Can that feed identify whether traffic diverted onto them after 2025-01-05?

## Why it matters

The README currently reports the spillover question as unanswerable on the
primary roster rather than answered in the negative, and Phase 10 has never run.
Either answer changes the writeup.

If the feed identifies diversion, the study gains a mechanism section with an
estimate, and the spillover limitation narrows from "no units" to "no units in
the primary feed, but the secondary feed covers the exempt routes and says X".

If it does not, the limitation is confirmed on the one source that was supposed
to rescue it, and the study reports a second documented failure to identify —
this time for a reason that may be about measurement rather than about parallel
trends. That distinction is worth having in writing, because it says different
things about what better data would fix.

## Prediction

*Frozen once results exist.*

I expect this to fail, for two reasons, and I hold the second more strongly than
the first.

The weaker reason is the pattern of the study: the joint pre-trend test has
rejected in every sample and on every control set tried so far, and highways in
other boroughs are not obviously a better comparison for the FDR than
Manhattan surface streets were for each other. I expect the pre-trend test to
reject here too, at perhaps 60–70% confidence.

The stronger reason is measurement. Exploratory inspection of the raw feed
before writing this record (see Notes — this ordering matters and is disclosed
deliberately) shows that readings coded `speed = 0` carry `travel_time = 0` and
`status = -101`, and that their frequency peaks overnight rather than at rush
hour. They are outages, not standstills. Their share on the nine exempt in-zone
links runs 16% in 2023, 33% in 2024, 42% in 2025 and 50% in 2026, while the
control links hold flat near 17–20% throughout. If that holds up under the
per-hour, per-link accounting this analysis will do, the treated group's
observation set is being selected differently over time from the control group's,
and no fixed-effects estimator repairs that. I put roughly 85% on the
availability criterion below being breached.

I do not have a prediction for the sign or size of the ATT and am not
formulating one, because I expect the diagnostics to make it unreadable. If
forced: diversion onto exempt roads implies *slower* speeds there, so a negative
coefficient, but I would not bet on recovering it.

What would genuinely surprise me: flat pre-trends on this feed. Highway links
are more homogeneous than surface streets, and it is possible that the
comparison works better here than anything tried on the primary panel. That is
the case worth being open to, and it is why this is worth running rather than
asserting.

## Method

**Panel.** Build `data/processed/secondary_hourly_panel.parquet` with the same
schema the primary panel uses, so `src/analysis/did.py`,
`src/analysis/event_study.py`, `src/analysis/placebo_space.py` and
`src/analysis/honest_did.py` run against it unmodified. One row per
link × hour.

**Window.** 2023-01-01 through 2026-05-31. The feed holds 2023-01 … 2026-07 but
**2026-06 is missing**, so the window stops at 2026-05 to stay contiguous;
2026-07 is dropped rather than leaving a hole mid-panel. That gives 24
pre-treatment months and 17 post-treatment months, against the primary panel's
23 and 4.

**Outcome.** Hourly median of `speed`, in mph, over readings with `speed > 0`.
Zero-speed readings are dropped as missing, not averaged in as 0 mph. They carry
`travel_time = 0` and `status = -101`, and `AGENTS.md` already requires missing
numeric values to be `NaN` rather than `0`. An hour with no positive reading is
absent from the panel, not zero.

**Groups**, from `src.data.geo.classify_segment` on the decoded
`encoded_poly_line` (precision 5), never on `link_name`:

- **Treated** — the 9 `exempt_in_zone` links: FDR N/S between Catherine Slip and
  25th St, FDR S Catherine Slip to the Brooklyn Bridge, 12th Ave N 40th–57th,
  12th Ave S 57th–45th, 11th Ave s Gansevoort to West St, West St S Spring St to
  the BBT portal, and the two BBT Manhattan portal/toll-plaza links.
- **Control** — the 116 `control` links, all outside Manhattan.
- **Held out of both** — the 6 `boundary` links (they cross the 60th St line),
  the 5 `crossing` links (Lincoln Tunnel tubes and the Brooklyn Bridge / FDR
  connector: these measure the queue to enter, a different behaviour), and
  link_id `4616339` and `4616340`. Those last two are labelled
  `borough = Manhattan` but their geometry lies mostly in Brooklyn; they are
  approaches to the Brooklyn and Manhattan Bridges. `classify_segment` calls
  them `treated` because it trusts the borough label — see Notes. They are
  neither clean diversion receivers nor clean controls, so they are excluded and
  the exclusion is reported.

**Estimator.** Two-way fixed effects on link and hour-of-sample, as
`src/analysis/did.py` implements it, with `treated × post` the coefficient of
interest. Samples: all, weekday peak, weekday off-peak, weekend, matching the
primary cuts.

**Inference.** Randomization inference is **primary**, not a supplement. Nine
treated clusters is far below where cluster-robust asymptotics are trustworthy,
and H001 already measured those standard errors running up to 1.5× too tight on
a panel with 333 clusters. Reassign treatment at random among control links,
9 at a time, 500 draws, and report the share of draws producing an effect at
least as extreme. Cluster-robust standard errors are reported alongside, clearly
labelled as the weaker of the two.

**Diagnostics**, in this order, because an earlier one failing makes the later
ones unreadable:

1. **Availability.** Per group per month, the share of link-hours with at least
   one positive reading, out of hours where the link appears in the feed at all;
   and the count of links reporting. Compare the pre-mean to the post-mean for
   each group and take the difference in differences of those shares. Report the
   link roster entering and leaving the feed.
2. **Event study** by month, ±12 months around 2025-01-05, then the joint Wald
   test that all pre-treatment leads are zero, using the full cluster covariance
   (`event_study.pretrend_test`, method `cluster_robust_wald_chi2`). The
   corrected test, not the superseded sum-of-squared-t version.
3. **Rambachan & Roth (2023)** breakdown value via `src/analysis/honest_did.py`,
   at the ±12-month horizon.

**Outputs.** `outputs/tables/H007_*.csv` and `outputs/figures/H007_*.png`, per
the namespacing rule. Both analysis modules take `--out-prefix`.

## Acceptance criteria

*Frozen once results exist.*

Evaluated on the **all-hours** sample, with the other three cuts reported.

**Supports** — the feed identifies diversion. All three must hold:

1. The differential change in valid-hour availability between treated and
   control, pre-period mean to post-period mean, is **under 5 percentage
   points** in absolute value.
2. The joint pre-trend test **fails to reject** at the 5% level.
3. The randomization-inference p-value for the observed ATT is **below 0.05**.

If all three hold, the sign of the ATT is the finding: negative means measured
diversion onto the exempt routes, positive means the opposite.

**Refutes** — the feed does not identify diversion. Any one of:

1. The differential availability change is **5 percentage points or more**. The
   groups' observation sets are moving apart; the comparison is between
   different samples of hours, not different roads.
2. The joint pre-trend test **rejects** at the 5% level.
3. The Rambachan–Roth breakdown value is **below 0.5**, meaning the estimate
   survives only violations less than half the size of those already visible
   before the toll.

**Uninformative** — availability is parallel and the pre-trend test passes, but
the randomization-inference p-value is at or above 0.05 and the null
distribution is wide enough that a diversion effect of the size the toll
plausibly produced would not have been detected. This is the honest third
outcome and it must be reported as such: nine treated links is a small design,
and failing to find an effect in it is not evidence that none occurred. If this
is the verdict, report the minimum detectable effect alongside it.

The 5-percentage-point availability bar is set on the reasoning that the primary
study's headline effect was 1.17 mph on a pre-treatment treated mean near
10 mph, about 12%. A differential shift of 5% of observations between hours of
the day moves a group's mean hourly speed by more than that, because the spread
between the fastest and slowest hours on these links is far wider than 12%. A
selection effect able to manufacture the entire effect being estimated
disqualifies the design.

## Data required

All on hand. Nothing is blocked on the backfill.

- `data/raw/dot_speeds/*.parquet` — 42 monthly parts, 42.2M rows, 2023-01 …
  2026-07 with 2026-06 absent. 138 distinct links.
- `src/data/geo.py` — classifier, unchanged.
- No new ingestion, no network, no cost.

The primary E-ZPass archive is **not** required. This analysis does not touch it
and does not wait for 2023-01 or the post-period extension.

## Result

Answered 2026-09-13. Panel built by `python -m src.data.build_secondary_panel`,
analysis by `python -m src.analysis.h007_diversion`.

**The panel.** 42,216,965 raw rows across 42 monthly parts reduce to 41,179,694
readings in the 2023-01-01 … 2026-05-31 window
([H007_row_accounting.csv](../../outputs/tables/H007_row_accounting.csv)):
1,031,143 rows lie outside it — all of 2026-07, which the missing 2026-06
strands — and 6,128 fall in the ambiguous DST fall-back hour. Nothing else
drops. No row carries a null key, and there is not a single duplicate
`(link_id, ts)` pair in 42.2M rows, so the inherited "keep the highest `id`"
convention never binds on this feed. Of the readings kept, 32,359,570 have a
positive speed and 8,820,124 are zero-speed outages, dropped as missing rather
than averaged in as 0 mph. That gives 3,445,716 link-hours present in the feed,
of which 2,786,621 carry a usable hourly median. Groups are as the Method
specifies: 9 treated, 116 control, 6 boundary and 5 crossing held out, plus
link_ids `4616339` and `4616340` held out by id.

**The zero-speed diagnosis replicates**, measured independently on all 42.2M
rows. 9,129,474 readings carry `speed = 0`; 9,128,628 of them also carry
`travel_time = 0`; and all 9,129,474 carry `status = -101`. The hourly profile
inverts the congestion pattern, as the Notes describe. Over the full 2023-01 …
2026-05 window the zero rate on the nine treated links peaks at 47.8% at 03:00
against 28.8–29.4% through the afternoon, and feed-wide at 25.9% against about
20.4%; the 56% and 38% quoted under Notes are the same statistic on 2025 alone,
which is what the exploratory query covered. The yearly divergence reproduces
exactly — treated 16.0%, 32.8%, 42.4%, 48.7% across 2023–2026 against 21.3%,
19.2%, 20.5%, 23.4% elsewhere. One qualification on the third signature:
`status = -101` also accompanies 2,180,196 readings with a positive speed, so
the status flag alone does not identify an outage. `speed = 0` does.

### 1. Availability — the gate, and it fails first

Evaluated on all hours, with the other three cuts alongside
([H007_availability_gate.csv](../../outputs/tables/H007_availability_gate.csv)):

| Sample | Treated pre → post | Control pre → post | Treated change | Control change | **Differential** |
|---|---|---|---:|---:|---:|
| **all** | 78.6% → 59.2% | 82.9% → 84.6% | −19.40 pp | +1.76 pp | **−21.16 pp** |
| weekday peak | 80.2% → 60.8% | 82.9% → 84.9% | −19.40 pp | +1.94 pp | −21.34 pp |
| weekday off-peak | 77.3% → 58.0% | 82.8% → 84.6% | −19.40 pp | +1.72 pp | −21.11 pp |
| weekend | 79.8% → 60.4% | 82.9% → 84.6% | −19.41 pp | +1.72 pp | −21.14 pp |

The bar is 5 percentage points. The differential is more than four times it, in
every cut, and weighting months equally instead of by link-hours moves it to
−21.88 pp rather than rescuing it.

**Three of the nine treated links produce no usable speed in the post period**
([H007_availability_by_link.csv](../../outputs/tables/H007_availability_by_link.csv)).
`4616325`, 11th Ave southbound Gansevoort to West St at Spring St, emits nothing
but zero-speed readings for all 41 months and has never contributed an
observation. `4616323` (12th Ave S, 57th–45th) and `4616338` (12th Ave N,
40th–57th) report at 100% availability through 2024-03, fall to 71% in 2024-04,
and go to exactly zero from 2024-05 onward, permanently. The treated group is
eight contributing links before the toll and six after, and the three that leave
are the entire 11th/12th Avenue arm of the design — the West Side Highway
corridor, which is half the reason this feed was thought to answer the question.

Two further consequences. A treated link with no post-period observations has no
within-link variation in `treated × post`, so it contributes nothing to the ATT
at all: the estimate identifies off **six** links, not nine. And the two links
that die sat at opposite ends of the speed range, 6.45 mph and 33.35 mph
pre-treatment, so losing them is not a neutral thinning of the sample.

**The break predates the toll by eight months.** It lands in May 2024, event
month −8. This is not the toll changing what the sensors report; it is the
sensor attrition `AGENTS.md` records for autumn 2024, arriving early on this
corridor. The pre and post periods are measured on different subsets of the
treated roads for reasons that have nothing to do with the intervention.

The control side is unbalanced too, and in the direction the record anticipated
— 115 control links present in 2023 falling to 102–103 from 2024 — but it does
not move the same way
([H007_contributing_links.csv](../../outputs/tables/H007_contributing_links.csv)):

| Group | Pre: present / contributing | Post: present / contributing |
|---|---:|---:|
| treated | 9 / 8 | 9 / **6** |
| control | 116 / 94 | 103 / 96 |

The control group loses thirteen links from the feed and gains two contributing
ones; the treated group loses none from the feed and a quarter of its
contributors. Fifteen control links never contribute at all, five of them
publishing for 22,000 to 28,000 hours without a single positive reading.
Control availability moves by under 2 points across the toll date, so the
differential is almost entirely the treated side.

### 2. Event study and the joint pre-trend test

Monthly bins, ±12 months, reference k = −1 (December 2024), joint Wald test on
the full link-cluster covariance
([H007_pretrend.csv](../../outputs/tables/H007_pretrend.csv)):

| Sample | χ² (11 dof) | p | Verdict |
|---|---:|---:|---|
| **all** | 86.02 | 1.0e-13 | FAIL |
| weekday peak | 67.94 | 3.0e-10 | FAIL |
| weekday off-peak | 73.66 | 2.5e-11 | FAIL |
| weekend | 45.99 | 3.3e-06 | FAIL |

Only **one** of the eleven leads is individually significant at 5% (k = −9,
−1.96 mph, p = 0.048), and the joint test still rejects at 1e-13. That is the
corrected test earning its keep: the leads share a reference period and are
strongly correlated, and the superseded sum of squared individual t statistics
would have read this as nearly clean. The two most negative leads, k = −9 and
k = −8, are April and May 2024 — the two months in which the 12th Avenue links
degrade and die. That is a coincidence in timing, stated as such; this design
cannot separate the two.

The endpoint bins pool, as `build_dummies` does: k = −12 carries 13 months
(−24 … −12) and k = +12 carries 5 (12 … 16). Both are flagged in
[H007_event_study_all.csv](../../outputs/tables/H007_event_study_all.csv).

### 3. Rambachan–Roth breakdown value

At the ±12-month horizon
([H007_honest_did_h12.csv](../../outputs/tables/H007_honest_did_h12.csv)):

| Sample | Relative magnitude | Smoothness |
|---|---:|---:|
| **all** | 0.024 | 0.000 |
| weekday peak | 0.000 | 0.005 |
| weekday off-peak | 0.034 | 0.000 |
| weekend | 0.000 | 0.000 |

Every value is below 0.5, and three of the four are zero — the robust confidence
set covers zero before any violation is allowed at all. These are lower than
anything H002 or H005 found on the primary panel.

### The estimate, and the inference on it

Two-way fixed effects on link and hour-of-sample, 109 clusters
([H007_did_estimates.csv](../../outputs/tables/H007_did_estimates.csv),
[H007_randomization.csv](../../outputs/tables/H007_randomization.csv)):

| Sample | ATT (mph) | Clustered SE | Clustered 95% CI | **RI p** | Clustered p | RI null SD ÷ SE |
|---|---:|---:|---|---:|---:|---:|
| **all** | +0.354 | 1.457 | [−2.53, +3.24] | **0.804** | 0.808 | 1.18 |
| weekday peak | +1.137 | 1.392 | [−1.62, +3.90] | **0.431** | 0.416 | 1.15 |
| weekday off-peak | +0.524 | 1.416 | [−2.28, +3.33] | **0.745** | 0.712 | 1.26 |
| weekend | −0.425 | 1.619 | [−3.63, +2.78] | **0.802** | 0.794 | 1.10 |

Randomization inference is 500 draws labelling nine links of the 101-link
contributing control pool treated at the real tolling date. The randomization
p-values are the primary ones; the clustered p-values sit beside them and agree,
which is the only comfortable thing here. The clustered standard errors are
nonetheless 10–26% too tight against the null that chance reassignment actually
produces, consistent with H001's finding on the primary panel.

Nothing in that table is a diversion estimate. Diversion onto the exempt roads
implies *slower* speeds there, a negative coefficient; three of the four cuts
are positive, all four are within a standard error of zero, and the design that
produced them has already failed its first gate.

**What this design could have detected.** From the randomization null, any
|ATT| above **3.41 mph** would have scored p ≤ 0.05 on all hours, and the
effect needed for 80% power is **4.85 mph** — 17% of the 28.1 mph
pre-treatment treated mean. The other cuts need 4.52 to 5.02 mph. Even with
clean diagnostics, this design was only ever able to see very large diversion.

One number that must not be quoted on its own: the event study's post-treatment
coefficients average **+1.59 mph**, and seven of the thirteen are individually
significant at 5%. That is a different estimand from the +0.354 mph ATT — it
clips at +12 months and weights each month bin equally, where the ATT covers all
17 post months and is observation-weighted — and it is the quantity the
Rambachan–Roth bounds are built on. Both are unusable for the same reason.

### Supersession

This replaces `outputs/tables/spillover_secondary_monthly.csv`, which
`src/analysis/spillover_diagnostics.py` produces by filtering only
`speed_mph IS NOT NULL` and therefore averaging 8.8M zero-speed outages in as
0 mph. Any secondary-feed speed level taken from that file is biased toward
zero by roughly the local outage rate and should not be quoted.

## Verdict

**Refutes.** All three refutation conditions fire, on all four samples. Under
the criteria as written, the secondary feed cannot identify diversion onto the
toll-exempt in-zone routes.

**The gate that failed first is availability, and it is the one that settles
it.** The differential change in usable-hour availability is −21.16 pp against
a 5 pp bar. Criteria 2 and 3 fire too, but both are computed from a
cluster-robust covariance matrix resting on nine treated clusters — precisely
the regime in which this record made randomization inference primary because
such asymptotics cannot be trusted. A Wald test on eleven restrictions in that
regime over-rejects, so χ² = 86 is directional rather than exact, and the
Rambachan–Roth bounds consume the same matrix. Criterion 1 needs no asymptotics
whatsoever: it is a count of hours in which a sensor did or did not report.
**Read the verdict off criterion 1.** The other two are consistent with it and
add nothing it does not already establish.

**This is a measurement failure, not a parallel-trends failure**, and the
distinction is the point of having run this. The treated group loses a third of
its links — the whole West Side Highway arm — between the pre and post periods,
starting in May 2024, eight months before the toll existed. No fixed-effects
estimator repairs a comparison whose two periods are measured on different
roads. What better data would fix here is instrumentation: working speed sensors
on the 11th/12th Avenue corridor across the toll date. It is not a control-group
problem and would not be solved by a better comparison pool, a different
estimator, or more draws.

**The estimator and the inference are separate claims, and both are weak.** The
point estimate is +0.354 mph (all hours), positive where diversion predicts
negative, and 1.26% of the pre-treatment treated mean. Its randomization
p-value is 0.804. Its clustered standard error is 18% tighter than the spread
chance reassignment produces, so even the unimpressive clustered interval
overstates what is known. And the design's 80%-power minimum detectable effect
is 4.85 mph — had every diagnostic passed, a diversion effect of the size the
primary study's headline suggests (1.17 mph in-zone, 12%) would have been
invisible here. Six contributing treated links on three roadways cannot support
a precise estimate of anything.

**The prediction was right, and right for the reason it gave.** The record put
roughly 85% on the availability criterion being breached and 60–70% on the
pre-trend test rejecting; both happened, and the availability breach is the
decisive one. The thing that would have been surprising — flat pre-trends on
highway links — did not occur.

**On the criteria themselves.** They were well chosen and are not superseded.
Criterion 1 did the work and its 5-point bar was, if anything, generous: the
observed breach is more than four times it and any bar below about 20 points
returns the same answer, as the record's own Notes predicted. The one thing a
future record in this position should fix is the tension named above — two of
three refutation conditions built on cluster-robust asymptotics the same record
declares untrustworthy at this cluster count. It did not change this verdict,
because criterion 1 is independent of it and fires on its own, so there is
nothing here to supersede.

**What this does not settle.** It does not establish that diversion did or did
not occur; it establishes that this feed, on these nine links, cannot measure
it. It says nothing about the primary finding — the 1.17 mph in-zone
association and its failed identification are untouched. And even had it
succeeded, nine links on three roadways are not a random sample of anything:
the result would have been a statement about the FDR, the West Side Highway and
West Street, not about diversion in general.

**The obvious next specification is a new hypothesis, not a footnote to this
one.** Restricting the treated group to the six links that report throughout
would remove the compositional break, and is exactly the kind of move this
protocol exists to make visible: it must be registered with its prediction and
criteria before it runs. Two things a reader should weigh before proposing it.
The six survivors exclude the West Side Highway corridor, which is a large part
of what made the question worth asking. And the control side loses fifteen links
that never contribute at all, so a restricted design has to decide what to do
about them as well.

**What the study now reports on spillover.** The limitation moves from "no units
where diversion would show in the primary feed" to a second, independent
documented failure to identify — this one for a measurement reason rather than
an identification one. The README's existing instruction stands and now has a
second leg: the absent spillover estimate must not be read as evidence that no
diversion occurred.

## Notes

**Disclosure on ordering.** The zero-speed diagnosis described under Prediction
was done *before* this record was written, as exploratory work to establish
whether the analysis was feasible at all. It is disclosed rather than hidden,
because the 5-percentage-point availability criterion was written by someone who
already knew the raw yearly zero rates diverged by roughly 25 points. The
criterion is not tuned to that number — any threshold below about 20 points
returns the same verdict — but a reader is entitled to know the order things
happened in. No difference-in-differences, event study, or any estimate of the
ATT has been run on this feed. The prediction above was written with no estimate
in hand.

**Why zeros are outages.** Three independent signatures, measured on the full
42.2M rows: `travel_time` is 0 for 9,128,628 of 9,129,474 zero-speed readings
(a genuine standstill has a large travel time, not a zero one); `status` is
`-101` on every one of them; and the zero rate peaks overnight, 56% at 03:00
against 38% through the afternoon, which is the inverse of the congestion
pattern. The existing `src/analysis/spillover_diagnostics.py` filters only
`speed_mph IS NOT NULL` and therefore averages these in as 0 mph. Its committed
output `outputs/tables/spillover_secondary_monthly.csv` is contaminated by this
and should be treated as superseded by whatever this analysis produces.

**The primary panel is not affected.** Checked directly: zero-speed readings are
at most 0.014% of observations in any `treatment_group × post` cell of
`data/processed/hourly_panel.parquet`. This is a secondary-feed problem and
nothing in the README's headline finding rests on it.

**`classify_segment` trusts the borough label.** When this record was written,
`geo.py` defined `_in_manhattan_envelope` — a Manhattan bounding box its
docstring called "the geometric backstop" — but nothing called it. That dead
code was removed on 2026-09-13 after the backstop was measured against this
feed, and the measurement is the reason the two BQE approaches are held out by
`link_id` above rather than left to the classifier.

The box could not have served as a backstop. Its southern edge has to reach
40.680 N to cover the Battery, which also covers downtown Brooklyn, so both
`4616339` and `4616340` lie entirely inside it and a check against it rejects
neither. Requiring every vertex to fall inside instead changed six other links,
each for the wrong reason: four carry corrupt vertices near longitude zero
(`4616324`, `4620343`, `4616332`, `4456511`), and the two Brooklyn-Battery
Tunnel links genuinely reach Brooklyn because the tunnel does. Two of those six
— `4456494` and `4456502` — are in the treated group above, and the check would
have moved them into the control group. The held-out list stands as written.

**Link roster is unstable.** `AGENTS.md` records that 25 sensors stopped
reporting in autumn 2024 and never returned. The control group here falls from
115 reporting links in 2023 to 102–103 from 2024 on. The panel is unbalanced and
must be treated as such; the availability diagnostic exists partly to measure
this. **Confirmed on running, and presence turned out to be only half of it.**
Of the 116 control links present pre-treatment, 94 contribute a usable speed;
of the 103 present post-treatment, 96 do. The treated side loses no links from
the feed at all and still falls from 8 contributors to 6.

**Independent verification, 2026-09-13, by the session that registered this
record.** The deciding number was recomputed from `data/raw/dot_speeds/*.parquet`
without going through `build_secondary_panel`, classifying links with
`classify_segment` and counting an hour as usable if any reading in it carried a
positive speed. That gives a differential availability change of **−21.11 pp**
against the panel's −21.16, the 0.05 gap being the DST-hour and duplicate
handling the direct query skips. The three dead treated links reproduce exactly,
including that `4616325` has no positive speed in either period, and so does the
break: 12th Avenue north and south both sit at 100% availability through
2024-03, 71% in 2024-04, and 0.0% in every month from 2024-05. Criterion 1 fails
on a direct count of the raw feed, independent of the panel build.

One correction to the Result's reading of the Prediction. It reports the
overnight zero-rate figures quoted there as "higher than what reproduces here",
but both are right and measure different windows: 56.2% at 03:00 against a 38.3%
afternoon mean is 2025 alone, which is what the exploratory query covered, while
47.5% against 28.6% is the full 2023-01 … 2026-05 window the analysis uses. The
signature that matters — the zero rate peaking overnight, inverting the
congestion pattern — holds on both. Nothing in the verdict turns on it. The
Result has been reworded to say so rather than to imply the Notes overstated
anything.

**No owner decision was adopted.** D3 concerns four northern 11th Avenue
segments on the *primary* E-Z Pass roster (`108104`, `116080`, `80108`,
`81116`). The one 11th Avenue link in this treated group, `4616325`, is the
southern Route 9A alignment from Gansevoort St to West St at Spring St, which
the MTA exempts and which D3 explicitly does not reach. It contributes no
observations in any case.

**Event time is monthly here, not weekly.** `event_study.build_dummies` reads
its bins from a column named `event_week`; `src/analysis/h007_diversion.py`
writes the monthly index into that column and relabels the output, keeping the
weekly index alongside. Forty-one months of data would otherwise put more than a
hundred restrictions on the joint pre-trend test. One consequence to hold on to:
month k = 0 is January 2025, whose first four days precede tolling, so the k = 0
bin carries four pre-toll days out of thirty-one. `post` on the panel itself is
correct to the day.

## References

Verified against this repository's own previously verified citation strings:

- MacKinnon, James G., and Matthew D. Webb (2020). “Randomization inference for
  difference-in-differences with few treated clusters.” *Journal of
  Econometrics* 218(2):435–450. https://doi.org/10.1016/j.jeconom.2020.04.024

Cited by author, year and venue, but **not** verified against the published
article in this session — this project has no network budget, and the repository
carries no full citation string for either to check against. Volume, issue and
page numbers are therefore omitted rather than guessed, and a reader spot-
checking should confirm them:

- Rambachan, Ashesh, and Jonathan Roth (2023). “A More Credible Approach to
  Parallel Trends.” *Review of Economic Studies*.
- Roth, Jonathan (2022). “Pretest with Caution: Event-Study Estimates after
  Testing for Parallel Trends.” *American Economic Review: Insights*.
