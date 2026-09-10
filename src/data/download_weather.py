"""Hourly weather for Manhattan, as a control for the speed models.

Rain and snow slow traffic. If the post-treatment months were wetter than the
pre-treatment months, some of the estimated effect is weather rather than
tolling. `docs/methodology.md` already lists weather controls as a robustness
specification; this supplies them.

Source: Open-Meteo's historical archive (ERA5 reanalysis). Free, no key, and
crucially **not** on data.cityofnewyork.us - so it does not compete with the
speed backfill for Socrata's rate limit.

Coordinates are Manhattan mid-island (Central Park). One weather series is used
for the whole study area: the CRZ is about 4 miles across, well inside the
resolution at which precipitation differs meaningfully.

Usage:
    python -m src.data.download_weather --start 2023-01-01 --end 2026-09-30
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

import pandas as pd
import requests

from src.config import RAW_DIR, STUDY_START, TIMEZONE

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Central Park, Manhattan.
LAT, LON = 40.7812, -73.9665
WEATHER_PATH = RAW_DIR / "weather_hourly.parquet"

HOURLY_VARS = (
    "temperature_2m",
    "precipitation",
    "rain",
    "snowfall",
    "wind_speed_10m",
    "visibility",
)


def fetch(start: date, end: date) -> pd.DataFrame:
    """Hourly weather in LOCAL time, matching the speed feed's naive timestamps.

    The speed feed is naive America/New_York (verified both directions), so the
    archive is requested in that timezone and the tz offset dropped, giving a
    key that joins directly to `ts_hour` without any conversion.
    """
    resp = requests.get(
        ARCHIVE_URL,
        params={
            "latitude": LAT,
            "longitude": LON,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(HOURLY_VARS),
            "timezone": TIMEZONE,
        },
        timeout=120,
    )
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    df = pd.DataFrame(hourly)
    df["ts_hour"] = pd.to_datetime(df.pop("time"))
    df = df[["ts_hour", *HOURLY_VARS]]

    # Derived flags the models actually use, so the thresholds live in one place.
    df["is_wet"] = df["precipitation"].fillna(0) > 0.1  # mm in the hour
    df["is_snowing"] = df["snowfall"].fillna(0) > 0.0
    df["is_freezing"] = df["temperature_2m"] < 0.0
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=date.fromisoformat, default=STUDY_START)
    ap.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    df = fetch(args.start, args.end)
    WEATHER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(WEATHER_PATH, engine="pyarrow", index=False)
    log.info(
        "wrote %s (%s hours, %s .. %s)",
        WEATHER_PATH.name,
        f"{len(df):,}",
        df["ts_hour"].min(),
        df["ts_hour"].max(),
    )
    log.info(
        "wet hours %.1f%%  snowing %.1f%%  freezing %.1f%%",
        100 * df["is_wet"].mean(),
        100 * df["is_snowing"].mean(),
        100 * df["is_freezing"].mean(),
    )


if __name__ == "__main__":
    main()
