"""Central configuration: paths, constants, and analysis parameters.

Import from here instead of hard-coding paths, dataset ids, or the treatment
date. Nothing in this module reads or writes data.

Frozen decisions (do not change without documenting why in docs/methodology.md):
  - Research question .... effect of congestion pricing on traffic SPEEDS in the
                          Congestion Relief Zone, plus spillover near the boundary
  - Primary outcome ..... hourly MEDIAN link speed (mph)
  - Intervention date ... 2025-01-05 (tolling start)
  - Primary source ...... NYC DOT "Traffic Speeds NBE" (Socrata i4gi-tjb9)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# --- Paths ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("NYC_CP_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TABLES_DIR = OUTPUTS_DIR / "tables"

for _d in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, FIGURES_DIR, TABLES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Intervention ------------------------------------------------------------
# NYC Congestion Relief Zone tolling began on this date. This is the treatment
# date for every difference-in-differences / event-study specification.
TREATMENT_DATE = date(2025, 1, 5)

TIMEZONE = "America/New_York"  # all timestamps are stored/interpreted here
RANDOM_SEED = 20250105

# --- Study window -----------------------------------------------------------
# Two full years pre-treatment (parallel-trends checks, placebo dates) through
# the latest complete data. STUDY_END = None means "through the latest raw pull".
STUDY_START = date(2023, 1, 1)
STUDY_END: date | None = None

# --- Primary data source ---------------------------------------------------
# NYC DOT Traffic Speeds NBE: TRANSCOM probe / E-ZPass-reader link speeds,
# sub-hourly cadence, history from 2017-04-17.
# https://data.cityofnewyork.us/Transportation/DOT-Traffic-Speeds-NBE/i4gi-tjb9
SOCRATA_DOMAIN = "data.cityofnewyork.us"
DOT_SPEEDS_DATASET_ID = "i4gi-tjb9"

# Register a free token at data.cityofnewyork.us to lift anonymous rate limits.
# Never commit the token; export it in your shell or a local .env (gitignored).
SOCRATA_APP_TOKEN = os.environ.get("NYC_OPENDATA_APP_TOKEN")

# Column in the raw feed that carries the observation timestamp (naive local).
RAW_TIME_COL = "data_as_of"
# Stable per-segment identifier in the raw feed (the analysis unit).
RAW_SEGMENT_COL = "link_id"
RAW_SPEED_COL = "speed"

# --- Panel parameters ------------------------------------------------------
# Peak-hour definition (local time), used for the peak vs off-peak split.
AM_PEAK_HOURS = range(7, 10)  # 07:00-09:59
PM_PEAK_HOURS = range(16, 19)  # 16:00-18:59

# Clustering level for standard errors in the causal models (Phase 7+).
CLUSTER_VAR = "link_id"

# --- Canonical artifacts -------------------------------------------------
RAW_MANIFEST_PATH = RAW_DIR / "manifest.json"
STAGED_SPEEDS_PATH = INTERIM_DIR / "stg_speed_readings.parquet"
HOURLY_PANEL_PATH = PROCESSED_DIR / "hourly_panel.parquet"
DUCKDB_PATH = DATA_DIR / "nyc_cp.duckdb"
