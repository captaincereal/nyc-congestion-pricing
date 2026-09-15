# Decision Register

**NYC Congestion Relief Zone · speed study**

Compiled 2026-09-09, updated 2026-09-14 · treatment date 2025-01-05 ·
Validation details are recorded in the latest dated entry below.

All six open decisions were resolved on 2026-09-14; that entry is the fourth
below. Earlier entries are historical and are superseded where the latest audit
says so.

## Update 2026-09-15 — H010 has a hosted path, and its frozen criteria cannot be satisfied

The owner asked for a hosted path so H010 could run on Actions rather than on a
machine someone has to leave on. It is built. Building it surfaced a defect in
the record's own acceptance criteria, found before any result exists, and that
is the part worth reading.

### The defect

H010's Method names three counterfactuals and calls the flat one — the last
pre-boundary block, held level — "the model-free floor", on the reasoning that
"it cannot manufacture a deficit out of a ramp, and it will understate both D
and S".

**It does the opposite, and the direction matters.** Holding the last
pre-boundary block level puts the counterfactual *below* a rising series, which
shrinks the measured deficit and inflates the measured surplus. Both biases push
f the same way. On a fixture planting a deficit of 2,000 and a surplus of 200 per
block on a realistic morning ramp:

| Counterfactual | Deficit (true 6,000) | Surplus (true 600) | f (true 0.100) |
|---|---:|---:|---:|
| loglinear | 6,000.0 | 600.0 | **0.1000** |
| quadratic | 6,000.0 | 600.0 | **0.1000** |
| flat | **−2,098.2** | **8,698.2** | **undefined** |

The two fitted counterfactuals recover the planted truth exactly. The flat one
returns a **negative** deficit and a surplus fourteen times the truth.

### What that does to the criteria

Support criterion 1 requires f ≥ 0.05 under the frozen counterfactual **and**
≥ 0.02 under the flat one. At 05:00 the entries series rises steeply — that is
the whole reason the adjudication demoted the 05:00 estimate — so the flat
deficit is negative and f under it is undefined. **The second conjunct cannot be
satisfied by a true effect of any size, so support is unreachable.**

Refutation criterion 2 fires when "f is negative under any of the three
counterfactuals". A negative deficit against a positive surplus is a negative
ratio, so as written **that condition fires automatically**, before any data is
consulted.

Taken together the record would return "refutes" mechanically, whatever the
answer is. The implementation returns `NaN` rather than a negative number when
the deficit is not positive, on the ground that dividing by a negative deficit
is meaningless — so the code and the record's words disagree, and that
disagreement is disclosed here rather than resolved quietly in either direction.

### The pattern, stated plainly

This is the fourth criteria failure of the same family in this project, after
H008's maximum over a contaminated placebo set, H009's demand for a significant
zero, and the placebo bar the adjudication found computed on levels when the
estimand was a difference.

**It was written by the same session that diagnosed the first three, in the
document that diagnosed them.** The handoff's instruction — state criteria as
magnitudes and check that a true effect of the expected size could satisfy them
before freezing — was followed for the magnitudes and not for the check. A bar
was set on a statistic whose behaviour had not been measured.

The cheap lesson is that the rule needs a mechanical step rather than an
intention: before freezing a criterion, plant a true effect of the expected size
in a fixture and confirm the criterion passes. That check takes minutes and
would have caught all four.

### Amended, at the owner's direction, later the same day

The owner accepted the recommendation and directed the amendment, so it is made
on the 2026-09-12 H003 precedent: **before execution**, with the record
retaining its original text beside a dated amendment section that explains what
changed and why.

The flat counterfactual is removed from support criterion 1, from refutation
criterion 2 and from the spread clause, and stays reported as a diagnostic. The
spread clause now runs across the fitted pair, which is what it needed to do
anyway — a disagreement between a linear and a quadratic fit on the same six
blocks measures the curvature sensitivity that clause was written to catch.

**No magnitude changed.** 0.05, 0.02, 1.10, 0.95, 0.90 and the factor of two
are exactly as frozen, the frozen counterfactual is still log-linear, and the
Prediction is untouched. What was removed is a conjunct that could not be
evaluated. That distinction is the whole defence against reading this as an
author loosening their own bar, and the record makes it explicitly rather than
leaving a reader to work it out.

**The satisfiability check is now a test rather than an intention.** Planted true
effects across the predicted range of f fire support; 0.01 fires refutation;
0.03 fires uninformative; and support is reached while the flat counterfactual
still returns an undefined f, which is the amendment in one assertion. Anyone
freezing a criterion in this project should plant an effect of the size they
expect and confirm the criterion clears, before committing the record. All four
failures here would have been caught that way in minutes.

H010 may now be dispatched. It has still not been run.

### What was built

`src/analysis/h010_route_substitution.py` implements the record's Method as
written, including the flat counterfactual, so the code embodies no correction
the record has not made. Eleven tests in
`tests/test_h010_route_substitution.py` plant known deficits and surpluses and
check f comes back exactly; one is a characterisation test pinning the flat
counterfactual's inversion so it cannot quietly disappear.

`scripts/run_h010.py` and `.github/workflows/h010.yml` run it on a hosted
runner. The workflow is **`workflow_dispatch` only**, deliberately: `analysis.yml`
fires on every backfill completion and on pushes under `src/analysis/`, and a
pre-registered hypothesis re-answered on every push is a fresh draw each time.
The script also refuses to overwrite existing H010 artefacts without an explicit
`--allow-rerun`, because a silent second run would replace what an answered
record cites with nothing in the diff to show a second draw was taken.

Suite is 284 tests, ruff and black clean. Nothing has been run against the MTA
feed: the session that built this cannot reach `data.ny.gov`, and in any case
wrote the record, so execution and the Verdict belong elsewhere.

## Update 2026-09-14 (later still) — `main` is an orphan history, and four hypotheses have no commit-order evidence on it

Found while cleaning up merged branches. It is recorded because it bears on the
protocol rather than on the plumbing.

### What the history actually looks like

`main` begins at **c573209** ("Report the findings in the README", 2026-09-12),
which is a **root commit with no parent**. It shares **no common ancestor** with
either surviving `codex/*` branch. The project's original development history —
Phase 1-2 ingestion through Phase 8, the geometric treatment assignment, the
creation of this register — lives only on `codex/verify-then-aggregate`
(**b591c8e**, 51 commits unreachable from `main`).
`codex/finish-study-handoff` (**4b51954**) is a strict subset of it.

Every file is on `main`. The history behind them is not.

### Why that matters, stated plainly

`docs/hypotheses/README.md` says: "Git history is the enforcement: the record is
committed before the analysis, so a later reader can check the commit order."

**For H001, H002, H003 and H004 there is no such order on `main` to check.** All
four records enter in the root commit c573209, already carrying their Results
and Verdicts. A reader auditing `main` alone cannot distinguish a record written
before its analysis from one written after, for any of the four.

