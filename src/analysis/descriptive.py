"""Phase 6 — descriptive series for the CRZ speed study. No causal claims.

Produces, for every figure, the table behind it, so nothing rests on reading a
picture:

    outputs/tables/descriptive_summary.csv    group x period summary
    outputs/tables/weekly_median_speed.csv    weekly median speed per group
    outputs/tables/treated_control_gap.csv    the pre-trend series
    outputs/tables/hourly_profile.csv         hour-of-day profile, pre vs post
    outputs/figures/weekly_median_speed.png   treated vs control over time
    outputs/figures/treated_control_gap.png   the parallel-trends visual
    outputs/figures/hourly_profile.png        hour-of-day, pre vs post
    outputs/figures/coverage_over_time.png    links reporting per week

The gap figure is the one that matters for control selection (D2): under
parallel trends the treated-minus-control gap is flat before 2025-01-05. It is
plotted, not tested - a formal event-study test is Phase 8, and needs the
pre-period backfill.

Usage:
    python -m src.analysis.descriptive
"""

from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import (  # noqa: E402
    AM_PEAK_HOURS,
    FIGURES_DIR,
    HOURLY_PANEL_PATH,
    TABLES_DIR,
    TREATMENT_DATE,
)

log = logging.getLogger(__name__)

# Categorical slots in fixed order, never cycled. Validated for CVD separation
# and lightness band against the light surface; every series is also direct-
# labelled, which is the required relief for the sub-3:1 contrast warning.
SERIES_COLOR = {
    "treated": "#2a78d6",
    "control": "#eb6834",
    "exempt_in_zone": "#1baf7a",
    "boundary": "#eda100",
    "crossing": "#e87ba4",
}
GROUP_ORDER = ["treated", "control", "exempt_in_zone", "boundary", "crossing"]

INK = "#1a1a19"
INK_MUTED = "#6b6b66"
GRID = "#e4e4e0"
SURFACE = "#fcfcfb"


def _style(ax, *, ylabel: str, title: str, subtitle: str = "") -> None:
    """Recessive axes, one horizontal grid, no chartjunk."""
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=10)
    # Subtitle sits above the axes and the title above that, so neither the
    # title's descenders nor a wrapped subtitle collide with the plot area.
    ax.set_title(title, color=INK, fontsize=13, fontweight="bold", loc="left", pad=30)
    if subtitle:
        ax.text(
            0,
            1.015,
            subtitle,
            transform=ax.transAxes,
            color=INK_MUTED,
            fontsize=9.5,
            va="bottom",
            wrap=True,
        )


def _mark_treatment(ax) -> None:
    ax.axvline(TREATMENT_DATE, color=INK, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)
    ax.annotate(
        "tolling begins\n2025-01-05",
        xy=(TREATMENT_DATE, ax.get_ylim()[1]),
        xytext=(6, -4),
        textcoords="offset points",
        color=INK,
        fontsize=8.5,
        va="top",
        linespacing=1.35,
    )


def _save(fig, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    log.info("wrote %s", path)


def _write_table(df: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / name
    df.to_csv(path, index=False)
    log.info("wrote %s", path)


def load_panel(path=HOURLY_PANEL_PATH) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["ts_hour"] = pd.to_datetime(df["ts_hour"])
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["ts_hour"].dt.to_period("W").dt.start_time
    return df


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby(["treatment_group", "post"], observed=True)
        .agg(
            links=("link_id", "nunique"),
            link_hours=("median_speed_mph", "size"),
            median_speed_mph=("median_speed_mph", "median"),
            mean_speed_mph=("median_speed_mph", "mean"),
            mean_obs_per_hour=("n_obs", "mean"),
        )
        .reset_index()
        .round(3)
    )
    out["period"] = out["post"].map({True: "post", False: "pre"})
    return out.drop(columns=["post"])


def weekly_series(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["week", "treatment_group"], observed=True)["median_speed_mph"]
        .median()
        .reset_index()
        .rename(columns={"median_speed_mph": "weekly_median_mph"})
    )


