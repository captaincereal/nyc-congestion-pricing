# Agent handoff prompt

Give the next session this repository and one instruction:

> Read `docs/agent_handoff.md` and carry out the mission it describes.

`AGENTS.md` loads automatically and carries the standing conventions. Everything
below the rule is the mission.

---

You are taking over a causal-inference study that has reached its finding. Seven
pre-registered hypotheses are answered and they agree. The remaining work is not
to keep testing the identification — that is settled — but to finish the parts
of the study that were never run, and to fix a broken data pipeline.

Infer intent from context and carry work to completion. When a question can be
settled by reading the repo, measuring something, or running it, do that instead
of asking. Prepare a concrete, reviewable result before seeking approval.

## Start here, in this order

1. `docs/hypotheses/REGISTER.md` — every hypothesis, its status and verdict.
2. `docs/hypotheses/README.md` — the protocol you must follow. Short, not optional.
3. `README.md` — the current public finding.
4. `docs/owner_decisions.md` — what is waiting on the owner.

## First: confirm the backfill recovered

The Backfill failed on 2026-09-13 (run 5) with `HTTP 422` on every release
upload: the `data-raw` release had filled to GitHub's **1000-asset ceiling** —
853 day checkpoints from months long since complete, plus 89 state snapshots.
Raw assets were uploaded and never deleted, so every day ever checkpointed
stayed forever after its month part superseded it.

`ReleaseStore.publish` prunes before uploading. Three commits got it right, and
the second and third exist because the first was checked rather than trusted:

The first rule matched `DAY_NAME`, which is `.parquet` only. But `publish`
writes each checkpoint twice — the parquet from `state["assets"]` and its
`.receipt.json` through the compatibility block — so 408 receipts of complete
months were collectable by no rule at all. That rule freed 489 slots, not the
825 originally claimed, and the remaining backfill is roughly 496 more days each
stranding another receipt, so the release would have refilled part-way through
the post-period.

The second problem was that pruning broke the snapshots it keeps. `restore`
walks them newest-first and rejects any whose raw assets have gone; four of the
eight newest still pointed at 2023-02 days. The fallback chain would have become
four deep instead of eight, silently. Whatever a kept snapshot references is now
live too.

Simulated against the live release before pushing: **deletes 873, leaves 127**,
with all 27 month parts, all 27 verification receipts and all 8 snapshots intact
and restorable. If you find the release near 1000 again, or Backfill still
failing with 422, that simulation was wrong and this is the first thing to
repair. The downloader was never the problem — it was finishing months normally
right up to the upload failure.

One caution on timing. Scheduled runs on free runners are being delayed four to
five hours past their cron slots (`25 1,7,13,19` UTC; observed starts 06:17 and
12:46). A release still at 1000 shortly after a push means the job has not run
yet, not that the fix failed. Check the newest asset's `created_at` against your
push before concluding anything.

Consequence while it was stuck: the archive sits at **27 verified contiguous
months, 2023-02 … 2025-04**, 21.3M rows. `2023-01` was **22** days downloaded
when the failure hit — the newest state snapshot references days 01 through 22,
not the 28 previously recorded here — so it should complete quickly. The
post-period beyond 2025-04 has not started.

Two milestone notifications are wired into the backfill and open a GitHub issue
once each: when `2023-01` lands, and when the post-period is complete. Neither
has fired. Do not disable them. The 2023-01 body was rewritten on 2026-09-13 —
it still told the owner to rerun H002 and H004, which H005 and H006 superseded
the same day, so the issue would have opened asking for work already done. The
logic that decides when each fires is untouched.

## What the study found

Speeds inside the Congestion Relief Zone rose about **1.17 mph** relative to
comparison streets after tolling began on 2025-01-05, roughly 12% of the
pre-tolling treated mean. That association is robust. **It cannot be attributed
to the toll.**

Six answered hypotheses, each with its prediction committed before its code ran:

