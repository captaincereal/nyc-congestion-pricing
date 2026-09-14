# Adjudication — the entry-timing result (H008, H009)

| | |
|---|---|
| **What this is** | A reader's verdict on three existing records. It registers no hypothesis and runs no specification. |
| **Records adjudicated** | [H008](H008-toll-timing-bunching.md), [H009](H009-toll-timing-exempt-control.md), and the register entries for both |
| **Written** | 2026-09-14 |
| **Written by** | Claude Opus 5, a session that did not write H008 or H009 and had not seen their numbers before reading the records |
| **Asked for by** | `docs/agent_handoff.md`: "Whether this counts as supported is a judgement for a reader of the three records." |

## Why this file exists rather than an H010

H008 and H009 each failed a criterion that their own author diagnosed as
badly built, and the author declined to write a third record rewriting the
criterion. That was the right call. The estimate would not have moved, only the
label, and the label would have been chosen by someone who already knew it.

What the handoff asked for instead was a reader. This is that reading. It draws
on two things the records did not use, and neither is a new draw against the
data:

The first is the rest of H009's own output. `H009_difference.csv` holds the
difference in discontinuities at all 24 hour boundaries. The record reported
two of them. The other 22 are a placebo distribution for the difference
estimator itself, produced by the frozen specification in the same run, and
reading them is reading the study's own artefact.

The second is a measurement of the estimator on synthetic fixtures — planted
discontinuities with known answers. That touches no study data at all.

No specification was estimated against the MTA entry counts for this file. A
later reader can verify that claim: nothing in `outputs/tables/` changed.

## The finding

**A retiming response to the toll's price schedule is real, and the study
should say so.** The evidence that carries it is the 21:00 boundary, the
weekend-versus-weekday discrimination at 09:00, and the confinement of the
response to cars and motorcycles.

**The 05:00 estimate should stop leading the write-up.** It is the largest
number in the thread and the most exposed to the one bias this design does not
remove. Both records, the decision register, the README and the handoff
currently lead with it.

That reversal of emphasis is the substance of this adjudication. The rest of
this file is the evidence for it.

## What the design does remove, measured rather than argued

H009 rests on a claim about what a difference in discontinuities controls for:
a clock, a sensor batching at hour boundaries, and polynomial misfit all apply
to both series, so differencing removes them. Two of those three hold exactly,
and the third holds conditionally.

Planting known discontinuities in two synthetic series and running
`difference_in_discontinuities` unchanged:

| Fixture | delta returned | Correct answer |
|---|---:|---:|
| Tolled jumps +0.25, exempt flat | +0.2500 | +0.25 |
| Both jump +0.10, tolled +0.35 | +0.2500 | +0.25 |
| Tolled −0.70, exempt +0.07 | −0.7700 | −0.77 |
| Neither series jumps | −0.0000 | 0 |
| **Both jump +0.10 — a pure clock effect** | **−0.0000** | **0** |

The estimator recovers what it claims to and returns zero on a shared jump.
The identification argument is sound as far as it goes, and the code is
correct.

**Differential curvature passes straight through.** Give the two series
different quadratic curvature and plant no discontinuity anywhere:

| Curvature, tolled | Curvature, exempt | delta returned |
|---:|---:|---:|
| +2.0 | 0 | +0.3333 |
| +4.0 | 0 | +0.6667 |
| +8.0 | 0 | +1.3333 |
| +4.0 | +2.0 | +0.3333 |
| −4.0 | 0 | −0.6667 |

The bias tracks the *difference* in curvature between the two series and is
about two thirds of it in this parameterisation. Common curvature cancels; a
gap in curvature does not. A jump of two thirds of a log point out of nothing
at all is the same order as the largest estimate in the thread.

So the sentence that appears in H009, in the decision register and in the
README — "No clock, sensor artefact or curvature does that, because each would
move both series together" — is right about the clock and the sensor and wrong
about curvature. Curvature moves both series together only when both series
curve the same way.

## Where that bias can bite, and where it cannot

The 05:00 boundary sits in the steepest part of the day. H009 excluded hours
05:00 through 08:00 from its placebo set for exactly this reason, writing that
"entries rise roughly fivefold across these hours and a local linear fit cannot
track that curvature." The record then estimated its headline effect at 05:00
with that same local linear fit, on the reasoning that differencing handles it.
The table above shows differencing handles it only under an assumption about
the two series that nobody checked: that a commuter ramp on tolled streets and
a highway ramp on the FDR and the West Side Highway curve alike.