From H005 onward the enforcement works as described, and the commits are on
`main`:

| Hypothesis | Registration commit on `main` |
|---|---|
| H001–H004 | none — the records arrive fully answered in the root commit |
| H005, H006 | f01f988 Preregister H005 and H006 on the 27-month archive |
| H007 | 1faf8aa Preregister H007: can the secondary feed identify diversion? |
| H008 | ac96825 Preregister H008: do drivers retime entries to avoid the peak rate? |
| H009 | 4b57794 Preregister H009: does the timing response survive an unpaying control? |
| H010 | ac02681 Adjudicate the timing result, register H010, decide TLC |

The order for H001, H002 and H003 is demonstrable, but only on the codex branch:

    07e9c04  Add a hypothesis protocol and a skill that enforces it
    b6ee5ae  Register H002: Rambachan-Roth sensitivity
    141cc13  H001 answered: magnitude beats chance in 3 of 4 samples, peak does not
    d5b4558  Preregister H003 temporal aggregation before execution

**H004 has no registration commit in either history.** Its order is not
demonstrable from git at all, on any branch.

### What this does and does not undermine

It does not imply anything went wrong. H001 through H004 may well have been
registered before they ran, and their records read as though they were. What it
means is narrower and still worth saying: for those four the pre-registration
rests on the records' own text and on `REGISTER.md`'s dated appends rather than
on the mechanism the protocol names as its enforcement. A sceptical reader is
entitled to know which of the ten they are looking at.

H001 and H003 are two of the four lines of attack the README cites behind the
headline finding, so this is not confined to a corner of the study.

### The `data-raw` tag does not preserve it

`data-raw` points at **3ec6d90**, which sits on the codex branches **six commits
before** 07e9c04. An ancestor does not keep its descendants reachable, so
deleting the codex branches would leave the four commits above unreferenced and
eventually collectable, with `data-raw` unaffected.

### What was attempted and what blocked it

The owner directed: tag the history, then delete both codex branches. The tag
was created locally as an annotated tag `preregistration-history` at b591c8e.
**Pushing it failed**, as did deleting any branch, so **nothing was deleted** —
completing half of a tag-then-delete is the one outcome worse than doing
neither.

The failure is environmental rather than a property of the repository. This
session's git relay accepts pushes that add commits to a branch and silently
drops every other ref update: `git push origin --delete <branch>` and
`git push origin refs/tags/<tag>` both return "the remote end hung up
unexpectedly" followed by "Everything up-to-date", five attempts each with
backoff, while pushes of commits to `main` succeeded throughout the same
session. A later session on a different runner, or the owner locally, should
find these work normally.

### What is still to do

Push the tag, confirm it with `git ls-remote --tags origin`, and only then
delete `codex/verify-then-aggregate`, `codex/finish-study-handoff` and the
merged `claude/agent-handoff-mission-wo4wc7`. The confirmation step is not
optional: the tag is the only thing standing between a routine branch cleanup
and the loss of the H001–H003 audit trail.

If the branches are ever deleted without that tag, say so in this register
rather than leaving a reader to infer it from an absence.

## Update 2026-09-14 (later) — the timing result is adjudicated, and its headline boundary changes

The handoff asked for three things and said the most likely way to damage the
study now was to find something to run. Nothing was run against the data. Both
workflows were green on arrival, the suite passes, and `outputs/tables/` is
untouched by this session — checkable in the diff.

### The timing result: supported, with the emphasis reversed

[ADJUDICATION-timing.md](hypotheses/ADJUDICATION-timing.md) is a reader's
verdict on H008, H009 and their register entries, written by a session that
wrote none of them. It leaves both verdicts standing and takes no position that
re-scores either.

**It finds the retiming response supported, and it demotes 05:00.** Every
document here — H009, this register, the README, the handoff — led with the
05:00 difference of −0.759 as the cleanest identification in the project. That
ordering is now reversed, and the reason is specific.

Synthetic fixtures show what the difference estimator does and does not remove.
It recovers a planted difference exactly and returns **exactly zero** when both
series jump together, so the argument that a clock and a sensor artefact cancel
is sound. **Differential curvature does not cancel.** Give the two series
different quadratic curvature and plant no discontinuity at all, and the
estimator returns the curvature **gap ÷ 6** on a ±60 minute window, exactly —
two series whose ramps differ by four log points across the hour produce +0.667
out of nothing at all. The claim repeated in H009 and in this register,
that "no clock, sensor artefact or polynomial misfit does that, because each
would move both series together", is right about the first two and wrong about
the third.

05:00 sits in the steepest ramp of the day, the band H009 itself excluded from
its placebo set on curvature grounds before estimating its headline effect
inside it. H009's own output shows the contamination: at 06:00, 07:00 and 08:00
the difference is −0.218, −0.194 and −0.161, each with tolled falling and exempt
rising — the opposite-direction signature the record calls impossible, at a
quarter to a third of the magnitude. Against the raw block profile the fitted
estimate is **1.63×** the model-free drop at 05:00 and **1.18×** it at 21:00.

**21:00 is the boundary that holds.** `H009_difference.csv` carries the
difference at all 24 hour boundaries; the record reported two. Those 22 are the
natural placebo distribution for this estimand and nobody tabulated them. Under
H009's own pre-registered exclusions, 18 placebos remain, their differences
centred at **−0.061** with 17 of 18 negative. Against that, +0.0710 at 21:00 is
**the most positive of all 24 boundaries**, with the next most positive a fifth
of its size. Midnight's −0.747 matches the 05:00 estimate and is correctly
excluded on a mechanical ground: `_signed_minutes` wraps modulo the day, so at
that boundary the estimator compares a date's start to its own end 23 hours
later.

**The pre-registration is worth little on this thread and the support does not
come from it.** Two records had criteria a true effect could not satisfy. The
adjudication found a third weakness of the same family, a placebo bar built on
each series separately when the estimand is a difference, which nobody caught
before the run either. What carries the finding is a raw 10.8% jump at the
minute the peak rate ends, a weekend-versus-weekday contrast of 4.91× at 09:00
holding across six specifications, and a response confined to cars and
motorcycles — a cut that does not run through the estimator's weak point,
because curvature does not know a car from a bus.

**Nothing here touches the speed finding.** Retiming an entry is not avoiding
one.

### Route substitution is registered as H010

[H010](hypotheses/H010-exempt-route-substitution.md) tests the by-product H009
flagged and claimed nowhere. The claim that exempt entries rising at 05:00 are
this project's first direct evidence of route substitution appears in this
register and in the handoff, while the README says diversion is unidentified on
both feeds. One of those has to change whichever way H010 lands, which is why it
clears the decision-relevance bar.

It is posed in **vehicle counts rather than log points**, because a substitution
claim has to balance in vehicles and a 7% rise on the smaller series cannot
absorb a 27% fall on the larger one without the arithmetic being done. Its
criteria rest on two unmeasured quantities: the count-based diversion share, and
whether the surplus is made of the vehicle classes H008 showed respond. Its
author had seen every previously computed number at these boundaries and the
record discloses each, including the two of four detection points where the
exempt rise is negative and the 21:00 mirror that runs against the simple
diversion story.

