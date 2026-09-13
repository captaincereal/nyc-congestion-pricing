# Agent handoff prompt

Give the next session this repository and one instruction:

> Read `docs/agent_handoff.md` and carry out the mission it describes.

`AGENTS.md` loads automatically and carries the standing conventions. Everything
below the rule is the mission.

---

You are taking over a causal-inference study that is **essentially finished**.
Seven pre-registered hypotheses are answered and they agree, the frozen 44-month
archive is complete and verified, the pipeline is healthy, and the README
reports the finding from current artefacts.

This is a different job from the one earlier handoffs described. It is not to
keep testing the identification — that is settled — and not to repair the
pipeline, which is fixed. What is left is a small amount of optional work and a
set of decisions that belong to the owner. **The most likely way to damage this
study now is to find something to run.**

Infer intent from context and carry work to completion. When a question can be
settled by reading the repo, measuring something, or running it, do that instead
of asking. Prepare a concrete, reviewable result before seeking approval.

## Start here, in this order

1. `docs/hypotheses/REGISTER.md` — every hypothesis, its status and verdict.
2. `docs/hypotheses/README.md` — the protocol you must follow. Short, not optional.
3. `README.md` — the current public finding.
4. `docs/owner_decisions.md` — what is waiting on the owner.

## First: nothing is broken — read this before you go looking

Everything that was failing on 2026-09-13 is fixed, verified, and pushed. Start
by confirming it is still true rather than by re-diagnosing it:

    gh run list --workflow analysis.yml --limit 3
    gh run list --workflow backfill.yml --limit 3

Expect the newest of each to be green. If they are, there is no pipeline work.

