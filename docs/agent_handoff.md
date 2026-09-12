# Agent handoff prompt

Paste everything below the horizontal rule into Codex as the opening task, with
this repo connected. Standing conventions live in `AGENTS.md` and load
automatically; this file is the mission.

---

> **Takeover audit, 2026-09-12.** Read the newest decision-register entry before
> the historical status below. The old event-week boundary and joint pre-trend
> test were incorrect. Corrected tests reject in all four samples, including
> on the original contiguous window. Twelve exploratory robustness specs now
> exist, but source verification and owner decisions remain open. The old
> `--verify` compared sampled counts with raw counts; the replacement performs
> resumable raw-count plus deterministic replay. Backfill had never run and
> Analysis failed on an absent release; consult the register for actual rollout
> status. The README records that the current design cannot support a causal
> claim, while the full frozen study remains incomplete. No D1–D7 decision was
> newly adopted. Review `docs/owner_decisions.md` with the owner before doing so.

You are taking over a causal-inference study that is most of the way to an
answer and stuck on one thing. Finish it.

Infer intent from context and carry work to completion. Treat "can you", "I want
to" and "help me" as instructions to act. When a question can be settled by
reading the repo, measuring something, or trying it, do that instead of asking.
Prepare a concrete, reviewable result before seeking approval.

## What done looks like

The study reaches a defensible answer to its question: what the Congestion
Relief Zone toll did to traffic speeds inside the zone, and whether congestion
shifted just outside it. A defensible null counts. So does a documented finding
that this design cannot support a causal claim. A number that looks good because
an assumption went untested does not.

Concretely, that means the README's Result, Evidence, Robustness, Limitations
and Recommendation sections say something true, and the "no quotable result yet"
banner is gone because the evidence earned it.

## Instruction priority

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

Implementation shape, file layout, library choices, what to measure, what to
test, when to refactor, commit boundaries and messages, and how to structure any
workflow changes.

## Bring to the owner first

- Force-pushing, rewriting published history, or changing repository
  visibility. Branches and pull requests are normal and need no approval.
- Any step that would cost money. Say it costs money and propose a free path.
- Changing anything the brief marks frozen.
- Resolving D1–D7. Bring a recommendation with the evidence behind it. These are
  deliberately open because each changes what the study reports.

## Delegating

Parallel subagents help here more than usual, because much of the slow work is
network- or IO-bound. Reasonable splits: the staging rebuild and the
event-study rerun; separate agents on separate robustness specifications, which
are independent by construction. Err toward delegating more than feels natural.

## Where the project stands

Tolling began **2025-01-05**. The design is difference-in-differences with
two-way fixed effects (link and time), standard errors clustered by link, plus
an event study. Unit of analysis is link × hour; the outcome is hourly median
link speed in mph. `docs/decision_register.md` carries the detail.

Phases 1–8 have run. There is no quotable result.

| Phase | Status |
|---|---|
| 1 Setup | Complete |
| 2 Ingestion | 8 of 44 months; automated, see below |
| 3 Data quality | Checks written and run |
| 4 Panel | Built, has a post-treatment period |
| 5 Controls | Naive pool as a documented interim; D2 open |
| 6 Descriptives | Run |
| 7 DiD | Run, not quotable |
| 8 Event study | Run; the pre-trend test fails on two of four samples |
| 9–11 Robustness, mechanism, deliverables | Not started |

The provisional DiD on the 7-month window (323 link clusters) gives ATT +0.85
mph overall (SE 0.24, p=0.0004), +0.56 weekday peak, +0.72 weekday off-peak,
+1.30 weekend. Positive and significant in every cut, and unquotable.

## The one thing in the way

Everything downstream — D2, robustness, the writeup, any causal sentence —
waits on the pre-trend test. Current verdicts are in
`outputs/tables/pretrend_tests.csv`:

| Sample | chi2 | p | Verdict |
|---|---:|---:|---|
| all | 26.58 | 0.0053 | FAIL |
| offpeak | 52.32 | ~0 | FAIL |
| peak | 9.71 | 0.557 | pass |
| weekend | 15.44 | 0.163 | pass |

The likeliest explanation is that the only pre-period available runs 2024-10 to
2025-01-04, which is Thanksgiving through New Year. That is plausible, not
established, and it may instead be a real parallel-trends violation.

`python -m src.data.coverage_report` prints how far the backfill is from
answering that. The number that matters is the **longest unbroken pre-period**,
currently 3 months against the 12 a credible test wants. Post-treatment months
do not help this at all, however many land.

## What already runs without anyone watching

