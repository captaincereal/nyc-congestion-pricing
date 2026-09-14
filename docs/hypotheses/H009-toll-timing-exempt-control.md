# H009 — Does the entry-timing response survive a control group that pays no toll?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5, same session that ran H008 |
| **Answered by** | |
| **Supersedes / superseded by** | **Supersedes [H008](H008-toll-timing-bunching.md)** |

## Question

H008 found entries jumping at the two moments the toll price changes, and could
not clear its own bar. Its placebo set was the wrong instrument: twenty-one
other hour boundaries on the same series, compared by their *maximum*, in a
window that includes a morning ramp no local linear fit can track.

There is a better control sitting in the same dataset and H008 did not use it.
`excluded_roadway_entries` counts vehicles crossing the same detection points on
the **toll-exempt roadways** — the FDR Drive, the West Side Highway, the Hugh L.
Carey Tunnel, the Brooklyn Bridge approach to the FDR. 38,721,475 of them,
11.6% of all recorded entries. They are measured by the same sensors, in the
same 10-minute blocks, on the same days, subject to the same weather, traffic
and daily rhythm as the tolled entries beside them.

**They face no price discontinuity at 05:00 or 21:00, because they are never
charged.**

Does the timing discontinuity appear only where a price changes?

## Why it matters

This is the difference between a suggestive pattern and a controlled one. H008's
best defence was that a daily rhythm cannot know Saturday's peak starts four
hours later than Tuesday's. This is stronger: a daily rhythm cannot know which
*lane* a vehicle is in.

If exempt entries show no discontinuity while tolled entries at the same
detection point and the same minute do, the alternative explanations — rhythm,
sensor batching, reporting artefacts at hour boundaries, curvature the
polynomial cannot fit — are all controlled, because every one of them applies
equally to both groups. If exempt entries show the same jump, the H008 result is
an artefact and should be withdrawn rather than defended.

## Prediction

*Frozen once results exist.*

**Full disclosure, because this record supersedes one whose results I have
seen.** I know H008's numbers completely: tolled weekday tau of +0.1216 at 21:00
and −0.5138 at 05:00, a weekday placebo maximum of 0.1387, the weekend/weekday
09:00 ratio of 4.91×, all twelve detection groups correctly signed, and the
vehicle-class split. I therefore know that a percentile-based placebo bar would
probably let 21:00 through, and **that is exactly why the percentile is not the
primary criterion here.** Re-scoring the same estimate against a friendlier
ruler is not a test. The primary criterion below rests on the tolled-versus-exempt
comparison, which has not been computed at any boundary, in any specification.

What I have not measured and what I expect:

**The exempt discontinuity** *(not measured)*. I expect it to be near zero at
both boundaries, and I hold that at about 75%. The residual 25% is not doubt
about the price mechanism but about substitution: when the toll falls at 21:00,
a driver who had been routing along the FDR to avoid the charge has less reason
to, so exempt entries could *fall* as tolled entries rise. If that happens the
two groups move in opposite directions, which is a stronger price signature than
a flat control, not a weaker one. What would genuinely undermine this is exempt
entries jumping *upward* at 21:00 alongside the tolled ones.

**The difference in discontinuities** *(not measured)*. I expect it to be
positive at 21:00 and negative at 05:00 and to exceed the tolled estimate alone
if substitution is present. No point prediction: H008's 12.9% conflates the
notch with whatever the exempt series is doing, and separating them is the
point.

**Mass balance** *(not measured)*. If drivers are retiming rather than
cancelling, entries lost in the hour before a price rise should roughly reappear
in the hour after a price fall. I have no idea whether this holds and am not
pretending to — trips can be cancelled, diverted to exempt roads, or shifted
much further than an hour. This is registered as a descriptive quantity with no
threshold attached, because I cannot honestly set one.

**Persistence across 2025 and 2026** *(not measured)*. Twenty months is long
enough for habituation. I weakly expect the response to be stable rather than
decaying, at perhaps 55% — close to no view.

## Method

**Data.** As H008: `t6yz-b64h`, 10-minute blocks, 2025-01-05 onward, Socrata
aggregates cached under `data/raw/mta_crz/`. The addition is
`excluded_roadway_entries` alongside `crz_entries`.

**Sample.** The four detection groups that record both tolled and exempt
entries: FDR Drive at 60th St, Brooklyn Bridge, Hugh L. Carey Tunnel, West Side
Highway at 60th St. Restricting to these is what makes the comparison
within-location; the eight groups with no exempt roadway are reported separately
and are not part of the primary estimate.

