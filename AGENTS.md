# AGENTS.md

Causal study of NYC's Congestion Relief Zone toll (tolling began 2025-01-05) on
traffic speeds inside the zone, plus spillover just outside it.
Difference-in-differences with two-way fixed effects and an event study, on a
link × hour panel of hourly median speeds.

## Where to look

| When you need | Read |
|---|---|
| Current state, what's settled, what's open | `docs/decision_register.md` — start here |
| The frozen design you may not quietly change | `docs/project_brief.md` |
| The statistical spec, or why the data source changed | `docs/methodology.md` |
| Panel schema, column meanings | `docs/data_dictionary.md` |
| A pipeline command | `docs/reproducibility.md` |
| Paths, dataset ids, treatment date, column names | `src/config.py` |

Read what the task needs. There is no required pre-read.

## Permissions

The test suite uses synthetic fixtures and touches no network or production
data. Run it, fix failures your change caused, and rerun without asking:

```bash
python -m pytest
```

Ruff and black are likewise safe to run unprompted.

Ask before: pushing to a remote, making anything public, changing repository
visibility, or spending money (nothing in this project may cost money).

## Frozen

`docs/project_brief.md` fixes the research question, treatment date
(2025-01-05), primary outcome (hourly median link speed in mph), unit of
analysis (link × hour), treatment and control definitions, and the estimator.
Changing one requires a dated justification in `docs/methodology.md` — not a
quiet edit.

Seven decisions (D1–D7) in `docs/decision_register.md` are deliberately left
open because each changes what the study reports. Resolve them with evidence
and a dated entry, rather than defaulting one into the panel.

## Conventions

- Python 3.11+, ruff and black at line length 100, type hints on public
  functions.
- `pandas` for wrangling, `duckdb` for large tabular transforms, `statsmodels`
  for econometrics, `matplotlib` for plots.
- Every script exposes `main()` and runs as `python -m src....`.
- `data/raw/` is immutable. `data/interim/` is typed staging, `data/processed/`
  is analysis-ready panels. Figures to `outputs/figures/`, tables to
  `outputs/tables/`.
- Log `rows in -> rows out` and the reason for every drop.
- Missing numeric values are `NaN`, never `0` or `-999`.
- Report clustered standard errors, effect sizes and confidence intervals.
  Null results get reported the same as positive ones.

## Facts about this data that are expensive to rediscover

- **Timestamps are naive `America/New_York`.** Confirmed by DST signatures:
  2024-11-03 hour 01 doubles, 2025-03-09 hour 02 is empty. Converting them to
  UTC breaks every hour-of-day cut.
- **The feed publishes a rolling median, not independent readings** — a
  900-second median re-emitted every ~61s, so consecutive rows overlap ~93% and
  are often byte-identical. Ingestion deliberately keeps one reading per
  non-overlapping 15-minute window. Medianing 52 overlapping windows would
  over-weight whichever value persists longest.
- **`date_extract_m` is month; the minute function is `date_extract_mm`.** The
  wrong one matches nothing and returns zero rows without erroring.
- **Putting any function on the timestamp column in a SoQL `$where` clause
  collapses paging** — measured 255.8s versus 3.7s for the same page. The
  downsample is client-side for this reason.
- **Treatment assignment is geometric.** 60th Street is not a line of constant
  latitude; the Manhattan grid is rotated by more than a block. Classify on
  decoded polylines, never on `link_name`.
- **Link identity is not stable across the window.** 25 sensors stopped
  reporting in autumn 2024 and never returned, so a balanced-panel claim needs
  checking rather than assuming.

## Writing

The deliverable is a written report, so prose matters here as much as code.
Write clear, concise paragraphs, each developing one idea. Active voice, plain
language, concrete examples. Reach for a table when the content is genuinely
tabular; otherwise write sentences. Avoid nested lists.

Avoid: "Conclusion", "delve into", "leverage", "it's worth noting", "what's
important is", "In short", "The simplest mental model is", rhetorical
question-then-answer, "This isn't about X, it's about Y", and contrastive
"X, not Y" constructions.

When you resolve or advance something, add a dated entry to
`docs/decision_register.md`. That file is how the next session — possibly
months later — finds out what you learned.
