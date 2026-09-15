"""H010 — do drivers move onto toll-exempt roadways as the peak charge begins?

H009 measured the exempt series as a control and noticed it rising 7 log points
at 05:00 while tolled entries collapsed. It flagged that as possible route
substitution and claimed it nowhere.

This measures it in **vehicle counts rather than log points**, because a
substitution claim has to balance in vehicles: a 7% rise on the smaller series
cannot absorb a 27% fall on the larger one, and a ratio of two percentage
changes on series of different size answers no question anyone asked.

    f = S / D

D is the tolled deficit and S the exempt surplus over the three ten-minute
blocks beginning at the boundary, each measured against a counterfactual fitted
on the six blocks before it. Both are sums of vehicles across dates and
detection groups, so f is a ratio of totals rather than a mean of per-cell
ratios — the record specifies that.

The counterfactual is the weak point and the record says so. The adjudication in
docs/hypotheses/ADJUDICATION-timing.md showed a local linear fit through the
05:00 ramp carries curvature straight into the estimate, so f is reported under
three counterfactuals and a disagreement between them by more than a factor of
two is itself the finding.

Record: docs/hypotheses/H010-exempt-route-substitution.md, committed first.

**Written by the record's author and deliberately not run by them.** Whoever
executes this fills in Result and Verdict; see the record's Notes.

    python -m src.analysis.h010_route_substitution
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from src.analysis.h008_toll_timing import BLOCK_MINUTES, WEEKEND, _fetch
from src.analysis.h009_exempt_control import DUAL_GROUPS
from src.config import FIGURES_DIR, RANDOM_SEED, TABLES_DIR

log = logging.getLogger(__name__)

# The boundary the record asks about, and the one reported descriptively beside
# it. Substitution predicts exempt entries RISE at 05:00 as the charge begins
# and FALL at 21:00 as it ends; H009 measured a rise at both, which the record
# discloses and does not score.
PRIMARY_BOUNDARY = 5
MIRROR_BOUNDARY = 21

PRE_BLOCKS = 6  # 04:00-04:50 before an 05:00 boundary
POST_BLOCKS = 3  # 05:00-05:20, where substitution would land
COUNTERFACTUALS = ("loglinear", "flat", "quadratic")
FROZEN_COUNTERFACTUAL = "loglinear"

BOOTSTRAP_DRAWS = 500
BOOTSTRAP_ALPHA = 0.05

# H008 found the timing response confined to these two classes; trucks, taxis
# and buses were flat or wrong-signed. A sensor artefact has no reason to
# respect vehicle class, which is what makes this cut informative.
RESPONDER_PREFIXES = ("1 -", "5 -")

# Frozen in the record, before anything was measured.
SUPPORT_F = 0.05  # f under the frozen counterfactual
SUPPORT_F_FLOOR = 0.02  # f under the flat counterfactual; see _counterfactual
REFUTE_F = 0.02
SUPPORT_RATIO = 1.10  # responder share of surplus / share of baseline volume
REFUTE_RATIO = 0.95
COUNTERFACTUAL_SPREAD = 2.0  # f moving by more than this across the three
# Declared in advance: above this baseline share the ratio cannot reach 1.10
# however concentrated the surplus is, and criterion 2 is untestable.
FEASIBILITY_CEILING = 0.90


def load_dual_by_class(
    boundary_hours: tuple[int, ...] = (PRIMARY_BOUNDARY, MIRROR_BOUNDARY)
) -> pd.DataFrame:
    """Tolled and exempt entries per date x block x detection group x class.

    Restricted server-side to the hours either side of the boundaries, which
    cuts the pull by roughly a factor of six. `hour_of_day` is a plain integer
    column, so this does not hit the paging collapse AGENTS.md warns about —
    that one comes from putting a function on the timestamp column.
    """
    wanted = sorted({hour for boundary in boundary_hours for hour in (boundary - 1, boundary)})
    where = "hour_of_day in (" + ",".join(str(hour) for hour in wanted) + ")"
    frame = _fetch(
        "toll_date,hour_of_day,minute_of_hour,day_of_week,detection_group,vehicle_class,"
        "sum(crz_entries) as tolled,sum(excluded_roadway_entries) as exempt",
        "toll_date,hour_of_day,minute_of_hour,day_of_week,detection_group,vehicle_class",
        where=where,
    )
    rows_in = len(frame)
    frame = frame[frame["detection_group"].isin(DUAL_GROUPS)].copy()
    log.info(
        "rows in %s -> %s after restricting to the %s dual-recording points",
        f"{rows_in:,}",
        f"{len(frame):,}",
        len(DUAL_GROUPS),
    )
    frame["date"] = pd.to_datetime(frame["toll_date"]).dt.date
    frame["year"] = pd.to_datetime(frame["toll_date"]).dt.year
    for column in ("hour_of_day", "minute_of_hour", "tolled", "exempt"):
        frame[column] = pd.to_numeric(frame[column])
    frame["minute_of_day"] = frame["hour_of_day"] * 60 + frame["minute_of_hour"]
    frame["is_responder"] = frame["vehicle_class"].str.startswith(RESPONDER_PREFIXES)
    rows_in = len(frame)
    frame = frame[~frame["day_of_week"].isin(WEEKEND)].copy()
    log.info("rows in %s -> %s after dropping weekends", f"{rows_in:,}", f"{len(frame):,}")
    return frame


def exempt_is_populated_by_class(frame: pd.DataFrame) -> dict:
    """Does the feed carry `excluded_roadway_entries` at vehicle-class grain?

    The record requires confirming this rather than assuming it. If exempt
    counts collapse to a single class, or vanish entirely, criterion 2 is
    untestable and must be reported as such rather than worked around.
    """
    per_class = frame.groupby("vehicle_class", as_index=False)["exempt"].sum()
    nonzero = per_class[per_class["exempt"] > 0]
    total = float(per_class["exempt"].sum())
    return {
        "exempt_total": total,
        "classes_with_exempt": int(len(nonzero)),
        "classes_seen": int(len(per_class)),
        "populated_by_class": bool(total > 0 and len(nonzero) > 1),
    }


def _cell_matrix(part: pd.DataFrame, boundary_hour: int, column: str) -> tuple:
    """One row per cell, one column per block, ordered by minutes from boundary.

    Cells missing any of the nine blocks are dropped rather than interpolated,
    and the count is logged.
    """
    runs = part["minute_of_day"].to_numpy() - boundary_hour * 60
    keep = (runs >= -PRE_BLOCKS * BLOCK_MINUTES) & (runs < POST_BLOCKS * BLOCK_MINUTES)
    window = part.loc[keep].copy()
    window["run"] = runs[keep]

    wide = window.pivot_table(
        index=["date", "detection_group"], columns="run", values=column, aggfunc="sum"
    )
    expected = [block * BLOCK_MINUTES for block in range(-PRE_BLOCKS, POST_BLOCKS)]  # -60 .. +20
    missing = [run for run in expected if run not in wide.columns]
    if missing:
        return np.empty((0, len(expected))), pd.DataFrame(index=wide.index[:0])
    complete = wide[expected].dropna()
    dropped = len(wide) - len(complete)
    if dropped:
        log.info("dropped %s of %s cells for incomplete blocks", dropped, len(wide))
    return complete.to_numpy(dtype=float), complete


def _counterfactual(observed: np.ndarray, method: str) -> np.ndarray:
    """Predict the POST_BLOCKS from the PRE_BLOCKS, in counts.

    Fits are in log1p space and exponentiated back, matching how the boundary
    estimators in H008 and H009 treat this series.
    """
    pre_runs = np.arange(-PRE_BLOCKS, 0, dtype=float) * BLOCK_MINUTES
    post_runs = np.arange(0, POST_BLOCKS, dtype=float) * BLOCK_MINUTES
    pre = np.log1p(observed[:, :PRE_BLOCKS])

    if method == "flat":
        # The last pre-boundary block, held level. The record calls this a
        # model-free floor that understates both the deficit and the surplus.
        # It is not, on a rising series: holding level puts the counterfactual
        # BELOW the true ramp, which shrinks the deficit until it turns negative
        # and inflates the surplus, both pushing f the same way. Measured and
        # pinned in tests/test_h010_route_substitution.py; see the 2026-09-15
        # entry in docs/decision_register.md. Kept as the record specifies it,
        # and reported rather than relied on.
        return np.repeat(observed[:, PRE_BLOCKS - 1 : PRE_BLOCKS], POST_BLOCKS, axis=1)

    order = {"loglinear": 1, "quadratic": 2}[method]
    design_pre = np.vander(pre_runs, order + 1, increasing=True)
    design_post = np.vander(post_runs, order + 1, increasing=True)
    beta = pre @ np.linalg.pinv(design_pre).T
    return np.expm1(beta @ design_post.T)


def deficit_and_surplus(frame: pd.DataFrame, boundary_hour: int, method: str) -> pd.DataFrame:
    """Per-date tolled deficit and exempt surplus, in vehicles.

    Returned per date so the block bootstrap can resample whole dates with the
    two series still paired inside each one.
    """
    tolled, index = _cell_matrix(frame, boundary_hour, "tolled")
    exempt, _ = _cell_matrix(frame, boundary_hour, "exempt")
    if len(tolled) == 0 or len(exempt) == 0 or len(tolled) != len(exempt):
        return pd.DataFrame(columns=["date", "deficit", "surplus"])

    tolled_cf = _counterfactual(tolled, method)
    exempt_cf = _counterfactual(exempt, method)
    deficit = (tolled_cf - tolled[:, PRE_BLOCKS:]).sum(axis=1)
    surplus = (exempt[:, PRE_BLOCKS:] - exempt_cf).sum(axis=1)

    out = index.reset_index()[["date"]].copy()
    out["deficit"] = deficit
    out["surplus"] = surplus
    return out.groupby("date", as_index=False)[["deficit", "surplus"]].sum()


def diversion_share(per_date: pd.DataFrame, seed: int = RANDOM_SEED) -> dict:
    """f = total surplus / total deficit, with a block bootstrap over dates."""
    deficit = float(per_date["deficit"].sum())
    surplus = float(per_date["surplus"].sum())
    if deficit <= 0:
        # No deficit means no deterred traffic to divert, and f is undefined
        # rather than zero. Say so instead of dividing.
        return {
            "f": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "deficit": deficit,
            "surplus": surplus,
            "n_dates": int(len(per_date)),
            "note": "deficit is not positive; f undefined",
        }

    rng = np.random.default_rng(seed)
    deficits = per_date["deficit"].to_numpy(dtype=float)
    surpluses = per_date["surplus"].to_numpy(dtype=float)
    draws = np.empty(BOOTSTRAP_DRAWS)
    for draw in range(BOOTSTRAP_DRAWS):
        pick = rng.integers(0, len(per_date), len(per_date))
        drawn_deficit = deficits[pick].sum()
        draws[draw] = surpluses[pick].sum() / drawn_deficit if drawn_deficit > 0 else np.nan
    low, high = np.nanpercentile(
        draws, [100 * BOOTSTRAP_ALPHA / 2, 100 * (1 - BOOTSTRAP_ALPHA / 2)]
    )
    return {
        "f": surplus / deficit,
        "ci_low": float(low),
        "ci_high": float(high),
        "deficit": deficit,
        "surplus": surplus,
        "n_dates": int(len(per_date)),
        "note": "",
    }


def responder_concentration(frame: pd.DataFrame, boundary_hour: int, method: str) -> dict:
    """Criterion 2: is the exempt surplus disproportionately cars and motorcycles?

    Reports the baseline share first and the feasibility gate with it, so a
    reader sees whether the test could have discriminated before seeing whether
    it did.
    """
    runs = frame["minute_of_day"].to_numpy() - boundary_hour * 60
    pre = frame.loc[(runs >= -PRE_BLOCKS * BLOCK_MINUTES) & (runs < 0)]
    baseline_total = float(pre["exempt"].sum())
    baseline_responder = float(pre.loc[pre["is_responder"], "exempt"].sum())
    baseline_share = baseline_responder / baseline_total if baseline_total > 0 else float("nan")

    whole = deficit_and_surplus(frame, boundary_hour, method)["surplus"].sum()
    responders = deficit_and_surplus(frame[frame["is_responder"]], boundary_hour, method)[
        "surplus"
    ].sum()
    surplus_share = float(responders / whole) if whole > 0 else float("nan")

    testable = bool(baseline_share == baseline_share and baseline_share <= FEASIBILITY_CEILING)
    ratio = surplus_share / baseline_share if baseline_share > 0 else float("nan")
    return {
        "baseline_responder_share": baseline_share,
        "surplus_responder_share": surplus_share,
        "ratio": float(ratio),
        "testable": testable,
        "feasibility_ceiling": FEASIBILITY_CEILING,
        "verdict_input": (
            "untestable"
            if not testable
            else (
                "supports"
                if ratio >= SUPPORT_RATIO
                else "refutes" if ratio <= REFUTE_RATIO else "neither"
            )
        ),
    }


def evaluate_criteria(by_counterfactual: pd.DataFrame, concentration: dict) -> dict:
    """The frozen criteria, applied mechanically so they cannot drift.

    This reports which conditions fired. It does not write the Verdict — that
    belongs to whoever runs this, in the record.
    """
    frozen = by_counterfactual.set_index("counterfactual").loc[FROZEN_COUNTERFACTUAL]
    flat = by_counterfactual.set_index("counterfactual").loc["flat"]
    values = by_counterfactual["f"].to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    spread = float(np.nanmax(np.abs(finite)) / np.nanmin(np.abs(finite))) if len(finite) else np.nan

    support_1 = bool(
        frozen["f"] >= SUPPORT_F and flat["f"] >= SUPPORT_F_FLOOR and frozen["ci_low"] > REFUTE_F
    )
    support_2 = concentration["verdict_input"] == "supports"
    refute_1 = bool(frozen["f"] < REFUTE_F)
    refute_2 = bool(np.nanmin(finite) < 0) if len(finite) else False
    refute_3 = concentration["verdict_input"] == "refutes"
    uninformative = bool(
        (REFUTE_F <= frozen["f"] < SUPPORT_F)
        or (frozen["ci_low"] < REFUTE_F <= frozen["ci_high"])
        or (spread == spread and spread > COUNTERFACTUAL_SPREAD)
    )
    return {
        "support_1_f_clears_bars": support_1,
        "support_2_responders_concentrated": support_2,
        "refute_1_f_below_floor": refute_1,
        "refute_2_f_negative_somewhere": refute_2,
        "refute_3_responders_absent": refute_3,
        "uninformative": uninformative,
        "counterfactual_spread": spread,
        "spread_threshold": COUNTERFACTUAL_SPREAD,
        "criterion_2_testable": concentration["testable"],
    }


def _plot(frame: pd.DataFrame, boundary_hour: int, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(11, 4), sharex=True)
    for axis, column in zip(axes, ("tolled", "exempt"), strict=True):
        observed, _ = _cell_matrix(frame, boundary_hour, column)
        if len(observed) == 0:
            continue
        runs = np.arange(-PRE_BLOCKS, POST_BLOCKS) * BLOCK_MINUTES
        axis.plot(runs, observed.mean(axis=0), marker="o", label="observed")
        for method in COUNTERFACTUALS:
            predicted = _counterfactual(observed, method).mean(axis=0)
            axis.plot(runs[PRE_BLOCKS:], predicted, marker="x", linestyle="--", label=method)
        axis.axvline(0, color="grey", linewidth=1)
        axis.set_title(f"{column} entries around {boundary_hour:02d}:00")
        axis.set_xlabel("minutes from boundary")
        axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-prefix", default="H010")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    frame = load_dual_by_class()
    log.info(
        "panel: %s rows, %s dates, tolled %s, exempt %s",
        f"{len(frame):,}",
        f"{frame['date'].nunique():,}",
        f"{int(frame['tolled'].sum()):,}",
        f"{int(frame['exempt'].sum()):,}",
    )

    populated = exempt_is_populated_by_class(frame)
    log.info("exempt at vehicle-class grain: %s", populated)
    pd.DataFrame([populated]).to_csv(
        TABLES_DIR / f"{args.out_prefix}_exempt_class_grain.csv", index=False
    )

    rows = []
    for boundary in (PRIMARY_BOUNDARY, MIRROR_BOUNDARY):
        for method in COUNTERFACTUALS:
            result = diversion_share(deficit_and_surplus(frame, boundary, method))
            result.update(
                {"boundary_hour": boundary, "counterfactual": method, "is_primary": boundary == 5}
            )
            rows.append(result)
    shares = pd.DataFrame(rows)
    shares.to_csv(TABLES_DIR / f"{args.out_prefix}_diversion_share.csv", index=False)

    group_rows = []
    for boundary in (PRIMARY_BOUNDARY, MIRROR_BOUNDARY):
        for group, part in frame.groupby("detection_group"):
            result = diversion_share(deficit_and_surplus(part, boundary, FROZEN_COUNTERFACTUAL))
            result.update({"boundary_hour": boundary, "detection_group": group})
            group_rows.append(result)
    pd.DataFrame(group_rows).to_csv(
        TABLES_DIR / f"{args.out_prefix}_by_detection_group.csv", index=False
    )

    year_rows = []
    for boundary in (PRIMARY_BOUNDARY, MIRROR_BOUNDARY):
        for year, part in frame.groupby("year"):
            result = diversion_share(deficit_and_surplus(part, boundary, FROZEN_COUNTERFACTUAL))
            result.update({"boundary_hour": boundary, "year": int(year)})
            year_rows.append(result)
    pd.DataFrame(year_rows).to_csv(TABLES_DIR / f"{args.out_prefix}_by_year.csv", index=False)

    class_rows = []
    for vehicle_class, part in frame.groupby("vehicle_class"):
        result = diversion_share(deficit_and_surplus(part, PRIMARY_BOUNDARY, FROZEN_COUNTERFACTUAL))
        result.update({"vehicle_class": vehicle_class, "boundary_hour": PRIMARY_BOUNDARY})
        class_rows.append(result)
    pd.DataFrame(class_rows).to_csv(
        TABLES_DIR / f"{args.out_prefix}_by_vehicle_class.csv", index=False
    )

    concentration = responder_concentration(frame, PRIMARY_BOUNDARY, FROZEN_COUNTERFACTUAL)
    log.info("criterion 2: %s", concentration)
    pd.DataFrame([concentration]).to_csv(
        TABLES_DIR / f"{args.out_prefix}_responder_concentration.csv", index=False
    )

    criteria = evaluate_criteria(shares[shares["is_primary"]], concentration)
    log.info("criteria as frozen: %s", criteria)
    pd.DataFrame([criteria]).to_csv(TABLES_DIR / f"{args.out_prefix}_criteria.csv", index=False)

    _plot(frame, PRIMARY_BOUNDARY, FIGURES_DIR / f"{args.out_prefix}_counterfactual_05.png")
    _plot(frame, MIRROR_BOUNDARY, FIGURES_DIR / f"{args.out_prefix}_counterfactual_21.png")
    log.info("wrote %s_* tables and figures", args.out_prefix)


if __name__ == "__main__":
    main()