Criterion 2 carries a **feasibility gate declared in advance**: a baseline
cars-and-motorcycles share above 0.90 makes the bar unreachable, and it is then
recorded as untestable rather than failed. Two records here froze criteria a
true effect could not satisfy, and the damage came from nobody noticing until
afterwards.

Registered and not run. The execution prompt is in
[H010-execution-prompt.md](hypotheses/H010-execution-prompt.md) and belongs in a
fresh session, per the protocol.

### TLC trip records: recommended against, on evidence

H008 measured the vehicle class TLC covers, at both price boundaries: TLC
taxi/FHV gives τ = **−0.021** at 05:00 and **+0.004** at 21:00, against −0.862
and +0.254 for cars. TLC data therefore cannot carry the one design in this
project that does not need parallel trends, and a TLC before-and-after across
the cordon would inherit the identification failure H001–H006 documented. What
would justify revisiting it is an outcome other than link speed — zone-to-zone
trip duration with a real pre-period — as its own hypothesis.

**The distribution remains unverified and this session could not verify it.**
Its sandbox network policy denied CONNECT to every data host tried, including
`data.ny.gov` and `data.cityofnewyork.us`, which this project downloads from
daily. The failure says nothing about the sources. Confirm the endpoint from a
runner with normal egress before writing ingestion code.

### Four smaller things found, and one correction to the handoff

The handoff says to call `gh` at `C:/Program Files/GitHub CLI/gh.exe`. That is
specific to the machine it was written on. This session ran on Linux with no
`gh` at all and read run status, jobs and logs through the GitHub MCP tools
instead, which worked. The underlying warning still holds: without some
authenticated path to the Actions API, failures are undiagnosable from outside.

`src/analysis/h009_exempt_control.py` had **no tests**, while the H008 boundary
estimator beside it has four. The function that produced the study's most-quoted
estimate never got the same treatment. **Closed the same day**, at the owner's
direction: `tests/test_h009_exempt_control.py` adds nine, and the suite is now
273. They pin that the estimator recovers a planted difference, reports the
exempt series rather than the tolled one, returns **exactly zero** on a jump
shared by both series, absorbs the order-of-magnitude level gap between them,
and leaves the record's frozen exclusions at 18 placebo boundaries. One is a
characterisation test rather than a correctness one: differential curvature
comes through as gap ÷ 6 on a ±60 minute window, so changing that behaviour has
to be deliberate. Each test was checked against deliberately broken copies of
the estimator — swapping the two coefficients and absorbing fixed effects on
date alone — and both mutations fail five and seven of the nine.

H008's vehicle-class and detection-group cuts aggregate to day-of-week before
estimating (`src/analysis/h008_toll_timing.py:248`), so their standard errors
rest on **five clusters** while their point estimates use all 609 dates. The
point estimates are sound. Nothing quotes those standard errors and nothing
should.

The README's Data section said the MTA entry feed was **"not ingested"** while
its Evidence section reported two hypotheses run on 125M of its entries. True
when the mechanism check was abandoned, wrong from H008 onward, and now
corrected with the row counts.

### What did not change

The speed finding. +1.05 mph, pre-trends rejecting in all four samples on the
full 104-week pre-period, causally uninterpretable. The archive is complete at
44 of 44 verified months. D1–D7 stay as resolved on 2026-09-14 and none was
reopened. No code changed, no specification ran, and no artefact in
`outputs/tables/` was rewritten.

## Update 2026-09-14 — the six open decisions are resolved

The owner directed this session to decide D1, D2, D3, D5, D6 and D7 on their
behalf. Each is settled below. **No code changed** beyond a comment recording
D3's evidence: every verdict either confirms existing behaviour or closes a line
of work, and nothing was invented to make the exercise look larger.

One framing note, recorded because it shaped the verdicts. The instruction was
to decide with an eye to what might produce results. Decisions were **not** made
on that basis, because choosing a specification for the size of the number it
returns is the failure this project spent nine hypotheses documenting. Where the
productive choice and the correct one diverge — and on D1 they do — the correct
one was taken and the divergence is stated.

### D1 — Retain the unfiltered median as primary. **ADOPT.**

The quality filter is the only one of the six that visibly moves the headline:
`quality` gives +0.963 mph (SE 0.183) against the `contiguous_baseline` +0.849
(SE 0.239), a larger estimate with a tighter interval. `no_extreme_readings`
gives +0.932 (SE 0.234).

That is precisely why it is not promoted. Adopting a filter as the primary
outcome *because* it raises the coefficient and narrows the interval is
selection on the outcome, and the primary outcome is frozen in
`docs/project_brief.md`.

The substantive case is also weaker than it looks. The extreme-value problem is
real — 0.1976% of readings exceed 80 mph and the maximum is 11,674.7 mph — but
the primary outcome is an hourly **median**, which is already robust to them;
that is what a median is for. The probe-depth concern (10.88% of readings rest
on three probes or fewer) is the more serious one, and it stays reported as a
sensitivity where a reader can weigh it.

Note the memo's figures are stale against the completed archive: it cited
10.97%, 0.1125% and a 7,043.9 mph maximum, measured on eight months. The
direction of the argument is unchanged.

### D2 — Pre-treatment matching with held-out validation. **ADOPT as method; executed, and negative.**

The discipline it prescribes was right and remains binding on any future control
construction: freeze the features, the matching rule, the holdout dates and the
acceptance criteria before touching post-treatment outcomes, and do not promote
the naive pool or pick the pool with the most favourable coefficient.

Its substantive hope is refuted. H004 and H006 both executed it. Nearest-
neighbour made held-out flatness worse in all four samples; synthetic weights
fitted the matching window to a squared loss of exactly zero and still rejected
at p = 4.4e-07; H006 repeated it on seventy weeks with a clean July-September
holdout and every control set still rejected.

The memo said "wait for the contiguous pre-period to evaluate this
recommendation". That wait is over — the archive is complete at 44 months — and
the evaluation returned negative twice. The method is adopted; the line of work
is closed.

### D3 — Reclassify four northern 11th Avenue segments into treatment. **REJECT.**

The recommendation rests on the claim that the blanket `1[12]th Ave` exemption
"conflates these local streets with Route 9A". **The feed's own naming
contradicts it.** Two crosstown segments in `ezpass_segments.parquet` are named
*"14th Street – westbound – 7th Ave to 11 Ave/Rt 9A"* and its eastbound pair.
The data source identifies 11th Avenue **as** Route 9A.

The four segments D3 names — 108104, 116080, 80108, 81116 — are the only ones in
the roster whose roadway subject is 11th Avenue. All four are southbound and
their geometry is continuous from 23rd Street to 57th, which is the Route 9A
alignment through Manhattan: West Street, then 11th Avenue, then 12th Avenue
north of roughly 57th. Route 9A is toll-exempt, so the current classification is
correct and adopting D3 would have reclassified exempt highway as tolled local
street.

