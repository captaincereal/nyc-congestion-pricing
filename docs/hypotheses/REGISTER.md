# Hypothesis register

Append-only. Every registered hypothesis appears here whatever its verdict.
Protocol in [README.md](README.md).

The count matters as much as the contents. A clean finding after fifteen
attempts means something different from a clean finding after one, and a reader
cannot tell the difference from the finding alone.

## Registered

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H001](H001-placebo-in-space.md) | Is the DiD estimate larger than chance reassignment of control links? | answered | 2026-09-12 | Intermediate: magnitude beats chance in 3 of 4 samples, peak does not (p=0.09); analytic SEs too tight by <=1.5x |
| [H002](H002-honest-did-sensitivity.md) | How large a parallel-trends violation would it take to overturn the estimate? | answered | 2026-09-12 | Refutes: breakdown M = 0.044-0.151 across samples, far below 1. The estimate survives only violations 4-15% the size of those already observed pre-treatment |

## Queue — considered, not yet registered

These are candidates, not commitments. A queue entry becomes a record when
someone is about to run it, via the `research-prompt` skill, which forces the
prediction and acceptance criteria to be written first.

- **Synthetic control / synthetic DiD.** One cordon, one date, every treated
  link sharing one shock: structurally a comparative case study rather than a
  many-treated-units panel. These estimators construct parallel pre-trends by
  weighting instead of assuming them, which targets the observed failure
  directly (a 2x level gap and rejected leads).
- **Serial-correlation collapse.** Bertrand–Duflo–Mullainathan: collapse the
  panel to one pre and one post observation per link and re-estimate. If the
  estimate survives with honest uncertainty, the hourly specification is not
  merely borrowing significance from serial correlation.
- **Outcome weighting.** Hourly median speed treats a lightly used link the
  same as a heavy corridor. Whether a flow- or length-weighted outcome changes
  the picture bears on how the result should be described, whatever it is.


## 2026-09-12 — registration appended

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H003](H003-temporal-aggregation.md) | Does temporal aggregation change the association or its precision? | answered | 2026-09-12 | Refutes: daily is stable (<=0.14 mph, SE ratio <=1.39) but collapsing to one pre/post per link inflates SEs 3.8-6.2x, every CI covers zero, offpeak flips sign |
| [H004](H004-control-construction.md) | Can controls chosen on pre-treatment behaviour produce flat held-out leads? | answered | 2026-09-12 | Refutes: both rules reject out of sample everywhere. Nearest-neighbour made it worse; synthetic weights halved chi2, fit the matching window exactly, and still rejected at p=4.4e-07 |
| [H005](H005-honest-did-long-preperiod.md) | Do the breakdown values survive a two-year pre-period? | answered | 2026-09-13 | Refutes: 0.005-0.171 across horizons and samples. At matched horizon the longer pre-period barely moved them; widening the horizon lowers them monotonically |
| [H006](H006-control-construction-clean-holdout.md) | Does control matching fail on a holdout that is not holiday-dominated? | answered | 2026-09-13 | Refutes: every rule rejects on the clean July-September holdout. Holidays roughly double the statistic but do not cause the failure |

The serial-correlation-collapse queue entry above is now represented by H003;
the historical queue and the other registrations are preserved. Three
hypotheses are registered. H002 remains deferred until the contiguous pre-period.

2026-09-12, H003 prospective amendment before execution: at the owner's
direction, peak replaces all-hours as the primary decision sample and daily
peak becomes the lead metric. Estimators and stability thresholds are unchanged;
all cuts remain reported. The registration retains the original text and
the dated amendment. H002 remains deferred.

## 2026-09-13 — registration appended

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H007](H007-secondary-feed-diversion.md) | Can the secondary highway feed identify diversion onto toll-exempt in-zone routes? | proposed | 2026-09-13 | |

Phase 10's first record. This is the spillover question the primary roster
cannot answer — no control link lies within 808 m of the cordon — put to the
one source that covers the exempt routes diverted traffic would use. It is
registered against data already held and is not blocked on the backfill.
