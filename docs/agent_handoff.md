# Agent handoff prompt

Give the next session this repository and one instruction:

> Read `docs/agent_handoff.md` and carry out the mission it describes.

`AGENTS.md` loads automatically and carries the standing conventions. Everything
below the rule is the mission.

---

You are taking over a causal-inference study that has reached a defensible
negative finding and is now testing whether that finding survives better data.
Two analyses were running when this was written and may or may not have
finished; resolving that is your first job.

Infer intent from context and carry work to completion. When a question can be
settled by reading the repo, measuring something, or running it, do that instead
of asking. Prepare a concrete, reviewable result before seeking approval.

## Start here, in this order

1. `docs/hypotheses/REGISTER.md` — every hypothesis, its status and verdict.
2. `docs/hypotheses/README.md` — the protocol you must follow. It is short and
   it is not optional.
3. `docs/decision_register.md` — the project's running record.
4. `README.md` — the current public finding.

## Immediate: two runs were in flight

On 2026-09-13 around 10:30 EDT, two registered analyses were executing locally.
Check `outputs/tables/` before doing anything else.

**H005** (`docs/hypotheses/H005-honest-did-long-preperiod.md`) — Rambachan–Roth
sensitivity at three horizons. Horizons 12 and 26 completed; their artefacts are
`H005_honest_did_h12*.csv` and `H005_honest_did_h26*.csv`. Horizon 52 was still
running and may have failed on memory — it builds roughly a 9 GB dummy matrix on
5.4M link-hours. **A horizon-52 memory failure is an expected, reportable
outcome, not something to work around.** H005's criteria say so explicitly: the
verdict is judged at horizon 12, and a failure confined to the wider horizons is
a limit on what the panel supports.

Results so far, breakdown values under relative magnitudes:

| Sample | h12 | h26 |
|---|---:|---:|
| all | 0.093 | 0.063 |
| peak | 0.044 | 0.015 |
| offpeak | 0.054 | 0.034 |
| weekend | 0.171 | 0.112 |

**H006** (`docs/hypotheses/H006-control-construction-clean-holdout.md`) —
control construction judged on two holdouts. No output had appeared. Its command
was:

```
python -m src.analysis.control_construction --match-weeks -96 -27 \
  --holdout -26 -15 --holdout -12 -2 --out-prefix H006
```

**What to do with whatever you find.** If artefacts exist and the records still
say Pending, close them: fill in Result and Verdict from the committed outputs,
update `REGISTER.md`, commit. Do not touch Prediction or Acceptance criteria —
both records were registered before the code ran and the commit order is the
evidence. If a run did not complete, rerun it; the commands are above and in
each record's Method section.

H006 is the more important of the two. Read its Notes before interpreting it.

## What the study found

Speeds inside the Congestion Relief Zone rose about **1.17 mph** relative to
comparison streets after tolling began on 2025-01-05, roughly 12% of the
pre-tolling treated mean, on the current 27-month panel. That association is
robust. **It cannot be attributed to the toll**, and the README says so.

The estimate was 0.77 mph on the earlier 12-month panel. It moved by half again
when the pre-period lengthened, which is itself a reason not to treat the point
estimate as settled.

Four answered hypotheses, each pre-registered, all pointing the same way:

- **H001** placebo-in-space: clustered standard errors run up to 1.5× too tight;
  weekday peak fails randomisation inference at p = 0.092.
- **H002** Rambachan–Roth on 36 pre-weeks: breakdown values 0.044–0.151.
- **H003** temporal aggregation: daily is stable, but collapsing to one pre and
  one post observation per link inflates standard errors 3.8–6.2×, puts zero in
  every interval, and flips the off-peak sign.
- **H004** control construction: both matching rules rejected out of sample.
  Nearest-neighbour made it *worse*; synthetic weights fit the matching window to
  a squared loss of exactly zero and still rejected at p = 4.4e-07.

