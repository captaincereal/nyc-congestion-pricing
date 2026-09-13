# Owner-decision prompt

A prompt for handing D1, D2, D3, D5, D6 and D7 to a model for a second opinion.
Written 2026-09-13 against the completed 44-month archive; the figures below are
quoted from commit `089f89b`'s artefacts and from `docs/data_quality_report.md`
as regenerated on that run.

**This is not a hypothesis record and it is not in the register.** It runs no
analysis against the dataset, so it adds nothing to the multiplicity count. It
also does not decide anything: `docs/project_brief.md` reserves these six to the
owner, and the point of that reservation is that a person weighs them. The
prompt therefore asks for recommendations and reasoning, and the owner records
the decision afterwards with a dated entry in `docs/decision_register.md`.

Before reusing it, check the "what has changed" section still holds. It is the
part most likely to go stale, and a model reasoning from the original
2026-09-12 memo alone will reach the wrong answer on at least three of the six.

Two things to expect from a good answer. D7 is already executed, D2's
construction work is done and negative twice over, and D3's sensitivity measures
at roughly 0.001 mph — so three of the six should come back close to automatic,
and six weighty deliberations is a sign of padding rather than reading. The one
that deserves real scrutiny is D1: the quality filter raises the estimate from
+0.849 to +0.963 and tightens the standard error from 0.239 to 0.183, which
makes it the only one of the six that visibly moves the headline.

---

```
You are advising the owner of a causal-inference study on six open design
decisions. Your job is to RECOMMEND, with reasoning. You are not adopting
anything: the owner records the decision afterwards, and that separation is
deliberate.

Repository: github.com/captaincereal/nyc-congestion-pricing
If you have it checked out, read these first:
  docs/owner_decisions.md      the six recommendations as originally written
  docs/decision_register.md    the evidence trail and dated entries
  README.md                    the current public finding
  docs/project_brief.md        what is frozen and may not be changed
  docs/hypotheses/REGISTER.md  seven answered hypotheses

## The study, in brief

Difference-in-differences on NYC's Congestion Relief Zone toll (tolling began
2025-01-05), on a link x hour panel of hourly median speeds from NYC DOT E-Z
Pass local-street readers.

The finding, which is settled and NOT up for discussion: speeds inside the zone
rose about +1.05 mph relative to comparison streets (SE 0.27, 95% CI 0.53-1.57,
~11% of a 9.88 mph pre-treatment mean, 7.95M link-hours, 334 clusters). That
association is robust. It CANNOT be attributed to the toll. The joint test that
pre-tolling leads are zero rejects in all four samples (chi2 97.9 all, 69.7
weekday peak, 102.2 weekday off-peak, 46.7 weekend, 11 dof, weakest p 2.4e-06).

Seven pre-registered hypotheses agree. Do not propose reopening identification,
and do not propose searching for a control set that passes: the dataset is
fixed, every specification is another draw, and the register would have to carry
the count.

## What has changed since the memo was written on 2026-09-12

This matters more than anything else in this prompt. Three of the six rest on
premises that are no longer true.

- The archive is now COMPLETE: 44 of 44 frozen months, 2023-01 through 2026-08,
  all verified. 24 pre-treatment months (104 weeks) and 20 post. When the memo
  was written only 8 of 44 months were held.
- D7 ("complete the frozen window beginning January 2023") has therefore already
  been executed. Decide what, if anything, is left of it.
- D2 said "wait for the contiguous pre-period to evaluate this recommendation."
  That wait is over, and the evaluation has been done twice: H004 and H006 both
  REFUTE. Controls matched on pre-treatment behaviour reject out of sample
  everywhere; nearest-neighbour made held-out flatness worse; synthetic weights
  fit the matching window to a squared loss of exactly zero and still rejected at
  p=4.4e-07. H006 repeated it on a clean July-September holdout with a
  seventy-week matching window and every control set still rejected.
- Diversion was tested and is also unidentified (H007), for a different reason:
  the secondary feed stops reporting speeds on three of the nine toll-exempt
  in-zone links across the toll date, so usable-hour availability diverges by
  21.2 points against a pre-registered 5-point bar. A measurement failure, not
  an identification one.

## Current measured evidence, from committed artefacts

Robustness specifications (outputs/tables/robustness_comparison.csv). Ten hold
the October 2024 - April 2025 window fixed so they vary one thing at a time:

  contiguous_baseline     +0.849 (SE 0.239)
  quality                 +0.963 (SE 0.183)   >=3 readings/hr, >=4 probes/reading
  no_extreme_readings     +0.932 (SE 0.234)   drop hours with any reading >80 mph
  eleventh_as_treated     +0.850 (SE 0.237)   the D3 reassignment
  manhattan_controls      +0.476 (SE 0.240, p=0.049)
  outer_borough_controls  +0.881 (SE 0.251)
  all_available           +1.048 (SE 0.266)   full 44-month archive

Data quality on the complete archive (docs/data_quality_report.md):
  10.88% of readings have <=3 probes
  0.1976% of readings exceed 80 mph; maximum observed 11,674.7 mph
  0.028% are zero speed
  Duplicate-key and unmatched-segment checks both pass

## The six decisions

Read docs/owner_decisions.md for the full text. In short:

  D1  Retain the unfiltered hourly median as the primary outcome, and report
      probe-depth and 80 mph ceiling as separate sensitivity specifications
      rather than folding them into the primary.
  D2  Develop controls by pre-treatment matching with held-out validation,
      rather than promoting the naive pool or picking the pool with the most
      favourable post-treatment coefficient.
  D3  Reclassify four northern 11th Avenue surface segments (108104, 116080,
      80108, 81116) from exempt into treated. The blanket "11th/12th Ave"
      exemption conflates these local streets with Route 9A, which is genuinely
      toll-exempt. Inference from MTA sources and segment geometry.
  D5  Keep the two Williamsburg Bridge directions as separate outcomes in any
      exploratory crossing analysis rather than pooling them.
  D6  Normalise only derived corridor labels, via an auditable lookup, and only
      when corridor analysis begins. Keep original names and IDs intact.
  D7  Complete the frozen window beginning January 2023 rather than extending
      back into 2021-22 COVID-recovery years.

D4 was resolved before this work began.

## What to give me

For each of D1, D2, D3, D5, D6, D7:

1. ADOPT, ADOPT WITH MODIFICATION, REJECT, or MOOT — and if moot, say what
   already settled it.
2. Your reasoning in a short paragraph, citing the specific number or artefact
   that drives it.
3. What changes in what the study reports if the owner chooses the opposite.
   If nothing changes either way, say so plainly — that is a useful answer and
   means the decision can be recorded cheaply.
4. Anything the memo asserts that the current evidence contradicts.

Then, separately: which of the six actually matter for the published finding,
and which are housekeeping. Rank them. The owner's time is the scarce resource.

## Constraints

- Recommend; do not adopt. Write as advice to a person who will record the
  decision themselves.
- Nothing may cost money, and nothing may change what docs/project_brief.md
  marks frozen (research question, treatment date, primary outcome, unit of
  analysis, treatment and control definitions, estimator). If your advice would
  require changing a frozen item, say so explicitly and explain why it is worth
  the cost.
- A "do nothing" or "this is already settled" recommendation is a good outcome.
  Do not manufacture a change to look useful.
- Cite with author, year and venue. Flag anything you cannot cite precisely
  rather than guessing; this domain invites confident fabrication.
- Do not propose new specifications against this dataset. If you believe one is
  genuinely missing, say so in one sentence and note that it would need
  pre-registration first.
```
