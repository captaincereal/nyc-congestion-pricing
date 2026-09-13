# H006 — Does control matching fail on a holdout that is not holiday-dominated?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5 session |
| **Answered by** | — |
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

*Empty until run.*

## Verdict

*Empty until run.*

## Notes

The two-holdout design is the point. H004 could not separate "matching does not
work" from "October to December is atypical". Running the same rules against
both windows answers that directly: if the clean holdout passes and the holiday
one fails, holidays were the story; if both fail, they were not.

Reference for rule B: Abadie, Alberto, Alexis Diamond and Jens Hainmueller
(2010). "Synthetic Control Methods for Comparative Case Studies." *Journal of
the American Statistical Association* 105(490):493–505.
https://doi.org/10.1198/jasa.2009.ap08746