The corrected joint pre-trend test rejects in all four samples, and **rejects
harder on 96 pre-weeks than it did on 36** (χ² 45.6–100.2 against 43.6–87.1).
That kills the explanation every earlier caveat leaned on: the failure is not a
short-window or holiday artifact.

None of this is evidence that congestion pricing did nothing. It is evidence
that this comparison design cannot tell you either way. Keep that distinction in
every sentence you write; it is the study's entire contribution.

## The protocol, which is binding

Many sessions and several models work on this. The dataset is fixed, so every
specification tried against it is another draw, and enough draws produce a
clean-looking result by chance. Roth (2022) sharpens it: conditioning on a
diagnostic passing can leave the survivor *more* biased than not testing.

So: **any analysis whose output could reach the README gets a hypothesis record
committed before it runs**, with its prediction and acceptance criteria written
while they are still guesses. Exploratory work does not. The `research-prompt`
skill writes the record and a prompt together.

Predictions and acceptance criteria are frozen once results exist. If criteria
turn out badly chosen, supersede the record with a new one explaining why; do
not edit them. Failed and abandoned attempts stay in the register — the count of
attempts is part of what a reader needs.

Namespace outputs by hypothesis (`H0NN_*`). Both analysis modules take an
`--out-prefix` for exactly this reason.

## Data and infrastructure

The archive is **27 verified contiguous months, 2023-02 … 2025-04**, giving 96
pre-treatment weeks and 101 pre-treatment weeks in the panel. Every month is
verified against live source counts with deterministic replay. `2023-01` was
still downloading; it completes the frozen window's start.

Everything runs unattended on GitHub Actions, free, because the owner will not
leave a machine on:

- `backfill.yml` every six hours: verifies, then deepens the pre-period
  backwards before extending the post-period forward. State lives in the
  `data-raw` release, which is what the next pass resumes from.
- `analysis.yml` rebuilds the panel and reruns Phases 6–9 when data lands.
- `tests.yml` runs ruff, black and pytest. 205 tests currently pass.

Two milestone notifications are wired into the backfill and will open a GitHub
issue once each: when `2023-01` lands, and when the post-period is complete.
Do not disable them.

To work locally you need the archive on disk. Pull month parts, the manifest and
the segment table from the release, then `build_staging` → `geo` → `build_panel`.

## After H005 and H006

If H006 refutes — both rules reject on the clean holdout — the study's
conclusion is as well established as this data can make it. The work then is
Phase 10 and 11: the spillover and mechanism checks that remain unrun, and a
final writeup. Do not keep searching for a control set that passes; each further
attempt is another draw and the register would have to carry it.

If H006 supports — a rule gives flat leads on the clean holdout — D2 becomes
live. Rerun H002's sensitivity on that control set before writing any causal
sentence, and register it as a new hypothesis rather than reusing H005.

Either way, `docs/owner_decisions.md` holds recommendations on **D1, D2, D3, D5,
D6 and D7** that remain unadopted. They are reserved to the owner. You may
analyse them and bring evidence; you may not adopt one.

## Constraints

Zero budget, Python only, must run unattended on free runners. Research
integrity outranks the budget: if the only honest analysis costs money, say so
rather than quietly weakening it.

Cite with author, year and venue. Flag anything you cannot cite precisely rather
than guessing — models fabricate confidently in this domain.

## Bring to the owner first

- Force-pushing, rewriting published history, changing repository visibility.
  Branches and pull requests need no approval.
- Anything that costs money.
- Changing anything `docs/project_brief.md` marks frozen.
- Adopting any of D1–D7.

## Stopping

Work through this without pausing for permission between steps. Stop when you
hit something in the list above, when a measurement contradicts this brief in a
way that changes the plan, or when the work is done.

Waiting on the backfill is not a stopping point; there is always a registered
question or a writeup section available.

## First

Check `outputs/tables/` for H005 and H006 artefacts, then form your own view.
Parts of this brief will be stale. Correct it rather than trusting it, and say
what you found that differs.