H009's own output shows they do not. At the three placebo boundaries inside the
same ramp, where no price changes, the difference estimator returns:

| Boundary | tau tolled | tau exempt | delta |
|---|---:|---:|---:|
| 06:00 | −0.1763 | +0.0415 | **−0.2178** |
| 07:00 | −0.1897 | +0.0046 | **−0.1943** |
| 08:00 | −0.0659 | +0.0948 | **−0.1608** |

Those three carry the same signature the record calls impossible: tolled
falling, exempt rising, the two series moving in opposite directions. They are
also the three largest placebo differences in the table outside midnight. The
morning ramp produces the qualitative pattern H009 treats as decisive, at
roughly a quarter to a third of the magnitude.

The evening is a different regime. Around 21:00 the series is smooth, and the
neighbouring placebo differences are small: −0.073 at 19:00, −0.041 at 20:00,
−0.081 at 22:00. Nothing in the estimator's behaviour there gives a reason to
distrust it.

## The raw series, which needs no model at all

`H008_block_profile.csv` holds weekday entries per ten-minute block. The
boundary movements are visible in it directly, before any fit:

| Boundary | Last block before | First block after | Raw change | Fitted tau (H008) | Fitted ÷ raw |
|---|---:|---:|---:|---:|---:|
| 05:00 | 935,101 | 682,466 | **−27.0%** | −40.2% | **1.63×** |
| 21:00 | 1,429,992 | 1,584,656 | **+10.8%** | +12.9% | **1.18×** |

Both raw movements are real, both fall at exactly the two minutes a price
changes, and neither depends on a polynomial. The two boundaries differ in how
much of the reported estimate the model supplies. At 21:00 the fit adds about a
sixth. At 05:00 it adds about two thirds, all of it from extrapolating a rising
ramp forward to the boundary — which is the channel the fixtures above show is
not controlled.

The raw figures reproduce H008's own pre-registration disclosure exactly, where
the record reported scoping values of +10.8% and −27.0%. That agreement is a
check on this arithmetic, not a new result.

## The placebo distribution the records never computed

H009 built its placebo bar from the 95th percentile of |tau| on each series
separately. The natural bar for a difference in discontinuities is the
distribution of the difference, and the frozen run produced it at every
boundary without anyone tabulating it.

Applying H009's own pre-registered exclusions — midnight as a calendar
boundary, 05:00 through 08:00 as the curvature band — leaves 18 placebo
boundaries. Their deltas have mean **−0.0611** and standard deviation
**0.0552**, and 17 of the 18 are negative. The estimator has a systematic
negative offset at ordinary boundaries, so a two-sided comparison against zero
is the wrong comparison.

| Boundary | delta | Rank among 18 placebos | z against placebo centre |
|---|---:|---|---:|
| 21:00 | **+0.0710** | **most positive of all 24 boundaries**; the next most positive is +0.0140 | +2.39 |
| 05:00 | **−0.7589** | more negative than all 18; 3.2× the largest placebo magnitude (0.2401 at 23:00) | −12.63 |

Seven of the 18 placebos exceed the 21:00 delta in absolute value, and every
one of the seven runs the other way. Against the predicted direction — a price
falls at 21:00, so entries should rise — **no placebo boundary comes within a
factor of five of it**. This is the strongest single piece of evidence in the
thread, and neither record reported it.

Midnight is excluded on a mechanical ground worth stating, because its delta of
−0.7469 is otherwise the one placebo that matches the 05:00 estimate.
`_signed_minutes` wraps the running variable modulo the day
(`src/analysis/h008_toll_timing.py:95`), so at the midnight boundary the blocks
before and after come from opposite ends of the same calendar date, 23 hours
apart, and the date fixed effects compare a day's start to its own end. That is
not a boundary comparison, and both records were right to drop it in advance.

## Reading the two boundaries

**21:00 is supported.** The raw jump is +10.8% against a declining evening
trend. The fit adds little. The difference against vehicles that pay nothing is
+0.0710 with an interval of [0.0478, 0.0942], in a part of the day where the
estimator is demonstrably well behaved, and it is the most positive of 24
boundaries by a factor of five. It holds in both years, +0.0769 in 2025 and
+0.0609 in 2026. Three of the four dual-recording points are positive.

