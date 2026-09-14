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

## 2026-09-13 — H007 answered

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H007](H007-secondary-feed-diversion.md) | Can the secondary highway feed identify diversion onto toll-exempt in-zone routes? | answered | 2026-09-13 | Refutes: all three conditions fire in all four samples. Usable-hour availability diverges by 21.2 pp against a 5 pp bar; pre-trends reject (χ²=86.0, p=1e-13); breakdown M = 0.000–0.034 |

Supersedes the row above, which recorded H007 as proposed. **The gate that
failed first is availability, and it is the one the verdict rests on**: the
other two conditions are computed from a cluster-robust covariance on nine
treated clusters, the regime in which this record made randomization inference
primary because such asymptotics cannot be trusted. Criterion 1 is a count of
hours and needs no asymptotics.

Three of the nine treated links yield no usable speed after the toll — the
entire 11th/12th Avenue arm — and the break lands in May 2024, eight months
before tolling. This is a **measurement** failure rather than a
parallel-trends failure, which is the distinction the record was written to
draw. The ATT is +0.354 mph on all hours with a randomization p of 0.804, and
the design's 80%-power minimum detectable effect is 4.85 mph, so it could only
ever have seen very large diversion.

Seven hypotheses are registered and answered. Two sit in the queue above,
untouched. The restricted design suggested by H007's Verdict — treated limited
to the six links that report throughout — is **not** registered and must not be
run before it is.

## 2026-09-13 — registration appended

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H008](H008-toll-timing-bunching.md) | Do drivers retime entries to avoid the peak toll rate? | proposed | 2026-09-13 | |

The first hypothesis here that does not need a comparison group. It identifies
off the toll's own time-of-day price discontinuity, so it does not rest on
parallel trends — the assumption that H001 through H006 established this design
cannot satisfy — and it runs against a different dataset, the MTA entry counts,
so it is a fresh draw rather than another pass at the speed panel.

Eight hypotheses are registered. The record discloses that the weekday raw
discontinuities were seen during feasibility scoping before it was written, and
freezes its criteria on quantities not yet measured — chiefly the weekend 09:00
boundary, which is untouched and is the test that can tell a price from a clock.

### H008 answered, 2026-09-13

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H008](H008-toll-timing-bunching.md) | Do drivers retime entries to avoid the peak toll rate? | answered | 2026-09-13 | Uninformative: the primary 21:00 boundary (+12.9%) did not clear the placebo maximum (13.9%), so support cannot be claimed. Every surrounding test points the other way — weekend/weekday 09:00 discrimination 4.91x, 12 of 12 entry points correctly signed, 05:00 clearing placebos by 3.7x, and the response confined to cars and motorcycles |

Supersedes the row above, which recorded H008 as proposed. **The criterion that
failed was badly constructed and the record says so without reinterpreting it:**
it compares a point estimate to a *maximum* over twenty-one placebos, and that
maximum ranges from 0.05 to 0.25 across specifications while the estimate being
tested holds at +0.10 to +0.13. The placebo set includes the morning ramp, where
a local linear fit cannot track fivefold within-hour growth. A superseding
record should freeze a percentile instead, in advance.

The registered prediction that trucks would bunch harder than cars was **wrong**.
The response is entirely in cars and motorcycles; trucks, taxis and buses are
flat or wrong-signed. Taxis pay a per-trip surcharge and drive to a passenger's
schedule, freight runs to contracted windows, buses to a timetable.

Eight hypotheses are registered and answered. H008 is the first to use a design
that does not rest on parallel trends, and the first run against a dataset other
than the speed panel.

## 2026-09-13 — registration appended

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H009](H009-toll-timing-exempt-control.md) | Does the entry-timing response survive a control group that pays no toll? | proposed | 2026-09-13 | |

Supersedes [H008](H008-toll-timing-bunching.md), whose verdict of uninformative
stands and is not revised. H008's placebo set was the wrong instrument; this
record replaces it and says in advance why.

**The correction is not the point of this record, and the register should be
clear about that.** A percentile bar instead of a maximum would probably let
H008's 21:00 estimate through, and it was chosen by someone who already knew the
old bar had failed by 0.017 log points. A re-score is not a result. So the
primary criterion is a quantity never computed at any boundary: the difference
in discontinuities between tolled entries and the 38.7M `excluded_roadway_entries`
recorded at the same four detection points, on the same sensors and in the same
minutes, by vehicles that are never charged and face no price change.

Nine hypotheses are registered. The 21:00 discontinuity has now been examined
twice, and a reader is entitled to that count.

