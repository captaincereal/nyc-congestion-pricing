"""Event-study estimation of dynamic congestion-pricing effects.

    y_{i,t} = alpha_i + gamma_t + sum_{k != -1} theta_k * 1[event_time = k]
              + X_{i,t}*delta + e_{i,t}

  - event_time in weeks (default) relative to 2025-01-05
  - reference period k = -1 (omitted)
  - flat pre-period thetas support parallel trends; post thetas trace adjustment

Produces:
    outputs/tables/event_study_<outcome>.csv
    outputs/figures/event_study_<outcome>.png

Usage:
    python -m src.analysis.event_study [--outcome log_volume] [--horizon 12]
"""

from __future__ import annotations

import argparse
import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from src.config import FIGURES_DIR, HOURLY_PANEL_PATH, TABLES_DIR

log = logging.getLogger(__name__)

CONTROLS = ["temp_c", "precip_mm", "fuel_price", "is_holiday"]
REFERENCE_K = -1


def prepare(df: pd.DataFrame, outcome: str, horizon: int) -> pd.DataFrame:
    df = df.copy()
    df["ts_hour"] = pd.to_datetime(df["ts_hour"])

    if outcome == "log_volume":
        df["log_volume"] = np.log(df["volume"].where(df["volume"] > 0))

    # bin event_time (weeks) to [-horizon, +horizon]; only treated units get leads/lags
    k = df["event_time"].clip(-horizon, horizon)
    k = np.where(df["treated"].astype(bool), k, REFERENCE_K)
    df["k"] = k.astype(int)

    df["time_key"] = df["ts_hour"].dt.floor("h")
    df = df.dropna(subset=[outcome])
    return df


def build_dummies(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    ks = sorted(x for x in df["k"].unique() if x != REFERENCE_K)
    names = []
    for kk in ks:
        col = f"k_{'m' if kk < 0 else 'p'}{abs(kk)}"
        df[col] = (df["k"] == kk).astype(float)
        names.append(col)
    return df, names


def estimate(df: pd.DataFrame, outcome: str, dummy_cols: list[str]):
    exog_cols = dummy_cols + [c for c in CONTROLS if c in df.columns]
    panel = df.set_index(["sensor_id", "time_key"])
    res = PanelOLS(
        dependent=panel[outcome].astype(float),
        exog=panel[exog_cols].astype(float),
        entity_effects=True,
        time_effects=True,
        drop_absorbed=True,
    ).fit(cov_type="clustered", cluster_entity=True)
    log.info("\n%s", res.summary)
    return res


def coef_frame(res, dummy_cols: list[str]) -> pd.DataFrame:
    rows = [{"k": REFERENCE_K, "coef": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0}]
    ci = res.conf_int()
    for col in dummy_cols:
        sign, mag = col.split("_")[1][0], int(col.split("_")[1][1:])
        kk = -mag if sign == "m" else mag
        rows.append(
            {
                "k": kk,
                "coef": res.params[col],
                "se": res.std_errors[col],
                "ci_low": ci.loc[col, "lower"],
                "ci_high": ci.loc[col, "upper"],
            }
        )
    return pd.DataFrame(rows).sort_values("k").reset_index(drop=True)


def plot(coefs: pd.DataFrame, outcome: str):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axhline(0, color="grey", lw=1)
    ax.axvline(-0.5, color="black", linestyle="--", label="tolling start")
    ax.errorbar(
        coefs["k"],
        coefs["coef"],
        yerr=[coefs["coef"] - coefs["ci_low"], coefs["ci_high"] - coefs["coef"]],
        fmt="o-",
        capsize=3,
    )
    ax.set_xlabel("weeks relative to 2025-01-05")
    ax.set_ylabel(f"effect on {outcome}")
    ax.set_title(f"Event study: {outcome}")
    ax.legend()
    fig.tight_layout()
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=str(HOURLY_PANEL_PATH))
    parser.add_argument(
        "--outcome",
        default="log_volume",
        choices=["log_volume", "volume", "speed_mph", "travel_time_index"],
    )
    parser.add_argument("--horizon", type=int, default=12, help="max |weeks| from treatment")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raw = pd.read_parquet(args.panel)

    df = prepare(raw, args.outcome, args.horizon)
    df, dummy_cols = build_dummies(df)
    res = estimate(df, args.outcome, dummy_cols)
    coefs = coef_frame(res, dummy_cols)

    out_csv = TABLES_DIR / f"event_study_{args.outcome}.csv"
    coefs.to_csv(out_csv, index=False)
    fig = plot(coefs, args.outcome)
    out_png = FIGURES_DIR / f"event_study_{args.outcome}.png"
    fig.savefig(out_png, dpi=150)
    log.info("wrote %s and %s", out_csv, out_png)


if __name__ == "__main__":
    main()