**Estimator.** The H008 boundary estimator unchanged — ±60 minutes, order 1,
date fixed effects absorbed, clustered by date — applied to each series, then
differenced:

    delta = tau(tolled) − tau(exempt)

estimated jointly on a stacked panel with a `tolled` indicator so the difference
carries a standard error, interacted through the polynomial so each series keeps
its own trend. Clustered by date.

**The corrected placebo construction**, which is the other half of superseding
H008 and is frozen here:

- The bar is the **95th percentile** of |tau| across placebo boundaries, not the
  maximum. A maximum over twenty-one estimates is a statistic of the tail, and
  H008 demonstrated it moves between 0.05 and 0.25 across specifications while
  the quantity under test holds at +0.10 to +0.13.
- Boundaries **05:00 through 08:00 are excluded from the placebo set** in
  advance, on the stated ground that entries rise roughly fivefold within those
  hours and a local linear fit cannot track that curvature. This is a statement
  about the shape of the series, not about which boundaries are inconvenient,
  and it is written here before the percentile is computed.
- Midnight remains excluded, as in H008, as a calendar boundary.

**Cuts.** By detection group; by vehicle class, restricted to cars and
motorcycles, which H008 showed carry the entire response; by calendar year for
persistence.

**Outputs.** `outputs/tables/H009_*.csv`, `outputs/figures/H009_*.png`.

## Acceptance criteria

*Frozen once results exist.*

Primary is the **difference in discontinuities at weekday 21:00**, pooled across
the four dual-recording detection groups.

**Supports** — the timing response is a price response. All three:

1. **delta at weekday 21:00 is positive and its 95% confidence interval
   excludes zero.** This is the criterion that has not been measured in any
   form.
2. **The exempt series does not jump in the same direction as the tolled
   series** at either weekday boundary: tau(exempt) at 21:00 is not positive and
   significant, and at 05:00 is not negative and significant. An exempt series
   that moves *opposite* to the tolled one satisfies this.
3. **delta is correctly signed at 05:00 as well** — negative — so the result is
   not a single-boundary artefact.

**Refutes** — the H008 pattern is not a price response and should be withdrawn.
Any one of:

1. tau(exempt) has the same sign as tau(tolled) at both weekday boundaries and
   is at least half its magnitude. The discontinuity then belongs to the clock
   or the sensor, not the toll.
2. delta at weekday 21:00 has a confidence interval covering zero **and** the
   tolled estimate fails the corrected percentile bar. Both halves must fail;
   either alone is the uninformative case.
3. The difference is confined to one of the four detection groups.

**Uninformative** — delta is correctly signed but its interval covers zero, and
the exempt series is too thin or too noisy at these boundaries to bound the
comparison. Report the width of the interval and the implied minimum detectable
difference. With four groups rather than twelve this is a live possibility, and
the fact that the tolled estimate alone would clear the corrected percentile bar
does **not** convert this outcome into support.

## Data required

All available. No new source, no cost. One additional Socrata aggregate carrying
`excluded_roadway_entries` at block level.

## Result

*Filled in after running. Leave empty until then.*

## Verdict

*Filled in after running.*

## Notes

**What supersession means here.** H008's verdict of uninformative stands and is
not revised. Its criteria are not reinterpreted. This record replaces the
*instrument*, stating in advance why the old one was wrong and what the new one
is, which is the procedure `docs/hypotheses/README.md` prescribes when criteria
turn out badly chosen. If H009 refutes, H008's suggestive pattern is withdrawn
and both records say so.

**The count, honestly.** This is the second hypothesis against the MTA entry
data and the ninth registered overall. A reader is entitled to know that the
21:00 discontinuity has now been looked at twice, and that the corrected placebo
bar was chosen by someone who already knew the old one had failed by 0.017 log
points. That is precisely why the primary criterion is the exempt comparison
rather than the percentile: the percentile fix alone would be a re-score, and a
re-score is not a result.

**The substitution caveat.** Exempt roadways are a route choice as well as a
control. If the toll diverts traffic onto the FDR during peak hours, the exempt
series is itself treated — in the opposite direction — and delta then overstates
the pure timing response while still identifying its sign. This is stated now so
it cannot be discovered later as a convenience. It is also, separately, the
diversion question H007 could not answer on the speed feed, and a clean negative
exempt response at 21:00 would be the first direct evidence on it from any
source in this project.

**What this cannot establish, as with H008.** That the toll reduced congestion,
reduced total entries, or changed speeds. Retiming is not avoidance.
