# H011 execution prompt

Not a record, and not listed in the register. Paste the block below into a fresh
session — preferably a different model — after
`docs/hypotheses/H011-crossing-volume.md` is committed. The commit order is the
pre-registration and it is checkable in git history.

---

```
## What you are doing

You are measuring whether New York's congestion charge reduced the number of
vehicles entering the charging zone. The repository is a causal study of that
toll whose headline speed result is a documented failure to identify, across six
hypotheses, and that is not in question here. The volume question has never been
answerable because the MTA's zone-entry feed begins on the day tolling started,
so it has no "before".

A source survey on 2026-09-15 found one that does. `ebfx-2m7v` on data.ny.gov,
MTA Bridges and Tunnels Hourly Crossings, 13.5M rows by facility, direction,
hour and vehicle class, running 2019-01-01 to 2026-09-01. Two of that operator's
facilities are entry points to the zone and the rest are not, so the comparison
is between crossings run by one agency, counted by one system, reported in one
file. Every previous control group in this study was "similar streets" chosen by
an analyst, and all three attempts were rejected out of sample.

If inbound volume fell at the zone-bound crossings and held elsewhere, the study
gains its first causal estimate of something the policy was built to do. If it
did not, a widely repeated claim loses its most obvious support. Both are
results and a documented inability to tell is a third. Report whichever happens.

## What you need to know

Read these, in order. They are short:

- `docs/hypotheses/H011-crossing-volume.md` — the pre-registered record you are
  executing. Prediction and Acceptance criteria are frozen.
- `docs/hypotheses/README.md` — the protocol. Binding.
- `docs/source_recon.md` — where this dataset came from and what else exists.
- `docs/decision_register.md`, newest entries first — what has already failed
  here and why.

Facts you will otherwise rediscover the hard way:

- **Read the facility list out of the data before classifying anything.** Which
  crossings enter the zone is a question for the data's own `facility` values
  plus `docs/project_brief.md`, which names the Hugh L. Carey and Queens-Midtown
  tunnel approaches as zone-excluded roadways. Assuming it is the D3 error in a
  new place, and D3 turned on exactly this kind of inference. Write the
  classification down before you estimate.
- **Confirm which `direction` value is inbound** rather than trusting the label.
  A crossing counted outbound measures vehicles leaving.
- The pre-period is restricted to 2023-01 through 2024-12 for a stated reason:
  the pandemic is a differential shock to Manhattan-bound crossings far larger
  than a toll, and including it drives any Rambachan-Roth breakdown value toward
  zero mechanically. Report the full 2019 history as a sensitivity and expect it
  to look much worse.
- January 2025 is a transition month; tolling began on the 5th. Excluded from
  the primary, reported as a sensitivity.
- `src/analysis/honest_did.py` already computes breakdown values from event-study
  coefficients and their full cluster-robust covariance. Reuse it. Feed it the
  full covariance, not the diagonal standard errors.
- Namespace every output `H011_*`. Import what you need into a module of your
  own rather than repointing another module's paths, as h007, h009 and h010 do.

## The hypothesis, pre-registered

Primary is the Rambachan-Roth breakdown value on the restricted pre-period, with
the point estimate beside it. It is chosen because it is a magnitude, because
H002 and H005 report it on the link panel at 0.005 to 0.171 so this number is
directly comparable to what the failed design achieved, and because Roth (2022)
is the reason not to gate on a pre-trend test.

Supports, both required:
  1. Breakdown value M >= 1.0.
  2. The point estimate is a fall of at least 2%, and the randomization
     distribution puts it outside the middle 90% of facility reassignments.

Refutes, any one:
  1. M < 0.3 -- no better than the link panel.
  2. The point estimate is smaller than 1% in absolute value.
  3. The estimate is positive AND M >= 0.3.

Uninformative: M lands between 0.3 and 1.0, or the randomization distribution is
too coarse to place the estimate.

Apply them as written. If one turns out badly built, say so in the Verdict and
leave it applied -- this project has had four criteria failures and the damage
came from nobody noticing until afterwards, never from honest application.

## Method

Follow the record's Method. Where it leaves a choice open you are better placed
to make it; where it pins something down, that pin changes what the result
means.

Treat two questions as separate rather than one. Is the point estimate right --
does the facility comparison isolate the toll? And is the uncertainty honest --
there are nine facilities and two treated, so cluster-robust asymptotics cannot
be trusted, and C(9,2) = 36 possible assignments means the finest achievable
one-sided randomization p is about 0.028. Report the randomization distribution
and treat the clustered standard errors as the weaker number. This project has
already measured its clustered errors running up to 1.5x too tight.

The thing most likely to move your answer is substitution. Traffic pushed off a
tolled tunnel may appear on a control crossing, which makes the control partly
treated and inflates the estimate. Look for it directly: if the control
crossings rise as the treated ones fall, say so and bound it.

## Constraints

- Python only, zero budget, nothing may cost money. Runs unattended on free
  GitHub Actions runners.
- ruff and black at line length 100, type hints on public functions, every
  script exposes main() and runs as `python -m src....`.
- `python -m pytest` uses synthetic fixtures and no network. Run it, fix what
  your change broke.
- Missing numeric values are NaN, never 0. Log rows in -> rows out and the
  reason for every drop.
- Before freezing any criterion of your own, plant a true effect of the size you
  expect in a fixture and confirm the criterion fires. That rule exists because
  four criteria here could not be satisfied by any true effect.

## What to report

Fill in the record's Result and Verdict, add a row to
`docs/hypotheses/REGISTER.md`, and add a dated entry to
`docs/decision_register.md`.

Report the breakdown value, the point estimate with its interval, the
randomization distribution, the facility classification you used and where you
got it, the vehicle-class and per-facility cuts, the sensitivities, and which
acceptance criterion was met. Say what it changes and what it does not settle.

A null or an uninformative verdict is a successful outcome here and must be
reported as one. This study's most defensible finding so far is a documented
inability to identify an effect.

## Boundaries

This cannot establish that the toll improved speeds, reduced congestion or
changed travel times. It counts vehicles crossing nine fixed points. A driver
who reroutes to a free crossing and still enters the zone counts as a reduction
here while changing nothing on the street.

It also says nothing about the frozen speed question, which stays closed. Do not
reopen it, and do not let a volume result be written up as though it answered
it.

Cite anything methodological with author, year and venue, and flag what you
cannot cite precisely rather than guessing. Two records here carry page ranges
deliberately left unverified rather than invented.
```
