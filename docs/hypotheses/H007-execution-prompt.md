# H007 — execution prompt

Not a record, and not listed in the register. This is the prompt handed to a
fresh session to execute [H007](H007-secondary-feed-diversion.md). The record
was committed first; `git log` carries the order.

---

## What you are doing

You are running the spillover analysis for a causal study of New York City's
Congestion Relief Zone toll, which began on 2025-01-05. The study's primary
panel cannot answer the spillover question at all: its five `boundary` links
straddle 60th Street instead of sitting outside it, and the nearest control link
is about 808 m from the cordon, so there are no units where diversion would show.

A secondary feed does cover the right roads. `i4gi-tjb9` (DOT Traffic Speeds
NBE) carries nine links on the FDR Drive, the West Side Highway / 12th Avenue and
West Street — the toll-exempt routes a driver uses to cross Manhattan without
paying. Your question is whether that feed can identify diversion onto them.

What changes on the answer: if it can, the study gains a mechanism section with
an estimate. If it cannot, the study reports a second documented failure to
identify, and the reason matters — a measurement failure and a parallel-trends
failure say different things about what better data would fix.

**A documented inability to identify the effect is a successful outcome here.**
Do not reach for something positive to hand back. This study's contribution so
far is precisely a careful account of what its data cannot support.

## What you need to know

The repository is a Python project at the path you have been given. Read
`AGENTS.md` first; it is short and carries conventions that are expensive to
rediscover. Then read the record, `docs/hypotheses/H007-secondary-feed-diversion.md`,
in full — but consider forming your own view of the feasibility questions before
you read its Prediction section, which is frozen and will anchor you.

Facts established already, which you may rely on without re-deriving:

- The feed is at `data/raw/dot_speeds/*.parquet`: 42 monthly parts, 42.2M rows,
  138 distinct links, covering 2023-01 … 2026-07 **with 2026-06 missing**.
- Readings coded `speed = 0` are **outages, not standstills**. 9,128,628 of the
  9,129,474 zero-speed rows also have `travel_time = 0`; every one has
  `status = -101`; and the zero rate peaks overnight (56% at 03:00 against 38%
  through the afternoon), which is the inverse of a congestion pattern. Treat
  them as missing. `AGENTS.md` requires missing numerics to be `NaN`, never `0`.
- `src/analysis/spillover_diagnostics.py` filters only `speed_mph IS NOT NULL`
  and so averages those zeros in as 0 mph. Its committed output
  `outputs/tables/spillover_secondary_monthly.csv` is contaminated. You are
  superseding it; say so in what you write.
- The **primary** panel is clean on this axis — zero-speed readings are at most
  0.014% of any `treatment_group × post` cell. Nothing in the study's headline
  finding depends on this problem. Do not go looking for it there.
- `src/data/geo.py` holds the geometric classifier. Treatment assignment is
  geometric, on decoded polylines, **never** on `link_name` — 60th Street is not
  a line of constant latitude and the Manhattan grid is rotated by more than a
  block. The secondary feed's `encoded_poly_line` decodes at **precision 5**.
- `classify_segment` trusts the `borough` label; `_in_manhattan_envelope` exists
  but has no call sites. On this feed that mislabels link_id `4616339` and
  `4616340` (BQE approaches to the Brooklyn and Manhattan Bridges, labelled
  Manhattan but geometrically in Brooklyn) as `treated`. The record tells you to
  hold both out. Do not fix `geo.py` as part of this work; a separate task
  covers it.
- Link identity is not stable: 25 sensors stopped reporting in autumn 2024 and
  never returned. Control links here fall from 115 reporting in 2023 to 102–103
  from 2024 on. The panel is unbalanced.

Reusable machinery, which you should prefer over writing your own:

- `src/analysis/did.py` — `estimate()` is two-way FE with errors clustered by
  link, fixed effects absorbed by alternating projections. `TIME_KEY = "ts_hour"`,
  `OUTCOME = "median_speed_mph"`.
- `src/analysis/event_study.py` — `build_dummies()`, `estimate()`, `coef_frame()`,
  and `pretrend_test()`, which is the **corrected** joint Wald test using the
  full cluster covariance (`cluster_robust_wald_chi2`). An earlier version summed
  squared individual t-statistics and ignored the covariance between leads; it
  is superseded and you must not reintroduce it.
- `src/analysis/placebo_space.py` — `placebo_draws()` and `_p()` for
  randomization inference.
- `src/analysis/honest_did.py` — Rambachan & Roth (2023) sensitivity, takes
  `--out-prefix` and stamps the horizon into filenames.

Note that `did.py`, `event_study.py` and `placebo_space.py` load
`HOURLY_PANEL_PATH` directly in their own `load()` and do **not** take
`--out-prefix`. Only `control_construction.py` and `honest_did.py` do. So import
their functions as a library from a new module rather than trying to drive their
CLIs; do not repoint `HOURLY_PANEL_PATH`, and do not change the behaviour of the
primary pipeline.

## The hypothesis, pre-registered

The record is `docs/hypotheses/H007-secondary-feed-diversion.md`, committed
before this prompt was written. Its Prediction and Acceptance criteria are
frozen. If you conclude the criteria were badly chosen, say so plainly in the
Verdict and supersede the record with a new one — **do not edit the frozen
sections**, and do not quietly reinterpret a threshold.

The criteria, stated here so they cannot drift. Evaluate on the **all-hours**
sample; report the other three cuts.

**Supports** — the feed identifies diversion. All three must hold:

