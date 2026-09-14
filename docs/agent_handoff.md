# Agent handoff prompt

Give the next session this repository and one instruction:

> Read `docs/agent_handoff.md` and carry out the mission it describes.

`AGENTS.md` loads automatically and carries the standing conventions. Everything
below the rule is the mission.

---

You are taking over a causal-inference study that is **finished**, in the sense
that matters: the data are complete, the pipeline is healthy, nine
pre-registered hypotheses are answered, the six open design decisions are
resolved, and the README reports the finding from current artefacts.

**The job left is judgement, not production.** One result needs a verdict that
its own author should not give. One by-product deserves a record. One dataset is
untried and may not be worth trying. Everything else is done.

Read "Where results can and cannot come from" before planning anything. **The
most likely way to damage this study now is to find something to run.**

Infer intent from context and carry work to completion. When a question can be
settled by reading the repo, measuring something, or running it, do that instead
of asking.

## Start here, in this order

1. `docs/hypotheses/REGISTER.md` — every hypothesis, its status and verdict.
2. `docs/hypotheses/README.md` — the protocol you must follow. Short, not optional.
3. `README.md` — the current public finding.
4. `docs/decision_register.md` — the audit trail, newest entry first.

## The state, in one pass

Confirm rather than re-derive:

    "C:/Program Files/GitHub CLI/gh.exe" run list --workflow analysis.yml --limit 3
    "C:/Program Files/GitHub CLI/gh.exe" run list --workflow backfill.yml --limit 3

Both newest runs should be green. If they are, there is no pipeline work.

- **Archive complete.** 44 of 44 frozen months, 2023-01 … 2026-08, all verified.
  24 pre-treatment months, 20 post. The backfill has nothing left to fetch and
  now exits early.
- **Results current.** `analysis.yml` rebuilds the panel and Phases 6-9 when the
  backfill completes, and takes `workflow_dispatch`. About five minutes.
- **Decisions closed.** D1-D7 resolved 2026-09-14; no code changed as a result.
- **264 tests pass.** State lives in the `data-raw` release, which sits in
  the low hundreds of assets and no longer drifts toward the 1000 ceiling.
  The exact count moves as months complete and their day checkpoints are
  pruned; what matters is that it is nowhere near the cap.

Everything that broke on 2026-09-13 is fixed and verified: a release that had
filled to GitHub's 1000-asset ceiling, and an analysis failing on an unmatched
segment. Details are in `docs/decision_register.md` if you need them; you should
not. Three consequences do matter:

`publish` **replaces** `ANCILLARY` assets (segment table, weather) rather than
refusing them; month parts and day checkpoints remain immutable and a test pins
that. A failing HARD data-quality check **prints its offending rows** to stderr.
And the segment roster is **reconciled** against the parts on disk rather than
sampled — `missing_segment_sids` plus `top_up_segments`, before staging.

`gh` is installed and authenticated but **not on the Git Bash PATH**. Call it by
full path or from PowerShell. Without it the Actions log API returns 403 and
failures are undiagnosable from outside.

Scheduled runs are delayed hours past their cron slots. **State that has not
changed shortly after a push means the job has not run, not that it failed.**
Check `run_started_at` or an asset's `created_at` against your push before
concluding anything — an hour was lost to that on 2026-09-13.

## What the study found

Speeds inside the Congestion Relief Zone rose about **1.05 mph** relative to
comparison streets after tolling began on 2025-01-05, roughly 11% of the
pre-tolling treated mean. That association is robust. **It cannot be attributed
to the toll.**

