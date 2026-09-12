# Agent handoff prompt

Paste everything below the horizontal rule into Codex as the opening task, with
this repo connected. Standing conventions live in `AGENTS.md` and load
automatically; this file is the mission.

---

You are taking over a half-finished causal-inference study. It has been worked
on in bursts across several sessions, and every session has died on the same
rock: the data backfill needs roughly 20–25 hours of continuous downloading, and
the owner will not leave a desktop running overnight. Make that constraint go
away, then finish the study.

Infer intent from context and carry work to completion. Treat "can you", "I want
to" and "help me" as instructions to act. When you hit a question you can answer
by reading the repo, measuring something, or trying it, do that instead of
asking. Prepare a concrete, reviewable result before seeking approval.

## What done looks like

Two things, in this order.

**One.** The remaining ~37 months of E-Z Pass data land without a local machine
involved, for free, resuming by itself after any interruption. The owner opens
their laptop to finished work rather than a job needing supervision.

**Two.** The study reaches a defensible answer to its question: what the
Congestion Relief Zone toll did to traffic speeds inside the zone, and whether
congestion shifted just outside it. A defensible null, or a documented finding
that this design cannot support a causal claim, both count as reaching an
answer. A number that looks good because an assumption went untested does not.

## Instruction priority

When guidance conflicts, this is the order:

1. Anything the owner tells you directly in conversation.
2. Research integrity: the frozen design in `docs/project_brief.md`, honest
   reporting of nulls and failed assumption tests, no causal language without
   defending the assumptions.
3. The two hard constraints: zero dollars, and no dependency on the owner's
   computer being on.
4. This document.
5. `AGENTS.md` and `.cursor/rules/`.
6. Your own judgment about what would be nicer.

Point 2 outranks point 3. If the only honest analysis costs money, say so and
stop rather than quietly weakening the analysis to fit the budget.

## Decide on your own

Implementation shape, file layout, library choices, how to structure the
workflow, what to measure, what to test, how to order the backfill, when to
refactor, commit boundaries and messages.

## Bring to the owner first

- Force-pushing, rewriting published history, or changing repository
  visibility. Working on a branch and opening a pull request is normal and
  needs no approval.
- Any step that would cost money. The correct move is to say it costs money and
  propose a free path.
- Changing anything the brief marks frozen.
- Resolving D1–D7. Bring a recommendation with the evidence behind it. These
  are deliberately open because each changes what the study reports.

Everything else is yours.

## Delegating

Parallel subagents help here more than they usually do, because the slow work is
network-bound rather than CPU-bound. Reasonable splits: one agent probing
download throughput while another drafts the workflow; separate agents on the
staging rebuild and the event-study rerun once data lands. Delegate whenever it
saves wall-clock time or buys an independent check on a result. Err toward
delegating more than feels natural.

## Where the project stands

Tolling began **2025-01-05**. The design is difference-in-differences with
two-way fixed effects (link and time), standard errors clustered by link, plus
an event study. Unit of analysis is link × hour; the outcome is hourly median
link speed in mph. `docs/decision_register.md` carries the detail and is the
file to read first.

Phases 1–8 have run. There is no quotable result.

| Phase | Status |
|---|---|
| 1 Setup | Complete |
| 2 Ingestion | **8 of ~45 months on disk** — the bottleneck |
| 3 Data quality | Checks written, run on the priority window |
| 4 Panel | Built, has a post-treatment period |
| 5 Controls | Naive pool as a documented interim; D2 open |
| 6 Descriptives | Run |
| 7 DiD | Run, not quotable |
| 8 Event study | Run; the formal pre-trend test fails |
| 9–11 Robustness, mechanism, deliverables | Not started |

The provisional DiD on the 7-month window (323 link clusters) gives ATT +0.85
mph overall (SE 0.24, p=0.0004), +0.56 weekday peak, +0.72 weekday off-peak,
+1.30 weekend. Positive and significant in every cut. It stays unquotable
because the pre-period is about three months, control selection is unresolved,
no placebo test exists, and the event study's joint pre-trend test on weeks
k = −12…−2 rejects flatness: `all` χ²=26.6, df=11, p=0.0053; `offpeak` χ²=52.3,
p≈0; `peak` p=0.557 and `weekend` p=0.163 both pass.

The likeliest explanation is the thing you are here to fix. The entire available
pre-period runs 2024-10 through 2025-01-04, which is Thanksgiving through New
Year — a poor window for testing parallel trends. That explanation is plausible
rather than established. A longer, less holiday-dominated pre-period is the only
way to find out, and it may confirm a real violation instead.

One result worth trusting: pre-tolling median speeds come out at treated 7.86
mph, boundary 9.73, control 15.64, exempt-in-zone 19.43, crossings 36.61.
In-zone surface streets landing near 8 mph against roughly 8.2 mph published for
the Manhattan CBD means geometry, unit conversion, treatment assignment and
hourly aggregation are all working. The pipeline measures what it claims to. The
problem is coverage.

## The blocking problem

Target window is 2023-01 through the present, about 45 months. Eight are on
disk: 2024-06, 2024-10, 2024-11, 2024-12, 2025-01, 2025-02, 2025-03, 2025-04.

`data/raw/ezpass_manifest.json` reports coverage as 2024-06 through 2025-04, but
2024-07, 2024-08 and 2024-09 are absent, so the window has a hole and that
`coverage` field misleads. Filling those three months first makes 2024-06
through 2025-04 contiguous.

Measured throughput, from `logs/priority_backfill_20260910_211244.log` and
`logs/catchup_20260911_101305.log`: ingestion fetches one calendar day per
request, roughly 335k raw rows down to 28k kept. A day takes about 45 seconds
when the server is healthy and 120–180 seconds when it is not, with frequent
503s, 500s and read timeouts. A month takes 30–40 minutes, so the ~37 remaining
months come to 20–25 hours.