**Residual uncertainty, stated rather than buried.** The feed's "11 Ave/Rt 9A"
label appears at 14th Street, not at 23rd to 57th, so the identification along
the D3 segments is an inference from that label plus the continuous alignment.
It has not been checked against an MTA tolling document or a NYSDOT route log.
What would settle it definitively is either of those. The `eleventh_as_treated`
sensitivity stays in the robustness table, and it shows the choice moves the
coefficient by about 0.001 mph — so the cost of being wrong in either direction
is numerically negligible, and the reason to get it right is correctness of a
frozen definition rather than the estimate.

### D5 — Keep the two Williamsburg Bridge directions separate. **ADOPT.**

`194196` is eastbound out of Manhattan and `197195` is westbound in. Pooling
them would average entry and exit behaviour into one number that describes
neither. Two links also carry very little independent information for clustered
inference, so any crossing analysis stays exploratory and neither link belongs
in the primary surface-street model. Costs nothing; prevents a real error.

### D6 — Normalise only derived corridor labels, when corridor analysis begins. **ADOPT.**

A conditional rule with no current cost: no corridor analysis exists, and the
secondary diagnostic is at link × month, so spelling variants cannot split an
estimate today. Adopting it now means the auditable lookup is required before
the first corridor aggregate rather than retrofitted after one. Original names
and IDs stay intact.

### D7 — Complete the frozen window beginning January 2023. **ADOPTED — and executed.**

Done on 2026-09-13. The archive holds all 44 frozen months, 2023-01 through
2026-08, every one verified: 24 pre-treatment months and 20 post. The memo
argued against extending back into 2021-22 COVID-recovery years instead, and
that remains the position — no extension is planned or needed.

### What this changes about the finding

Nothing. The speed result stands: +1.05 mph, pre-trend test rejecting in all
four samples on the full 104-week pre-period, causally uninterpretable. None of
the six decisions was capable of changing that, which is itself worth recording
— the open decisions were never what stood between this study and a result.

## Update 2026-09-13 (later) — a behavioural response the study can actually identify

The archive completed at 44 of 44 verified months and `analysis.yml` rebuilt
everything from it. The headline association fell to **+1.05 mph** (SE 0.27,
7.95M link-hours, 334 clusters) and the joint pre-trend test still rejects in
all four samples on the full 104-week pre-period. The "too little pre-period"
explanation is now exhausted rather than unlikely: there is no more to add.

**Two new hypotheses opened a different line and it works.** The toll is higher
in a peak window and discounted overnight, switching at 05:00 and 21:00 on
weekdays and 09:00 at weekends — derived from the MTA feed's own `time_period`,
not from the published tariff. That is a price discontinuity inside the
post-period, so identification rests on the minutes either side of it and not on
parallel trends.

[H008](hypotheses/H008-toll-timing-bunching.md) found entries jumping at both
boundaries. [H009](hypotheses/H009-toll-timing-exempt-control.md) superseded it
with a control the speed study never had: `excluded_roadway_entries`, 38.7M
vehicles on the toll-exempt roadways crossing the same detection points, on the
same sensors, in the same ten-minute blocks, who are never charged.

**At 05:00 the two series move in opposite directions** — tolled −0.6889, exempt
+0.0701, difference **−0.759 [−0.795, −0.723]** — at all four dual-recording
points with every interval excluding zero. No clock, sensor artefact or
polynomial misfit does that, because each would move both series together. At
21:00 the design separated a shared evening rhythm of 5.6 log points from a
price-attributable **+7.1** [4.8, 9.4]. Both persist across 2025 and 2026. The
response is confined to cars and motorcycles; trucks, taxis and buses are flat
or wrong-signed, which H008 predicted backwards.

**Neither record cleared its own bar, and the register should be blunt about
why.** H008 compared its estimate to a *maximum* over twenty-one placebo
boundaries, a set contaminated by the morning ramp. H009 required its control to
show no *significant* movement, which 609 days and 125M entries can never
deliver — it demanded a precisely estimated zero. Both are gates built on the
wrong scale, drafted by the same author within an hour. That pattern should
discount the pre-registration value of both, and it is why no third record
rewrites the criterion: the estimate would not move, only the label, and it
would move for someone who already knew it.

**Nothing here bears on the speed finding.** Retiming an entry is not avoiding
one. The study still cannot say whether the toll reduced congestion, reduced
entries, or changed speeds.

**One by-product, flagged and claimed nowhere.** Exempt entries rising as tolled
ones collapse at 05:00 is the first direct evidence of route substitution this
project has obtained from any source. H007 could not measure it on the speed
feed because the sensors on those roads had failed. It would need its own record
before it could be reported.

**Open decisions are unchanged.** D1, D2, D3, D5, D6 and D7 remain reserved to
the owner and none has been adopted.

## Update 2026-09-13 — the secondary feed cannot measure diversion either, and the reason is measurement

[H007](hypotheses/H007-secondary-feed-diversion.md) is answered and **refutes**.
The spillover question is now closed on both feeds, for two different reasons,
and the difference between them is the useful part.

The primary E-Z Pass roster cannot answer it because it contains no units where
diversion would show — the five `boundary` links straddle 60th Street and the
nearest control is 808 m out. That is a coverage limitation. The secondary DOT
feed (`i4gi-tjb9`) does carry the nine toll-exempt in-zone links traffic would
divert onto, and it cannot answer it either, because **it stops measuring three
of them**. `4616325` (11th Ave S) has never emitted a positive speed in 41
months. `4616323` and `4616338` (12th Ave S and N) report at full availability
through March 2024, degrade in April, and go permanently dark from May 2024.
The treated group is eight contributing links before the toll and six after,
and the three that leave are the whole West Side Highway arm of the design.

The pre-registered availability gate measures this as a **−21.16 pp**
differential change in usable-hour availability against a 5 pp bar, identical to
within 0.25 pp in all four hour-of-week cuts. The joint pre-trend test also
rejects (χ² = 86.0 on 11 monthly leads, p = 1e-13) and the Rambachan–Roth
breakdown value is 0.000–0.034, so all three refutation conditions fire. **Read
the verdict off the availability gate.** The other two consume a cluster-robust
covariance matrix resting on nine treated clusters, which is exactly the regime
the same record calls untrustworthy; the availability gate is a count of hours
and needs no asymptotics at all.

**The break predates the toll by eight months**, so it is instrumentation, not
the intervention. That is what makes this a measurement failure rather than a
parallel-trends failure, and it says what better data would fix: working speed
sensors on the 11th/12th Avenue corridor across the toll date. A better control
pool, a different estimator and more draws would all change nothing.

