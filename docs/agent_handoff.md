# Agent handoff prompt

Give the next session this repository and one instruction:

> Read `docs/agent_handoff.md` and carry out the mission it describes.

`AGENTS.md` loads automatically and carries the standing conventions. Everything
below the rule is the mission.

---

You are taking over a causal-inference study that has reached its finding. Six
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

The Backfill failed repeatedly on 2026-09-13 with `HTTP 422` on every release
upload. Diagnosed and fixed the same day: the `data-raw` release had filled to
GitHub's **1000-asset ceiling** — 853 day checkpoints from months long since
complete, plus 89 state snapshots. Raw assets were uploaded and never deleted,
so every day ever checkpointed stayed forever after its month part superseded
it.

`ReleaseStore.publish` now prunes before uploading: day checkpoints go once
their month is complete in the manifest, and state snapshots keep the eight
newest. Month parts, verification receipts and ancillary assets are never
touched. It should self-heal on the first scheduled pass, freeing roughly 825
slots.

**Check that it actually did.** If the release is still at or near 1000 assets,
or Backfill is still failing with 422, the fix did not take and that is the
first thing to repair. The downloader itself was never the problem — it was
finishing months normally right up to the upload failure.

Consequence while it was stuck: the archive sits at **27 verified contiguous
months, 2023-02 … 2025-04**. `2023-01` was 28 days downloaded when the failure
hit, so it should complete quickly. The post-period beyond 2025-04 has not
started.

Two milestone notifications are wired into the backfill and open a GitHub issue
once each: when `2023-01` lands, and when the post-period is complete. Neither
has fired. Do not disable them.

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

**Phase 10 — spillover and mechanism, never run.** The five `boundary` links
straddle 60th Street rather than sitting outside it, and no control link lies
within 500 m of the cordon (nearest ≈ 808 m), so the panel has no units where
diversion would show most clearly. That is a coverage limitation to characterise
honestly, not a null to report. The secondary `i4gi-tjb9` feed — 42 months,
40.2M rows, already held — covers exactly the toll-exempt roads and crossings
where diverted traffic would go. MTA entry and TLC checks have not been touched.

**Phase 11 — the writeup.** The README is current and honest; treat it as the
spine rather than starting over. What it lacks is the mechanism section and any
treatment of the secondary feed.

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

Namespace outputs `H0NN_*`. Both analysis modules take `--out-prefix`, and
`honest_did` also stamps the horizon, because reruns would otherwise overwrite
the artefacts an earlier record cites.

## Infrastructure

Everything runs unattended on GitHub Actions, free, because the owner will not
leave a machine on. `backfill.yml` every six hours (verify, then deepen the
pre-period backwards, then extend forward); `analysis.yml` rebuilds the panel
and reruns Phases 6–9 when data lands; `tests.yml` runs ruff, black and pytest.
211 tests pass. State lives in the `data-raw` release.

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
