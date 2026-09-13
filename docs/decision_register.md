# Decision Register

**NYC Congestion Relief Zone · speed study**

Compiled 2026-09-09, updated 2026-09-13 · treatment date 2025-01-05 ·
Validation details are recorded in the latest dated entry below.

Six decisions are open. Earlier entries are historical and are superseded
where the latest audit says so. Each open decision changes what the study reports, so it is
deliberately left unmade rather than defaulted into the panel.

## Update 2026-09-13 — the secondary feed cannot measure diversion either, and the reason is measurement

[H007](hypotheses/H007-secondary-feed-diversion.md) is answered and **refutes**.
The spillover question is now closed on both feeds, for two different reasons,
and the difference between them is the useful part.

The primary E-Z Pass roster cannot answer it because it contains no units where
diversion would show — the five `boundary` links straddle 60th Street and the
nearest control is 808 m out. That is a coverage limitation. The secondary DOT
feed (`i4gi-tjb9`) does carry the nine toll-exempt in-zone links traffic would
divert onto, and it cannot answer it either, because **it stops measuring three
of them**. `4616325` (11th Ave S) has never emitted a positive speed in 41
months. `4616323` and `4616338` (12th Ave S and N) report at full availability
through March 2024, degrade in April, and go permanently dark from May 2024.
The treated group is eight contributing links before the toll and six after,
and the three that leave are the whole West Side Highway arm of the design.

The pre-registered availability gate measures this as a **−21.16 pp**
differential change in usable-hour availability against a 5 pp bar, identical to
within 0.25 pp in all four hour-of-week cuts. The joint pre-trend test also
rejects (χ² = 86.0 on 11 monthly leads, p = 1e-13) and the Rambachan–Roth
breakdown value is 0.000–0.034, so all three refutation conditions fire. **Read
the verdict off the availability gate.** The other two consume a cluster-robust
covariance matrix resting on nine treated clusters, which is exactly the regime
the same record calls untrustworthy; the availability gate is a count of hours
and needs no asymptotics at all.

**The break predates the toll by eight months**, so it is instrumentation, not
the intervention. That is what makes this a measurement failure rather than a
parallel-trends failure, and it says what better data would fix: working speed
sensors on the 11th/12th Avenue corridor across the toll date. A better control
pool, a different estimator and more draws would all change nothing.

The estimate, which is not quotable: ATT +0.354 mph on all hours (clustered SE
1.457, randomization p = 0.804 on 500 draws), positive where diversion predicts
negative. The clustered standard errors run 10–26% tighter than the
randomization null, consistent with H001. The design's 80%-power minimum
detectable effect is 4.85 mph, 17% of the pre-treatment treated mean — even with
clean diagnostics it could not have seen a diversion effect the size of the
study's own headline association.

**Two artefacts change status.** `data/processed/secondary_hourly_panel.parquet`
is new, built by `python -m src.data.build_secondary_panel`, and is the panel
any future secondary-feed work should start from; it treats zero-speed readings
as the outages they are. `outputs/tables/spillover_secondary_monthly.csv` is
**superseded**: `src/analysis/spillover_diagnostics.py` filters only
`speed_mph IS NOT NULL` and so averages 8.8M zero-speed outages in as 0 mph.
Speed levels taken from it are biased toward zero by roughly the local outage
rate. The primary panel is unaffected — zero-speed readings are at most 0.014%
of any `treatment_group × post` cell there.

**Still open.** Whether diversion occurred. H007 establishes only that this feed
on these nine links cannot measure it. The restricted design its Verdict names —
treated limited to the six links reporting throughout — is a new hypothesis and
must be registered before it runs.

---

## Update 2026-09-13 — the "geometric backstop" in geo.py was dead code, and could not have worked

`src/data/geo.py` defined a Manhattan bounding box (`_in_manhattan_envelope`,
`MANHATTAN_LON_MIN`/`MAX`, `MANHATTAN_LAT_MIN`/`MAX`) and a comment calling it
the geometric backstop on the borough label. Nothing called it. It has been
removed and the docstrings corrected. **No treatment assignment changed**: the
primary roster still classifies 185 control, 148 treated, 6 exempt, 5 boundary,
2 crossing, exactly as before.

