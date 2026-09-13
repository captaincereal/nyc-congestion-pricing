# H005 — Do the breakdown values survive a two-year pre-period?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5 session |
| **Answered by** | — |
| **Supersedes / superseded by** | supersedes [H002](H002-honest-did-sensitivity.md) on the 27-month archive; H002's verdict stands for the 12-month one |

## Question

H002 found breakdown values of 0.044 to 0.151 on eight contiguous pre-treatment
months. The archive now holds 27 verified contiguous months with **96
pre-treatment weeks**. Does the Rambachan & Roth breakdown value change once the
violations it calibrates against are measured over nearly two years rather than
eight months?

## Why it matters

H002's own record deferred and then flagged this: the breakdown value is
measured *relative* to observed pre-treatment violations, so the yardstick moves
when the pre-period does. Its result was explicitly provisional on a longer
window.

The longer window also removes the main escape hatch. Every previous failure
carried the caveat that the pre-period was short and holiday-dominated. With 96
weeks that caveat is gone, and the answer — either way — is close to final for
this design.

## Prediction

*Frozen once results exist.*

Breakdown values stay well below 1, with moderate confidence. The corrected
joint pre-trend test on the long window rejects *harder* than on the short one
(χ² 45.6 to 100.2 against 43.6 to 87.1), so the violations being bounded against
have not shrunk.

Direction of change is genuinely uncertain and I offer no prediction on it. Two
effects push opposite ways: a longer pre-period gives more opportunities for a
large week-to-week move, which raises the maximum first difference in the
denominator and would *lower* the breakdown value; but more pre-periods also
estimate the coefficients more precisely, which tightens the covariance and
would *raise* it.

## Method

`src/analysis/honest_did.py` unchanged, on the rebuilt 27-month panel.

Three horizons, all frozen here:

- **±12 weeks — primary.** Directly comparable to H002; the only thing that
  differs is the panel underneath.
- **±26 weeks** and **±52 weeks** — secondary. These are what the longer
  pre-period actually buys: event-time bins that were pooled into the endpoint
  before are now genuine weekly estimates. Reported to show whether the
  conclusion depends on how much of the pre-period the restriction sees.

Relative magnitudes is the primary restriction family, smoothness secondary, as
in H002. Breakdown values plus robust confidence sets at M̄ ∈ {0, 0.5, 1, 2}.
All four samples.

Covariance must be positive definite at each horizon; a longer horizon estimates
more coefficients from the same clusters, so this is not guaranteed and a
failure there is an outcome, not an error to work around.

## Acceptance criteria

*Frozen once results exist.*

Judged at the ±12 primary horizon, with ±26 and ±52 reported alongside.

- **Supports** — breakdown value above 1 in at least one sample with the robust
  set excluding zero. The estimate tolerates violations larger than those
  observed, and the design is not dead.
- **Refutes** — breakdown values remain below 1 across all samples. The
  conclusion from H002 holds on a pre-period long enough that window length can
  no longer be blamed.
- **Uninformative** — covariance rank-deficient at the primary horizon, or the
  package fails on inputs it accepted before. A failure confined to ±26 or ±52
  is not uninformative; it is a reportable limit on how many bins this panel
  supports, and the ±12 result still stands.

## Data required

The 27-month verified archive (2023-02 … 2025-04), rebuilt locally. 2023-01 is
still downloading and is not required: 96 pre-weeks already exceeds what the
±52 horizon needs.

## Result

*Empty until run.*

## Verdict

*Empty until run.*

## Notes

H001's finding that clustered standard errors run up to 1.5× too tight still
applies: that covariance is this analysis's input, so the robust sets here
remain, if anything, too narrow.

This does not repair the design. It measures how badly it is broken on data long
enough that shortness is no longer an excuse.