The estimate, which is not quotable: ATT +0.354 mph on all hours (clustered SE
1.457, randomization p = 0.804 on 500 draws), positive where diversion predicts
negative. The clustered standard errors run 10–26% tighter than the
randomization null, consistent with H001. The design's 80%-power minimum
detectable effect is 4.85 mph, 17% of the pre-treatment treated mean — even with
clean diagnostics it could not have seen a diversion effect the size of the
study's own headline association.

**Two artefacts change status.** `data/processed/secondary_hourly_panel.parquet`
is new, built by `python -m src.data.build_secondary_panel`, and is the panel
any future secondary-feed work should start from; it treats zero-speed readings
as the outages they are. `outputs/tables/spillover_secondary_monthly.csv` is
**superseded**: `src/analysis/spillover_diagnostics.py` filters only
`speed_mph IS NOT NULL` and so averages 8.8M zero-speed outages in as 0 mph.
Speed levels taken from it are biased toward zero by roughly the local outage
rate. The primary panel is unaffected — zero-speed readings are at most 0.014%
of any `treatment_group × post` cell there.

**Still open.** Whether diversion occurred. H007 establishes only that this feed
on these nine links cannot measure it. The restricted design its Verdict names —
treated limited to the six links reporting throughout — is a new hypothesis and
must be registered before it runs.

---

## Update 2026-09-13 — the "geometric backstop" in geo.py was dead code, and could not have worked

`src/data/geo.py` defined a Manhattan bounding box (`_in_manhattan_envelope`,
`MANHATTAN_LON_MIN`/`MAX`, `MANHATTAN_LAT_MIN`/`MAX`) and a comment calling it
the geometric backstop on the borough label. Nothing called it. It has been
removed and the docstrings corrected. **No treatment assignment changed**: the
primary roster still classifies 185 control, 148 treated, 6 exempt, 5 boundary,
2 crossing, exactly as before.

Wiring it in was the other option, and was measured first. It fails on both
feeds. On the primary E-Z Pass roster it is a provable no-op — all 176
Manhattan-labelled segments lie wholly inside the box. On the secondary feed
(`i4gi-tjb9`) it does not catch the two links it was supposed to catch, because
the box has to reach 40.680 N to cover the Battery and therefore also covers
downtown Brooklyn. Links `4616339` and `4616340` — the BQE approaches to the
Brooklyn and Manhattan Bridges, labelled `borough = Manhattan` with Brooklyn
geometry — sit entirely inside it. So do ten Brooklyn-labelled E-Z Pass
segments on Atlantic Ave and Flatbush Ave.

Requiring every vertex inside the box instead moves six links, each for the
wrong reason. Four have corrupt geometry, with vertices decoding to longitudes
near zero (`4616324`, `4620343`, `4616332`, `4456511`). The two
Brooklyn-Battery Tunnel links reach Brooklyn because the tunnel does, and both
are in H007's treated group: `4456494` and `4456502` would have been moved into
its control group. That is worse than the problem.

**What remains open.** `classify_segment` still trusts the borough label alone,
so the two BQE approaches still come back `treated`, which is wrong — an
approach to a tolled crossing is toll-exposed, and plain `control` would be
wrong too. H007 excludes both by `link_id`, which is the proportionate fix
while two links are affected. If a later feed or a longer roster makes the
disagreement general, the fix is a river-side or borough-polygon test, not a
bounding box. `tests/test_geo.py` pins all three facts: the borough label is
the only gate, the BQE misclassification is characterised so that changing it
has to be deliberate, and a bounding box provably cannot backstop the label.

---

## Update 2026-09-12 — inference corrected; the current design cannot identify the effect

The takeover audit found two statistical implementation errors, an unusable
verification command, and an unstarted hosted backfill. The mission was not
blocked only by throughput. No open owner decision or frozen definition was
changed. Recommendations are in [owner_decisions.md](owner_decisions.md).

**Current answer.** The implemented comparison design cannot support a causal
claim about speed improvements or nearby diversion. This is not a causal null
and does not establish that a better control design will fail. The README now
reports this finding, withholds effect magnitudes until source verification
completes, and identifies the remaining work. Files in `outputs/tables/` are
explicitly provisional computational diagnostics on the stored archive.

**Invalid old gate.** The event-study joint test had summed squared individual
t statistics, ignoring covariance between the leads. It now uses the full
link-cluster covariance in a Wald test and records method, rank and tested bins.
DuckDB's integer week difference also put January 1–4 into event week zero;
the corrected floor-of-elapsed-days definition keeps every pre-tolling hour
negative. The weather event study no longer allocates an N×N projection.
Regression tests compare the covariance calculation and weather residualization
with independent matrix/explicit fixed-effects calculations.

**Rerun.** All four corrected pre-period tests reject on the current eight-month
archive. Rejection also occurs on the original contiguous October–April window,
so the isolated June month is not the explanation. Exact diagnostics are in
`pretrend_tests.csv` and `robustness_pretrend_contiguous.csv`. These supersede
every earlier joint test and pass/fail label in this register. Holidays remain
an untested explanation. The ±12-week endpoint bins pool more distant weeks;
new metadata makes that explicit rather than implying a full-year weekly test.

**Robustness.** Twelve separate specifications now run reproducibly, including
geographic controls, quality exclusions, hourly mean, transition removal,
common-link roster, two pre-period placebos and a D3 assignment sensitivity.
Non-placebo associations remain positive, but are sensitive to control choice.
The two placebo tests do not reject zero. Neither finding repairs rejected
leads. Matching with held-out validation, a full-year placebo and daily
aggregation remain pending; D1/D2/D3 remain unadopted.

**Spillover.** The five primary boundary links straddle the cordon. The distance
audit finds no wholly outside Manhattan control within 500 m of the current
line, and nine within 1 km. A 500 m outside-band analysis therefore has no
primary units. This is a coverage limitation, not demonstrated control
contamination at 500 m. The secondary archive actually holds 42,216,965 raw
rows; the descriptive replay retains 42,210,837 readings after null/duplicate/DST
handling, producing 3,532,556 link-hours and 5,199 link-months across 42 months.
These summaries make no causal diversion claim. Both bridge directions are
retained separately by link; the older claim that both measure entry was wrong.

**Archive and quality.** Primary coverage remains eight of 44 complete target
months: June 2024 and October 2024–April 2025. Staging now includes all held
months: 5,977,804 readings produce 1,587,630 link-hours. The July–September gap
leaves only three contiguous full pre-treatment months. The larger quality
audit finds 10.97% of readings at three probes or fewer, 0.1125% above 80 mph,
and a maximum of 7,043.9 mph. The common-link sensitivity is not a balanced
hour-by-hour panel claim.

**Verification repaired.** The old `--verify` compared retained 15-minute rows
with the unsampled source count and never updated the manifest. Verification
now compares raw-page totals with live raw counts, repeats deterministic
downsampling, and compares the retained fields against immutable disk data.
Day receipts bind to the raw part's hash and the versioned verification method.
Only a completed matching replay upgrades a month. `--verify-existing` and a
runtime budget allow hosted passes to resume. Legacy flags cannot become
current verification evidence merely because a file exists or has a matching
hash. End dates are exclusive, and in-progress months must never be finalized.
The one-minute live verification probe completed and matched June 1–3 against
the source, then exited cleanly before the next page (about 75 seconds elapsed,
including an in-flight request). Three daily receipts are held; June remains
unverified until all 30 days match. No raw part bytes changed.

