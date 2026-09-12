# NYC Congestion Pricing — Effect on Traffic Speeds

Estimating the causal effect of NYC's Congestion Relief Zone toll (tolling began
**2025-01-05**) on traffic speeds inside the zone, and testing whether congestion
shifted to nearby areas.

> **Status:** Phases 1–8 run on the 2024-10 … 2025-04 priority window
> (descriptives, a provisional difference-in-differences, and a first event
> study). **No quotable result yet** — the pre-period is ~3 months, the formal
> event-study pre-trend test fails on the full and off-peak samples, and
> control selection (D2) is open. The backfill to 2023-01 runs on a schedule in
> GitHub Actions, prioritized for analytical value; `outputs/tables/pretrend_tests.csv`
> carries the current verdict on whether anything here is quotable yet.
> Robustness (Phase 9) not started. See `docs/decision_register.md`.

---

## Question

What was the effect of congestion pricing on traffic speeds inside the
Congestion Relief Zone (CRZ), and is there evidence that congestion shifted to
areas just outside the zone boundary?

Secondary: do effects differ peak vs off-peak and weekday vs weekend? Do MTA
entry and TLC data support the mechanism? (Phase 10.)

## Result

_TBD — Phase 7–8._

## Evidence

_TBD — difference-in-differences estimate with clustered standard errors; event
study of dynamic effects around 2025-01-05._

## Robustness

_TBD — Phase 9: alternative controls, placebo dates, pre/post windows, sensor
quality filters, aggregation level._

## Limitations

- The NYC DOT speed feed is highway/arterial-biased; surface-street coverage
  inside the CRZ is thinner. Coverage is quantified in the data-quality report.
- Parallel-trends is an assumption, tested but not proven, via pre-period
  event-study coefficients.
- Speed is a proxy for congestion; volume (MTA entries) is a separate check.

## Recommendation

_TBD — executive summary, recommendation-first._

---

## Method

- **Difference-in-differences**: CRZ links (treated) vs. comparable links
  outside the zone (control), before vs. after 2025-01-05, with link and
  time fixed effects and SEs clustered by link.
- **Event study**: dynamic coefficients around the tolling date to check
  pre-trends and trace the adjustment path.
- **Placebo / robustness**: separate specifications, not tweaks to the primary
  model.

See `docs/methodology.md` for the full specification and identifying
assumptions, and `docs/project_brief.md` for frozen definitions.

## Data

**Primary — NYC DOT E-Z Pass local-street speeds** (`erdf-2akx` +
`6a2s-2t65`, NYC Open Data). Two datasets with identical schemas that join with
no gap, covering 2021-04-08 to the present. `median_speed_fps` on ~346 named
street segments, including the tolled Manhattan grid.

**Secondary — NYC DOT Traffic Speeds NBE** (`i4gi-tjb9`). This was the original
primary source. It carries only ~123 links city-wide and **none** on tolled CRZ
surface streets — every in-zone link is a toll-exempt highway (FDR Drive, West
Side Highway) or a crossing — so it cannot support the primary specification. It
is retained for the spillover/diversion analysis, since those exempt roads are
exactly where displaced traffic would go. Full reasoning in the 2026-09-08
decision record in `docs/methodology.md`.

Schema and conventions in `docs/data_dictionary.md`; open questions in
`docs/decision_register.md`; further sources in `docs/future_data_sources.md`.

## Project structure

```
data/         raw/ (immutable) · interim/ (typed staging) · processed/ (panels)
docs/         brief · data dictionary · methodology · reproducibility · data-quality report
sql/          DuckDB: 01 staging · 02 quality checks · 03 hourly panel
src/
  data/       download · inspect_schema · build_staging · quality_report
  analysis/   descriptive (Phase 6) · did (Phase 7) · event_study (Phase 8)
  visualization/
notebooks/    exploratory analysis (orchestrate + narrate only)
tests/        unit tests for src/ transformations
outputs/      figures/ · tables/ — tracked; the results are the deliverable
scripts/      priority_backfill.sh (range order) · data_release.sh (CI storage)
.github/      backfill · analysis · tests workflows
```

## Getting started

```bash
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows
pip install -e ".[dev]"

python -m src.data.coverage_report    # how far the backfill is, and whether the
                                      # pre-trend test clears yet
```

Ingestion runs on a schedule in GitHub Actions rather than locally — the
backfill is ~21 hours against a feed that throttles, and it resumes itself
across passes. To pull months locally anyway:

```bash
python -m src.data.download_ezpass --start 2023-01-01   # primary; needs NYC_OPENDATA_APP_TOKEN
python -m src.data.download        --start 2023-01-01   # secondary (DOT highways, spillover)
```

Full pipeline, workflows and environment variables: `docs/reproducibility.md`.

## License

MIT (see `pyproject.toml`).
