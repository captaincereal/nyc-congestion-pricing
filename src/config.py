"""Central configuration: paths, constants, and analysis parameters.

Import from here instead of hard-coding paths, dataset ids, or the treatment
date. Nothing in this module reads or writes data.

Frozen decisions (do not change without documenting why in docs/methodology.md):
  - Research question .... effect of congestion pricing on traffic SPEEDS in the
                          Congestion Relief Zone, plus spillover near the boundary
  - Primary outcome ..... hourly MEDIAN link speed (mph)
  - Intervention date ... 2025-01-05 (tolling start)
  - Primary source ...... NYC DOT E-Z Pass local-street speeds
                          (Socrata erdf-2akx + 6a2s-2t65)
  - Secondary source .... NYC DOT "Traffic Speeds NBE" (i4gi-tjb9), highways
                          only; used for the spillover/diversion analysis

The primary source changed on 2026-09-08; i4gi-tjb9 has no links on tolled CRZ
surface streets. See the decision record in docs/methodology.md.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# --- Paths ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load a local, gitignored .env if present (Socrata token, optional data dir).
# Never commit .env; see .env.example for the shape.
load_dotenv(PROJECT_ROOT / ".env")
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
# NYC DOT E-Z Pass reader speeds on LOCAL STREETS. Two Socrata datasets with
# identical schemas and the same 351 `sid`s, joining with no gap:
#   erdf-2akx  2021-04-08 .. 2024-07-07  (108.4M rows)
#   6a2s-2t65  2024-07-08 .. present     ( 82.1M rows)
# `median_speed_fps` is the frozen primary outcome, measured on genuine tolled
# CRZ surface streets. See the 2026-09-08 decision record in docs/methodology.md
# for why this replaced i4gi-tjb9 as primary.
SOCRATA_DOMAIN = "data.cityofnewyork.us"

EZPASS_DATASET_IDS = ("erdf-2akx", "6a2s-2t65")
# The date at which coverage hands over from erdf-2akx to 6a2s-2t65.
EZPASS_SPLIT_DATE = date(2024, 7, 8)

EZPASS_TIME_COL = "median_calculation_timestamp"
EZPASS_SEGMENT_COL = "sid"
EZPASS_SPEED_COL = "median_speed_fps"  # feet/second; convert to mph in staging
EZPASS_GEOM_COL = "polyline"  # encoded polyline; CRZ assignment is geometric
# Only 900-second (15-minute) aggregations are usable; the feed also emits 0.
EZPASS_AGG_PERIOD_SEC = 900
FPS_TO_MPH = 0.681818  # 3600 / 5280

# --- Secondary source (spillover / diversion analysis) ----------------------
# NYC DOT Traffic Speeds NBE: TRANSCOM probe / E-ZPass-reader link speeds,
# sub-hourly cadence, history from 2017-04-17.
# https://data.cityofnewyork.us/Transportation/DOT-Traffic-Speeds-NBE/i4gi-tjb9
# Demoted from primary on 2026-09-08: it carries only ~123 links city-wide and
# none on tolled CRZ surface streets. Retained because FDR Drive and the West
# Side Highway are the toll-EXEMPT roads traffic can divert onto, and the
# tunnel/bridge links are the tolled entry points.
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
EZPASS_PARTS_DIR = RAW_DIR / "ezpass_speeds"
EZPASS_MANIFEST_PATH = RAW_DIR / "ezpass_manifest.json"
STAGED_SPEEDS_PATH = INTERIM_DIR / "stg_speed_readings.parquet"
HOURLY_PANEL_PATH = PROCESSED_DIR / "hourly_panel.parquet"
DUCKDB_PATH = DATA_DIR / "nyc_cp.duckdb"