**Hosted diagnosis.** At 16:59 UTC there had been no Backfill run. The first
Analysis run had failed because the `data-raw` release did not exist and DuckDB
found no raw parquet files. The latest Tests run was green. Exact URLs and the
failure excerpt are in `outputs/tables/workflow_audit.json`. Workflow fixes
make absent/pre-only input explicit, fail on actual release download errors,
persist verification receipts, and run sensitivity/provenance generation.
The jobs use standard hosted runners and refuse private repositories, preserving
the zero-dollar constraint. See the deployment entry below for actual rollout
status; a YAML fix alone is not evidence that a hosted job succeeded.

**Measured export experiment.** Sequential anonymous probes streamed the first
16 MB of each full-dataset CSV at 1.72 and 2.11 MB/s, including startup. Three
50,000-row paging probes exceeded a 35-second read timeout; the remaining
`:id` probe achieved 0.23 MB/s. The sample is capped and not evidence of sustained
whole-export throughput, total transfer size or identical retained data. The
existing backfill is preserved. Commands and exact timings are in
`scripts/benchmark_socrata.py` and `outputs/tables/socrata_benchmark.json`.

**Local validation:** 121 synthetic tests pass, with one expected pandas warning
from the deliberately malformed-timestamp fixture. Ruff and Black pass across
source, tests and scripts. Bash/YAML validation passes. Staging, panel building,
all four event studies, weather sensitivities, 12 robustness fits and the
secondary summary completed on the actual stored data. Passing these checks
does not substitute for source verification or the robustness assumptions.

### Hosted deployment verified — 2026-09-12

