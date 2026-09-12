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

## Queue — considered, not yet registered

These are candidates, not commitments. A queue entry becomes a record when
someone is about to run it, via the `research-prompt` skill, which forces the
prediction and acceptance criteria to be written first.

- **Rambachan–Roth sensitivity.** The pre-trend test rejects in all four
  samples. Rather than treating that as a gate, bound how large a post-treatment
  violation would have to be, relative to observed pre-treatment violations, to
  overturn the conclusion, and report the breakdown value. A breakdown value
  near zero is a real and reportable finding about this design.
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
