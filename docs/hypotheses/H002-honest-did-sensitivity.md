# H002 — How large a parallel-trends violation would it take to overturn the estimate?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-12 |
| **Registered by** | Claude Opus 5 session (methodology review) |
| **Answered by** | — |
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

*Empty until run.*

## Verdict

*Empty until run.*

## Notes

Interacts with H001. If placebo-in-space shows the analytic standard errors
understate the true spread, the covariance matrix fed into this analysis is
itself too tight, and the robust confidence sets reported here will be too
narrow. Whichever runs second should say how the other's result bears on it.

This does not repair the design. It measures how badly it is broken, which is a
different and more useful thing than a p-value below a threshold.
