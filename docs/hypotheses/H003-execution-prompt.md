# Independent execution prompt for H003

Implement and execute the one registered question in
`docs/hypotheses/H003-temporal-aggregation.md`: does daily or collapsed
pre/post aggregation change the existing speed association or its nominal
precision? Read that record, the hypothesis protocol, existing estimator and
SQL. Its prediction, exact methods and acceptance criteria are frozen.

Use only the eight hash-bound original parts and geometry in
`docs/verification_targets.json`. Before any real estimation, require the
strict `verification_summary` gate to pass. Implementation and synthetic
tests can precede gate completion. Rebuild an isolated panel from exactly
those inputs; additional backfill months must not enter this exercise.

Predict positive aggregate coefficients within 0.25 mph of the common-roster
hourly reference and SE ratios at most 1.5 in all-hours. Both thresholds must
hold for descriptive support. A threshold failure refutes stability; source,
support, identification or numerical failure is uninformative and takes
precedence. Report the point and precision components separately, with all
95% CIs and their inclusion of zero. The full record controls any ambiguity.

Use Python, zero dollars, standard free public GitHub runners, resumable and
unattended. Do not execute H002, construct D2 controls, adopt D1–D7, alter raw
parts, add filtering or weather, or search for a favorable specification.
Keep every failed/null result. Outputs must start H003_. Record code and input
hashes and update only Result/Verdict and status after execution; append the
register history. A documented inability to identify the effect is successful
work. Treat daily weighting/date effects and collapsed equal-link weighting
as estimand changes, not a pure SE repair. Existing link-cluster SEs already
allow within-link serial correlation under their asymptotic assumptions.

Read H001's available result and explain complementarity and limitations;
do not rerun it. Cite author, year and venue precisely, and flag uncertain
references. The registration lists verified methodological citations.
