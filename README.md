# NYC Congestion Pricing — Effect on Traffic Speeds

Estimating the causal effect of NYC's Congestion Relief Zone toll (tolling began
**2025-01-05**) on traffic speeds inside the zone, and testing whether congestion
shifted to nearby areas.

> **Status:** Phase 1–2 (setup + ingestion). No causal results yet. This README
> is a skeleton; the sections below fill in as the analysis progresses.

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

Primary and (for now) only source: **NYC DOT Traffic Speeds NBE**
(`i4gi-tjb9`, NYC Open Data). Schema and conventions in
`docs/data_dictionary.md`. Secondary sources are deferred — see
`docs/future_data_sources.md`.

## Project structure

```
data/         raw/ (immutable) · interim/ (typed staging) · processed/ (panels)
docs/         brief · data dictionary · methodology · reproducibility · data-quality report
sql/          DuckDB: 01 staging · 02 quality checks · 03 hourly panel
src/
  data/       download · inspect_schema · build_staging · quality_report
  analysis/   descriptive · did · event_study        (stale scaffold — rewritten Phase 6+)
  visualization/
notebooks/    exploratory analysis (orchestrate + narrate only)
tests/        unit tests for src/ transformations
outputs/      figures/ · tables/
```

## Getting started

```bash
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows
pip install -e ".[dev]"

python -m src.data.download --start 2023-01-01       # needs NYC_OPENDATA_APP_TOKEN
python -m src.data.inspect_schema
```

Full pipeline and environment variables: `docs/reproducibility.md`.

## License

MIT (see `pyproject.toml`).
