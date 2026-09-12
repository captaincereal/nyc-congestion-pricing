# H003 — Does temporal aggregation change the association or its precision?

| | |
|---|---|
| **Status** | proposed — blocked on original-eight source verification |
| **Registered** | 2026-09-12 |
| **Registered by** | Codex coordinating session, before implementation or execution |
| **Answered by** | Pending; independent fresh-context implementation |
| **Supersedes / superseded by** | none |

## Question

Do daily and collapsed pre/post versions of the existing speed comparison
materially change its point estimate or nominal uncertainty?

## Why it matters

Bertrand, Duflo and Mullainathan (2004, Quarterly Journal of Economics)
show how serial dependence can invalidate conventional DiD inference and
evaluate before/after averaging. The current hourly model already clusters
by link, allowing within-link serial dependence asymptotically. Aggregation
therefore tests robustness of weighting, temporal controls and nominal
precision; it does not automatically correct an unclustered hourly model.
Neither method addresses a common cordon-level shock or repairs failed trends.

## Prediction

Frozen before execution. With modest confidence, in the all-hours sample both
aggregate estimates will remain positive, within 0.25 mph of the common-roster
hourly reference, with standard errors no more than 1.5 times its standard
error. These are descriptive stability predictions, not predictions of a
causal effect or calibrated tests of estimator equality.

## Method

1. Use exactly the eight parts and the segment file whose hashes are frozen
   in `docs/verification_targets.json`: June and October–December 2024,
   January–April 2025. Require complete raw-count/deterministic-replay daily
   receipts and verified manifest records for all eight before execution.
   Build the panel from those parts only using the existing staging, geometry
   and hourly-median SQL. Include January 1–4 in pre-treatment. The treatment
   date remains January 5, 2025; no treatment/control reassignment is permitted.
2. Analyze the existing all, peak, offpeak and weekend cuts. Within each cut,
   restrict to treated/control links observed both pre and post, and use the
   same retained hours and link roster for all three specifications. Do not
   impute missing hours, impose minimum counts, trim speed, add weather, or
   construct controls. Report any exclusions and observation counts.
3. Hourly reference: existing two-way link and datetime fixed effects,
   equal link-hour weight, link-cluster covariance and existing finite-sample
   correction; report inference with t(G−1) critical values.
4. Daily: arithmetic mean of the hourly median outcome for each link and local
   calendar date, equal link-day weight, link and date fixed effects, and
   link-cluster covariance with the same correction convention and t(G−1).
   Daily treatment is treated × date-on/after-January-5. Daily averaging and
   replacing datetime effects with date effects change temporal composition;
   coefficient movement cannot be attributed only to serial correlation.
5. Collapsed: compute each link's direct mean across its available hourly
   median outcomes separately pre and post (do not first equally weight days).
   Regress the post-minus-pre difference on an intercept and treated status,
   equally weighting links. Use HC1 covariance and t(G−2) critical values.
   This avoids mechanically counting absorbed link effects again in a
   two-row-per-link finite-sample correction. Link weighting differs from the
   unbalanced hourly model and is part of this registered sensitivity.
6. Report beta, SE, 95% CI, two-sided p, observations, links by treatment,
   degrees of freedom, aggregation/reference beta difference, SE ratio, and
   CI inclusion of zero for every specification and cut. Preserve numerical
   failures as result rows with explanations. All-hours determines the
   summary verdict; the three other cuts are secondary and all are retained.
   No selection of a favorable cut or post-result threshold changes.

## Acceptance criteria

Frozen before execution; thresholds are descriptive alarms chosen here, not
cutoffs established by the cited literature.

- **Supports aggregation stability:** both all-hours aggregate coefficients
  are positive with absolute hourly-reference differences at most 0.25 mph,
  and both SE ratios are at most 1.5. Report magnitude and precision components
  separately. Nominal CI inclusion of zero is reported separately and never
  establishes zero effect, spatial independence, or causal identification.
- **Refutes aggregation stability:** either aggregate coefficient is zero or
  negative, either absolute difference exceeds 0.25 mph, or either SE ratio
  exceeds 1.5. Identify the failing component; this is not a test of no toll
  effect. A wider CI is not by itself evidence that the point effect is absent.
- **Uninformative:** the original-eight source gate fails, common pre/post
  support or identifying variation is absent, estimation fails to converge,
  covariance is not finite/positive, or the specified exercise cannot be
  reproduced. This outcome takes precedence over numerical comparisons.
  The exercise can support descriptive stability while remaining
  uninformative about causality; the latter limitation is always reported.

## Data required

The immutable eight-month archive is held but all eight were unverified at
registration (June has three of thirty daily receipts). Completion of source
verification gates execution. Additional backfill parts cannot enter H003.
The full January 2023 onward backfill remains a separate coverage requirement.

## Result

Pending.

## Verdict

Pending.

## Notes

Outputs are `outputs/tables/H003_*` and, if needed, `outputs/figures/H003_*`.
Record code commit, input hashes and source receipts with the results.
H001's available control-only placebo smoke run is related but does not test
the same sampling distribution: different group sizes and geographically
dispersed partitions can change its spread. Read existing results; do not
rerun H001 or relabel its exploratory tail fraction as an exact randomization
p-value. H002, D2 construction and all owner decisions remain deferred.

References, verified against the published papers:

- Bertrand, Marianne, Esther Duflo, and Sendhil Mullainathan (2004).
  “How Much Should We Trust Differences-In-Differences Estimates?”
  *Quarterly Journal of Economics* 119(1):249–275, especially §IV.C and Table VI.
  https://doi.org/10.1162/003355304772839588
- Cameron, A. Colin, and Douglas L. Miller (2015). “A Practitioner's Guide to
  Cluster-Robust Inference.” *Journal of Human Resources* 50(2):317–372.
  https://doi.org/10.3368/jhr.50.2.317
- MacKinnon, James G., and Matthew D. Webb (2020). “Randomization inference
  for difference-in-differences with few treated clusters.”
  *Journal of Econometrics* 218(2):435–450.
  https://doi.org/10.1016/j.jeconom.2020.04.024

## Owner-directed amendment — 2026-09-12, before execution

After registration and before any H003 data estimation, the owner specified:
“Daily aggregation (step 3): primary driver of final peak metric” and
“Peak result: main actionable output for downstream reasoning.”

This prospective amendment makes **peak** the primary decision sample and
the **daily peak coefficient and its uncertainty** the lead reported metric.
The hourly peak reference and collapsed peak estimate remain the registered
comparators. Apply the same prediction and the same joint descriptive
stability thresholds above to the peak cut instead of all-hours. All-hours,
offpeak and weekend remain fully reported secondary cuts. No estimator,
input, treatment, threshold or inference procedure changes. The original
registration above is retained for audit; this amendment controls the sample
priority. “Actionable” here means usable for downstream methodological
reasoning, not identified evidence of a causal toll effect. H001 is now
completed; inspect its completed result rather than treating its earlier
smoke run as the final exercise.