The parts are tiny: about 5 MB of parquet per month, so the complete 45-month
raw primary dataset is around 225 MB. Latency is the whole difficulty, which is
why free infrastructure can absorb it.

Previous sessions lost work because `download_month()` accumulates a month in
memory and writes the parquet only when the month finishes. Killing it at minute
35 of 40 discards all 35 minutes. The manifest checkpoints across months, never
within one. The logs show a partial 2024-07 and a partial 2023-11 lost this way.

Two more facts for the rebuild. The Socrata app token is already stored as a
GitHub Actions secret named `NYC_OPENDATA_APP_TOKEN`, so a workflow can read it
from `secrets.NYC_OPENDATA_APP_TOKEN`. It is a rate-limit identifier for public
data rather than a credential, but keep it out of files and logs. All eight
parts carry `verified: false`, because row counts were never checked against a
live `count(1)` — `--verify` upgrades that, and should run before any published
number.

## Work order one: ingestion that survives the machine being off

Design it however you think best. The constraints it has to satisfy:

Free, with no trial that later bills. Progress continues while the owner's
computer is off, which rules out anything needing an interactive session or an
open browser tab. Any job can be killed at an arbitrary moment, so checkpoints
have to be fine-grained enough that a kill costs minutes rather than an hour,
and the next run resumes with no manual bookkeeping. Raw parts persist somewhere
durable outside whatever ephemeral disk the job ran on, without bloating `main`.
Socrata is a free public API serving other people, so stay single-threaded
against it and keep the retry and backoff behaviour — the project already
measured that concurrent requests make throughput worse.

GitHub Actions is the obvious fit. The repo is public, so Actions minutes are
not a constraint, and nothing is scheduled yet — `.github/` does not exist. Confirm the current job time limit and runner disk
yourself rather than trusting any number in this document.

Before building scheduling around a 25-hour job, spend about 30 minutes finding
out whether it needs to be 25 hours. Socrata exposes a whole-dataset CSV export
at `/api/views/{id}/rows.csv?accessType=DOWNLOAD` that streams rather than pages;
`erdf-2akx` has ~108M rows and `6a2s-2t65` ~82M, so the full files are large, but
nothing requires landing them — stream through DuckDB or a chunked reader,
filter to `aggregation_period_sec = 900` and the study window, downsample, write
parquet. If it holds a few MB/s it beats paging by an order of magnitude. It may
equally be throttled or time out. Measure it, report the numbers, move on either
way. Ordering by Socrata's internal `:id` instead of
`$order=median_calculation_timestamp,sid` is a second cheap experiment worth
running.

`scripts/priority_backfill.sh` already orders the backfill by analytical value
rather than chronology, so partial progress banks the months that matter most.
Keep that property.

Once raw data flows, the same mechanism should carry staging, the panel build,
descriptives, the DiD and the event study, publishing tables and figures back to
the repo. Anything that leaves the owner running long jobs locally has missed
the point.

## Work order two: finish the study

Re-stage and rebuild the panel on the full window, rerun the data-quality
report, and run `--verify` on the primary parts.

Then rerun Phase 8 on a real pre-period. This is the moment the study turns on:
either the pre-trend test clears once the window is no longer
Thanksgiving-to-New-Year, or it does not and the naive control pool is genuinely
inadequate. Report the answer prominently either way.

Then resolve D2, control selection, which the frozen design says must rest on
pre-treatment trends rather than geography. Match on pre-treatment trend,
restrict to Manhattan above 60th, or build a synthetic control. Pre-tolling
levels differ by nearly 2× between treated and control, which DiD tolerates
since it identifies off changes, though it deserves stating in the limitations.

The remaining open decisions: D1 cleaning thresholds, where 10.2% of readings
rest on three or fewer probe vehicles and 0.085% exceed 80 mph with a monthly
maximum of 962; D3 whether the four 11th Avenue segments are really exempt, a
one-line change in `EXEMPT_PATTERNS` in `src/data/geo.py`; D5 the two
Williamsburg Bridge crossing segments; D6 roadway-name normalisation; D7 how far
back to pull, given the feed reaches 2021-04-08 but 2021–22 carries COVID
recovery dynamics.

Phase 9 is robustness: alternative controls, placebo treatment dates,
alternative pre/post windows, dropping the ±2-week transition, sensor-quality
filters, alternative aggregation. Each is a separate specification rather than
an edit to the primary model, and they land in a comparison table showing
whether the conclusion moves.

Phase 10 covers spillover and mechanism, using the boundary links and the
secondary `i4gi-tjb9` feed — 42 months and 40.2M rows already on disk, covering
exactly the toll-exempt roads and crossings where diverted traffic would go.

Phase 11 fills in the README's Result, Evidence, Robustness, Limitations and
Recommendation sections, which currently read TBD under a "no quotable result
yet" banner. That banner comes down when the evidence earns it.

## Verification

Test what would otherwise break silently: transformations in `src/`,
treatment assignment, the panel build, anything touching timestamps. Existing
coverage is 58 tests. Exhaustive suites around straightforward code cost more
than they return here, so keep verification proportionate.

The check that matters more than any unit test is whether a result survives
contact with the robustness table. Treat that as the real verification step.

## Stopping

Work through both work orders without pausing for permission between steps.
Stop when you hit something in "bring to the owner first", when a measurement
contradicts this brief in a way that changes the plan, or when both work orders
are done.

Running out of easy work is not a stopping point. If ingestion is waiting on a
scheduled job, move to the analysis, the documentation, or the open decisions.

## First

Read `docs/decision_register.md`, then form your own view of the repo state.
Parts of this brief will be stale; correct it rather than trusting it, and say
what you found that differs.
