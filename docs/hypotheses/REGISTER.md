# Hypothesis register

Append-only. Every registered hypothesis appears here whatever its verdict.
Protocol in [README.md](README.md).

The count matters as much as the contents. A clean finding after fifteen
attempts means something different from a clean finding after one, and a reader
cannot tell the difference from the finding alone.

## Registered

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H001](H001-placebo-in-space.md) | Is the DiD estimate larger than chance reassignment of control links? | running | 2026-09-12 | — |
| [H002](H002-honest-did-sensitivity.md) | How large a parallel-trends violation would it take to overturn the estimate? | deferred — needs contiguous pre-period | 2026-09-12 | — |

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
- **D2 control construction with held-out validation.** Blocked until the
  contiguous pre-period lands; see `docs/owner_decisions.md`.

## 2026-09-12 — registration appended

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H003](H003-temporal-aggregation.md) | Does temporal aggregation change the association or its precision? | proposed — source verification gate | 2026-09-12 | Pending |

The serial-correlation-collapse queue entry above is now represented by H003;
the historical queue and the other registrations are preserved. Three
hypotheses are registered. H002 remains deferred until the contiguous pre-period.

2026-09-12, H003 prospective amendment before execution: at the owner's
direction, peak replaces all-hours as the primary decision sample and daily
peak becomes the lead metric. Estimators and stability thresholds are unchanged;
all cuts remain reported. The registration retains the original text and
the dated amendment. H002 remains deferred.
