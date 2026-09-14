# H010 — Do drivers move onto toll-exempt roadways as the peak charge begins?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-14 |
| **Registered by** | Claude Opus 5, a session that did not write H008 or H009 and adjudicated them in [ADJUDICATION-timing.md](ADJUDICATION-timing.md) |
| **Answered by** | |
| **Supersedes / superseded by** | none. Claims a by-product flagged in [H009](H009-toll-timing-exempt-control.md) and claimed nowhere. |

## Question

At 05:00, as the peak toll rate begins, tolled entries collapse while entries on
the toll-exempt roadways beside them rise. H009 measured the rise as a control
and flagged it in passing as "the first direct evidence of route substitution
this project has obtained from any source", without testing it.

Is that rise route substitution — drivers taking a free road instead of paying —
and is it large enough, counted in vehicles, to be a substantive share of the
traffic the toll deters at that moment?

## Why it matters

The claim is already in the study's prose. `docs/decision_register.md` and
`docs/agent_handoff.md` both carry it as the project's first direct evidence of
diversion, and the README's spillover section currently says the opposite — that
diversion is unidentified on both available feeds. One of those has to change
whichever way this comes out.

If the exempt gain is a substantive share of the tolled loss, the study has a
diversion result from a source H007 could not use, on the exact roads H007's
sensors had stopped measuring, and the spillover section needs rewriting.

If the gain is a rounding error against the tolled loss, the flagged by-product
is withdrawn, the register and handoff lose a sentence each, and H009's exempt
series is vindicated as a clean control rather than a partly treated one — which
matters for how much weight the 05:00 difference can carry.

The question is also about *where deterred traffic goes*, which no hypothesis
here has asked. H007 asked whether the speed feed could see diversion and found
its sensors dark. This asks a different source a different question, in counts
rather than speeds.

## Prediction

*Frozen once results exist.*

**Disclosure, in full, because I have read H009's output.** I know the pooled
weekday exempt discontinuity at 05:00 is **+0.0701** and at 21:00 **+0.0555**. I
know the 05:00 split across the four dual-recording points: FDR Drive **+0.1129**,
Hugh L. Carey Tunnel **+0.1083**, Brooklyn Bridge **−0.0086**, West Side Highway
**−0.0652** — two of four negative. I know the exempt discontinuity at 05:00 is
+0.0830 in 2025 and +0.0477 in 2026. I know the tolled series falls 27.0% raw at
that boundary and that H009's fitted figure at the four dual points is −49.8%.

Two things follow. The criteria below are set on quantities I have **not** seen,
each marked. And the detection-point consistency of the exempt rise is
contaminated as a test, so it is registered as a reported quantity with no
threshold rather than dressed up as one.

**The count-based diversion share** *(not measured)*. Nothing in
`outputs/tables/` holds exempt entries as counts at these blocks, so the
absolute arithmetic is untouched. I expect the share to land between 0.05 and
0.25 and I hold that loosely, at about 60%. The reasoning is scale: a +7% move
on a smaller series cannot absorb a −27% move on a larger one, so whatever the
exempt rise is, it accounts for a minority of deterred entries. Where in that
range it falls is the question.

**The vehicle-class composition of the exempt surplus** *(not measured, and the
most informative test here)*. H008 established that the tolled response is
entirely cars and motorcycles, with trucks, taxis and buses flat or
wrong-signed. If the exempt surplus is the same drivers on a different road, it
must be concentrated in the same classes. A sensor artefact, a reporting
convention or a highway's own morning rhythm has no reason to respect vehicle
class. I hold at about 70% that the surplus is disproportionately cars and
motorcycles.

**Where the surplus sits in time** *(not measured)*. Substitution predicts the
exempt gain lands in the blocks immediately after 05:00, mirroring the tolled
deficit. A gain spread evenly across the hour after the boundary points at a
difference in the shape of the two morning ramps instead. I hold at about 65%
that it is concentrated in the first three blocks.

**The 21:00 mirror** *(measured in log points, and it runs against the simple
story)*. Substitution predicts exempt entries *fall* when the peak ends and the
tolled road gets cheap. The pooled exempt discontinuity at 21:00 is positive,
+0.0555, at three of four points. I have no prediction that reconciles this and
am not inventing one; the honest reading is either that the evening exempt
series is dominated by a shared rhythm the 05:00 series is not, or that the
05:00 rise is not substitution. Reported, not scored.

## Method

**Data.** `t6yz-b64h` on `data.ny.gov`, as H008 and H009, via
`src.analysis.h008_toll_timing._fetch`, cached under `data/raw/mta_crz/`. The
addition is `vehicle_class` in the grouping alongside `excluded_roadway_entries`.
Confirm that the feed populates `excluded_roadway_entries` at vehicle-class
grain rather than only in the roadway total; if it does not, say so and report
criterion 2 as untestable rather than working around it.

**Sample.** The four dual-recording detection groups H009 used — FDR Drive at
60th St, Brooklyn Bridge, Hugh L. Carey Tunnel, West Side Highway at 60th St —
weekdays only.

**Estimand, and it is deliberately not a log discontinuity.** The quantity is a
ratio of vehicle counts:

    f = S / D