### H009 answered, 2026-09-13

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H009](H009-toll-timing-exempt-control.md) | Does the entry-timing response survive a control group that pays no toll? | answered | 2026-09-13 | Does not support **as specified**, and none of the three branches fits. Criterion 2 required a control series to show no *significant* same-direction movement, which 609 days and 125M entries can never deliver. Refute 1 encoded the same test correctly, with a magnitude threshold, and did not fire |

Supersedes the row above, which recorded H009 as proposed.

**The substantive result is strong and is stated separately from the verdict.**
At 05:00 tolled and exempt entries move in **opposite directions** on the same
sensors in the same minutes — tolled −0.6889, exempt +0.0701, difference −0.7589
[−0.7946, −0.7232] — consistently at all four dual-recording points. No clock,
batching artefact or polynomial misfit produces that, because each would move
both series together. At 21:00 the design separated a shared evening rhythm of
5.6 log points from a price-attributable 7.1, which H008's raw 12.7 conflated.
Both persist across 2025 and 2026.

**Two consecutive records have had flawed criteria and the register should say
so plainly.** H008 compared a point estimate to a maximum over a contaminated
placebo set; H009 required a significant zero. Both are gates built on the wrong
scale — tail statistics and significance where magnitude thresholds belonged.
One is bad luck; two in a row by the same author within an hour is a systematic
weakness in drafting, and it should discount the pre-registration value of both.
It is also why no H010 re-runs this comparison with the criterion rewritten:
the estimate would not move, only the label, and the label would then have been
chosen by someone who already knew it.

Nine hypotheses are registered and answered. The 21:00 discontinuity has been
examined twice and the reader is entitled to that count.

## 2026-09-14 — the timing thread is adjudicated, and route substitution is registered

No hypothesis was re-scored and no specification was run against the data.

**[ADJUDICATION-timing.md](ADJUDICATION-timing.md)** is a reader's verdict on
H008, H009 and the register entries above, written by a session that did not
write either record. `docs/agent_handoff.md` asked for one on the ground that
the author of two flawed criteria should not be the one deciding what they
amount to. It leaves both verdicts standing — H008 uninformative, H009 does not
support as specified — and reaches a judgement about the underlying evidence
that the verdicts do not carry.

It finds the retiming response supported and **reverses which boundary carries
it**. Every document in this project currently leads with 05:00 and its
difference of −0.759 as the cleanest identification here. The adjudication puts
21:00 first and demotes 05:00 to real in direction and unreliable in magnitude.

Three things it drew on that the records did not, none of them a new draw. The
frozen H009 run estimated the difference in discontinuities at all 24 boundaries
and reported two; against the other 22, the 21:00 difference is **the most
positive of all 24**, with the next most positive a fifth of its size, while
seven placebo boundaries exceed it in absolute value and all seven run the other
way. Synthetic fixtures show the estimator returns exactly zero on a shared jump,
as H009 argues, and passes **differential curvature straight through** at
exactly the curvature gap ÷ 6, which H009 argues is impossible — and 06:00,
07:00 and 08:00 carry the same opposite-direction signature the record calls
decisive, at a quarter to a third of the magnitude. The raw block profile shows
the fitted estimate is 1.18× the model-free jump at 21:00 and 1.63× it at 05:00.

| ID | Title | Status | Registered | Verdict |
|---|---|---|---|---|
| [H010](H010-exempt-route-substitution.md) | Do drivers move onto toll-exempt roadways as the peak charge begins? | proposed | 2026-09-14 | |

H009 flagged exempt entries rising at 05:00 as the project's first direct
evidence of route substitution and claimed it nowhere. The decision register and
the handoff repeat the claim; the README says the opposite, that diversion is
unidentified on both feeds. This record tests it, in **vehicle counts rather
than log points**, because a substitution claim has to balance in vehicles.

Its author had seen every previously computed number at these boundaries and the
record discloses each one, including the two of four detection points where the
exempt rise is negative and the 21:00 mirror that runs against the simple
diversion story. The criteria rest on two quantities nobody has measured: the
count-based diversion share, and whether the exempt surplus is made of the
vehicle classes H008 showed respond to the price. Criterion 2 carries a
**feasibility gate declared in advance** — a baseline share above 0.90 makes it
unreachable, and it is then recorded as untestable rather than failed. Two
records here have frozen criteria a true effect could not satisfy, and the
damage came from nobody noticing until afterwards.

Ten hypotheses are registered, nine answered. The 05:00 boundary has now been
examined four times and the reader is entitled to that count.