def plot_weekly(weekly: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for g in GROUP_ORDER:
        s = weekly[weekly.treatment_group == g].sort_values("week")
        if s.empty:
            continue
        ax.plot(s["week"], s["weekly_median_mph"], color=SERIES_COLOR[g], linewidth=2, zorder=3)
        ax.annotate(
            g,
            xy=(s["week"].iloc[-1], s["weekly_median_mph"].iloc[-1]),
            xytext=(7, 0),
            textcoords="offset points",
            color=SERIES_COLOR[g],
            fontsize=9,
            va="center",
            fontweight="bold",
        )
    _style(
        ax,
        ylabel="weekly median speed (mph)",
        title="Weekly median speed by treatment group",
        subtitle="Levels, not effects. Groups differ sharply in level, which is expected.",
    )
    _mark_treatment(ax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.margins(x=0.12)
    _save(fig, "weekly_median_speed.png")


def gap_series(weekly: pd.DataFrame) -> pd.DataFrame:
    wide = weekly.pivot_table(
        index="week", columns="treatment_group", values="weekly_median_mph", aggfunc="first"
    )
    if not {"treated", "control"} <= set(wide.columns):
        return pd.DataFrame()
    gap = (wide["treated"] - wide["control"]).rename("treated_minus_control_mph").reset_index()
    gap["period"] = (gap["week"] >= pd.Timestamp(TREATMENT_DATE)).map({True: "post", False: "pre"})
    return gap


def plot_gap(gap: pd.DataFrame) -> None:
    if gap.empty:
        log.warning("gap series empty - skipping figure")
        return
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.plot(
        gap["week"],
        gap["treated_minus_control_mph"],
        color=SERIES_COLOR["treated"],
        linewidth=2,
        zorder=3,
    )
    ax.scatter(
        gap["week"],
        gap["treated_minus_control_mph"],
        s=26,
        color=SERIES_COLOR["treated"],
        zorder=4,
        edgecolor=SURFACE,
        linewidth=1.4,
    )
    _style(
        ax,
        ylabel="treated − control (mph)",
        title="Treated-minus-control gap, weekly",
        subtitle=(
            "Under parallel trends this is FLAT before the toll. A sloping pre-period "
            "means the control group is not a valid counterfactual (see D2)."
        ),
    )
    _mark_treatment(ax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.margins(x=0.06)
    _save(fig, "treated_control_gap.png")


def hourly_profile(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df.treatment_group.isin(["treated", "control"])]
    return (
        sub.groupby(["treatment_group", "post", "hour"], observed=True)["median_speed_mph"]
        .median()
        .reset_index()
        .rename(columns={"median_speed_mph": "median_mph"})
    )


def plot_hourly(prof: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for g in ("treated", "control"):
        for post, dash in ((False, (0, (4, 3))), (True, None)):
            s = prof[(prof.treatment_group == g) & (prof.post == post)].sort_values("hour")
            if s.empty:
                continue
            ax.plot(
                s["hour"],
                s["median_mph"],
                color=SERIES_COLOR[g],
                linewidth=2,
                linestyle=dash or "-",
                zorder=3,
                label=f"{g} · {'post' if post else 'pre'}",
            )
    for lo, hi, lab in ((min(AM_PEAK_HOURS), max(AM_PEAK_HOURS), "AM peak"), (16, 18, "PM peak")):
        ax.axvspan(lo - 0.5, hi + 0.5, color=GRID, alpha=0.55, zorder=1)
        ax.text(
            (lo + hi) / 2,
            ax.get_ylim()[0],
            lab,
            ha="center",
            va="bottom",
            fontsize=8.5,
            color=INK_MUTED,
        )
    _style(
        ax,
        ylabel="median speed (mph)",
        title="Speed by hour of day, before and after tolling",
        subtitle="Dashed = pre-treatment, solid = post. Shaded bands are the frozen peak windows.",
    )
    ax.set_xlabel("hour of day (America/New_York)", color=INK_MUTED, fontsize=10)
    ax.set_xticks(range(0, 24, 3))
    leg = ax.legend(frameon=False, fontsize=9, labelcolor=INK_MUTED, loc="lower right")
    leg.set_zorder(5)
    _save(fig, "hourly_profile.png")


def plot_coverage(df: pd.DataFrame) -> None:
    cov = (
        df.groupby(["week", "treatment_group"], observed=True)["link_id"]
        .nunique()
        .reset_index()
        .rename(columns={"link_id": "links"})
    )
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for g in GROUP_ORDER:
        s = cov[cov.treatment_group == g].sort_values("week")
        if s.empty:
            continue
        ax.plot(s["week"], s["links"], color=SERIES_COLOR[g], linewidth=2, zorder=3)
        ax.annotate(
            g,
            xy=(s["week"].iloc[-1], s["links"].iloc[-1]),
            xytext=(7, 0),
            textcoords="offset points",
            color=SERIES_COLOR[g],
            fontsize=9,
            va="center",
            fontweight="bold",
        )
    _style(
        ax,
        ylabel="links reporting",
        title="Reporting coverage by week",
        subtitle="A step at the toll date would confound the estimate. Watch for one.",
    )
    _mark_treatment(ax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.margins(x=0.12)
    _save(fig, "coverage_over_time.png")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = load_panel()
    log.info(
        "panel: %s link-hours, %s .. %s",
        f"{len(df):,}",
        df["date"].min().date(),
        df["date"].max().date(),
    )

    summary = summary_table(df)
    _write_table(summary, "descriptive_summary.csv")
    log.info("\n%s", summary.to_string(index=False))

    weekly = weekly_series(df)
    _write_table(weekly, "weekly_median_speed.csv")
    plot_weekly(weekly)

    gap = gap_series(weekly)
    _write_table(gap, "treated_control_gap.csv")
    plot_gap(gap)
    if not gap.empty:
        pre = gap[gap.period == "pre"]["treated_minus_control_mph"]
        post = gap[gap.period == "post"]["treated_minus_control_mph"]
        log.info(
            "gap: pre mean %.3f (sd %.3f, n=%d) | post mean %.3f (sd %.3f, n=%d)",
            pre.mean(),
            pre.std(),
            len(pre),
            post.mean(),
            post.std(),
            len(post),
        )

    prof = hourly_profile(df)
    _write_table(prof, "hourly_profile.csv")
    plot_hourly(prof)

    plot_coverage(df)


if __name__ == "__main__":
    main()
