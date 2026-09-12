# H002 — How large a parallel-trends violation would it take to overturn the estimate?

| | |
|---|---|
| **Status** | answered |
| **Registered** | 2026-09-12 |
| **Registered by** | Claude Opus 5 session (methodology review) |
| **Answered by** | Claude Opus 5 session, 2026-09-12, on the 12-month verified archive |
| **Supersedes / superseded by** | none |

## Question

Under Rambachan & Roth (2023), post-treatment violations of parallel trends are
bounded relative to the violations actually observed in the pre-period. What is
the **breakdown value** `M̄` — the largest relative violation at which the 95%
robust confidence set for the treatment effect still excludes zero?

## Why it matters

The README currently states that the implemented design cannot support a causal
claim. That conclusion rests on a binary rejection of a joint pre-trend test,
which is the weakest available basis for it. Roth (2022) shows such tests are
often underpowered against violations large enough to matter, and that
conditioning on one can leave the surviving estimate *more* biased than not
testing at all. The project is architected around exactly that gate.

A breakdown value replaces the binary with a magnitude, and the statement
improves whichever way it lands:

- `M̄` near zero — the design is confirmed uninformative, but now quantitatively,
  and the claim stops depending on a test the literature warns against leaning on.
- `M̄` meaningfully above 1 — the effect survives post-treatment violations
  *larger* than those actually observed pre-treatment, which is a qualified but
  real finding that the current write-up would be wrong to have foreclosed.

Either outcome is more defensible than what stands today.

## Prediction

Breakdown value low — most likely below 0.5, plausibly at or near zero, meaning
the robust confidence set includes zero even under violations smaller than those
observed. The corrected joint tests reject hard in all four samples (χ² 42–79 on
11 df), so the observed pre-period violations are large, and `M̄` is measured
relative to them.

Less confident about the ordering across samples. Peak rejects least hard
(χ²=57) and weekend least of all (χ²=42), so those may show the highest
breakdown values, but the relationship between a joint test statistic and a
breakdown value is not monotone and this is a guess.

## Method

Rambachan & Roth (2023) sensitivity analysis on the existing event-study
coefficients.

Inputs are the vector of event-time coefficients and **the full cluster-robust
variance-covariance matrix** — not the diagonal standard errors. The 2026-09-12
audit corrected the joint test to use the full covariance, so the matrix exists;
it needs persisting to disk, which it currently is not.

Report under both restriction families:

- **Relative magnitudes (`M̄`)** — post-treatment violation bounded as a multiple
  of the largest observed pre-treatment violation. This is the primary result.
- **Smoothness (`M`)** — bounds the curvature of the violation path. A secondary
  reading, since a cordon toll has no obvious reason to produce a smoothly
  accelerating differential trend.

Run for all four samples. Report the breakdown value and the robust confidence
set at a few fixed values of `M̄` (0, 0.5, 1, 2), so the shape is visible rather
than just the threshold.

Implementation: the `diff-diff` Python package provides this; the original
reference implementation is the R package `HonestDiD`. Python only, per the
project constraints. If the package cannot consume this project's inputs
directly, implementing the relative-magnitudes case is tractable, but say so
rather than silently substituting a different method.

## Acceptance criteria

- **Supports** — breakdown value above 1 in at least one pre-specified sample,
  with the robust confidence set excluding zero. The effect survives violations
  larger than those observed pre-treatment.
- **Refutes** — breakdown value at or near zero across all samples. The robust
  confidence set includes zero even under minimal assumed violation, confirming
  the design is uninformative about the effect's sign or size.
- **Uninformative** — the method cannot be applied faithfully: the covariance
  matrix is rank-deficient, the pre-period has too few usable event-time bins,
  or the endpoint bins pool so many weeks that "observed pre-treatment violation"
  has no stable meaning. Report this as a result about the panel, not a failure
  to complete the task.

Note on `M̄` between 0 and 1: this is a real region, not a tie. It means the
conclusion survives only if post-treatment violations are *smaller* than what
was already observed — a weak position worth stating precisely rather than
rounding to either verdict.

## Data required

None beyond the eight months already held. Runs on the current panel and does
not wait on the backfill. Should be re-run once the contiguous pre-period lands,
because the observed violations it calibrates against will change.

## Result

