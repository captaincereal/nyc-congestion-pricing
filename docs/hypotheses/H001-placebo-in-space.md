# H001 — Is the DiD estimate larger than chance reassignment of control links?

| | |
|---|---|
| **Status** | running |
| **Registered** | 2026-09-12 |
| **Registered by** | Claude Opus 5 session (repo automation / methodology review) |
| **Answered by** | — |
| **Supersedes / superseded by** | none |

> **Registered after implementation.** The protocol in `README.md` did not exist
> when this analysis was written, and the code was committed first (`b486854`).
> The prediction below was stated in conversation before the 500-draw run
> produced numbers, but it does not have the commit-order guarantee that later
> records will. Treat its pre-registration as weaker than the protocol requires.
> Recorded this way rather than backdated.

## Question

The frozen specification clusters standard errors by link and reports
ATT +0.85 mph with p = 0.0004. Does a randomly chosen set of control links,
switched on at the real tolling date, produce estimates that large as often as
chance alone would suggest?

## Why it matters

Clustering by link treats 148 tolled links as 148 independent draws. One cordon
began tolling on one date, so every treated link shares a single shock and the
effective number of independent treated clusters is far nearer one. Cluster-
robust t tests over-reject badly in that regime (MacKinnon & Webb 2020).

If the analytic standard error substantially understates the spread that chance
reassignment produces, then every p-value in Phase 7 is overstated and the
study's stated precision is wrong independently of the parallel-trends problem.
That changes how the result must be described even if the point estimate stands.

## Prediction

The analytic clustered standard error understates the placebo spread — `se_ratio`
above 1, plausibly well above. The randomisation p-value is expected to be
orders of magnitude larger than the analytic p, while possibly still below 0.05.

Stated before the 500-draw run. The 40-draw smoke test on the weekend sample had
already shown `se_ratio` 1.44 and randomisation p 0.024 against an analytic
3.8e-06, so this prediction is partly informed rather than blind.

## Method

`src/analysis/placebo_space.py`. For each of 500 draws per sample: restrict to
control links, label a random subset "treated" at the real tolling date, and
re-estimate the frozen two-way FE DiD. The draw size preserves the real treated
share (81 of 177 controls) rather than copying the treated count, because
drawing 148 from 177 would leave 29 as the comparison group and make every draw
nearly the same set.

Real treated links are excluded from the placebo pool, so the effect under test
cannot leak into its own null. Each draw relabels a whole set of links at one
date, so the reference distribution inherits the panel's serial correlation,
spatial correlation and single-common-shock structure.

Both coefficient-based and t-based randomisation p-values are reported. The
t-based one is the more reliable when the treated group is atypical of the pool,
which here it is: treated links sit near 7.9 mph against controls near 15.6.

Seeded on `RANDOM_SEED`; draws are reproducible.

## Acceptance criteria

- **Supports** — randomisation p below 0.05 and `se_ratio` near 1. The estimate
  is distinguishable from chance and the analytic inference was roughly honest.
- **Refutes** — randomisation p above 0.05. Chance reassignment of control links
  produces estimates this large often enough that the magnitude carries no
  evidential weight, and the Phase 7 p-values are artefacts of the clustering
  assumption.
- **Uninformative** — draws fail to converge, or the control pool proves too
  small for the placebo distribution to be stable across seeds.

An intermediate outcome is expected and is not a dodge: randomisation p below
0.05 together with `se_ratio` well above 1 would mean the effect survives an
honest null while the reported precision was substantially overstated. That is
a finding about the inference procedure, and it gets reported as one.

## Data required

None beyond the eight months already held. This runs on the current panel and
does not wait on the backfill.

## Result

*Pending: 500-draw run across all four samples in progress.*

Smoke test, weekend sample, 40 draws — indicative only, and 40 draws cannot
resolve below p ≈ 0.024:

| Sample | beta | analytic SE (p) | placebo SD | se_ratio | randomisation p |
|---|---:|---|---:|---:|---:|
| weekend | +1.141 | 0.242 (3.8e-06) | 0.350 | 1.44 | 0.024 |

## Verdict

*Pending.*

## Notes

This bounds how surprising the magnitude is. It does not test parallel trends
and does not repair the rejected pre-period leads — those need the
Rambachan–Roth sensitivity analysis and probably a different control
construction. A placebo-in-space result cannot rescue a design whose leads
reject; it can only tell you whether the magnitude was ever worth arguing about.

The first implementation drew `k = n_treated` from the control pool. The smoke
test exposed it: 148 of 177 leaves 29 controls and makes every draw nearly
identical. Fixed before any result was recorded.