| | Finding |
|---|---|
| **H001** | Clustered SEs up to 1.5× too tight; weekday peak fails randomisation inference at p = 0.092 |
| **H002** | Breakdown values 0.044–0.151 on 36 pre-weeks |
| **H003** | Daily aggregation stable; collapsing to one pre/post per link inflates SEs 3.8–6.2×, zero enters every interval, off-peak flips sign |
| **H004** | Both matching rules rejected out of sample; nearest-neighbour made it worse |
| **H005** | Breakdown values 0.005–0.171 on 96 pre-weeks, falling monotonically as the horizon widens |
| **H006** | Every control set rejects on a clean July–September holdout; holidays roughly double the statistic but do not cause the failure |

The joint pre-trend test rejects in all four samples and **rejects harder on 96
pre-weeks than on 36**. Every explanation that would have rescued the finding —
too little pre-period, an atypical holiday window, a poorly chosen comparison
group — has been tested and none survives.

**Do not reopen this.** Searching for a control set that passes is another draw
against fixed data, and the register would have to carry the count. If you
believe there is a specification nobody tried, register it with a prediction
first, and expect it to fail.

None of this is evidence that congestion pricing did nothing. It is evidence
that this comparison design cannot tell you either way. Hold that distinction in
every sentence you write; it is the study's contribution.

## The work that remains

**Phase 10 — spillover is done; mechanism is not.** The spillover half ran on
2026-09-13 as [H007](hypotheses/H007-secondary-feed-diversion.md) and **refutes**.
The five `boundary` links straddle 60th Street rather than sitting outside it,
and no control link lies within 500 m of the cordon (nearest ≈ 808 m), so the
primary panel has no units where diversion would show. The secondary
`i4gi-tjb9` feed does carry those units — nine toll-exempt in-zone links — and
stops reporting speeds on three of them across the toll date, so it cannot
measure diversion either. Usable-hour availability diverges by 21.2 points
against a 5-point bar. That is a **measurement** failure, not an identification
one, and it is characterised in the record and the decision register rather than
reported as a null.

The MTA entry check is now closed too, and not by running it. The MTA's
Congestion Relief Zone vehicle-entry series (`t6yz-b64h`, data.ny.gov) is titled
*Beginning 2025* and runs 2025-01-05 to 2026-09-05, checked 2026-09-13. It
starts on the tolling date, because the detection gear that produces the counts
was installed to operate the toll, so it has **no pre-treatment period** and can
support no before-and-after comparison at all. That is structural and waiting
does not fix it. Do not register a hypothesis against it expecting to identify
anything; it can describe post-tolling entry volumes and nothing more.

**TLC trip records are the one untried mechanism source** and the only one with
a pre-period. They have not been ingested and would need their own record. The
per-year archives on NYC Open Data reach back to at least 2014; the current
trip records are distributed as monthly files outside the Socrata endpoints this
project uses, and that exact source has not been verified — confirm it rather
than assuming it.

Before touching the secondary feed: read the zero-speed entry in `AGENTS.md`.
Start from `data/processed/secondary_hourly_panel.parquet`
(`python -m src.data.build_secondary_panel`), not from
`spillover_diagnostics.py`, whose committed table averages 8.8M outages in as
0 mph and is superseded.

**Phase 11 — the writeup.** The README is current and honest; treat it as the
spine rather than starting over. What it lacks is the mechanism section.

Anything whose output could reach the README needs a hypothesis record committed
before it runs. Phase 10 work qualifies.

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
and reruns Phases 6–9 when data lands; `tests.yml` runs ruff, black and pytest.
253 tests pass. State lives in the `data-raw` release.

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
  construction work is done and negative (H004, H006); the decision is still the
  owner's to record.

## Stopping

Work through this without pausing for permission between steps. Stop when you
hit something in the list above, when a measurement contradicts this brief in a
way that changes the plan, or when the work is done.

Waiting on the backfill is not a stopping point; Phase 10 runs on data already
held.

## First

Diagnose the failed Backfill run, then form your own view of the repo. Parts of
this brief will be stale. Correct it rather than trusting it, and say what you
found that differs.