[PR #1](https://github.com/captaincereal/nyc-congestion-pricing/pull/1) passed
hosted tests and merged as `af93a066`. The original eight immutable primary
parts, segment/weather files, manifest and three-day June verification receipt
were seeded into the [data release](https://github.com/captaincereal/nyc-congestion-pricing/releases/tag/data-raw).
Upload digests were checked; no existing raw part was overwritten.

The first repaired [Analysis run](https://github.com/captaincereal/nyc-congestion-pricing/actions/runs/34707540983)
completed successfully and committed its regenerated results as `0c6ca41`.
[Tests on merged main](https://github.com/captaincereal/nyc-congestion-pricing/actions/runs/34707540919)
also passed. Its corrected joint-test verdicts agree with the local run.
The hosted panel was downloaded and matched the tracked provenance hash.

[Backfill](https://github.com/captaincereal/nyc-congestion-pricing/actions/runs/34707558019)
was explicitly started on main. At the recorded check its setup and archive
restore had succeeded and its Download step was running; verification and
publication were still pending. This is confirmation of an active hosted run,
not a claim that the missing months or full verification have completed.
The existing six-hour schedule will resume later passes without owner uptime.
Exact statuses, asset digests and check time are in
`outputs/tables/hosted_rollout.json`. The saved local project has the delivered
code and corrected derived data. The next research action is owner review of
the six open recommendations, while hosted data collection continues.

Everything below this entry is historical unless explicitly reconfirmed above.

> **Update 2026-09-10.** Since this register was first compiled the priority
> window (2024-10 … 2025-04, seven months, three either side of the toll) has
> been ingested and staged, the panel rebuilt with a post-treatment period, and
> **Phases 6 (descriptives) and 7 (difference-in-differences) run** — see "The
> result so far" below. **D4 is resolved** (5763399). The full pre-period
> backfill to 2023-01 now runs unattended in CI (see the 2026-09-12 entry). The Phase 7 DiD is
> **not quotable**: it rests on a 7-month window, parallel trends has no formal
> test yet (Phase 8, needs the backfill), control selection is still open (D2),
> and there is no placebo test. (Phase 8 has since run and the pre-trend test
> fails — see the 2026-09-12 entry below.)

---

## Update 2026-09-12 — the backfill no longer needs a machine left on

The binding constraint was never Socrata's throughput on its own. It was
throughput *times* the requirement that one machine stay awake for all of it.
Ingestion had two properties that made an interruption expensive: a month was
accumulated in memory and written only on completion, and nothing bounded a run
against a clock. Killing it at minute 35 of 40 discarded all 35, which is how
the partial 2024-07 and 2023-11 pulls were lost.

Three changes remove that.

**Day checkpoints.** Each day now lands in `data/raw/ezpass_days/` as it
completes and the month part is assembled from those, so an interruption costs
one day. Parquet writes go through a temp file and a rename, so no kill can
leave a torn part that later reads as a complete month.

**A wall-clock budget.** `--max-runtime` stops a run cleanly and `--month-budget`
keeps it from starting a month it cannot finish, so a scheduled job ends by its
own choice with nothing in flight rather than being hard-killed.

**Scheduled execution.** `.github/workflows/backfill.yml` runs every six hours,
downloads for about five, publishes to the `data-raw` release and exits;
`analysis.yml` rebuilds the panel and reruns Phases 6-8 whenever data lands.
The release is the resume state, since a runner's disk does not survive the job.

Two instruments came with it, because a pipeline nobody watches has to report
on itself. `src/data/coverage_report.py` answers how far the backfill is from
what the study needs — leading with pre-period depth rather than month count,
since post-treatment months do not help the pre-trend test. And
`event_study.py` now upserts its verdict into
`outputs/tables/pretrend_tests.csv`, so the gate on every estimate in this
project is a file rather than a line in a log. `outputs/` is tracked from now
on, which makes each increment of data a visible diff.

The four pre-trend tests reproduce exactly after the rewrite (all chi2=26.58
p=0.0053, offpeak 52.32 p~0, peak 9.71 p=0.557, weekend 15.44 p=0.163),
confirming the checkpointing changed nothing about what the pipeline computes.

**Nothing about the analysis changed.** Eight months are still on disk, two of
four samples still fail the pre-trend test, and D2 is still open. This entry
records that the project can now make progress while nobody is watching, not
that it has made any.

---

## Where the project stands

| Phase | | Status |
|---|---|---|
| 1 | Setup | Complete |
| 2 | Ingestion | **8 of 44 months** on disk (2024-06, then 2024-10 … 2025-04); the rest runs on a schedule in GitHub Actions |
| 3 | Data quality | Checks written and run on the seven months |
| 4 | Panel | Built, with a post-treatment period (2025-01-05 onward) |
| 5 | Controls | Naive pool used as a documented interim; **D2** still open |
| 6 | Descriptives | Run — weekly series, pre-trend gap, hourly profile, coverage |
| 7 | Difference-in-differences | Run on the 7-month window (not quotable — see below) |
| 8 | Event study | Rewritten and run (2026-09-10); formal pre-trend test now exists, and it fails on the full/offpeak samples — see below |
| 9–11 | Robustness, mechanism, deliverables | Not started |

The pipeline runs end to end on real data, including a post-treatment period.
The binding constraint now is the **length of the pre-period**: seven months
is too short for a credible parallel-trends test, so the backfill to 2023-01
gates Phase 8 and any quotable estimate.

---

## The result so far

### Pre-tolling levels (pipeline validation)

Median speed by treatment group, **pre-tolling** (2024-10-01 … 2025-01-04).
Levels, not effects. Source: `outputs/tables/descriptive_summary.csv`.

| Group | Median mph | Links | Link-hours |
|---|---:|---:|---:|
| treated | 7.86 | 148 | 286,229 |
| boundary | 9.73 | 5 | 11,334 |
| control | 15.64 | 169 | 315,695 |
| exempt_in_zone | 19.43 | 6 | 11,731 |
| crossing | 36.61 | 2 | 4,589 |

**External corroboration.** In-zone surface streets sit near 8 mph before
tolling, against roughly 8.2 mph published for the Manhattan CBD. Geometry, unit
conversion, treatment assignment and hourly aggregation all have to be correct
for that number to land there — it is the strongest evidence the pipeline
measures what we think it measures. The ordering also vindicates separating the
groups: folding 37 mph bridge segments or 19 mph Route 9A into an 8 mph treated
group would badly distort the estimate, and boundary segments land between
treated and control, which is what straddling 60th Street should look like.

### Phase 7 difference-in-differences — NOT quotable

Frozen two-way FE spec, estimated on the 7-month window
(`outputs/tables/did_estimates.csv`, 323 link clusters):

| Sample | ATT mph | SE | p | 95% CI | % of pre-treated mean |
|---|---:|---:|---:|---|---:|
| all | +0.85 | 0.24 | 0.0004 | [+0.38, +1.32] | +8.9 |
| weekday peak | +0.56 | 0.26 | 0.031 | [+0.05, +1.08] | +7.1 |
| weekday off-peak | +0.72 | 0.23 | 0.0016 | [+0.27, +1.16] | +7.3 |
| weekend | +1.30 | 0.28 | 6e-06 | [+0.75, +1.86] | +13.2 |

Positive and significant in every cut; the weekend effect being ~2× the weekday
peak effect independently matches published work. Weather robustness
(`did_estimates_weather.csv`): the post period is colder and snowier, which
biases the estimate *downward*, and treated × weather interactions move β by
≤5%. **Why it is not quotable:** 7-month window, D2 open, no placebo, and —
see below — the formal pre-trend test does not clear on this window either.

### Phase 8 event study — first run, formal pre-trend test now exists

`src/analysis/event_study.py` was a dead scaffold (referenced `volume`,
`sensor_id`, `fuel_price`, `travel_time_index` — none exist; `linearmodels`
isn't even a dependency) and has been rewritten against the real panel: same
two-way FE absorption as `did.py`, generalized from one treatment dummy to one
`treated x event_week` dummy per week, reference week `k = -1`, clustered by
link. Control links are folded to the reference bin (tolling has one start
date for everyone, so a bare, non-interacted week dummy would be collinear
with the time fixed effects).

**This replaces the Phase 6 weekly-slope eyeball check with an actual test**,
and the result is more cautious than that check suggested:

| Sample | Joint pre-trend test (k < -1, weeks -12..-2) | Verdict |
|---|---|---|
| all | χ²=26.6, df=11, p=0.0053 | **FAILS** — pre-period not flat |
| peak | χ²=9.7, df=11, p=0.557 | passes |
| offpeak | χ²=52.3, df=11, p≈0 | **FAILS hard** |
| weekend | χ²=15.4, df=11, p=0.163 | passes |

The post-period path (`outputs/tables/event_study_all.csv`) is directionally
consistent with the Phase 7 DiD — mostly positive, growing from ~+0.6 mph at
k=1 to ~+1.1 mph by k=7-11 — which is reassuring. But the pre-period, especially
in the **offpeak** cut, is not flat: several weeks in the 7-month window's
14-week pre-period are individually significant (k=-11, -4, -3), most plausibly
because that window is Thanksgiving-through-New-Year, which is exactly the kind
of atypical pre-period D2 already worried about, not genuine drift. **This
means D2 is not merely "open" — the naive control pool has now failed a real
test on part of the sample, which the Phase 6 check was too coarse to catch.**
It should be re-run once the backfill gives a longer, less holiday-dominated
pre-period before it is used to decide D2 either way.

---

## Settled and verified

Each of these was tested, not assumed.

**The original source could not answer the question.** `i4gi-tjb9` carries ~123
links city-wide. Of the 18 inside the zone, every one is toll-*exempt* (FDR
Drive, West Side Highway) or a crossing. Zero on Broadway, Fifth, Park,
Lexington, 34th, 42nd, Canal. The treated group was empty. Replaced by the EZ
Pass local-street feeds; the old source retained for spillover.

**Timestamps are naive America/New_York, not UTC.** Confirmed from both
directions. Fall-back 2024-11-03: hour 01 doubles, 103 readings vs 51 on the
control Sunday. Spring-forward 2025-03-09: hour 02 is empty, 0 vs 1,063 on the
control Sunday. Under UTC neither signature would appear. Every hour-of-day cut,
including the peak definitions, is correct as written.

**The feed republishes a rolling median, not independent readings.** A
900-second median re-emitted about every 61 seconds — 52 readings per
segment-hour, ~93% overlap, frequently byte-identical. Ingestion keeps one
reading per non-overlapping 15-minute window. Measured: mean 3.71 readings per
link-hour, maximum 4, zero hours above 4.

**Reported speed is internally consistent.** Checked independently against
`link_length_ft / median_tt_sec`: median disagreement 0.002 mph, 0% of rows
differ by more than 5 mph. Validates the fps→mph conversion against a field not
used to compute it.

**Treatment assignment is geometric, not name matching.** Polylines decoded and
tested against the 60th Street line — which is *not* constant latitude, since
the grid is rotated by more than a block. Verified: segment 1004 decodes to
40.7514, −73.9761, the real 42nd & Lexington, running east as labelled.

---

## Open decisions

### D1 — Cleaning thresholds

10.2% of readings rest on ≤3 probe vehicles. Separately, 0.085% of readings
exceed 80 mph, monthly maximum 962 mph — physically impossible on a Manhattan
surface street.

The panel applies **no** value cleaning. The frozen outcome is a median
precisely so sparse extremes do not drive it, and every diagnostic a filter
would need is carried on each row.

> **Decide:** set a minimum sample depth and a speed ceiling, or keep the panel
> unfiltered and treat both as robustness variants?

### D2 — How controls get selected — *blocks Phase 5*

The frozen design requires controls chosen on pre-treatment trends, not
geography. That is load-bearing: pre-tolling, treated sits at 7.86 mph and
control at 15.64 — a level gap of nearly 2×.

DiD identifies off changes, so the gap is not disqualifying by itself. The
Phase 6 eyeball check (treated−control gap slope ≈ +0.011 mph/week) suggested
the naive pool might be a live option — but the **Phase 8 formal pre-trend
test (2026-09-10) rejects flatness overall (p=0.005) and hard in the offpeak
cut (p≈0)**, and passes only for peak and weekend. That is a real signal
against the naive pool as-is, not just a weak counterfactual concern, though
it is confounded with the pre-period being mostly Thanksgiving-New Year.

> **Decide:** match on pre-treatment trend, restrict to Manhattan above 60th, or
> build a synthetic control? Re-run the Phase 8 pre-trend test on a longer,
> less holiday-dominated pre-period once the backfill lands before deciding —
> the current failure may be a short-window artifact rather than a real
> parallel-trends violation, but it should not be waved off either.

### D3 — Is 11th Avenue actually exempt?

Route 9A's street-level extent south of 57th is genuinely ambiguous. Four 11th
Avenue segments are classified `exempt_in_zone`, removing them from treatment.
If wrong they belong in treatment; if right they belong in the spillover
analysis, since exempt roads are where diverted traffic goes.

> **Decide:** confirm or reverse. Four segments, a one-line change in
> `EXEMPT_PATTERNS` (`src/data/geo.py`).

### D4 — The 32 unassigned links — *RESOLVED 2026-09-09 (5763399)*

324 distinct links appear in the readings but the segment attribute table held
only 297 — so 32 links, **7.94% of readings**, carried no borough and no
geometry, and therefore no treatment group. Cause: building that table from a
single day; the roster changes over time. The fix was to refetch it across nine
sample days spanning both datasets.

**Update 2026-09-09 — these are probably decommissioned sensors.** Of the 33
unassigned links, 25 stop reporting entirely during autumn 2024 (last readings
cluster on 2024-11-13, 11-20/21 and 12-22) and never appear in the post period.
That is almost certainly why they were absent from the 2025-01-06 segment
sample — they were already gone by then. The refetch samples 2023-01, 2023-07,
2024-01 and 2024-06, all of which precede the shutdown, so recovery is likely.

Two consequences worth noting. First, these links have **no post-treatment
observations**, so a DiD would drop them regardless; leaving them unassigned
costs control-pool size, not identification. Second, sensors decommissioning
mid-window is itself a finding: link identity is not stable across the study
period, which matters for D7 and for any balanced-panel claim.

> **Resolved.** The refetch ran across nine sample days spread over the study
> window: the segment attribute table went 297 → 346 segments and the 39
> unassigned links (64,981 link-hours) dropped to **zero**. Treated grew
> 130 → 148 links, control 154 → 175. Both hard data-quality checks
> (`hard_duplicate_key`, `hard_unmatched_segments`) now pass. The decommissioned
> sensors remain a finding: link identity is not stable across the window, which
> still matters for D7 and any balanced-panel claim.

### D5 — What happens to the crossings

Two Williamsburg Bridge segments (sid 194196 / 197195) measure the queue to
*enter* the zone, not circulation within it — a different behaviour, near 37 mph
against treated's ~8. Held separate rather than dropped. Published work reports
the largest speed gains on crossings, so they are substantively interesting in
their own right.

> **Decide:** estimate crossings as a separate specification, or exclude them?

### D6 — Roadway name normalisation

The feed carries both `57th St` and `57th Street` for the same street, and some
names arrive mojibaked with a corrupted en dash. Classification is unaffected —
that runs on geometry — but per-roadway or corridor-level aggregation would
split the street in two.

> **Decide:** normalise now, or leave until a corridor-level analysis needs it?

### D7 — How much history to pull

The frozen window starts 2023-01-01 (two pre-treatment years). The feed reaches
back to 2021-04-08, so a longer pre-period is available for placebo dates and
trend testing — at real cost, since throughput measured 3s–80s per page.
2021–22 also carries COVID recovery dynamics, a confound rather than a bonus.

> **Decide:** hold at 2023-01, or extend once the backfill completes?

---

## Data on hand

| Source | Role | Coverage | Months | Rows (staged) |
|---|---|---|---:|---:|
| `erdf-2akx` + `6a2s-2t65` | Primary | 2024-10 … 2025-04 | 7 / ~45 | 5,162,965 |
| `i4gi-tjb9` | Secondary (spillover) | 2023-01 … 2026-07 | 42 / 45 | 40,249,114 |

The primary source was pulled **priority-window first** — 2024-10 through
2025-04, three-plus months either side of the toll — so analysis was not blocked
behind a 44-month backfill. The rest now runs on a schedule in GitHub Actions
(`.github/workflows/backfill.yml`), about five hours per pass, resuming from
the `data-raw` release. Socrata still throttles sustained requests hard; what
changed is that nobody has to sit through it. `python -m src.data.coverage_report`
prints where it has got to.

**Caveat on the manifest.** All seven primary parts are recorded
`verified: false`. Row counts were not pre-checked against a live `count(1)`,
because that query defeats Socrata's index and ran for minutes. Completeness
currently means "paging finished cleanly", not "the row count was confirmed".
Running `--verify` upgrades this, and should happen before any published result.

---

## Known risks

- **Pre-period is only ~3 months.** The panel now has a post-treatment period,
  but the pre-period runs 2024-10 → 2025-01-04. That is enough for a descriptive
  read and a provisional DiD, not for a credible parallel-trends test or placebo
  dates. The backfill to 2023-01 lifts this; Phase 8 waits on it.
- **Throughput is not under our control.** 3s–80s per page, load-sensitive and
  erratic. Concurrent requests make it markedly worse, so the download runs alone.
- **A month is held in memory until complete.** Losing the process mid-month
  discards up to 30 minutes. The manifest protects across months, not within one.
- **Segment roster drifts over time.** D4 (now resolved) was the visible
  symptom; the deeper point is that link identity is not guaranteed stable
  across a four-year window, which matters for a balanced panel.
- **Primary parts are unverified.** Seven `verified: false` parts; run
  `--verify` before any published number.

### Cleared

- ~~**Links may drop out at the treatment boundary**~~ — checked 2026-09-09
  (pre-refetch counts: control 154/154, treated 130/130, exempt 6/6, boundary
  5/5, crossings 2/2, zero dropouts). All dropouts were `unassigned` links that
  stopped reporting in autumn 2024, well before tolling, so they cannot
  introduce a discontinuity at 2025-01-05. **Recheck after the D4 refetch:** the
  post-refetch descriptive summary shows treated 148→145 and control 169→167
  links across pre/post (a link is counted if it has ≥1 link-hour in the
  period), so a handful of links now appear in one period only. Whether that is
  a genuine boundary discontinuity or just sparse coverage at the panel edges
  needs a proper balance check on the current panel — carry as a small open
  item, not a cleared one.
