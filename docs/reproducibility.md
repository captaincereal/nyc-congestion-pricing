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
# Phase 2 — ingest the raw speed feeds (immutable, manifest-tracked)
python -m src.data.download_ezpass --start 2023-01-01   # PRIMARY  (E-Z Pass local streets)
python -m src.data.download        --start 2023-01-01   # SECONDARY (DOT highways, spillover)
python -m src.data.download_ezpass --start 2023-01-01 --verify   # raw count + retained-row replay
python -m src.data.download_ezpass --verify --verify-existing --max-runtime 45

# Phase 2 — inspect the real schema, timezone, cardinality, duplicates
python -m src.data.inspect_schema        # note: still points at the secondary DOT feed

# Phase 3 — stage + run data-quality checks + write the report
python -m src.data.build_staging               # sql/01_stage_ezpass.sql -> stg_speed_readings
python -m src.data.build_staging --source dot  # sql/01_stage_speeds.sql -> stg_dot_highway_readings
python -m src.data.quality_report              # runs sql/02 + writes docs/data_quality_report.md

# Phase 4 — geometric CRZ treatment assignment, then the link x hour panel
python -m src.data.geo            # decode polylines -> data/interim/segment_treatment.parquet
python -m src.data.build_panel    # sql/03_hourly_panel.sql -> data/processed/hourly_panel.parquet

# Optional enrichment — hourly weather for the weather robustness check (not on
# data.cityofnewyork.us, so it costs the speed backfill nothing)
python -m src.data.download_weather

# Phase 6 — descriptive series (no causal claims)
python -m src.analysis.descriptive

# Phase 7 — difference-in-differences
python -m src.analysis.did
python -m src.analysis.did --weather      # robustness: treated x weather interactions

# Phase 8 — event study
python -m src.analysis.event_study
python -m src.analysis.event_study --sample peak    # also: offpeak, weekend
python -m src.analysis.event_study --weather         # robustness: treated x weather

# Phase 9 — separate exploratory sensitivities and original-window lead test
python -m src.analysis.robustness
python -m src.analysis.assignment_audit       # geometry evidence for owner decision D2

# Phase 10 diagnostic only — requires the secondary raw archive
python -m src.analysis.spillover_diagnostics
# Optional --secondary-parts '/path/to/dot_speeds/*.parquet' reads another archive.

# Capture exact input/code/table hashes after generating the outputs
python -m src.analysis.provenance
```

`src/data/validate.py` (panel sanity checks) is written but not yet wired in.

```bash
# Where the backfill has got to, and whether the pre-trend test clears yet
python -m src.data.coverage_report
```

## Running it unattended

The backfill is ~21 hours against a feed that throttles, so it runs on GitHub
Actions rather than on anyone's machine.

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/backfill.yml` | every 6h, or manual | Downloads for ~5h, publishes what it got, exits |
| `.github/workflows/analysis.yml` | after a backfill, on analysis changes, or manual | Rebuilds the panel, reruns Phases 6-8, commits `outputs/` |
| `.github/workflows/tests.yml` | push and pull request | ruff, black, pytest |

A job here is capped at six hours, so the backfill is a chain rather than one
run. Each pass gets a download budget (`BACKFILL_BUDGET_MIN`, hosted default 255)
shared across `scripts/priority_backfill.sh`, and stops before starting a month
it cannot finish. Hosted runs reserve a further 45 minutes for verification.
Budgets are checked between requests/days; a request already in flight can run
past that budget, so the job retains a larger 350-minute hard limit.

State lives in the GitHub release tagged `data-raw`: month parts, the segment
attribute table, the manifest, and the rebuilt panel. A runner's disk is wiped
when the job ends, so what that release holds is exactly what the next pass
skips. `scripts/data_release.sh pull|push` moves files between the two.

Within a month, each day is checkpointed to `data/raw/ezpass_days/` as it
lands, so an interruption costs one day rather than a month. Those checkpoints
are cached between passes on a best-effort basis; a cache miss costs one month
of re-downloading, not correctness.

Two flags exist for this and are equally usable locally:

```bash
python -m src.data.download_ezpass --start 2023-01-01 --max-runtime 300
BACKFILL_BUDGET_MIN=120 scripts/priority_backfill.sh
```

Local runs need `NYC_OPENDATA_APP_TOKEN` in `.env`; CI reads it from the
repository secret of the same name.

## Determinism

- `RANDOM_SEED = 20250105` (`src/config.py`) for anything stochastic.
- SQL transforms are deterministic: same raw input + same commit ⇒ same output.
- The raw pull is *not* bit-identical across dates (the feed grows), so each
  pull is dated and recorded in a manifest — `data/raw/ezpass_manifest.json`
  (primary) and `data/raw/manifest.json` (secondary). Analyses cite the
  manifest entry (SHA-256 + row count) they were run against. Primary parts
  currently carry `verified: false`; run `--verify` before quoting any result.
  Verification first compares raw pages with live raw counts, then repeats the
  deterministic downsample and compares all retained reading fields. It never
  compares a sampled row count with an unsampled count. Completed daily receipts
  in `data/raw/ezpass_verification/` bind to the part hash and method version and
  persist in the release. A month is upgraded only after all its days match.
  `verified_at` dates this source audit; it is not a guarantee against future
  upstream revisions. `--verify-existing` skips absent months but verifies held
  parts. End dates are exclusive and ingestion refuses in-progress months.

## Row-count tracking

Each stage logs `rows in → rows out` and the reason for any drop. The
data-quality report reproduces the full funnel from raw to panel.
