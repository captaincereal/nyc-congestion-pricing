"""Difference-in-differences estimation of the congestion-pricing effect.

Two-way fixed-effects specification:

    y_{i,t} = alpha_i + gamma_t + beta * treated_post_{i,t} + X_{i,t}*delta + e_{i,t}

  - alpha_i : sensor fixed effects
  - gamma_t : time fixed effects (date x hour by default)
  - beta    : ATT, the coefficient of interest
  - SEs clustered by sensor_id (config.CLUSTER_VAR)

Outcomes: log(volume), speed_mph, travel_time_index.

Usage:
    python -m src.analysis.did [--outcome log_volume] [--time-fe date_hour]
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from src.config import CLUSTER_VAR, HOURLY_PANEL_PATH, TABLES_DIR

log = logging.getLogger(__name__)

CONTROLS = ["temp_c", "precip_mm", "fuel_price", "is_holiday"]


def prepare(df: pd.DataFrame, outcome: str, time_fe: str) -> pd.DataFrame:
    df = df.copy()
    df["ts_hour"] = pd.to_datetime(df["ts_hour"])

    if outcome == "log_volume":
        df["log_volume"] = np.log(df["volume"].where(df["volume"] > 0))

    if time_fe == "date_hour":
        df["time_key"] = df["ts_hour"].dt.floor("h")
    elif time_fe == "day_plus_how":
        df["time_key"] = df["ts_hour"].dt.date.astype("string")
        df["how"] = df["ts_hour"].dt.dayofweek * 24 + df["ts_hour"].dt.hour
    else:
        raise ValueError(f"unknown time_fe: {time_fe}")

    keep = [
        "sensor_id",
        "time_key",
        outcome,
        "treated_post",
        *[c for c in CONTROLS if c in df.columns],
    ]
    if "how" in df.columns:
        keep.append("how")
    df = df.dropna(subset=[outcome, "treated_post"])[keep]
    return df.set_index(["sensor_id", "time_key"])


def estimate(df: pd.DataFrame, outcome: str, *, with_controls: bool = True) -> object:
    exog_cols = ["treated_post"]
    if with_controls:
        exog_cols += [c for c in CONTROLS + ["how"] if c in df.columns]

    exog = df[exog_cols].astype(float)
    mod = PanelOLS(
        dependent=df[outcome].astype(float),
        exog=exog,
        entity_effects=True,
        time_effects=True,
        drop_absorbed=True,
    )
    res = mod.fit(cov_type="clustered", cluster_entity=True)
    log.info("\n%s", res.summary)
    return res


def results_table(res, outcome: str) -> pd.DataFrame:
    b = res.params["treated_post"]
    se = res.std_errors["treated_post"]
    return pd.DataFrame(
        [
            {
                "outcome": outcome,
                "att": round(b, 4),
                "std_error": round(se, 4),
                "t_stat": round(res.tstats["treated_post"], 2),
                "p_value": round(res.pvalues["treated_post"], 4),
                "ci_low": round(res.conf_int().loc["treated_post", "lower"], 4),
                "ci_high": round(res.conf_int().loc["treated_post", "upper"], 4),
                "n_obs": int(res.nobs),
                "cluster_var": CLUSTER_VAR,
            }
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=str(HOURLY_PANEL_PATH))
    parser.add_argument(
        "--outcome",
        default="log_volume",
        choices=["log_volume", "volume", "speed_mph", "travel_time_index"],
    )
    parser.add_argument("--time-fe", default="date_hour", choices=["date_hour", "day_plus_how"])
    parser.add_argument("--no-controls", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raw = pd.read_parquet(args.panel)
    df = prepare(raw, args.outcome, args.time_fe)

    res = estimate(df, args.outcome, with_controls=not args.no_controls)
    table = results_table(res, args.outcome)

    out = TABLES_DIR / f"did_{args.outcome}.csv"
    table.to_csv(out, index=False)
    log.info("wrote %s\n%s", out, table.to_string(index=False))


if __name__ == "__main__":
    main()