Wiring it in was the other option, and was measured first. It fails on both
feeds. On the primary E-Z Pass roster it is a provable no-op — all 176
Manhattan-labelled segments lie wholly inside the box. On the secondary feed
(`i4gi-tjb9`) it does not catch the two links it was supposed to catch, because
the box has to reach 40.680 N to cover the Battery and therefore also covers
downtown Brooklyn. Links `4616339` and `4616340` — the BQE approaches to the
Brooklyn and Manhattan Bridges, labelled `borough = Manhattan` with Brooklyn
geometry — sit entirely inside it. So do ten Brooklyn-labelled E-Z Pass
segments on Atlantic Ave and Flatbush Ave.

Requiring every vertex inside the box instead moves six links, each for the
wrong reason. Four have corrupt geometry, with vertices decoding to longitudes
near zero (`4616324`, `4620343`, `4616332`, `4456511`). The two
Brooklyn-Battery Tunnel links reach Brooklyn because the tunnel does, and both
are in H007's treated group: `4456494` and `4456502` would have been moved into
its control group. That is worse than the problem.

**What remains open.** `classify_segment` still trusts the borough label alone,
so the two BQE approaches still come back `treated`, which is wrong — an
approach to a tolled crossing is toll-exposed, and plain `control` would be
wrong too. H007 excludes both by `link_id`, which is the proportionate fix
while two links are affected. If a later feed or a longer roster makes the
disagreement general, the fix is a river-side or borough-polygon test, not a
bounding box. `tests/test_geo.py` pins all three facts: the borough label is
the only gate, the BQE misclassification is characterised so that changing it
has to be deliberate, and a bounding box provably cannot backstop the label.

---

## Update 2026-09-12 — inference corrected; the current design cannot identify the effect

The takeover audit found two statistical implementation errors, an unusable
verification command, and an unstarted hosted backfill. The mission was not
blocked only by throughput. No open owner decision or frozen definition was
changed. Recommendations are in [owner_decisions.md](owner_decisions.md).

**Current answer.** The implemented comparison design cannot support a causal
claim about speed improvements or nearby diversion. This is not a causal null
and does not establish that a better control design will fail. The README now
reports this finding, withholds effect magnitudes until source verification
completes, and identifies the remaining work. Files in `outputs/tables/` are
explicitly provisional computational diagnostics on the stored archive.

**Invalid old gate.** The event-study joint test had summed squared individual
t statistics, ignoring covariance between the leads. It now uses the full
link-cluster covariance in a Wald test and records method, rank and tested bins.
DuckDB's integer week difference also put January 1–4 into event week zero;
the corrected floor-of-elapsed-days definition keeps every pre-tolling hour
negative. The weather event study no longer allocates an N×N projection.
Regression tests compare the covariance calculation and weather residualization
with independent matrix/explicit fixed-effects calculations.

**Rerun.** All four corrected pre-period tests reject on the current eight-month
archive. Rejection also occurs on the original contiguous October–April window,
so the isolated June month is not the explanation. Exact diagnostics are in
`pretrend_tests.csv` and `robustness_pretrend_contiguous.csv`. These supersede
every earlier joint test and pass/fail label in this register. Holidays remain
an untested explanation. The ±12-week endpoint bins pool more distant weeks;
new metadata makes that explicit rather than implying a full-year weekly test.

**Robustness.** Twelve separate specifications now run reproducibly, including
geographic controls, quality exclusions, hourly mean, transition removal,
common-link roster, two pre-period placebos and a D3 assignment sensitivity.
Non-placebo associations remain positive, but are sensitive to control choice.
The two placebo tests do not reject zero. Neither finding repairs rejected
leads. Matching with held-out validation, a full-year placebo and daily
aggregation remain pending; D1/D2/D3 remain unadopted.

**Spillover.** The five primary boundary links straddle the cordon. The distance
audit finds no wholly outside Manhattan control within 500 m of the current
line, and nine within 1 km. A 500 m outside-band analysis therefore has no
primary units. This is a coverage limitation, not demonstrated control
contamination at 500 m. The secondary archive actually holds 42,216,965 raw
rows; the descriptive replay retains 42,210,837 readings after null/duplicate/DST
handling, producing 3,532,556 link-hours and 5,199 link-months across 42 months.
These summaries make no causal diversion claim. Both bridge directions are
retained separately by link; the older claim that both measure entry was wrong.