The backfill is ~21 hours against a feed that throttles, and the owner will not
leave a machine on. That is solved and you should not rebuild it:

- Each day is checkpointed to `data/raw/ezpass_days/` as it lands, so an
  interruption costs a day rather than a month. Parquet writes are atomic.
- `--max-runtime` and `--month-budget` let a run stop cleanly against a clock
  instead of being killed mid-write.
- `.github/workflows/backfill.yml` runs every six hours, downloads for about
  five, publishes to the `data-raw` release and exits. `analysis.yml` rebuilds
  the panel and reruns Phases 6–8 when data lands, committing `outputs/`.
  `tests.yml` runs ruff, black and pytest.
- `scripts/priority_backfill.sh` holds the range order, pre-period first. Its
  union covers the whole frozen window, so a fresh environment converges on
  complete coverage on its own.

**Caveat: as of this writing those workflows had been validated locally but
never actually run on GitHub Actions.** Check whether they have, and whether
they are succeeding, before assuming data is flowing. If the first runs failed,
fixing them is the highest-value thing you can do, because everything else waits
on data. Treat a red run as the priority, not a distraction.

One measurement never got made, and is worth 30 minutes because it could
compress 21 hours into one: Socrata exposes a whole-dataset CSV export at
`/api/views/{id}/rows.csv?accessType=DOWNLOAD` that streams rather than pages.
`erdf-2akx` has ~108M rows and `6a2s-2t65` ~82M, so the files are large, but
nothing requires landing them — stream through DuckDB, filter to
`aggregation_period_sec = 900` and the study window, downsample, write parquet.
If it holds a few MB/s it beats paging by an order of magnitude; it may equally
be throttled or time out. Ordering by Socrata's internal `:id` rather than
`$order=median_calculation_timestamp,sid` is a second cheap experiment. Measure,
report numbers, move on either way.

## The work

Rerun Phase 8 as the pre-period deepens. This is the gate, and the answer goes
in the decision register either way. If the test clears once the window is no
longer holiday-dominated, the study is unblocked. If it still fails on a year of
clean pre-period, the naive control pool is genuinely inadequate and that is a
real finding, not a setback.

Resolve D2, control selection, which the frozen design says must rest on
pre-treatment trends rather than geography: match on pre-treatment trend,
restrict to Manhattan above 60th, or build a synthetic control. Pre-tolling
levels differ by nearly 2× between treated and control, which DiD tolerates
since it identifies off changes, though it belongs in the limitations.

Run `--verify` on the primary parts before quoting any number. All of them
currently carry `verified: false`, meaning paging finished cleanly but row
counts were never checked against a live `count(1)`.

Then the remaining open decisions: D1 cleaning thresholds, where 10.2% of
readings rest on three or fewer probe vehicles and 0.085% exceed 80 mph with a
monthly maximum of 962; D3 whether the four 11th Avenue segments are really
exempt, a one-line change in `EXEMPT_PATTERNS` in `src/data/geo.py`; D5 the two
Williamsburg Bridge crossing segments; D6 roadway-name normalisation; D7 how far
back to pull, given the feed reaches 2021-04-08 but 2021–22 carries COVID
recovery dynamics.

Phase 9 is robustness: alternative controls, placebo treatment dates,
alternative pre/post windows, dropping the ±2-week transition, sensor-quality
filters, alternative aggregation. Each is a separate specification rather than
an edit to the primary model, and they land in a comparison table showing
whether the conclusion moves.

Phase 10 covers spillover and mechanism, using the boundary links and the
secondary `i4gi-tjb9` feed — 42 months and 40.2M rows already held, covering
exactly the toll-exempt roads and crossings where diverted traffic would go.

Phase 11 is the writeup.

## Verification

Test what would otherwise break silently: transformations in `src/`, treatment
assignment, the panel build, anything touching timestamps. Existing coverage is
68 tests. Exhaustive suites around straightforward code cost more than they
return, so keep verification proportionate.

The check that matters more than any unit test is whether a result survives the
robustness table. Treat that as the real verification step.

## Stopping

Work through this without pausing for permission between steps. Stop when you
hit something in "bring to the owner first", when a measurement contradicts this
brief in a way that changes the plan, or when the study has an answer.

Waiting on data is not a stopping point. The backfill fills in over days, so
when it is mid-flight, move to the open decisions, the robustness
specifications, the spillover analysis, or the writeup scaffolding.

## First

Read `docs/decision_register.md`, check whether the workflows have run and are
green, then form your own view. Parts of this brief will be stale; correct it
rather than trusting it, and say what you found that differs.
