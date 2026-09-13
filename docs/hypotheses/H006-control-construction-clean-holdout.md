# H006 — Does control matching fail on a holdout that is not holiday-dominated?

| | |
|---|---|
| **Status** | answered |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5 session |
| **Answered by** | Claude Opus 5 session, 2026-09-13 |
| **Supersedes / superseded by** | supersedes [H004](H004-control-construction.md) on the 27-month archive; H004's verdict stands for the 12-month one |

> Construction work behind **D2**, like H004. Running it does not adopt D2.

## Question

H004 built controls from pre-treatment behaviour and both rules rejected on a
held-out window. That window was October to December 2024, so the failure was
confounded with holiday dynamics and H004 said so. With 96 pre-treatment weeks
now available, does the same construction fail on a holdout that contains no
major holiday?

## Why it matters

This is the cleanest remaining shot at D2, and the last obvious escape route for
the study's central finding.

Every negative result so far has carried the same caveat: short pre-period,
holiday-dominated window. The archive now runs 2023-02 to 2025-04, verified and
contiguous. If matching fails here, on a summer holdout, with a 70-week matching
window, the caveat is exhausted and the conclusion that this link roster cannot
support the frozen design is about as well established as this data can make it.

If it passes, the study has a comparison group and Phase 9 becomes live.

## Prediction

*Frozen once results exist.*

Failure on the primary holdout, with moderate confidence — higher than the low
confidence H004 was registered with. Two things moved since: the corrected joint
pre-trend test rejects *harder* on the long window than the short one (χ² 45.6
to 100.2 against 43.6 to 87.1), and H002's breakdown values were already far
below any robust threshold. Neither is consistent with a comparison group that
merely looked bad because of the holidays.

I expect the holiday holdout to reject at least as hard as the clean one. If the
clean holdout rejects *more* than the holiday one, that would be genuinely
surprising and worth flagging rather than explaining away.

No prediction on which rule does better; H004's ordering (synthetic beats
nearest-neighbour) was itself unpredicted.

## Method

`src/analysis/control_construction.py`, features and rules **unchanged** from
H004 so the only moving parts are the data and the windows. Nearest-neighbour
keeps 60 donors; synthetic weights keep those above 0.001; the 500 m boundary
exclusion applies first.

**Windows**, in event weeks, frozen here:

- **Matching window:** k = −96 … −27, seventy weeks, roughly 2023-03 to
  2024-06. Features are built here and nowhere else.
- **Primary holdout:** k = −26 … −15, twelve weeks, roughly 2024-07-07 to
  2024-09-28. July through September contains no Thanksgiving, Christmas or New
  Year. This is the clean test.
- **Secondary holdout:** k = −12 … −2, the window H004 used. Reported under the
  identical rules so the two are directly comparable, which is what isolates the
  holiday explanation.

Weeks −14 and −13 sit between the holdouts and are used by neither.

The naive pool is reported on both holdouts as the baseline comparator, exactly
as in H004.

No post-treatment coefficient is computed until the verdict is written into this
record.

## Acceptance criteria

*Frozen once results exist.*

Judged on the `all` sample at the **primary** (clean) holdout, with peak, offpeak
and weekend reported alongside, and the secondary holdout reported for contrast.

- **Supports** — at least one rule fails to reject at the 5% level on the
  primary holdout while retaining at least 30 donors. The design has a credible
  comparison group and the holiday explanation was real.
- **Refutes** — both rules reject on the primary holdout. Matching fails on a
  window with no holiday confound and a pre-period long enough to fit on, so the
  study reports that this link roster cannot support the frozen design and stops
  searching.
- **Uninformative** — fewer than 30 donors survive, the windows cannot be
  separated, the weight optimisation fails to converge, or the held-out test is
  degenerate at the primary holdout.

A p-value between 0.05 and 0.10 counts as rejecting, as in H004, fixed in
advance so a near miss cannot be talked up afterwards.

**Not licensed by a "supports" verdict:** H001's finding that clustered standard
errors run up to 1.5× too tight applies to this test too, so a marginal pass is
weaker than its nominal p-value. Any causal estimate built on a passing rule
still needs the Rambachan–Roth sensitivity rerun on that control set.

## Data required

The 27-month verified archive (2023-02 … 2025-04), giving 96 contiguous
pre-treatment weeks. 2023-01 is still downloading and is not needed: the
matching window ends at k = −96, which this archive already covers.

## Result