where **D** is the tolled deficit and **S** the exempt surplus over the three
ten-minute blocks beginning 05:00, each measured against a counterfactual fitted
on the six blocks before the boundary and extrapolated across it.

Counts rather than log points, for a stated reason. A ratio of two percentage
changes on series of different size answers no question anyone asked, and the
substitution claim is about vehicles moving from one road to another. It has to
balance in vehicles.

**The counterfactual, frozen here.** A log-linear fit on the six pre-boundary
blocks per date and detection group, extrapolated to the three post blocks,
exponentiated back to counts. Deficit and surplus are the summed differences
between observed and counterfactual across dates and groups.

This estimator is the one the [adjudication](ADJUDICATION-timing.md) found
biased by curvature in this band, and the bias is not removed by taking a ratio.
So report **f under three counterfactuals**: the frozen log-linear one, a
flat-level counterfactual using the last pre-boundary block alone, and a
quadratic fit on the same six blocks. The flat-level version is the
model-free floor — it cannot manufacture a deficit out of a ramp, and it will
understate both D and S. If f moves by more than a factor of two across the
three, the ramp is driving the answer and that is the finding.

**Inference.** Block bootstrap over dates, 500 draws, resampling whole dates so
the two series stay paired within a date. Report the interval on f. Do not
report a p-value against zero; f is a share and the question is its size.

**Cuts.** By detection group; by vehicle class; by year. The 21:00 boundary is
computed the same way and reported descriptively.

**Outputs.** `outputs/tables/H010_*.csv`, `outputs/figures/H010_*.png`. Import
what you need from `h008_toll_timing` and `h009_exempt_control` into a module of
your own rather than repointing their paths, as H007 and H009 did.

## Acceptance criteria

*Frozen once results exist.*

Primary is **f at weekday 05:00**, pooled across the four dual-recording points,
under the frozen log-linear counterfactual.

**Supports** — deterred traffic moves onto the exempt roadways. Both:

1. **f ≥ 0.05 under the frozen counterfactual, and ≥ 0.02 under the model-free
   flat-level counterfactual**, with the bootstrap interval on the frozen
   estimate excluding 0.02. One deterred entry in twenty reappearing on a free
   road within twenty minutes is a substantive amount of diversion, and the
   second half stops a ramp artefact carrying the result on its own.
2. **The exempt surplus is disproportionately cars and motorcycles.** Their
   share of the surplus, divided by their share of exempt volume in the six
   pre-boundary blocks, is at least **1.10**.

**Refutes** — the exempt rise is not substitution. Any one of:

1. **f < 0.02 under the frozen counterfactual.** Whatever moves the exempt
   series, it is not absorbing a policy-relevant share of deterred entries.
2. **f is negative** under any of the three counterfactuals — the exempt series
   loses vehicles at 05:00 once counted rather than logged.
3. **The cars-and-motorcycles ratio in criterion 2 is at or below 0.95**, so the
   surplus is made of the classes H008 showed do not respond to the price.

**Uninformative** — f lands between 0.02 and 0.05, or its bootstrap interval
spans that range, or f moves by more than a factor of two across the three
counterfactuals. Report f under each, the interval, and the implied range of
vehicles. A diversion share this design cannot pin to better than "somewhere
between negligible and substantial" is a real outcome and must be reported as
one.

**A feasibility gate on criterion 2, declared before the run.** If cars and
motorcycles are more than 90% of exempt volume in the pre-boundary blocks, the
ratio cannot reach 1.10 however concentrated the surplus is, and the criterion
cannot discriminate. Measure that baseline share first, report it, and if it
exceeds 0.90 record criterion 2 as **untestable** rather than as failed. Two
records in this project have frozen criteria a true effect could not satisfy;
this one states its own ceiling in advance so the same failure is visible before
the result exists rather than after.

## Data required

All on hand. One additional Socrata aggregate on a public dataset already
cached, no new source, no cost, no dependency on the backfill. The speed archive
is not used and is not affected.

## Result

*Filled in after running.*

## Verdict

*Filled in after running.*

## Notes

**What this cannot establish.** That the toll reduced congestion, reduced total
entries, or changed speeds. It also cannot establish that diversion did not
occur anywhere: it measures one substitution margin, at four detection points,
in the twenty minutes after one price change. Drivers who divert onto roads
these sensors do not watch, who retime instead of rerouting, or who divert at a
different hour are all outside it. H007 established that the speed feed cannot
see this corridor at all, so a negative here closes a measurement channel rather
than the question.

**On the count of attempts.** This is the tenth registered hypothesis and the
third against the MTA entry counts. The 05:00 boundary has now been examined by
H008, by H009, by the adjudication, and by this record. A reader is entitled to
that count, and to the fact that this record's author had seen every previous
number at these boundaries before writing it.

**Why the exempt series being partly treated cuts both ways.** H009 named this
in its own notes: if drivers divert onto the exempt roadways, the control is
treated in the opposite direction, and the 05:00 difference of −0.759 overstates
the pure timing response while still identifying its sign. A large f here
therefore *weakens* H009's headline magnitude at the same time as it produces a
diversion finding. Whoever runs this should state that consequence in the
verdict rather than reporting only the half that reads as a discovery.