1. Differential change in valid-hour availability between treated and control,
   pre-period mean to post-period mean, **under 5 percentage points** absolute.
2. The joint pre-trend test **fails to reject** at the 5% level.
3. Randomization-inference p-value for the observed ATT **below 0.05**.

If all three hold, the ATT's sign is the finding: negative means measured
diversion onto the exempt routes.

**Refutes** — the feed does not identify diversion. Any one of:

1. Differential availability change **5 percentage points or more**.
2. The joint pre-trend test **rejects** at the 5% level.
3. Rambachan–Roth breakdown value **below 0.5**.

**Uninformative** — availability parallel and pre-trends pass, but the RI
p-value is at or above 0.05 and the null distribution is wide enough that a
plausible diversion effect would not have been detected. Report the minimum
detectable effect if this is the verdict. Nine treated links is a small design;
failing to find an effect in it is not evidence none occurred.

## Method

Build `data/processed/secondary_hourly_panel.parquet` with the same schema the
primary panel uses, then run the existing estimators against it.

**Window.** 2023-01-01 through 2026-05-31. Stop at 2026-05 because 2026-06 is
missing; drop 2026-07 rather than leave a hole. That gives 24 pre-treatment
months and 17 post.

**Outcome.** Hourly median of `speed` in mph over readings with `speed > 0`. An
hour with no positive reading is absent from the panel, not zero. Preserve the
secondary staging conventions already in the repo: naive `America/New_York`
timestamps with no conversion, one row per `(link_id, ts)` keeping the highest
`id`, and exclusion of the ambiguous DST fall-back hour.

**Groups**, from `classify_segment` on the decoded `encoded_poly_line`:

- Treated: the 9 `exempt_in_zone` links.
- Control: the 116 `control` links, all outside Manhattan.
- Held out of both: the 6 `boundary`, the 5 `crossing`, and link_ids `4616339`
  and `4616340`. Report the exclusions.

**Estimator.** Two-way FE on link and hour-of-sample, `treated × post` the
coefficient of interest. Samples: all, weekday peak, weekday off-peak, weekend.

**Inference.** Randomization inference is **primary**. Nine treated clusters is
far below where cluster-robust asymptotics are trustworthy, and H001 already
measured those standard errors running up to 1.5× too tight on a 333-cluster
panel. Reassign treatment at random among control links, 9 at a time, 500 draws.
Report clustered SEs alongside, labelled as the weaker of the two.

**Diagnostics, in this order** — an earlier one failing makes the later ones
unreadable, so report them in sequence and say which gate failed first:

1. **Availability.** Per group per month: share of link-hours with at least one
   positive reading, out of hours where the link appears in the feed at all; and
   the count of links reporting. Compute the pre-to-post difference in
   differences of those shares. This is criterion 1 and it is a gate.
2. **Event study** by month, ±12 months, then the joint Wald test that all
   pre-treatment leads are zero, via `event_study.pretrend_test`.
3. **Rambachan–Roth** breakdown value at the ±12-month horizon.

Implementation choices inside that are yours. Pin down anything that changes
what the result means; leave the rest to your judgement.

**Outputs.** `outputs/tables/H007_*.csv` and `outputs/figures/H007_*.png`. The
namespacing is not optional — reruns would otherwise overwrite artefacts an
earlier record cites.

## Constraints

- **Zero budget.** Nothing in this project may cost money. No paid APIs, no
  hosted compute.
- Python only. The environment is at `.venv`; use `.venv/Scripts/python.exe` on
  Windows. `pandas`, `duckdb`, `statsmodels`, `matplotlib`, `numpy` are
  available.
- No new network ingestion. Everything you need is on disk.
- `ruff`, `black` at line length 100, and `pytest` must all stay green. Run them
  before you finish. Add tests for anything new that has logic in it.
- `data/raw/` is immutable.
- Log `rows in -> rows out` and the reason for every drop.
- Do not push to a remote, and do not change anything `docs/project_brief.md`
  marks frozen.
- Decisions D1, D2, D3, D5, D6 and D7 in `docs/owner_decisions.md` are reserved
  to the owner. You may analyse them; you may not adopt one.

## What to report

- The numbers, with uncertainty, and the path to every artefact.
- **Which acceptance criterion was met** — supports, refutes, or uninformative —
  and which gate failed first if one did.
- What it changes about what the study reports, and what it does not settle.
- Fill in the record's Result and Verdict sections. Leave the frozen sections
  alone. Update `REGISTER.md` — it is append-only.
- Add a dated entry to `docs/decision_register.md`.

Separate the estimator from the inference when you report. A point estimate can
be fine while its standard errors are fiction, and this study has already found
exactly that once. Say something about each.

Tell me what would change the conclusion, not everything that is imperfect.

Cite with author, year and venue. Flag anything you cannot cite precisely rather
than guessing — models fabricate confidently in this domain, and the citations
in this repo get spot-checked.

## Boundaries

This analysis cannot establish that diversion did or did not occur. At most it
establishes whether this feed, on these nine links, can measure it.

It says nothing about the primary finding. The 1.17 mph in-zone association and
its failed identification are settled and out of scope. **Do not re-open the
search for a control set that passes on the primary panel** — that question is
closed, every further attempt is another draw against fixed data, and the
register would have to carry the count.

Nine treated links, all on three roadways, are not a random sample of anything.
Even in the best case the result is a statement about the FDR, the West Side
Highway and West Street, not about diversion in general.