Matching window k = −96 … −27 (70 weeks), 148 treated links and 185 controls in
the donor pool. The 500 m boundary rule again excluded **zero** controls. Rule A
kept 60 donors; rule B put weight above 0.001 on **31** donors, with a
matching-window fit loss of **2.67**. Both holdouts judged inside one
horizon-26 event-study specification, so they are directly comparable.

Joint pre-trend Wald test, held-out windows only:

**Primary holdout — k = −26 … −15, roughly 2024-07-07 to 2024-09-28, no major
holiday** (dof 12):

| Control set | all | peak | offpeak | weekend |
|---|---|---|---|---|
| naive (185) | χ²=43.7, p=1.7e-05 | χ²=69.7, p=3.7e-10 | χ²=49.6, p=1.7e-06 | χ²=46.1, p=6.8e-06 |
| A — nearest 60 | χ²=42.6, p=2.6e-05 | χ²=59.0, p=3.5e-08 | χ²=53.9, p=2.9e-07 | χ²=54.9, p=1.9e-07 |
| **B — synthetic 31** | χ²=36.4, p=2.8e-04 | χ²=35.9, p=3.4e-04 | **χ²=31.9, p=1.4e-03** | χ²=39.3, p=9.4e-05 |

**Secondary holdout — k = −12 … −2, H004's October–December window** (dof 11):

| Control set | all | peak | offpeak | weekend |
|---|---|---|---|---|
| naive | χ²=94.6 | χ²=78.0 | χ²=96.3 | χ²=45.7 |
| A — nearest 60 | χ²=133.1 | χ²=83.8 | χ²=112.9 | χ²=96.9 |
| B — synthetic 31 | χ²=75.1 | χ²=62.8 | χ²=51.8 | χ²=58.8 |

Every cell rejects. The best result anywhere is rule B on off-peak at the clean
holdout, p = 1.4e-03, still more than an order of magnitude below the 0.05
threshold.

## Verdict

**Refutes.** Both rules reject on the primary holdout, in every sample. Matching
on pre-treatment behaviour does not deliver parallel trends on this link roster,
on a window with no holiday confound, fitted on seventy weeks.

**The holiday explanation is answered, and the answer is "partly, but not
enough".** This is what the two-holdout design was for. Holidays are real:
every control set rejects roughly twice as hard on the October–December window
as on the clean one — rule B goes from χ²=36.4 clean to χ²=75.1 holiday on the
full sample. So H004's caveat was legitimate. But the clean window still rejects
decisively, so holidays were aggravating a failure rather than causing one. That
distinction could not be drawn before and can be now.

**Rule B could not fit the long matching window, and that is the honest
version.** In H004 the synthetic weights achieved a squared loss of exactly zero
on 24 weeks, an in-sample fit so perfect it was evidence of nothing. Against 70
weeks the same optimiser reaches 2.67 and concentrates onto 31 donors. It is
still the best rule at both holdouts, and it still rejects. The earlier exact
fit was degeneracy, not skill.

**Rule A remains no better than not trying.** On the clean holdout it is
indistinguishable from the naive pool (χ²=42.6 against 43.7); on the holiday
holdout it is substantially worse (133.1 against 94.6). Nearest-neighbour
selection on these features does not transport, in either window.

**Donor count is at the edge.** Rule B retains 31 donors against the
pre-registered minimum of 30, with the top five weights carrying 46% of the
mass. That clears the bar as written, but it is close enough that the criteria
would have been worth setting higher, and a reader should treat rule B's
clustered inference as thin.

The prediction held on both counts: failure on the primary holdout, and the
holiday holdout rejecting at least as hard as the clean one.

**What this licenses.** Under the registered criteria, the study reports that
the available link panel cannot support the frozen design, and stops searching
for a control set that passes. Further attempts are further draws against the
same data, and the register would have to carry the count.

**What it does not license.** Still no evidence that congestion pricing had no
effect. This says the comparison cannot answer the question. A different
outcome, a different geography, or a roster with links nearer the cordon could
all still identify something — see the coverage limitation that no control link
sits within 500 m of the boundary.

## Notes

The two-holdout design is the point. H004 could not separate "matching does not
work" from "October to December is atypical". Running the same rules against
both windows answers that directly: if the clean holdout passes and the holiday
one fails, holidays were the story; if both fail, they were not.

Reference for rule B: Abadie, Alberto, Alexis Diamond and Jens Hainmueller
(2010). "Synthetic Control Methods for Comparative Case Studies." *Journal of
the American Statistical Association* 105(490):493–505.
https://doi.org/10.1198/jasa.2009.ap08746