The qualification is the spread across those points: Brooklyn Bridge gives
+0.2086, West Side Highway +0.0815, FDR +0.0433, and the Hugh L. Carey Tunnel
−0.0281. The pooled estimate leans on Brooklyn Bridge, which is three times it.
A price response need not be uniform across entry points, and H008 found all
twelve correctly signed on the tolled series alone, so this reads as
heterogeneity rather than as an artefact. It does mean the pooled +7.1 log
points should be quoted with its range.

**05:00 is real in direction and unreliable in magnitude.** The raw drop of 27%
against a rising ramp is not a modelling artefact, and no smooth process
explains a fall at the minute the peak rate begins. The reported −0.759 is a
different claim. It rests on a linear extrapolation through the steepest
curvature of the day, in the band the record itself declared unfit for this
estimator, and the fixtures show differential curvature entering the difference
undamped. The adjacent placebo boundaries put the contamination at up to 0.22,
so curvature does not account for the bulk of a 0.759 — but it is enough that
the number should not be quoted as though it were measured cleanly.

**The vehicle-class split is the most informative cut in the thread and it
survives all of this**, because it does not run through the boundary estimator's
weak point. Cars and motorcycles carry the entire response, at −0.862 and −0.616
at 05:00; single-unit trucks, multi-unit trucks, taxis and buses are flat or
wrong-signed. Curvature does not know a car from a bus. Neither does a clock.
The one caveat is inferential: that cut aggregates to day-of-week before
estimating, so its standard errors rest on five clusters
(`src/analysis/h008_toll_timing.py:248`). The point estimates use all 609 dates
and are fine. Nothing in the study quotes those standard errors, and nothing
should.

## What a reader should take from the three records

The claim **drivers retime entries in response to the toll's time-of-day price
schedule** is supported. Three independent things carry it, and no one of them
depends on the criteria that failed: a raw +10.8% jump at the minute the peak
rate ends, against nothing comparable at any other hour in the predicted
direction; a weekend-versus-weekday contrast at 09:00 of 4.91× that holds
across all six specifications; and a response confined to the vehicle classes
with discretion over departure time.

The claim that this is **the cleanest identification in this project by a wide
margin**, resting on 05:00, should be withdrawn as written. The cleanest
identification in this project is the 21:00 difference, and it is a smaller and
less dramatic number.

**The pre-registration is worth very little on this thread, and the support
above does not come from it.** Two consecutive records had criteria that could
not do their job, drafted by one author within an hour. This adjudication found
a third weakness of the same family — a placebo bar built on each series
separately when the estimand is a difference — which nobody caught before the
run either. What the finding rests on is the robustness of the estimates across
specifications, boundaries, entry points, vehicle classes and years, and a
reader should weigh it as that kind of evidence rather than as a pre-registered
test that passed.

**Nothing here bears on the speed finding**, which is unchanged. Retiming an
entry is not avoiding one, and the study still cannot say whether the toll
reduced congestion, reduced entries or changed speeds.

## What this adjudication does not settle

It does not re-score H008 or H009. Both verdicts stand as written —
uninformative and does-not-support-as-specified — and their frozen sections are
untouched. A verdict is a statement about whether a record cleared its own bar,
and neither did.

It does not license quoting −0.759 as a clean estimate, and it does not replace
it with a corrected one. Producing a better 05:00 number would mean choosing a
new specification while knowing what the old one returned, which is the failure
the protocol exists to prevent. If the magnitude at 05:00 ever matters enough to
pin down, it needs its own record, frozen in advance, with a curvature-robust
estimator chosen before it is run and a statement of why that is not
relabelling.

It says nothing about whether the exempt series rising at 05:00 is route
substitution. That is [H010](H010-exempt-route-substitution.md), registered and
not yet run, and this file deliberately takes no position on how it comes out.

## One gap this exposed

`src/analysis/h009_exempt_control.py` has no tests. The H008 boundary estimator
has four, including a planted discontinuity and a planted zero
(`tests/test_h008_toll_timing.py`), added in a commit of its own after H008 was
answered. The function that produced the study's most-quoted estimate never got
the same treatment, and the fixtures in this file are the ones that would do it:
recovery of a planted difference, a zero on a shared jump, and the curvature
sensitivity above pinned so that changing it has to be deliberate.

The fixtures ran clean, so this is a gap in the permanent record rather than a
defect in the result.
