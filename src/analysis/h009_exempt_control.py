"""H009 — does the entry-timing discontinuity survive a control that pays no toll?

H008 compared the toll boundaries to other hour boundaries on the same series.
That set contains the morning ramp, where entries rise fivefold within the hour
and a local linear fit cannot track the curvature, and it was summarised by a
maximum, which is a statistic of the tail.

The control here is different in kind: `excluded_roadway_entries`, vehicles on
the toll-exempt roadways crossing the same detection points, on the same
sensors, in the same ten-minute blocks. They are never charged, so no price
changes for them at 05:00 or 21:00. A daily rhythm, a sensor batching at hour
boundaries, and polynomial misfit all apply equally to both series; a price does
not. The estimand is the difference in discontinuities.

Record: docs/hypotheses/H009-toll-timing-exempt-control.md, committed first.

    python -m src.analysis.h009_exempt_control
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from src.analysis.h008_toll_timing import (
    BANDWIDTH_MINUTES,
    POLY_ORDER,
    WEEKDAY_TOLL_BOUNDARIES,
    WEEKEND,
    _fetch,
    _signed_minutes,
    estimate_discontinuity,
)
from src.config import TABLES_DIR

log = logging.getLogger(__name__)

# The four detection points that record both a tolled and an exempt roadway.
# Restricting to these is what makes the comparison within-location.
DUAL_GROUPS = (
    "FDR Drive at 60th St",
    "Brooklyn Bridge",
    "Hugh L. Carey Tunnel",
    "West Side Highway at 60th St",
)
# Frozen in the record, before the percentile was computed: entries rise about
# fivefold across these hours and a local linear fit cannot track that.
CURVATURE_EXCLUDED = (5, 6, 7, 8)
CALENDAR_EXCLUDED = (0,)
PLACEBO_PERCENTILE = 95


def load_dual() -> pd.DataFrame:
    """Tolled and exempt entries per date x block at the dual-recording points."""
    frame = _fetch(
        "toll_date,hour_of_day,minute_of_hour,day_of_week,detection_group,"
        "sum(crz_entries) as tolled,sum(excluded_roadway_entries) as exempt",
        "toll_date,hour_of_day,minute_of_hour,day_of_week,detection_group",
    )
    frame = frame[frame["detection_group"].isin(DUAL_GROUPS)].copy()
    frame["date"] = pd.to_datetime(frame["toll_date"]).dt.date
    frame["year"] = pd.to_datetime(frame["toll_date"]).dt.year
    for column in ("hour_of_day", "minute_of_hour", "tolled", "exempt"):
        frame[column] = pd.to_numeric(frame[column])
    frame["minute_of_day"] = frame["hour_of_day"] * 60 + frame["minute_of_hour"]
    frame["is_weekend"] = frame["day_of_week"].isin(WEEKEND)
    return frame


def _series(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    out = frame[["date", "minute_of_day", "detection_group", "year"]].copy()
    out["entries"] = frame[column].to_numpy()
    return out


def difference_in_discontinuities(
    frame: pd.DataFrame,
    boundary_hour: int,
    bandwidth: int = BANDWIDTH_MINUTES,
    order: int = POLY_ORDER,
) -> dict:
    """delta = tau(tolled) - tau(exempt), estimated jointly so it carries an SE.

    Both series are stacked with a `tolled` indicator interacted through the
    whole polynomial, so each keeps its own trend and its own day effects. Fixed
    effects are absorbed on date x series for that reason: the two series differ
    in level by an order of magnitude and nothing should be identified off that.
    """
    stacked = []
    for label, column in ((1.0, "tolled"), (0.0, "exempt")):
        part = _series(frame, column)
        part["tolled"] = label
        stacked.append(part)
    panel = pd.concat(stacked, ignore_index=True)

    run = _signed_minutes(panel["minute_of_day"].to_numpy(), boundary_hour)
    keep = (run >= -bandwidth) & (run < bandwidth)
    window = panel.loc[keep].copy()
    window["run"] = run[keep]
    window["post"] = (window["run"] >= 0).astype(float)
    if window.empty or window["entries"].sum() <= 0:
        return {"boundary_hour": boundary_hour, "delta": np.nan, "se": np.nan}

    post = window["post"].to_numpy()
    tolled = window["tolled"].to_numpy()
    columns = [post, post * tolled]
    for power in range(1, order + 1):
        run_power = window["run"].to_numpy() ** power
        columns += [run_power, run_power * post, run_power * tolled, run_power * post * tolled]
    X = np.column_stack(columns)
    y = np.log1p(window["entries"].to_numpy(dtype=float))

    # date x series: the two series differ hugely in level, and day effects are
    # not shared between them.
    codes, _ = pd.factorize(
        window["date"].astype(str) + "|" + window["tolled"].astype(str), sort=False
    )
    for matrix in (y, X):
        totals = np.zeros((codes.max() + 1,) + matrix.shape[1:])
        counts = np.bincount(codes, minlength=codes.max() + 1)
        np.add.at(totals, codes, matrix)
        totals = (totals.T / counts).T
        matrix -= totals[codes]

    date_codes, _ = pd.factorize(window["date"], sort=False)
    XtX = X.T @ X
    beta = np.linalg.solve(XtX, X.T @ y)
    resid = y - X @ beta
    inverse = np.linalg.inv(XtX)
    meat = np.zeros_like(XtX)
    for cluster in range(date_codes.max() + 1):
        rows = date_codes == cluster
        score = X[rows].T @ resid[rows]
        meat += np.outer(score, score)
    n_clusters = date_codes.max() + 1
    vcov = inverse @ meat @ inverse * (n_clusters / max(n_clusters - 1, 1))

    delta, delta_se = float(beta[1]), float(np.sqrt(vcov[1, 1]))
    return {
        "boundary_hour": boundary_hour,
        "tau_exempt": float(beta[0]),
        "tau_exempt_se": float(np.sqrt(vcov[0, 0])),
        "delta": delta,
        "se": delta_se,
        "ci_low": delta - 1.96 * delta_se,
        "ci_high": delta + 1.96 * delta_se,
        "delta_pct": float(np.expm1(delta) * 100),
        "n_obs": int(len(window)),
        "n_dates": int(n_clusters),
    }


def placebo_bar(frame: pd.DataFrame, column: str) -> dict:
    """The corrected bar: 95th percentile of |tau|, curvature hours excluded."""
    series = _series(frame, column)
    taus = {}
    for hour in range(24):
        if hour in CURVATURE_EXCLUDED or hour in CALENDAR_EXCLUDED:
            continue
        if hour in WEEKDAY_TOLL_BOUNDARIES:
            continue
        taus[hour] = abs(estimate_discontinuity(series, hour)["tau"])
    values = np.array(list(taus.values()))
    return {
        "series": column,
        "n_placebos": len(values),
        "p95": float(np.percentile(values, PLACEBO_PERCENTILE)),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "sd": float(values.std(ddof=1)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-prefix", default="H009")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    dual = load_dual()
    weekday = dual[~dual["is_weekend"]]
    log.info(
        "dual-recording points: %s rows, %s dates | tolled %s, exempt %s",
        f"{len(dual):,}",
        f"{dual['date'].nunique():,}",
        f"{int(dual['tolled'].sum()):,}",
        f"{int(dual['exempt'].sum()):,}",
    )

    rows = []
    for hour in range(24):
        result = difference_in_discontinuities(weekday, hour)
        tolled_only = estimate_discontinuity(_series(weekday, "tolled"), hour)
        result["tau_tolled"] = tolled_only["tau"]
        result["is_toll_boundary"] = hour in WEEKDAY_TOLL_BOUNDARIES
        rows.append(result)
    main_table = pd.DataFrame(rows)
    main_table.to_csv(TABLES_DIR / f"{args.out_prefix}_difference.csv", index=False)

    bars = pd.DataFrame([placebo_bar(weekday, c) for c in ("tolled", "exempt")])
    bars.to_csv(TABLES_DIR / f"{args.out_prefix}_placebo_bar.csv", index=False)

    per_group = []
    for group, part in weekday.groupby("detection_group"):
        for hour in WEEKDAY_TOLL_BOUNDARIES:
            result = difference_in_discontinuities(part, hour)
            result["detection_group"] = group
            per_group.append(result)
    pd.DataFrame(per_group).to_csv(
        TABLES_DIR / f"{args.out_prefix}_by_detection_group.csv", index=False
    )

    per_year = []
    for year, part in weekday.groupby("year"):
        for hour in WEEKDAY_TOLL_BOUNDARIES:
            result = difference_in_discontinuities(part, hour)
            result["year"] = int(year)
            per_year.append(result)
    pd.DataFrame(per_year).to_csv(TABLES_DIR / f"{args.out_prefix}_by_year.csv", index=False)

    for hour in WEEKDAY_TOLL_BOUNDARIES:
        row = main_table[main_table["boundary_hour"] == hour].iloc[0]
        log.info(
            "%02d:00  tau_tolled=%+.4f  tau_exempt=%+.4f  delta=%+.4f [%.4f, %.4f]",
            hour,
            row["tau_tolled"],
            row["tau_exempt"],
            row["delta"],
            row["ci_low"],
            row["ci_high"],
        )
    for _, bar in bars.iterrows():
        log.info(
            "placebo bar (%s): p95=%.4f over %d boundaries (max %.4f)",
            bar["series"],
            bar["p95"],
            bar["n_placebos"],
            bar["max"],
        )
    log.info("wrote %s_* tables", args.out_prefix)


if __name__ == "__main__":
    main()