| | Finding |
|---|---|
| **H001** | Clustered SEs up to 1.5× too tight; weekday peak fails randomisation inference at p = 0.092 |
| **H002** | Breakdown values 0.044–0.151 on 36 pre-weeks |
| **H003** | Daily aggregation stable; collapsing to one pre/post per link inflates SEs 3.8–6.2×, zero enters every interval, off-peak flips sign |
| **H004** | Both matching rules rejected out of sample; nearest-neighbour made it worse |
| **H005** | Breakdown values 0.005–0.171 on 96 pre-weeks, falling as the horizon widens |
| **H006** | Every control set rejects on a clean July–September holdout; holidays aggravate the failure but do not cause it |
| **H007** | The secondary feed cannot measure diversion either — it stops reporting on three of nine exempt in-zone links, availability diverging 21.2 points against a 5-point bar. A measurement failure, not an identification one |
| **H008** | Entries jump at both moments the toll price changes. Uninformative: the 21:00 boundary (+12.9%) missed a placebo maximum of 13.9%. Response confined to cars and motorcycles, predicted backwards |
| **H009** | Superseding H008 with a control that pays no toll. At 05:00 tolled entries fall 69 log points while exempt entries on the same sensors rise 7; difference −0.759 [−0.795, −0.723]. Does not support **as specified** |

The joint pre-trend test rejects in all four samples on the full 104-week
pre-period: χ² 97.9, 69.7, 102.2, 46.7 on 11 dof. Lengthening the pre-period
never rescued it. Every explanation that would have saved the finding — too
little pre-period, an atypical holiday window, a poor comparison group — has
been tested, and **the pre-period explanation is now exhausted rather than
merely unlikely: there is no more to add.**

**Do not reopen this.** Searching for a control set that passes is another draw
against fixed data and the register carries the count. None of this is evidence
that congestion pricing did nothing; it is evidence that this comparison design
cannot tell you either way. Hold that distinction in every sentence you write —
it is the study's contribution.

## The three things actually left

**1. The timing result needs a verdict, and its author should not give it.**

H008 and H009 found a large, precisely estimated behavioural response to the
toll's peak/overnight price schedule, identified off a discontinuity rather than
parallel trends. The strongest piece: at 05:00 tolled entries fall 69 log points
while toll-exempt vehicles on the same sensors, in the same ten-minute blocks,
*rise* 7 — a difference of −0.759, consistent at all four dual-recording points.
No clock, sensor artefact or curvature does that, because each would move both
series together.

Neither record cleared its own pre-registered bar, and both criteria were flawed
in the same way. **A third record rewriting the criterion is the wrong move**:
the estimate would not shift, only the label, and the label would then have been
chosen by someone who already knew it. Whether this counts as supported is a
judgement for a reader of the three records. If you disagree and register H010,
say in it explicitly why you are not simply relabelling, and expect scepticism.

**2. Route substitution is unregistered and unclaimed.**

Exempt-roadway entries *rising* as tolled entries collapse at 05:00 is the first
direct evidence of diversion this project has obtained from any source. H007
could not see it on the speed feed because the sensors on those roads had
failed. It is a by-product of a design aimed at something else, so it is flagged
in H009 and claimed nowhere. It would need its own record — and that record
would be a genuinely new question, not a re-score.

**3. TLC trip records are the only untried source with a pre-period.**

Not ingested. Would need its own record. Weigh whether it is worth it: a clean
TLC result would describe a "cannot identify" finding better rather than change
it. Its current distribution is monthly files outside the Socrata endpoints this
project uses, and that source has **not** been verified — confirm it rather than
assuming.

## Where results can and cannot come from

Be honest with yourself about this before planning. The instinct to produce a
positive finding is exactly what the protocol exists to resist.

**Closed, and not by accident.** The speed question. Seven hypotheses, a
completed archive, a full 24-month pre-period, three attempts at control
construction. The design cannot identify the effect and more specifications will
not change that — they will only eventually produce a clean-looking one by
chance.

**Open, and where anything real will come from.** Designs that do not need
parallel trends. The toll's own price structure is the existing example and it
worked: a discontinuity in time-of-day, with a control group that pays nothing.
That is why H008 and H009 produced something the speed panel never could.

**A note on what "results" means here.** The documented failure to identify *is*
a result, and it is the study's most defensible one. A study that says "here is
what these data can and cannot support, and here is the evidence for both" is
finished work, not a draft awaiting a better number. If you end a session having
confirmed that and added nothing, say so — that is a valid and correct outcome.

## How this project has recently gone wrong

Two habits, both learned the hard way on 2026-09-13.

