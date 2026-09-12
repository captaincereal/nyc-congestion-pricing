# H004 — Can controls chosen on pre-treatment behaviour produce flat held-out leads?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-12 |
| **Registered by** | Claude Opus 5 session, at owner direction to work on D2 |
| **Answered by** | — |
| **Supersedes / superseded by** | none |

> This is the construction work behind **D2**. Registering and running it does
> not adopt D2. The result comes back as a recommendation with its evidence, per
> the standing reservation of D1–D7 to the owner.

## Question

The frozen design requires controls selected on pre-treatment behaviour rather
than geographic convenience. Does a control set built that way produce leads
that are flat on a **held-out** stretch of pre-treatment weeks the matching never
saw?

## Why it matters

Every finding so far converges on the same place. The corrected joint tests
reject in all four samples (H003 era), the magnitude barely clears chance
reassignment and fails outright on peak (H001), and the breakdown value under
Rambachan–Roth sits between 0.044 and 0.151 (H002). None of that says the toll
had no effect; it says the naive control pool cannot answer the question.

D2 is the remaining route to an answer. If controls chosen on pre-treatment
behaviour give flat held-out leads, the study has a credible comparison group
and Phase 9 becomes meaningful. If they do not, the honest conclusion is that
this link roster cannot support the frozen design, and the study reports that
instead of an estimate.

The held-out split is what separates this from fitting to the test. Choosing
controls to make a pre-trend test pass, then reporting that same test, is
circular — and Roth (2022) shows the survivor of such a selection can be *more*
biased than an unselected one. Fitting on one stretch of the pre-period and
judging on another the matching never touched is the guard.

## Prediction

*Frozen once results exist.*

Weak expectation of failure, held with low confidence. Trend matching on 24
weeks should improve held-out flatness relative to the naive pool, but probably
not enough to stop the joint test rejecting, because the rejections so far are
large (χ² 42–79 on 11 df) and because the held-out window is October–December,
which carries the holiday dynamics already suspected of driving part of the
problem.

Genuinely uncertain about the ordering across samples, and about whether the
synthetic-weight rule beats the nearest-neighbour rule. No prediction offered on
either.

## Method

**Boundary exclusion, first.** Any control link within **500 m** of the 60th
Street line is removed from the donor pool before matching, so diversion cannot
contaminate the comparison. The existing distance audit finds none within 500 m
and nine within 1 km, nearest about 808 m, so this is expected to exclude
nothing on the current roster — a coverage limitation to report, not evidence of
cleanliness. 250 m and 1 km are reported as sensitivities.

**Windows.** 36 contiguous pre-treatment weeks are available (2024-05-01 to
2025-01-04).

- **Matching window:** event weeks k = −36 … −13 (24 weeks). Features are built
  here and nowhere else.
- **Held-out window:** event weeks k = −12 … −2 (11 weeks). Never seen by the
  matching. This is the same window the event study's joint test uses.

**Features.** Computed per link on the matching window only:

1. Weekly mean of the hourly median speed, **demeaned by that link's own
   matching-window mean**. Levels differ roughly twofold between treated and
   control, and DiD identifies off changes, so the trajectory shape is the
   object of interest and the level is not.
2. Week-over-week first differences of (1).
3. Hour-of-day profile: mean speed by hour, demeaned by the link's own mean.
4. Weekday-minus-weekend mean speed difference, demeaned likewise.

All features standardised across links before any distance is computed.

**Two candidate rules**, both frozen, reported side by side:

- **A — nearest neighbour.** Euclidean distance in standardised feature space
  from each control link to the treated group's mean feature vector. Keep the
  nearest **60** donors. Sixty is chosen to be a substantial minority of the 183
  available, large enough for clustered inference and small enough to be
  selective; it is a design choice, not a calibrated optimum.
- **B — synthetic weights.** Non-negative weights over control links summing to
  one, minimising squared distance between the weighted control weekly
  trajectory and the treated weekly trajectory across the matching window
  (Abadie, Diamond & Hainmueller 2010). Links with weight below 0.001 are
  dropped from the reported roster.

**Evaluation.** For each rule, re-run the existing event-study specification
restricted to that donor set and compute the joint pre-trend test **on the
held-out window only** (k = −12 … −2), with the same full cluster-robust
covariance Wald test used elsewhere. Report the naive pool under the identical
held-out test as the baseline comparator.

**No post-treatment outcome is examined, and no post-treatment coefficient is
computed, until the held-out verdict is written into this record.** That
ordering is the point of the exercise and is checkable in the commit history.

## Acceptance criteria

*Frozen once results exist.*

Judged on the `all` sample, with peak, offpeak and weekend reported alongside.

- **Supports** — at least one rule gives a held-out joint pre-trend test that
  fails to reject at the 5% level, and does so while retaining enough donors for
  clustered inference (at least 30 control links). The frozen design has a
  credible comparison group and Phase 9 can proceed on it.
- **Refutes** — both rules still reject on the held-out window. Pre-treatment
  matching on this roster does not deliver parallel trends, and the study should
  report that the available link panel cannot support the frozen design rather
  than continue searching for a control set that passes.
- **Uninformative** — fewer than 30 donors survive either rule, the matching and
  held-out windows cannot be separated cleanly, the weight optimisation fails to
  converge, or the held-out test is degenerate (rank-deficient covariance, or
  too few observed weekly bins). Report as a limitation of the panel.

A p-value between 0.05 and 0.10 counts as rejecting for this purpose. The
threshold is fixed in advance precisely so it cannot be relaxed afterwards to
accommodate a near miss.

**Not licensed by a "supports" verdict:** flat held-out leads are evidence for
parallel trends, not proof of it. H001's finding that clustered standard errors
run up to 1.5× too tight applies to this test as well, so a marginal pass should
be read as weaker than its nominal p-value. Any subsequent causal estimate still
needs the Rambachan–Roth sensitivity re-run on the new control set.

## Data required

The 12-month verified archive already held (2024-05 … 2025-04), giving 36
contiguous pre-treatment weeks. The frozen design asks for 24 pre-treatment
months and this is eight, so the matching window is 24 weeks rather than years.
That is a real limitation: a rule validated here may not survive on the full
window, and this analysis should be re-run when the backfill reaches 2023-01.

## Result

*Empty until run.*

## Verdict

*Empty until run.*

## Notes

Relationship to the other records: H001 bounds how surprising the magnitude is,
H002 bounds how much violation the estimate tolerates, H003 shows the precision
does not survive collapsing. All three describe the *current* comparison. H004
is the first that tries to build a better one.

The held-out window is October–December 2024, which includes Thanksgiving and
the run-up to New Year. That makes it a demanding test, which is a virtue, but
it also means a failure here is confounded with holiday dynamics and cannot by
itself establish that trend matching is hopeless. If both rules reject, the
sensible follow-up is to repeat the split on a non-holiday held-out window once
the backfill provides one, rather than to conclude the approach is dead.

Reference for rule B: Abadie, Alberto, Alexis Diamond and Jens Hainmueller
(2010). "Synthetic Control Methods for Comparative Case Studies." *Journal of
the American Statistical Association* 105(490):493–505.
https://doi.org/10.1198/jasa.2009.ap08746
