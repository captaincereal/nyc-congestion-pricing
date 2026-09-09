# Decision Register

**NYC Congestion Relief Zone · speed study**

Compiled 2026-09-09 · treatment date 2025-01-05 · head `692f0c9` · 54 tests passing

Seven decisions are open and blocking the causal work. Everything below them is
settled, verified and reproducible. Each open decision changes what the study
reports, so all seven are deliberately left unmade rather than defaulted into
the panel.

---

## Where the project stands

| Phase | | Status |
|---|---|---|
| 1 | Setup | Complete |
| 2 | Ingestion | **4 of 45 months** (primary source) |
| 3 | Data quality | Checks written and run |
| 4 | Panel | Built — but no post-treatment period yet |
| 5 | Controls | Blocked on **D2** |
| 6–11 | Causal work | Not started |

The pipeline runs end to end on real data. What it does not have is a
post-treatment period: every row currently sits before 2025-01-05, so no effect
can be estimated. The month crossing the toll start is downloading now.

---

## The one result so far

Median speed by treatment group, **pre-tolling** (Oct–Nov 2024, 406,479
link-hours). These are levels, not effects.

| Group | Median mph | Links |
|---|---:|---:|
| treated | 8.06 | 130 |
| boundary | 9.51 | 5 |
| unassigned | 9.96 | 32 |
| control | 15.50 | 149 |
| exempt_in_zone | 18.41 | 6 |
| crossing | 34.89 | 2 |

**External corroboration.** In-zone surface streets sit at 8.06 mph before
tolling, against roughly 8.2 mph published for the Manhattan CBD. Geometry, unit
conversion, treatment assignment and hourly aggregation all have to be correct
for that number to land there — it is the strongest evidence the pipeline
measures what we think it measures.

The ordering also vindicates separating the groups: folding 34.89 mph bridge
segments or 18.41 mph Route 9A into an 8.06 mph treated group would have badly
distorted the estimate. Boundary segments land between treated and control,
which is what straddling 60th Street should look like.

---

## Settled and verified

Each of these was tested, not assumed.

**The original source could not answer the question.** `i4gi-tjb9` carries ~123
links city-wide. Of the 18 inside the zone, every one is toll-*exempt* (FDR
Drive, West Side Highway) or a crossing. Zero on Broadway, Fifth, Park,
Lexington, 34th, 42nd, Canal. The treated group was empty. Replaced by the EZ
Pass local-street feeds; the old source retained for spillover.

**Timestamps are naive America/New_York, not UTC.** On the fall-back date
2024-11-03, segment `1004` carries 103 readings in hour 01 against 51 in each
neighbouring hour, and 51 in that hour on the control Sunday — exactly the
doubling expected when 01:00–01:59 runs twice. Under UTC no hour would double.
Every hour-of-day cut, including the peak definitions, is correct as written.

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
geography. That is now load-bearing: treated sits at 8.06 mph, control at 15.50
— a level gap of nearly 2×.

DiD identifies off changes, so the gap is not disqualifying. But a naive
outer-borough control pool gives a weak counterfactual, and parallel trends is
more plausible between comparably congested streets.

> **Decide:** match on pre-treatment trend, restrict to Manhattan above 60th, or
> build a synthetic control?

### D3 — Is 11th Avenue actually exempt?

Route 9A's street-level extent south of 57th is genuinely ambiguous. Four 11th
Avenue segments are classified `exempt_in_zone`, removing them from treatment.
If wrong they belong in treatment; if right they belong in the spillover
analysis, since exempt roads are where diverted traffic goes.

> **Decide:** confirm or reverse. Four segments, a one-line change in
> `EXEMPT_PATTERNS` (`src/data/geo.py`).

### D4 — The 32 unassigned links

324 distinct links appear in the readings but the segment attribute table held
only 297 — so 32 links, **7.94% of readings**, carry no borough and no geometry,
and therefore no treatment group. Cause: building that table from a single day;
the roster changes over time.

The fix is written (nine sample days across both datasets) but not yet run — it
costs ~60 API requests and would compete with the download.

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

> **Pending:** refetch runs once the priority window finishes; then report how
> many of the 33 are recovered.

### D5 — What happens to the crossings

Two Williamsburg Bridge segments measure the queue to *enter* the zone, not
circulation within it — a different behaviour, at 34.89 mph against treated's
8.06. Held separate rather than dropped. Published work reports the largest
speed gains on crossings, so they are substantively interesting in their own
right.

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

| Source | Role | Coverage | Months | Rows |
|---|---|---|---:|---:|
| `erdf-2akx` + `6a2s-2t65` | Primary | 2024-10 … 2024-12 | 3 / 45 | 2,258,704 |
| `i4gi-tjb9` | Secondary (spillover) | 2023-01 … 2026-07 | 42 / 45 | 40,249,114 |

The primary source is pulled **priority-window first** — 2024-10 through
2025-03, three months either side of the toll — so analysis is not blocked
behind a 45-month backfill. `2025-01` is downloading now and is the first month
to cross 2025-01-05.

**Caveat on the manifest.** All three primary parts are recorded
`verified: false`. Row counts were not pre-checked against a live `count(1)`,
because that query defeats Socrata's index and ran for minutes. Completeness
currently means "paging finished cleanly", not "the row count was confirmed".
Running `--verify` upgrades this, and should happen before any published result.

---

## Known risks

- **No post-treatment data yet.** Nothing about the toll's effect can be said
  until `2025-01` lands. Every current figure is a pre-period level.
- **Throughput is not under our control.** 3s–80s per page, load-sensitive and
  erratic. Concurrent requests make it markedly worse, so the download runs alone.
- **A month is held in memory until complete.** Losing the process mid-month
  discards up to 30 minutes. The manifest protects across months, not within one.
- **Segment roster drifts over time.** D4 is the visible symptom; the deeper
  point is that link identity is not guaranteed stable across a four-year
  window, which matters for a balanced panel.

### Cleared

- ~~**Links may drop out at the treatment boundary**~~ — checked 2026-09-09 and
  the panel is balanced where it counts. Every analysis group has all its links
  in both periods: control 154/154, treated 130/130, exempt 6/6, boundary 5/5,
  crossings 2/2, **zero** dropouts. All 25 dropouts are `unassigned` links that
  stopped reporting in autumn 2024, well before tolling — so they cannot
  introduce a discontinuity at 2025-01-05.