**The archive is complete.** 44 of 44 frozen months, 2023-01 … 2026-08, every
one verified — 24 pre-treatment and 20 post. Both milestone issues opened (#3,
#4). The backfill has nothing left to fetch; it now breaks out early with
"Frozen 44-month archive complete", which is why run 6 finished in 3h18m rather
than spending its 285-minute budget.

**The results are current.** `analysis.yml` rebuilt everything from the complete
archive at 2026-09-13T22:34Z (commit `089f89b`), and the README's Evidence,
Robustness and Limitations sections were rewritten from those tables in
`7696130`. Every figure quoted there was checked back against the CSV it cites.
The headline association is now **+1.05 mph** on all hours, down from 1.17 on 27
months, and the joint pre-trend test still rejects in all four samples.

What was wrong, and why none of it needs revisiting:

The release had filled to GitHub's 1000-asset ceiling and every upload 422'd.
Pruning now runs before uploading; the release sits at 178 assets with zero
stranded day receipts. Two defects in the first fix were found by checking it
rather than trusting it — it matched `.parquet` only, leaving 408 receipts
uncollectable, and it broke four of the eight snapshots it keeps.

Then `analysis.yml` failed on the completed archive with
`hard_unmatched_segments`. The cause was sid **33024**, the westbound Belt
Parkway east of JFK: a sparse sensor with 2,325 readings across 44 months that
reported on none of the ten sampled days, so it reached the panel with no
geometry. It classifies as `control`, so no treated definition moved. Day
sampling could never have found it, and a full re-fetch confirmed that — it
returned a byte-identical table. The roster is now **reconciled** instead of
sampled: `missing_segment_sids` diffs the sids in the parts on disk against the
attribute table and `top_up_segments` looks each gap up by id, before staging.

Three things changed shape as a result, and they are the ones to know about:

`publish` now **replaces** `ANCILLARY` assets (the segment table, the weather
file) rather than refusing them. Month parts and day checkpoints are still
immutable and a test pins that distinction. The cost is documented at the call
site: snapshots written before a replacement stop being restorable, so the
fallback chain shortens until fresh ones accumulate.

A failing HARD data-quality check now **prints its offending rows** to stderr.
The previous exit said only "see the report", and `analysis.yml` uploads no
artifact, so the report died with the runner.

`gh` is installed and authenticated on the owner's machine but is **not on the
Git Bash PATH**; call it as `"C:/Program Files/GitHub CLI/gh.exe"` or from
PowerShell. Without it the Actions log API returns 403 and failures are
effectively undiagnosable from outside.

## Timing, if you ever wait on a workflow

Scheduled runs on free runners are delayed hours past their cron slots
(`25 1,7,13,19` UTC; observed starts 06:17, 12:46, 16:58). **A release or a
table that has not changed shortly after a push means the job has not run yet,
not that something failed.** Check the newest asset's `created_at`, or the run's
`run_started_at`, against your push before concluding anything — an hour was
lost to that on 2026-09-13.

`analysis.yml` fires on `workflow_run` when the backfill completes, and also
takes `workflow_dispatch`, so you can trigger it directly instead of waiting:

    gh workflow run analysis.yml
    gh run watch <id>

It takes about five minutes end to end on the complete archive.

## What the study found

Speeds inside the Congestion Relief Zone rose about **1.05 mph** relative to
comparison streets after tolling began on 2025-01-05, roughly 11% of the
pre-tolling treated mean, on the complete 44-month archive. That association is
robust. **It cannot be attributed to the toll.**

Seven answered hypotheses, each with its prediction committed before its code
ran:

| | Finding |
|---|---|
| **H001** | Clustered SEs up to 1.5× too tight; weekday peak fails randomisation inference at p = 0.092 |
| **H002** | Breakdown values 0.044–0.151 on 36 pre-weeks |
| **H003** | Daily aggregation stable; collapsing to one pre/post per link inflates SEs 3.8–6.2×, zero enters every interval, off-peak flips sign |
| **H004** | Both matching rules rejected out of sample; nearest-neighbour made it worse |
| **H005** | Breakdown values 0.005–0.171 on 96 pre-weeks, falling monotonically as the horizon widens |
| **H006** | Every control set rejects on a clean July–September holdout; holidays roughly double the statistic but do not cause the failure |
| **H007** | The secondary feed cannot measure diversion either: it stops reporting speeds on three of nine toll-exempt in-zone links, availability diverging 21.2 points against a 5-point bar. A measurement failure, not an identification one |

The joint pre-trend test rejects in all four samples on the full 104-week
pre-period: χ² 97.9, 69.7, 102.2 and 46.7 on 11 dof. Lengthening the pre-period
never rescued it — three of the four rise monotonically from 36 to 96 to 104
weeks, weekday peak easing slightly at the last step while staying far beyond
rejection. Every explanation that would have rescued the finding — too little
pre-period, an atypical holiday window, a poorly chosen comparison group — has
been tested and none survives, and **the pre-period explanation is now exhausted
rather than merely unlikely: there is no more to add.**

**Do not reopen this.** Searching for a control set that passes is another draw
against fixed data, and the register would have to carry the count. If you
believe there is a specification nobody tried, register it with a prediction
first, and expect it to fail.

None of this is evidence that congestion pricing did nothing. It is evidence
that this comparison design cannot tell you either way. Hold that distinction in
every sentence you write; it is the study's contribution.

## The work that remains

Very little, and none of it is analysis. Be honest with yourself about that
before inventing something to run. **The study has reached its finding, the data
are complete, and the pipeline is healthy.** Adding specifications now is the
exact failure the protocol below exists to prevent.

**Phase 10 is closed except for TLC.** The spillover half ran as
[H007](hypotheses/H007-secondary-feed-diversion.md) and refutes: the secondary
`i4gi-tjb9` feed carries the nine toll-exempt in-zone links traffic would divert
onto, and stops reporting speeds on three of them across the toll date, so
usable-hour availability diverges by 21.2 points against a 5-point bar. That is
a **measurement** failure, not an identification one. The MTA entry check is
closed structurally: `t6yz-b64h` begins on the tolling date, so it has no
pre-treatment period and no estimator recovers a counterfactual that was never
instrumented. Waiting does not fix it.

**TLC trip records are the only untried source with a pre-period.** They have
not been ingested and would need their own registered record. Two cautions.
Their current distribution is monthly files outside the Socrata endpoints this
project uses, and that exact source has **not** been verified here — confirm it
rather than assuming it. And weigh whether it is worth the ingest at all: the
question it would answer is a mechanism check on a finding that is already
"cannot identify", so a clean TLC result would not change the conclusion, only
describe it better.

**Phase 11 is done.** The README's Evidence, Robustness and Limitations sections
were rewritten from the completed archive on 2026-09-13 and every figure was
checked against the CSV it cites. Treat it as the spine. If you extend it, keep
the labelling discipline it now has: the association, pre-trend test and
robustness table are rebuilt by `analysis.yml` from the current panel, while the
hypothesis records each stand on the panel they were answered on, and the
section says so explicitly. **Do not restate H001–H006 against the 44-month
panel.** Rerunning one is a fresh draw and needs its own registration.

**What actually wants doing** is the owner's, not yours. D1, D2, D3, D5, D6 and
D7 are still open and still reserved. D2's construction work is done and
negative (H004, H006) and D3's sensitivity is measured and small — the
`eleventh_as_treated` spec moves the coefficient by about 0.001 mph — so both
are decisions waiting on a person, not on more evidence.
[`owner_decision_prompt.md`](owner_decision_prompt.md) is written for handing
those six to a model for a second opinion; it recommends and does not adopt, and
its figures were checked against the committed tables. Keep that distinction if
you use it.

Before touching the secondary feed: read the zero-speed entry in `AGENTS.md`.
Start from `data/processed/secondary_hourly_panel.parquet`
(`python -m src.data.build_secondary_panel`), not from
`spillover_diagnostics.py`, whose committed table averages 8.8M outages in as
0 mph and is superseded.

Anything whose output could reach the README needs a hypothesis record committed
before it runs.

## The protocol, which is binding

Many sessions and several models work on this. The dataset is fixed, so every
specification tried against it is another draw, and enough draws produce a
clean-looking result by chance. Roth (2022) sharpens it: conditioning on a
diagnostic passing can leave the survivor *more* biased than not testing.

Predictions and acceptance criteria are frozen once results exist. If criteria
turn out badly chosen, supersede the record with a new one explaining why; do
not edit them. Failed and abandoned attempts stay in the register — the count is
part of what a reader needs. The `research-prompt` skill writes a record and a
prompt together.

Namespace outputs `H0NN_*`. `control_construction` and `honest_did` take
`--out-prefix`, and `honest_did` also stamps the horizon, because reruns would
otherwise overwrite the artefacts an earlier record cites. `did`, `event_study`
and `placebo_space` do not take one and load `HOURLY_PANEL_PATH` in their own
`load()`; H007 imported their functions from a module of its own rather than
repointing that path, which is the pattern to copy.

## Infrastructure

Everything runs unattended on GitHub Actions, free, because the owner will not
leave a machine on. `backfill.yml` every six hours (verify, then deepen the
pre-period backwards, then extend forward); `analysis.yml` rebuilds the panel
and reruns Phases 6-9 when the backfill completes, and takes
`workflow_dispatch`; `tests.yml` runs ruff, black and pytest.
258 tests pass. State lives in the `data-raw` release.

To work locally: pull month parts, the manifest and the segment table from the
release, then `build_staging` → `geo` → `build_panel`.

## Constraints

Zero budget, Python only, unattended on free runners. Research integrity
outranks the budget: if the only honest analysis costs money, say so rather than
quietly weakening it.

Cite with author, year and venue. Flag anything you cannot cite precisely —
models fabricate confidently in this domain.

## Bring to the owner first

- Force-pushing, rewriting published history, changing repository visibility.
  Branches and pull requests need no approval.
- Anything that costs money.
- Changing anything `docs/project_brief.md` marks frozen.
- Adopting any of **D1, D2, D3, D5, D6, D7** — all still open, all reserved.
  You may analyse them and bring evidence; you may not adopt one. D2's
  construction work is done and negative (H004, H006) and D3's sensitivity is
  measured and negligible; both are now waiting on a person rather than on more
  evidence.
- Pushing to a remote. `AGENTS.md` says to ask and this brief does not, which is
  a real conflict. It was put to the owner on 2026-09-13 and they chose
  push-to-main, so that is the standing answer — but say what you pushed.

## Stopping

Work through this without pausing for permission between steps. Stop when you
hit something in the list above, when a measurement contradicts this brief in a
way that changes the plan, or when the work is done.

**The work may already be done.** If the two workflow checks are green, the
register shows seven answered hypotheses, and the README quotes the current
tables, then the honest report is that there is nothing to do and the remaining
items belong to the owner. Saying so is a valid outcome and a better one than
manufacturing a hypothesis to fill the session.

## First

Confirm the two workflows are green, then form your own view of the repo. Parts
of this brief will be stale — it has been wrong before, in ways that mattered:
it once said the prune freed 825 slots when the rule as written freed 489, and
that `2023-01` was 28 days downloaded when the snapshot said 22. **Correct it
rather than trusting it, and say what you found that differs.**

Two habits that paid off on 2026-09-13 and are worth repeating. Check a fix
against live state instead of assuming it took — the release was simulated
asset-by-asset before the change was pushed, which is how two further defects
surfaced. And when a failure is opaque, make it explain itself rather than
guessing from outside; the unmatched segment was found in one line only after
the check was made to print its rows.