**Archive and quality.** Primary coverage remains eight of 44 complete target
months: June 2024 and October 2024–April 2025. Staging now includes all held
months: 5,977,804 readings produce 1,587,630 link-hours. The July–September gap
leaves only three contiguous full pre-treatment months. The larger quality
audit finds 10.97% of readings at three probes or fewer, 0.1125% above 80 mph,
and a maximum of 7,043.9 mph. The common-link sensitivity is not a balanced
hour-by-hour panel claim.

**Verification repaired.** The old `--verify` compared retained 15-minute rows
with the unsampled source count and never updated the manifest. Verification
now compares raw-page totals with live raw counts, repeats deterministic
downsampling, and compares the retained fields against immutable disk data.
Day receipts bind to the raw part's hash and the versioned verification method.
Only a completed matching replay upgrades a month. `--verify-existing` and a
runtime budget allow hosted passes to resume. Legacy flags cannot become
current verification evidence merely because a file exists or has a matching
hash. End dates are exclusive, and in-progress months must never be finalized.
The one-minute live verification probe completed and matched June 1–3 against
the source, then exited cleanly before the next page (about 75 seconds elapsed,
including an in-flight request). Three daily receipts are held; June remains
unverified until all 30 days match. No raw part bytes changed.

**Hosted diagnosis.** At 16:59 UTC there had been no Backfill run. The first
Analysis run had failed because the `data-raw` release did not exist and DuckDB
found no raw parquet files. The latest Tests run was green. Exact URLs and the
failure excerpt are in `outputs/tables/workflow_audit.json`. Workflow fixes
make absent/pre-only input explicit, fail on actual release download errors,
persist verification receipts, and run sensitivity/provenance generation.
The jobs use standard hosted runners and refuse private repositories, preserving
the zero-dollar constraint. See the deployment entry below for actual rollout
status; a YAML fix alone is not evidence that a hosted job succeeded.

**Measured export experiment.** Sequential anonymous probes streamed the first
16 MB of each full-dataset CSV at 1.72 and 2.11 MB/s, including startup. Three
50,000-row paging probes exceeded a 35-second read timeout; the remaining
`:id` probe achieved 0.23 MB/s. The sample is capped and not evidence of sustained
whole-export throughput, total transfer size or identical retained data. The
existing backfill is preserved. Commands and exact timings are in
`scripts/benchmark_socrata.py` and `outputs/tables/socrata_benchmark.json`.

**Local validation:** 121 synthetic tests pass, with one expected pandas warning
from the deliberately malformed-timestamp fixture. Ruff and Black pass across
source, tests and scripts. Bash/YAML validation passes. Staging, panel building,
all four event studies, weather sensitivities, 12 robustness fits and the
secondary summary completed on the actual stored data. Passing these checks
does not substitute for source verification or the robustness assumptions.

### Hosted deployment verified — 2026-09-12

