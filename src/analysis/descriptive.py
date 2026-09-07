"""Descriptive statistics and pre/post trend summaries.

Produces:
    outputs/tables/descriptive_summary.csv   group x period means
    outputs/tables/pre_post_change.csv       raw and seasonally-adjusted change
    outputs/figures/trend_volume.png         weekly mean volume, treated vs control

Usage:
    python -m src.analysis.descriptive
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

from src.config import FIGURES_DIR, HOURLY_PANEL_PATH, TABLES_DIR, TREATMENT_DATE

log = logging.getLogger(__name__)

OUTCOMES = ["volume", "speed_mph", "travel_time_index"]


def load_panel(path=HOURLY_PANEL_PATH) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["ts_hour"] = pd.to_datetime(df["ts_hour"])
    df["group"] = df["treated"].map({True: "CBD (treated)", False: "control"})
    df["period"] = df["post"].map({True: "post", False: "pre"})
    return df


def group_period_means(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in OUTCOMES if c in df.columns]
    out = df.groupby(["group", "period"])[cols].agg(["mean", "std", "count"]).round(3)
    return out


def pre_post_change(df: pd.DataFrame) -> pd.DataFrame:
    """Raw and seasonally-adjusted pre->post change per group.

    Seasonal adjustment: for each (week-of-year, hour-of-week) cell, subtract the
    pre-period mean for that cell, then average the residuals in each period.
    """
    cols = [c for c in OUTCOMES if c in df.columns]
    df = df.copy()
    df["woy"] = df["ts_hour"].dt.isocalendar().week.astype(int)
    df["how"] = df["ts_hour"].dt.dayofweek * 24 + df["ts_hour"].dt.hour

    rows = []
    for group, g in df.groupby("group"):
        pre_mask = g["period"] == "pre"
        for col in cols:
            pre, post = g.loc[pre_mask, col], g.loc[~pre_mask, col]
            raw = post.mean() - pre.mean()

            cell_mean = g.loc[pre_mask].groupby(["woy", "how"])[col].mean()
            resid = g[col] - g.set_index(["woy", "how"]).index.map(cell_mean).to_numpy()
            adj = resid[~pre_mask.to_numpy()].mean() - resid[pre_mask.to_numpy()].mean()

            rows.append(
                {
                    "group": group,
                    "outcome": col,
                    "raw_change": round(raw, 3),
                    "seasonally_adj_change": round(float(adj), 3),
                    "pct_change": round(100 * raw / pre.mean(), 2) if pre.mean() else None,
                }
            )
    return pd.DataFrame(rows)


def plot_weekly_trend(df: pd.DataFrame, outcome: str = "volume"):
    weekly = df.set_index("ts_hour").groupby("group")[outcome].resample("W").mean().reset_index()
    fig, ax = plt.subplots(figsize=(10, 5))
    for group, g in weekly.groupby("group"):
        ax.plot(g["ts_hour"], g[outcome], label=group)
    ax.axvline(pd.Timestamp(TREATMENT_DATE), color="black", linestyle="--", label="tolling start")
    ax.set_title(f"Weekly mean {outcome}: CBD vs control")
    ax.set_xlabel("week")
    ax.set_ylabel(outcome)
    ax.legend()
    fig.tight_layout()
    return fig


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = load_panel()

    means = group_period_means(df)
    means.to_csv(TABLES_DIR / "descriptive_summary.csv")
    log.info("wrote %s", TABLES_DIR / "descriptive_summary.csv")

    change = pre_post_change(df)
    change.to_csv(TABLES_DIR / "pre_post_change.csv", index=False)
    log.info("wrote %s", TABLES_DIR / "pre_post_change.csv")

    fig = plot_weekly_trend(df, "volume")
    fig.savefig(FIGURES_DIR / "trend_volume.png", dpi=150)
    log.info("wrote %s", FIGURES_DIR / "trend_volume.png")


if __name__ == "__main__":
    main()
