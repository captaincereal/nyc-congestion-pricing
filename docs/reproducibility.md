# Reproducibility

Every processed dataset must be rebuildable from raw source data with the
commands below. Raw data is immutable and never edited by hand.

## Environment

```bash
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS/Linux:         source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install        # optional: ruff + black on commit
```

Python 3.11+ is required. Exact resolved versions are captured in
`requirements.lock` after the first install (`pip freeze > requirements.lock`).

## Optional configuration (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `NYC_OPENDATA_APP_TOKEN` | Socrata app token — lifts anonymous rate limits | none (anonymous) |
| `NYC_CP_DATA_DIR` | Relocate the `data/` tree (e.g. to a large disk) | `<repo>/data` |

Put these in a local `.env` (gitignored) or export them in your shell. The
token is never written to disk by this project.

## Pipeline

```bash
# Phase 2 — ingest the raw speed feed (immutable, manifest-tracked)
python -m src.data.download --start 2023-01-01

# Phase 2 — inspect the real schema, timezone, cardinality, duplicates
python -m src.data.inspect_schema

# Phase 3 — stage + run data-quality checks + write the report
python -m src.data.build_staging          # runs sql/01_stage_speeds.sql (DuckDB)
python -m src.data.quality_report         # runs sql/02 + writes docs/data_quality_report.md

# Phase 4+ (not yet implemented)
# python -m src.data.build_panel
```

## Determinism

- `RANDOM_SEED = 20250105` (`src/config.py`) for anything stochastic.
- SQL transforms are deterministic: same raw input + same commit ⇒ same output.
- The raw pull is *not* bit-identical across dates (the feed grows), so each
  pull is dated and recorded in `data/raw/manifest.json`. Analyses cite the
  manifest entry (SHA-256 + row count) they were run against.

## Row-count tracking

Each stage logs `rows in → rows out` and the reason for any drop. The
data-quality report reproduces the full funnel from raw to panel.
