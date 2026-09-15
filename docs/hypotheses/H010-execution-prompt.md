# H010 execution prompt

Not a record, and not listed in the register. Paste the block below into a fresh
session — preferably a different model — after
`docs/hypotheses/H010-exempt-route-substitution.md` is committed. The commit
order is the pre-registration and it is checkable in git history.

---

```
## What you are doing

You are measuring whether drivers reroute onto toll-free roadways at the moment
New York's Congestion Relief Zone peak toll rate begins, at 05:00 on weekdays.
The repository is a causal study of that toll. Its headline speed result is a
documented failure to identify, established across six hypotheses and not in
question here. A separate thread found that entries collapse at the two minutes
the toll price changes, and measured toll-exempt vehicles at the same sensors as
a control. Those exempt entries rose by about 7 log points at 05:00 while tolled
entries fell. That rise was flagged in passing as possible route substitution and
never tested.

If the rise is a substantive share of the traffic the toll deters at that
moment, the study gains a diversion result it has never had, and its spillover
section — which currently says diversion is unidentified on both available data
feeds — has to be rewritten. If the rise is a rounding error once counted in
vehicles, two documents lose a claim they currently make, and the exempt series
is vindicated as a clean control. Either outcome changes what the project
reports. A null is a successful result here and must be reported as one.

## What you need to know

Read these four, in this order. They are short and they carry the context you
need without a tour of the repo:

- `docs/hypotheses/H010-exempt-route-substitution.md` — the pre-registered
  record you are executing. Its Prediction and Acceptance criteria are frozen.
- `docs/hypotheses/ADJUDICATION-timing.md` — what an independent reader
  concluded about the two records this one follows. It matters because it shows,
  with synthetic fixtures, that the boundary estimator used at 05:00 is biased by
  differential curvature between the two series, and that 05:00 sits in the
  steepest ramp of the day. Your counterfactual has the same exposure.
- `docs/hypotheses/H009-toll-timing-exempt-control.md` — the design that
  produced the by-product, and its own note that a diverted-onto exempt series
  is itself treated.
- `docs/hypotheses/README.md` — the protocol. It is binding and it is short.

Facts you will otherwise rediscover the hard way:

- The data is `t6yz-b64h` on `data.ny.gov`, hourly vehicle entries by detection
  point and vehicle class in ten-minute blocks, 2025-01-05 onward. Ten minutes
  is the finest resolution available and it caps how close to the cutoff you can
  look.
- `src.analysis.h008_toll_timing._fetch` runs one cached Socrata aggregate.
  Reruns are free because it caches by query hash under `data/raw/mta_crz/`.
- The peak window is derived from the feed's own `time_period` column, not from
  the published tariff. Peak is hours 05-20 Monday to Friday. Do not cite an MTA
  tolling document for the schedule unless you have actually read one.
- `crz_entries` is the tolled count, `excluded_roadway_entries` the exempt one.
  Both appear on the same rows at the four detection groups that watch both.
- The four dual-recording groups are FDR Drive at 60th St, Brooklyn Bridge, Hugh
  L. Carey Tunnel, West Side Highway at 60th St.
- `did`, `event_study` and `placebo_space` load a panel path in their own
  `load()`. Do not repoint it. Import the functions you need into a module of
  your own, as `h007_diversion.py` and `h009_exempt_control.py` both do.
- Namespace every output `H010_*`. Reruns must not overwrite artefacts an
  earlier record cites.

## The hypothesis, pre-registered

The record is the authority; these are its criteria inline so they cannot be
quietly reinterpreted.

The estimand is a ratio of vehicle counts, not of log points:

    f = S / D

D is the tolled deficit and S the exempt surplus over the three ten-minute
blocks beginning 05:00, each measured against a counterfactual fitted on the six
blocks before the boundary and extrapolated across it. Frozen counterfactual:
log-linear on those six blocks, per date and detection group, exponentiated back
to counts. Also report f under a flat-level counterfactual using the last
pre-boundary block alone, and under a quadratic on the same six blocks.
Inference by block bootstrap over whole dates, 500 draws.

As amended on 2026-09-15, before execution, at the owner's direction. The
record retains the original text beside the amendment and explains it; read that
section rather than taking this summary on trust. The flat counterfactual is
still computed and reported, and is scored on nothing, because on a rising
series it drives the deficit negative and inflates the surplus.

Supports, both required:
  1. f >= 0.05 under the frozen counterfactual, with the bootstrap interval on
     that estimate excluding 0.02.
  2. The exempt surplus is disproportionately cars and motorcycles: their share
     of the surplus divided by their share of exempt volume in the six
     pre-boundary blocks is at least 1.10.

Refutes, any one:
  1. f < 0.02 under the frozen counterfactual.
  2. f is negative under either FITTED counterfactual (log-linear or quadratic).
  3. The cars-and-motorcycles ratio in criterion 2 is at or below 0.95.

Uninformative: f lands between 0.02 and 0.05, or its bootstrap interval spans
that range, or f moves by more than a factor of two across the fitted pair.

Feasibility gate declared in advance: if cars and motorcycles are more than 90%
of exempt volume in the pre-boundary blocks, criterion 2 cannot reach 1.10 and
must be recorded as untestable rather than failed. Measure that baseline share
and report it before you look at the surplus.

Apply the criteria as written. If one turns out badly built, say so in the
verdict and leave it applied as written — this project has had two records whose
criteria a true effect could not satisfy, and the damage came from nobody
noticing until afterwards, not from the criteria being applied honestly.

## Method

`src/analysis/h010_route_substitution.py` already implements this, and
`scripts/run_h010.py` runs it and commits the artefacts. On a hosted runner,
dispatch the H010 workflow. The criteria are encoded in `evaluate_criteria`, so
what fires is mechanical; your job is the Verdict and the writing, not the
arithmetic.

Follow the record's Method section. Where it leaves a choice open, you are
better placed to make it than its author was; where it pins something down, that
pin changes what the result means, so keep it.

Two things to treat as separate questions rather than one. First, is the point
estimate of f right — does the counterfactual reconstruct what the exempt series
would have done? Second, is the uncertainty on it honest — does a bootstrap over
dates capture the variation that matters, given the two series are paired within
a date and serially correlated across them? This project has already found
clustered standard errors running up to 1.5x too tight against randomization
inference on its speed panel. Report on each separately.

The curvature exposure is the thing most likely to move your answer. The
adjudication file shows the difference estimator returning two thirds of a log
point out of nothing when two series have different curvature, and 05:00 is
where the tolled series ramps hardest. Your three counterfactuals exist to bound
that. If they disagree by more than a factor of two, that disagreement is the
result and you should report it as such rather than picking the middle one.

## Constraints

- Python only, zero budget, nothing here may cost money. Everything runs on free
  GitHub Actions runners unattended.
- ruff and black at line length 100, type hints on public functions, every
  script exposes `main()` and runs as `python -m src....`.
- `python -m pytest` uses synthetic fixtures and touches no network. Run it and
  fix what your change broke.
- Missing numeric values are NaN, never 0. Log rows in -> rows out and the
  reason for every drop.

## What to report

Fill in the record's Result and Verdict sections, add a row to
`docs/hypotheses/REGISTER.md`, and add a dated entry to
`docs/decision_register.md`.

Report f under all three counterfactuals with its bootstrap interval, the
vehicle counts behind it, the baseline cars-and-motorcycles share, the
vehicle-class decomposition of the surplus, the split across the four detection
points, the 21:00 mirror descriptively, and which acceptance criterion was met.

Say what it changes and what it does not settle. Two documents currently claim
this as the project's first direct evidence of route substitution —
`docs/decision_register.md` and `docs/agent_handoff.md`. If your result does not
support that, say which sentences have to come out.

## Boundaries

This cannot establish that the toll reduced congestion, reduced total entries,
or changed speeds. Retiming an entry is not avoiding one, and nothing here bears
on the speed finding.

A negative result closes a measurement channel rather than the diversion
question. Drivers who divert onto roads these four sensors do not watch, who
retime instead of rerouting, or who divert at another hour are all outside what
you are measuring.

A large f cuts both ways and you must say so. If substantial diversion is
happening, the exempt series is a partly treated control, and the −0.759
difference H009 reports at 05:00 overstates the pure timing response while still
identifying its sign. Report that consequence alongside the discovery rather
than only the half that reads well.

Cite anything methodological with author, year and venue. Flag what you cannot
cite precisely rather than guessing — models fabricate confidently in this
domain, and two records in this repo carry page ranges deliberately left
unverified rather than invented.
```