Run on the rebuilt 12-month panel (2024-05 … 2025-04) from the verified
release archive: 36 contiguous pre-treatment weeks, so every tested bin from
k = −12 to −2 is a genuinely observed week rather than a pooled endpoint. 11
pre bins, 13 post bins, 331 link clusters. Covariance positive definite in every
sample (minimum eigenvalue 2.3e-03 to 5.4e-03), so the bounds are identified.

`src/analysis/honest_did.py`; artefacts `outputs/tables/H002_honest_did.csv`,
`H002_honest_did_grid.csv`, `outputs/figures/H002_honest_did_*.png`.

**Breakdown values** — the smallest violation at which the robust confidence
set stops excluding zero:

| Sample | relative magnitudes | smoothness |
|---|---:|---:|
| all | **0.083** | 0.034 |
| peak | **0.044** | 0.024 |
| offpeak | **0.054** | 0.024 |
| weekend | **0.151** | 0.034 |

**Robust confidence sets** across the grid (relative magnitudes, mph):

| Sample | M = 0 | M = 0.5 | M = 1 | M = 2 |
|---|---|---|---|---|
| all | [0.50, 1.65] | [−2.42, 4.57] | [−5.35, 7.49] | [−11.19, 13.34] |
| peak | [0.22, 1.66] | [−2.10, 3.97] | [−4.42, 6.29] | [−9.06, 10.93] |
| offpeak | [0.33, 1.50] | [−2.93, 4.76] | [−6.19, 8.02] | [−12.72, 14.55] |
| weekend | [0.91, 2.07] | [−2.08, 5.07] | [−5.08, 8.07] | [−11.08, 14.07] |

At M = 0 — parallel trends imposed exactly — every interval excludes zero, which
simply restates the Phase 7 result. Allowing any appreciable violation destroys
it: by M = 0.5 the intervals are two to five mph wide on either side of zero,
an order of magnitude wider than the estimate they are bounding.

## Verdict

**Refutes.** Breakdown values run 0.044 to 0.151, far below the registered
threshold of 1 and below any value that could be called robust.

Read plainly: the estimate survives only if post-treatment differential drift
stays under roughly 4 to 15 percent of the largest differential movement already
visible in the pre-period. The pre-period violations are not small — the joint
tests reject hard in every sample — so this is a demand that the counterfactual
behave far better after tolling than it demonstrably did before. Nothing about
this setting justifies that assumption.

The prediction was right on magnitude and half right on ordering. It expected
values "below 0.5, plausibly at or near zero", which held everywhere. It guessed
weekend and peak might rank highest; weekend is indeed highest at 0.151, while
peak came out lowest at 0.044. The record flagged that ordering as a guess.

**This strengthens rather than replaces the existing finding.** The README
already says the implemented design cannot support a causal claim. That rested
on a binary test rejection, which Roth (2022) warns is a weak basis. It now
rests on a magnitude: the conclusion breaks under violations an order of
magnitude smaller than the ones the data already exhibit.

**It is not a causal null.** A low breakdown value says this design cannot
distinguish the effect from plausible differential drift. It says nothing about
whether congestion pricing raised speeds. A better control construction could
still recover an answer; that is D2, and it remains open.

**The true breakdown values are probably lower still.** H001 found the analytic
clustered standard errors too tight by up to a factor of 1.5. That same
covariance is the input here, so these robust sets are, if anything, too narrow.
The interaction anticipated in the Notes below runs in the direction that makes
the refutation stronger, not weaker.

## Notes

**Deferred 2026-09-12, same day as registration.** `M̄` is measured relative to
the pre-treatment violations actually observed, and those currently come from
three contiguous holiday-dominated months with endpoint bins pooling more
distant weeks. The yardstick this analysis calibrates against will change
substantially once the frozen window completes, so a result now would very
likely be superseded — spending a registered attempt for little information.
The "Uninformative" criterion above anticipated this; the sequencing judgement
was the part that was wrong.

Run this after the contiguous pre-period lands, not before. The question stands;
only the timing was misjudged.

Interacts with H001. If placebo-in-space shows the analytic standard errors
understate the true spread, the covariance matrix fed into this analysis is
itself too tight, and the robust confidence sets reported here will be too
narrow. Whichever runs second should say how the other's result bears on it.

This does not repair the design. It measures how badly it is broken, which is a
different and more useful thing than a p-value below a threshold.