**Acceptance criteria failed twice in a row, the same way.** H008 compared an
estimate to a *maximum* over 21 placebo boundaries, a set contaminated by a
morning ramp where a local linear fit cannot track fivefold growth. H009
required a control series to show no *significant* movement, which 609 days and
125M observations can never deliver — it demanded a precisely estimated zero. A
refutation condition in the same record encoded the identical idea correctly,
with a magnitude threshold, and behaved fine.

So: **state criteria as magnitudes you would find convincing, never as
significance or tail statistics**, and before freezing, ask whether a true
effect of the size you expect could actually satisfy them. Two consecutive
failures by one author should also tell you to have criteria read by something
other than whatever wrote them.

**Check a fix against live state instead of assuming it took.** The release
prune was simulated asset-by-asset before being pushed, and that is how two
further defects surfaced. And when a failure is opaque, make it explain itself
rather than guessing from outside — the unmatched segment was found in one line
only after the check was made to print its rows.

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

Anything whose output could reach the README needs a record committed **before**
it runs. Namespace outputs `H0NN_*`. `control_construction` and `honest_did`
take `--out-prefix`, and `honest_did` stamps the horizon, because reruns would
otherwise overwrite artefacts an earlier record cites. `did`, `event_study` and
`placebo_space` do not take one and load `HOURLY_PANEL_PATH` in their own
`load()`; H007 and H009 imported their functions from modules of their own
rather than repointing that path, which is the pattern to copy.

**Do not restate H001–H006 against the 44-month panel.** Each cites the
artefacts it was answered on; rerunning one is a fresh draw. The README's
labelling reflects this and should be preserved: the association, pre-trend test
and robustness table are rebuilt by `analysis.yml` from the current panel, while
each record stands on its own.

Before touching the secondary speed feed: read the zero-speed entry in
`AGENTS.md`. `speed = 0` means **outage**, not standstill. Start from
`data/processed/secondary_hourly_panel.parquet`, not `spillover_diagnostics.py`,
whose committed table averages 8.8M outages in as 0 mph and is superseded.

## Infrastructure

Everything runs unattended on GitHub Actions, free, because the owner will not
leave a machine on. `backfill.yml` every six hours; `analysis.yml` on backfill
completion or `workflow_dispatch`; `tests.yml` runs ruff, black and pytest.

To work locally: pull month parts, the manifest and the segment table from the
release, then `build_staging` → `geo` → `build_panel`.

## Constraints

Zero budget, Python only, unattended on free runners. Research integrity
outranks the budget: if the only honest analysis costs money, say so rather than
quietly weakening it.

Cite with author, year and venue. Flag anything you cannot cite precisely —
models fabricate confidently in this domain, and two records in this repo carry
citations with page ranges deliberately left unverified rather than guessed.

## Bring to the owner first

- Force-pushing, rewriting published history, changing repository visibility.
  Branches and pull requests need no approval.
- Anything that costs money.
- Changing anything `docs/project_brief.md` marks frozen.
- **Reopening a resolved decision.** D1-D7 were settled on 2026-09-14 with
  reasoning in `docs/decision_register.md`. If evidence contradicts one, bring
  it rather than quietly re-deciding — especially **D3**, whose rejection rests
  on the feed naming 11th Avenue "11 Ave/Rt 9A" plus a continuous 23rd-to-57th
  alignment, and not on an MTA tolling document. A tolling document or NYSDOT
  route log would settle it beyond doubt.
- Pushing to a remote. `AGENTS.md` says ask and this brief does not, which is a
  real conflict. Put to the owner on 2026-09-13; they chose push-to-main, so
  that is the standing answer — but say what you pushed.

## Stopping

Work through this without pausing for permission between steps. Stop when you
hit something in the list above, when a measurement contradicts this brief in a
way that changes the plan, or when the work is done.

**The work may already be done.** If both workflows are green, the register
shows nine answered hypotheses, and the README quotes the current tables, then
the honest report is that there is nothing to do. Saying so is better than
manufacturing a hypothesis to fill the session.

## First

Confirm the two workflows are green, then form your own view of the repo. Parts
of this brief will be stale — it has been wrong before in ways that mattered. It
once said a prune freed 825 slots when the rule as written freed 489, and that
2023-01 was 28 days downloaded when the snapshot said 22. **Correct it rather
than trusting it, and say what you found that differs.**