[PR #1](https://github.com/captaincereal/nyc-congestion-pricing/pull/1) passed
hosted tests and merged as `af93a066`. The original eight immutable primary
parts, segment/weather files, manifest and three-day June verification receipt
were seeded into the [data release](https://github.com/captaincereal/nyc-congestion-pricing/releases/tag/data-raw).
Upload digests were checked; no existing raw part was overwritten.

The first repaired [Analysis run](https://github.com/captaincereal/nyc-congestion-pricing/actions/runs/34707540983)
completed successfully and committed its regenerated results as `0c6ca41`.
[Tests on merged main](https://github.com/captaincereal/nyc-congestion-pricing/actions/runs/34707540919)
also passed. Its corrected joint-test verdicts agree with the local run.
The hosted panel was downloaded and matched the tracked provenance hash.

[Backfill](https://github.com/captaincereal/nyc-congestion-pricing/actions/runs/34707558019)
was explicitly started on main. At the recorded check its setup and archive
restore had succeeded and its Download step was running; verification and
publication were still pending. This is confirmation of an active hosted run,
not a claim that the missing months or full verification have completed.
The existing six-hour schedule will resume later passes without owner uptime.
Exact statuses, asset digests and check time are in
`outputs/tables/hosted_rollout.json`. The saved local project has the delivered
code and corrected derived data. The next research action is owner review of
the six open recommendations, while hosted data collection continues.

Everything below this entry is historical unless explicitly reconfirmed above.

> **Update 2026-09-10.** Since this register was first compiled the priority
> window (2024-10 … 2025-04, seven months, three either side of the toll) has
> been ingested and staged, the panel rebuilt with a post-treatment period, and
> **Phases 6 (descriptives) and 7 (difference-in-differences) run** — see "The
> result so far" below. **D4 is resolved** (5763399). The full pre-period
> backfill to 2023-01 now runs unattended in CI (see the 2026-09-12 entry). The Phase 7 DiD is
> **not quotable**: it rests on a 7-month window, parallel trends has no formal
> test yet (Phase 8, needs the backfill), control selection is still open (D2),
> and there is no placebo test. (Phase 8 has since run and the pre-trend test
> fails — see the 2026-09-12 entry below.)

---

## Update 2026-09-12 — the backfill no longer needs a machine left on

The binding constraint was never Socrata's throughput on its own. It was
throughput *times* the requirement that one machine stay awake for all of it.
Ingestion had two properties that made an interruption expensive: a month was
accumulated in memory and written only on completion, and nothing bounded a run
against a clock. Killing it at minute 35 of 40 discarded all 35, which is how
the partial 2024-07 and 2023-11 pulls were lost.

Three changes remove that.

**Day checkpoints.** Each day now lands in `data/raw/ezpass_days/` as it
completes and the month part is assembled from those, so an interruption costs
one day. Parquet writes go through a temp file and a rename, so no kill can
leave a torn part that later reads as a complete month.

**A wall-clock budget.** `--max-runtime` stops a run cleanly and `--month-budget`
keeps it from starting a month it cannot finish, so a scheduled job ends by its
own choice with nothing in flight rather than being hard-killed.

**Scheduled execution.** `.github/workflows/backfill.yml` runs every six hours,
downloads for about five, publishes to the `data-raw` release and exits;
`analysis.yml` rebuilds the panel and reruns Phases 6-8 whenever data lands.
The release is the resume state, since a runner's disk does not survive the job.

Two instruments came with it, because a pipeline nobody watches has to report
on itself. `src/data/coverage_report.py` answers how far the backfill is from
what the study needs — leading with pre-period depth rather than month count,
since post-treatment months do not help the pre-trend test. And
`event_study.py` now upserts its verdict into
`outputs/tables/pretrend_tests.csv`, so the gate on every estimate in this
project is a file rather than a line in a log. `outputs/` is tracked from now
on, which makes each increment of data a visible diff.

The four pre-trend tests reproduce exactly after the rewrite (all chi2=26.58
p=0.0053, offpeak 52.32 p~0, peak 9.71 p=0.557, weekend 15.44 p=0.163),
confirming the checkpointing changed nothing about what the pipeline computes.

**Nothing about the analysis changed.** Eight months are still on disk, two of
four samples still fail the pre-trend test, and D2 is still open. This entry
records that the project can now make progress while nobody is watching, not
that it has made any.

---

## Where the project stands

| Phase | | Status |
|---|---|---|
| 1 | Setup | Complete |
| 2 | Ingestion | **8 of 44 months** on disk (2024-06, then 2024-10 … 2025-04); the rest runs on a schedule in GitHub Actions |
| 3 | Data quality | Checks written and run on the seven months |
| 4 | Panel | Built, with a post-treatment period (2025-01-05 onward) |
| 5 | Controls | Naive pool used as a documented interim; **D2** still open |
| 6 | Descriptives | Run — weekly series, pre-trend gap, hourly profile, coverage |
| 7 | Difference-in-differences | Run on the 7-month window (not quotable — see below) |
| 8 | Event study | Rewritten and run (2026-09-10); formal pre-trend test now exists, and it fails on the full/offpeak samples — see below |
| 9–11 | Robustness, mechanism, deliverables | Not started |

The pipeline runs end to end on real data, including a post-treatment period.
The binding constraint now is the **length of the pre-period**: seven months
is too short for a credible parallel-trends test, so the backfill to 2023-01
gates Phase 8 and any quotable estimate.

---

## The result so far

### Pre-tolling levels (pipeline validation)

Median speed by treatment group, **pre-tolling** (2024-10-01 … 2025-01-04).
Levels, not effects. Source: `outputs/tables/descriptive_summary.csv`.

| Group | Median mph | Links | Link-hours |
|---|---:|---:|---:|
| treated | 7.86 | 148 | 286,229 |
| boundary | 9.73 | 5 | 11,334 |
| control | 15.64 | 169 | 315,695 |
| exempt_in_zone | 19.43 | 6 | 11,731 |
| crossing | 36.61 | 2 | 4,589 |

**External corroboration.** In-zone surface streets sit near 8 mph before
tolling, against roughly 8.2 mph published for the Manhattan CBD. Geometry, unit
conversion, treatment assignment and hourly aggregation all have to be correct
for that number to land there — it is the strongest evidence the pipeline
measures what we think it measures. The ordering also vindicates separating the
groups: folding 37 mph bridge segments or 19 mph Route 9A into an 8 mph treated
group would badly distort the estimate, and boundary segments land between
treated and control, which is what straddling 60th Street should look like.

### Phase 7 difference-in-differences — NOT quotable

Frozen two-way FE spec, estimated on the 7-month window
(`outputs/tables/did_estimates.csv`, 323 link clusters):

| Sample | ATT mph | SE | p | 95% CI | % of pre-treated mean |
|---|---:|---:|---:|---|---:|
| all | +0.85 | 0.24 | 0.0004 | [+0.38, +1.32] | +8.9 |
| weekday peak | +0.56 | 0.26 | 0.031 | [+0.05, +1.08] | +7.1 |
| weekday off-peak | +0.72 | 0.23 | 0.0016 | [+0.27, +1.16] | +7.3 |
| weekend | +1.30 | 0.28 | 6e-06 | [+0.75, +1.86] | +13.2 |

Positive and significant in every cut; the weekend effect being ~2× the weekday
peak effect independently matches published work. Weather robustness
(`did_estimates_weather.csv`): the post period is colder and snowier, which
biases the estimate *downward*, and treated × weather interactions move β by
≤5%. **Why it is not quotable:** 7-month window, D2 open, no placebo, and —
see below — the formal pre-trend test does not clear on this window either.

### Phase 8 event study — first run, formal pre-trend test now exists

`src/analysis/event_study.py` was a dead scaffold (referenced `volume`,
`sensor_id`, `fuel_price`, `travel_time_index` — none exist; `linearmodels`
isn't even a dependency) and has been rewritten against the real panel: same
two-way FE absorption as `did.py`, generalized from one treatment dummy to one
`treated x event_week` dummy per week, reference week `k = -1`, clustered by
link. Control links are folded to the reference bin (tolling has one start
date for everyone, so a bare, non-interacted week dummy would be collinear
with the time fixed effects).

**This replaces the Phase 6 weekly-slope eyeball check with an actual test**,
and the result is more cautious than that check suggested:

| Sample | Joint pre-trend test (k < -1, weeks -12..-2) | Verdict |
|---|---|---|
| all | χ²=26.6, df=11, p=0.0053 | **FAILS** — pre-period not flat |
| peak | χ²=9.7, df=11, p=0.557 | passes |
| offpeak | χ²=52.3, df=11, p≈0 | **FAILS hard** |
| weekend | χ²=15.4, df=11, p=0.163 | passes |

The post-period path (`outputs/tables/event_study_all.csv`) is directionally
consistent with the Phase 7 DiD — mostly positive, growing from ~+0.6 mph at
k=1 to ~+1.1 mph by k=7-11 — which is reassuring. But the pre-period, especially
in the **offpeak** cut, is not flat: several weeks in the 7-month window's
14-week pre-period are individually significant (k=-11, -4, -3), most plausibly
because that window is Thanksgiving-through-New-Year, which is exactly the kind
of atypical pre-period D2 already worried about, not genuine drift. **This
means D2 is not merely "open" — the naive control pool has now failed a real
test on part of the sample, which the Phase 6 check was too coarse to catch.**
It should be re-run once the backfill gives a longer, less holiday-dominated
pre-period before it is used to decide D2 either way.

---

## Settled and verified

Each of these was tested, not assumed.

**The original source could not answer the question.** `i4gi-tjb9` carries ~123
links city-wide. Of the 18 inside the zone, every one is toll-*exempt* (FDR
Drive, West Side Highway) or a crossing. Zero on Broadway, Fifth, Park,
Lexington, 34th, 42nd, Canal. The treated group was empty. Replaced by the EZ
Pass local-street feeds; the old source retained for spillover.

**Timestamps are naive America/New_York, not UTC.** Confirmed from both
directions. Fall-back 2024-11-03: hour 01 doubles, 103 readings vs 51 on the
control Sunday. Spring-forward 2025-03-09: hour 02 is empty, 0 vs 1,063 on the
control Sunday. Under UTC neither signature would appear. Every hour-of-day cut,
including the peak definitions, is correct as written.

**The feed republishes a rolling median, not independent readings.** A
900-second median re-emitted about every 61 seconds — 52 readings per
segment-hour, ~93% overlap, frequently byte-identical. Ingestion keeps one
reading per non-overlapping 15-minute window. Measured: mean 3.71 readings per
link-hour, maximum 4, zero hours above 4.

**Reported speed is internally consistent.** Checked independently against
`link_length_ft / median_tt_sec`: median disagreement 0.002 mph, 0% of rows
differ by more than 5 mph. Validates the fps→mph conversion against a field not
used to compute it.

**Treatment assignment is geometric, not name matching.** Polylines decoded and
tested against the 60th Street line — which is *not* constant latitude, since
the grid is rotated by more than a block. Verified: segment 1004 decodes to
40.7514, −73.9761, the real 42nd & Lexington, running east as labelled.

---

## Open decisions

### D1 — Cleaning thresholds

10.2% of readings rest on ≤3 probe vehicles. Separately, 0.085% of readings
exceed 80 mph, monthly maximum 962 mph — physically impossible on a Manhattan
surface street.

The panel applies **no** value cleaning. The frozen outcome is a median
precisely so sparse extremes do not drive it, and every diagnostic a filter
would need is carried on each row.

> **Decide:** set a minimum sample depth and a speed ceiling, or keep the panel
> unfiltered and treat both as robustness variants?

### D2 — How controls get selected — *blocks Phase 5*

The frozen design requires controls chosen on pre-treatment trends, not
geography. That is load-bearing: pre-tolling, treated sits at 7.86 mph and
control at 15.64 — a level gap of nearly 2×.

DiD identifies off changes, so the gap is not disqualifying by itself. The
Phase 6 eyeball check (treated−control gap slope ≈ +0.011 mph/week) suggested
the naive pool might be a live option — but the **Phase 8 formal pre-trend
test (2026-09-10) rejects flatness overall (p=0.005) and hard in the offpeak
cut (p≈0)**, and passes only for peak and weekend. That is a real signal
against the naive pool as-is, not just a weak counterfactual concern, though
it is confounded with the pre-period being mostly Thanksgiving-New Year.

> **Decide:** match on pre-treatment trend, restrict to Manhattan above 60th, or
> build a synthetic control? Re-run the Phase 8 pre-trend test on a longer,
> less holiday-dominated pre-period once the backfill lands before deciding —
> the current failure may be a short-window artifact rather than a real
> parallel-trends violation, but it should not be waved off either.

### D3 — Is 11th Avenue actually exempt?

Route 9A's street-level extent south of 57th is genuinely ambiguous. Four 11th
Avenue segments are classified `exempt_in_zone`, removing them from treatment.
If wrong they belong in treatment; if right they belong in the spillover
analysis, since exempt roads are where diverted traffic goes.

> **Decide:** confirm or reverse. Four segments, a one-line change in
> `EXEMPT_PATTERNS` (`src/data/geo.py`).

### D4 — The 32 unassigned links — *RESOLVED 2026-09-09 (5763399)*

324 distinct links appear in the readings but the segment attribute table held
only 297 — so 32 links, **7.94% of readings**, carried no borough and no
geometry, and therefore no treatment group. Cause: building that table from a
single day; the roster changes over time. The fix was to refetch it across nine
sample days spanning both datasets.

**Update 2026-09-09 — these are probably decommissioned sensors.** Of the 33
unassigned links, 25 stop reporting entirely during autumn 2024 (last readings
cluster on 2024-11-13, 11-20/21 and 12-22) and never appear in the post period.
That is almost certainly why they were absent from the 2025-01-06 segment
sample — they were already gone by then. The refetch samples 2023-01, 2023-07,
2024-01 and 2024-06, all of which precede the shutdown, so recovery is likely.

Two consequences worth noting. First, these links have **no post-treatment
observations**, so a DiD would drop them regardless; leaving them unassigned
costs control-pool size, not identification. Second, sensors decommissioning
mid-window is itself a finding: link identity is not stable across the study
period, which matters for D7 and for any balanced-panel claim.

> **Resolved.** The refetch ran across nine sample days spread over the study
> window: the segment attribute table went 297 → 346 segments and the 39
> unassigned links (64,981 link-hours) dropped to **zero**. Treated grew
> 130 → 148 links, control 154 → 175. Both hard data-quality checks
> (`hard_duplicate_key`, `hard_unmatched_segments`) now pass. The decommissioned
> sensors remain a finding: link identity is not stable across the window, which
> still matters for D7 and any balanced-panel claim.

### D5 — What happens to the crossings

Two Williamsburg Bridge segments (sid 194196 / 197195) measure the queue to
*enter* the zone, not circulation within it — a different behaviour, near 37 mph
against treated's ~8. Held separate rather than dropped. Published work reports
the largest speed gains on crossings, so they are substantively interesting in
their own right.

> **Decide:** estimate crossings as a separate specification, or exclude them?

### D6 — Roadway name normalisation

The feed carries both `57th St` and `57th Street` for the same street, and some
names arrive mojibaked with a corrupted en dash. Classification is unaffected —
that runs on geometry — but per-roadway or corridor-level aggregation would
split the street in two.

> **Decide:** normalise now, or leave until a corridor-level analysis needs it?

### D7 — How much history to pull

The frozen window starts 2023-01-01 (two pre-treatment years). The feed reaches
back to 2021-04-08, so a longer pre-period is available for placebo dates and
trend testing — at real cost, since throughput measured 3s–80s per page.
2021–22 also carries COVID recovery dynamics, a confound rather than a bonus.

> **Decide:** hold at 2023-01, or extend once the backfill completes?

---

## Data on hand

| Source | Role | Coverage | Months | Rows (staged) |
|---|---|---|---:|---:|
| `erdf-2akx` + `6a2s-2t65` | Primary | 2024-10 … 2025-04 | 7 / ~45 | 5,162,965 |
| `i4gi-tjb9` | Secondary (spillover) | 2023-01 … 2026-07 | 42 / 45 | 40,249,114 |

The primary source was pulled **priority-window first** — 2024-10 through
2025-04, three-plus months either side of the toll — so analysis was not blocked
behind a 44-month backfill. The rest now runs on a schedule in GitHub Actions
(`.github/workflows/backfill.yml`), about five hours per pass, resuming from
the `data-raw` release. Socrata still throttles sustained requests hard; what
changed is that nobody has to sit through it. `python -m src.data.coverage_report`
prints where it has got to.

**Caveat on the manifest.** All seven primary parts are recorded
`verified: false`. Row counts were not pre-checked against a live `count(1)`,
because that query defeats Socrata's index and ran for minutes. Completeness
currently means "paging finished cleanly", not "the row count was confirmed".
Running `--verify` upgrades this, and should happen before any published result.

---

## Known risks

- **Pre-period is only ~3 months.** The panel now has a post-treatment period,
  but the pre-period runs 2024-10 → 2025-01-04. That is enough for a descriptive
  read and a provisional DiD, not for a credible parallel-trends test or placebo
  dates. The backfill to 2023-01 lifts this; Phase 8 waits on it.
- **Throughput is not under our control.** 3s–80s per page, load-sensitive and
  erratic. Concurrent requests make it markedly worse, so the download runs alone.
- **A month is held in memory until complete.** Losing the process mid-month
  discards up to 30 minutes. The manifest protects across months, not within one.
- **Segment roster drifts over time.** D4 (now resolved) was the visible
  symptom; the deeper point is that link identity is not guaranteed stable
  across a four-year window, which matters for a balanced panel.
- **Primary parts are unverified.** Seven `verified: false` parts; run
  `--verify` before any published number.

### Cleared

- ~~**Links may drop out at the treatment boundary**~~ — checked 2026-09-09
  (pre-refetch counts: control 154/154, treated 130/130, exempt 6/6, boundary
  5/5, crossings 2/2, zero dropouts). All dropouts were `unassigned` links that
  stopped reporting in autumn 2024, well before tolling, so they cannot
  introduce a discontinuity at 2025-01-05. **Recheck after the D4 refetch:** the
  post-refetch descriptive summary shows treated 148→145 and control 169→167
  links across pre/post (a link is counted if it has ≥1 link-hour in the
  period), so a handful of links now appear in one period only. Whether that is
  a genuine boundary discontinuity or just sparse coverage at the panel edges
  needs a proper balance check on the current panel — carry as a small open
  item, not a cleared one.
