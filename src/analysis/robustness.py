"""Exploratory sensitivity checks on the currently available primary panel.

These separate specifications do not choose D1/D2/D3 or alter the primary
panel. The October 2024--April 2025 contiguous window is the comparison
baseline; June is added only in the all-available sensitivity. Controls remain
unapproved candidates, source completeness is unverified, and a significant
coefficient is not a causal finding.

    python -m src.analysis.robustness
    python -m src.analysis.robustness --spec quality --skip-event-study
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from src.analysis import did, event_study
from src.config import HOURLY_PANEL_PATH, TABLES_DIR, TREATMENT_DATE

log = logging.getLogger(__name__)
BASELINE_START = pd.Timestamp("2024-10-01")
BASELINE_END = pd.Timestamp("2025-05-01")  # exclusive
TOLL_START = pd.Timestamp(TREATMENT_DATE)

SPECIFICATIONS = {
    "contiguous_baseline": "October 2024-April 2025; all candidate controls",
    "all_available": "All available months, including isolated June 2024",
    "manhattan_controls": "Manhattan candidate controls only; treated unchanged",
    "outer_borough_controls": "Outer-borough candidate controls only; treated unchanged",
    "drop_transition": "Exclude [treatment-14 days, treatment+14 days)",
    "quality": "Keep hours with at least 3 readings and every reading >=4 probes",
    "no_extreme_readings": "Keep hours with zero readings exceeding 80 mph",
    "mean_outcome": "Hourly mean speed in place of the hourly median",
    "common_link_roster": "Keep links with observations in both pre and post periods",
    "placebo_2024_11_17": "Placebo November 17; actual pretreatment observations only",
    "placebo_2024_12_01": "Placebo December 1; actual pretreatment observations only",
    "eleventh_as_treated": "D3 sensitivity: reassign 11th Avenue exempt links to treated",
}


def prepare_spec(panel: pd.DataFrame, specification: str) -> tuple[pd.DataFrame, dict]:
    """Build one sensitivity frame without mutating the panel or its assignment."""
    if specification not in SPECIFICATIONS:
        raise ValueError(f"unknown specification {specification!r}")
    d = panel.copy()
    d[did.TIME_KEY] = pd.to_datetime(d[did.TIME_KEY])
    if specification != "all_available":
        d = d[d[did.TIME_KEY].ge(BASELINE_START) & d[did.TIME_KEY].lt(BASELINE_END)].copy()

    reassigned_links = 0
    if specification == "eleventh_as_treated":
        changed = d["treatment_group"].eq("exempt_in_zone") & d["roadway"].str.match(
            r"11th\s+Ave", case=False, na=False
        )
        reassigned_links = d.loc[changed, "link_id"].nunique()
        d.loc[changed, "treatment_group"] = "treated"

    d = d[d["treatment_group"].isin(["treated", "control"])].copy()
    d["treated"] = d["treatment_group"].eq("treated")
    treatment_date = TOLL_START
    outcome = did.OUTCOME
    if specification == "manhattan_controls":
        d = d[d["treated"] | d["borough"].str.lower().eq("manhattan")].copy()
    elif specification == "outer_borough_controls":
        d = d[d["treated"] | ~d["borough"].str.lower().eq("manhattan")].copy()
    elif specification == "drop_transition":
        d = d[
            d[did.TIME_KEY].lt(TOLL_START - pd.Timedelta(days=14))
            | d[did.TIME_KEY].ge(TOLL_START + pd.Timedelta(days=14))
        ].copy()
    elif specification == "quality":
        d = d[d["n_obs"].ge(3) & d["min_n_samples"].ge(4)].copy()
    elif specification == "no_extreme_readings":
        d = d[d["n_over_80"].eq(0)].copy()
    elif specification == "mean_outcome":
        outcome = "mean_speed_mph"
        d[did.OUTCOME] = d[outcome]
    elif specification.startswith("placebo_"):
        # Never let actual treated observations contaminate a placebo.
        d = d[d[did.TIME_KEY].lt(TOLL_START)].copy()
        treatment_date = pd.Timestamp(specification.removeprefix("placebo_").replace("_", "-"))

    d["post"] = d[did.TIME_KEY].ge(treatment_date)
    d = d.dropna(subset=[did.OUTCOME]).copy()
    if specification == "common_link_roster":
        presence = d.groupby("link_id")["post"].nunique()
        d = d[d["link_id"].isin(presence[presence.eq(2)].index)].copy()
    d["treated_post"] = d["treated"] & d["post"]
    d["event_week"] = ((d[did.TIME_KEY] - treatment_date).dt.days // 7).astype(int)
    log.info(
        "%s: %s -> %s link-hours; %s",
        specification,
        f"{len(panel):,}",
        f"{len(d):,}",
        SPECIFICATIONS[specification],
    )
    metadata = {
        "specification": specification,
        "description": SPECIFICATIONS[specification],
        "interpretation": "exploratory association; unverified source; controls unapproved",
        "outcome": outcome,
        "treatment_date": str(treatment_date.date()),
        "panel_start": str(d[did.TIME_KEY].min()) if not d.empty else None,
        "panel_end": str(d[did.TIME_KEY].max()) if not d.empty else None,
        "pre_observations": int((~d["post"]).sum()),
        "post_observations": int(d["post"].sum()),
        "treated_links": int(d.loc[d["treated"], "link_id"].nunique()),
        "control_links": int(d.loc[~d["treated"], "link_id"].nunique()),
        "reassigned_links": int(reassigned_links),
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    return d, metadata


def run_specs(panel: pd.DataFrame, specifications: list[str]) -> pd.DataFrame:
    """Fit requested separate DiD specifications and return the comparison."""
    rows = []
    for name in specifications:
        d, metadata = prepare_spec(panel, name)
        if d.empty or d["treated"].nunique() < 2 or d["post"].nunique() < 2:
            rows.append({**metadata, "status": "UNTESTABLE: missing treatment/group support"})
            continue
        result = did.estimate(d)
        rows.append({**metadata, **result, "status": "estimated"})
        log.info(
            "%s: %+.4f mph [%.4f, %.4f], p=%.4g",
            name,
            result["beta_mph"],
            result["ci_low"],
            result["ci_high"],
            result["p_value"],
        )
    return pd.DataFrame(rows)


def contiguous_event_screen(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rerun the corrected joint test on the original contiguous comparison window."""
    d, metadata = prepare_spec(panel, "contiguous_baseline")
    d, cols = event_study.build_dummies(d, horizon=12)
    result = event_study.estimate(d, cols)
    coefs = event_study.coef_frame(result, cols)
    test = event_study.pretrend_test(coefs, result)
    stat, p, dof = test if test else (np.nan, np.nan, 0)
    row = {
        **metadata,
        **result["pretrend_metadata"],
        "chi2": stat,
        "p_value": p,
        "dof": dof,
        "verdict": "UNTESTABLE" if test is None else "PASS" if p > 0.05 else "FAIL",
        "horizon": 12,
        "reference_week": -1,
        "observed_pre_week_min": int(d.loc[d["treated"], "event_week"].min()),
        "pre_tail_pooled": bool((d["event_week"] < -12).any()),
        "n_obs": result["n_obs"],
        "n_clusters": result["n_clusters"],
    }
    log.info("contiguous event study: chi2=%.4f, df=%d, p=%.6g", stat, dof, p)
    return coefs, pd.DataFrame([row])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", action="append", choices=list(SPECIFICATIONS))
    ap.add_argument("--skip-event-study", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    panel = pd.read_parquet(HOURLY_PANEL_PATH)
    results = run_specs(panel, args.spec or list(SPECIFICATIONS))
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(TABLES_DIR / "robustness_comparison.csv", index=False)
    if not args.skip_event_study:
        coefs, tests = contiguous_event_screen(panel)
        coefs.to_csv(TABLES_DIR / "robustness_event_study_contiguous.csv", index=False)
        tests.to_csv(TABLES_DIR / "robustness_pretrend_contiguous.csv", index=False)


if __name__ == "__main__":
    main()
