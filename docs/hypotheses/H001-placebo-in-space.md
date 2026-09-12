# H001 — Is the DiD estimate larger than chance reassignment of control links?

| | |
|---|---|
| **Status** | answered |
| **Registered** | 2026-09-12 |
| **Registered by** | Claude Opus 5 session (repo automation / methodology review) |
| **Answered by** | Claude Opus 5 session, 2026-09-12 |
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

500 draws per sample, 81 of 177 control links relabelled per draw, seeded on
`RANDOM_SEED`. `outputs/tables/placebo_space.csv`,
`outputs/figures/placebo_space_*.png`.

| Sample | beta | analytic SE | analytic p | placebo SD | se_ratio | rand. p (beta) | rand. p (t) |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | +0.793 | 0.212 | 2.2e-04 | 0.314 | 1.48 | 0.014 | 0.002 |
| offpeak | +0.688 | 0.205 | 8.6e-04 | 0.309 | 1.51 | 0.030 | 0.002 |
| peak | +0.604 | 0.229 | 8.7e-03 | 0.361 | 1.57 | **0.092** | 0.006 |
| weekend | +1.141 | 0.242 | 4.0e-06 | 0.329 | 1.36 | 0.002 | 0.002 |

The placebo distributions are centred near zero and roughly symmetric (2.5–97.5
percentiles about -0.62 to +0.57 for the full sample), so the null is
well behaved. A randomisation p of 0.002 is the floor at 500 draws (1/501) and
means no placebo draw reached the observed statistic.

## Verdict

**The intermediate outcome named in the acceptance criteria**, with one partial
refutation.

Randomisation p is below 0.05 on the coefficient-based test for three of four
samples, so the magnitude is distinguishable from chance reassignment of control
links. `se_ratio` is not near 1 — it sits at 1.36 to 1.57 — so the analytic
clustered standard errors are too tight and every Phase 7 p-value is
correspondingly overstated. Both halves of the pre-registered intermediate case.

**Peak refutes on the coefficient-based test** (p = 0.092). Chance reassignment
produces a peak-sized estimate about one time in eleven, so the weekday peak
effect carries little evidential weight from its magnitude alone. This is the
cut policy discussion cares most about, so the failure is not incidental.

What this changes: the reported precision is wrong, by roughly half again rather
than by orders of magnitude. The Phase 7 p-values of 1e-4 to 1e-6 should be read
as something nearer 1e-2, and the peak estimate as not distinguishable from
chance at conventional levels.

What it does not change: the corrected pre-trend tests still reject in all four
samples. An estimate that survives chance reassignment is not thereby a causal
effect — it means the number is not pure noise, which is a much weaker claim.
This result cannot rescue a design whose leads reject.

## Notes

**The t-based p-values are anti-conservative and should not be read as the
headline.** Placebo draws use 81 treated against 96 control links, while the
real estimate uses 148 against 177 and runs on a larger sample. Placebo
regressions therefore have mechanically larger standard errors and smaller t
statistics, so comparing the real t against that distribution flatters the real
estimate. The registered method anticipated the conservative direction this
introduces for the coefficient test but not the anti-conservative direction it
introduces for the t test. The coefficient-based p-values are the defensible
ones here, notwithstanding MacKinnon & Webb's general preference for t-based
randomisation inference when the treated group is atypical.

By the same argument `se_ratio` is an upper bound: the placebo spread is
inflated by the smaller groups, so the true understatement of the analytic SE is
somewhat below 1.4 to 1.6. The direction is not in doubt, the magnitude is.

Fixing this properly means either matching group sizes (impossible — the control
pool is 177 links) or a bootstrap correction for the size difference. Worth a
follow-up hypothesis if the peak result becomes load-bearing.

The prediction above expected `se_ratio` "plausibly well above" 1 and
randomisation p "orders of magnitude larger than the analytic p". The first was
an over-warning: an order-of-magnitude understatement was plausible from the
one-treated-cluster literature and did not materialise. The second held.

This bounds how surprising the magnitude is. It does not test parallel trends
and does not repair the rejected pre-period leads.

The first implementation drew `k = n_treated` from the control pool. The smoke
test exposed it: 148 of 177 leaves 29 controls and makes every draw nearly
identical. Fixed before any result was recorded.
