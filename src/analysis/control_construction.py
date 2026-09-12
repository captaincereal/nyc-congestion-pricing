"""H004 — build a control set from pre-treatment behaviour, judge it out of sample.

The frozen design requires controls chosen on pre-treatment behaviour rather
than geographic convenience. The trap is that choosing controls to make a
pre-trend test pass, and then reporting that same test, is circular: Roth (2022)
shows the survivor of such a selection can be more biased than an unselected
one.

The guard is a split the matching never sees:

    matching window   event weeks -36 .. -13   features built here only
    held-out window   event weeks -12 ..  -2   the verdict is computed here

Two rules are built on the matching window and judged on the held-out one:

    A  nearest neighbour  -- the 60 donors closest to the treated group's mean
                             standardised feature vector
    B  synthetic weights  -- non-negative weights summing to one that best
                             reproduce the treated weekly trajectory
                             (Abadie, Diamond & Hainmueller 2010)

Features are trajectory shapes, never levels. Treated links sit near 7.9 mph
against a control pool near 15.6, so matching on levels is impossible and
also beside the point: difference-in-differences identifies off changes, so
each link's weekly series is demeaned by its own matching-window mean before
any distance is computed.

Everything this module reports is a pre-treatment diagnostic. It computes no
post-treatment coefficient, by design and by the registered method — see
`docs/hypotheses/H004-control-construction.md`.

Usage:
    python -m src.analysis.control_construction
    python -m src.analysis.control_construction --boundary-metres 1000
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from scipy import optimize, stats

from src.analysis.did import OUTCOME, load
from src.analysis.event_study import build_dummies, estimate
from src.config import CLUSTER_VAR, OUTPUTS_DIR, TABLES_DIR

log = logging.getLogger(__name__)

# Frozen in the hypothesis record before implementation.
MATCH_WEEKS = (-36, -13)  # inclusive
HOLDOUT_WEEKS = (-12, -2)  # inclusive
N_NEIGHBOURS = 60
MIN_DONORS = 30
WEIGHT_FLOOR = 0.001
BOUNDARY_METRES = 500.0
REJECT_AT = 0.10  # a p-value below this counts as rejecting; fixed in advance

SAMPLES = ("all", "peak", "offpeak", "weekend")


def excluded_by_boundary(metres: float = BOUNDARY_METRES) -> set[str]:
    """Control links within `metres` of the 60th Street line.

    Diversion onto a nearby street would contaminate the comparison, so these
    leave the donor pool before matching rather than being handled afterwards.
    """
    path = OUTPUTS_DIR / "tables" / "boundary_distance_audit.csv"
    if not path.exists():
        log.warning("no boundary distance audit at %s; excluding nothing", path)
        return set()
    audit = pd.read_csv(path, dtype={"sid": str})
    near = audit[
        (audit["treatment_group"] == "control")
        & (audit["nearest_boundary_line_m"].astype(float) < metres)
    ]
    return set(near["sid"].astype(str))


def link_features(df: pd.DataFrame) -> pd.DataFrame:
    """Trajectory-shape features per link, from the matching window only.

    Each block is demeaned by the link's own matching-window mean so that the
    two-fold level gap between treated and control streets cannot drive the
    distance. What is left is the shape of the series.
    """
    d = df.dropna(subset=[OUTCOME]).copy()
    d["week"] = d["event_week"].astype(int)

    weekly = d.groupby([CLUSTER_VAR, "week"])[OUTCOME].mean().unstack("week")  # noqa: PD010
    weekly = weekly.sub(weekly.mean(axis=1), axis=0)

    diffs = weekly.diff(axis=1).iloc[:, 1:]

    hourly = d.groupby([CLUSTER_VAR, "hour"])[OUTCOME].mean().unstack("hour")  # noqa: PD010
    hourly = hourly.sub(hourly.mean(axis=1), axis=0)

    wk = d.groupby([CLUSTER_VAR, "is_weekend"])[OUTCOME].mean().unstack("is_weekend")  # noqa: PD010
    if wk.shape[1] == 2:
        gap = (wk.iloc[:, 0] - wk.iloc[:, 1]).rename("weekday_weekend_gap").to_frame()
        gap = gap.sub(gap.mean())
    else:
        gap = pd.DataFrame(index=weekly.index)

    feats = pd.concat(
        [
            weekly.add_prefix("wk_"),
            diffs.add_prefix("dwk_"),
            hourly.add_prefix("hr_"),
            gap,
        ],
        axis=1,
    )
    # A link missing a whole week carries no information there; zero after
    # demeaning is "no deviation", which is the neutral value for a distance.
    return feats.fillna(0.0)


def standardise(feats: pd.DataFrame) -> pd.DataFrame:
    sd = feats.std(axis=0).replace(0.0, np.nan)
    return ((feats - feats.mean(axis=0)) / sd).fillna(0.0)


def rule_nearest(z: pd.DataFrame, treated: list[str], donors: list[str], n: int) -> list[str]:
    """The `n` donors closest to the treated group's mean feature vector."""
    target = z.loc[z.index.intersection(treated)].mean(axis=0)
    pool = z.loc[z.index.intersection(donors)]
    dist = ((pool - target) ** 2).sum(axis=1).pow(0.5).sort_values()
    return list(dist.index[:n])


def rule_synthetic(
    weekly_treated: pd.Series, weekly_donors: pd.DataFrame
) -> tuple[pd.Series, float]:
    """Non-negative weights summing to one that best track the treated trajectory.

    Solved on the simplex by SLSQP from a uniform start. The objective is the
    squared distance between the weighted donor trajectory and the treated one
    across the matching window.
    """
    X = weekly_donors.to_numpy(dtype=float)  # donors x weeks
    y = weekly_treated.to_numpy(dtype=float)

    def loss(w: np.ndarray) -> float:
        return float(np.sum((w @ X - y) ** 2))

    n = X.shape[0]
    w0 = np.full(n, 1.0 / n)
    res = optimize.minimize(
        loss,
        w0,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}],
        options={"maxiter": 500, "ftol": 1e-10},
    )
    w = np.clip(res.x, 0.0, None)
    w = w / w.sum() if w.sum() > 0 else w0
    return pd.Series(w, index=weekly_donors.index), float(res.fun)


def holdout_pretrend(sample: str, keep: set[str], horizon: int = 12) -> dict:
    """Joint pre-trend Wald test on the held-out weeks for one donor set.

    Restricted to the held-out bins only, so the matching window contributes
    nothing to the verdict it is being judged by.
    """
    df = load(sample)
    df = df[df["treated"] | df[CLUSTER_VAR].isin(keep)].copy()
    n_ctrl = int(df.loc[~df["treated"], CLUSTER_VAR].nunique())
    if n_ctrl < MIN_DONORS:
        return {"status": f"only {n_ctrl} donors", "n_control": n_ctrl}

    df, dummy_cols = build_dummies(df, horizon)
    res = estimate(df, dummy_cols)

    lo, hi = HOLDOUT_WEEKS
    idx = []
    for i, col in enumerate(res["dummy_cols"]):
        tok = col.split("_")[1]
        k = -int(tok[1:]) if tok[0] == "m" else int(tok[1:])
        if lo <= k <= hi:
            idx.append(i)
    if len(idx) < 2:
        return {"status": "too few held-out bins", "n_control": n_ctrl}

    beta = np.asarray(res["beta"], float)[idx]
    vcov = np.asarray(res["vcov"], float)[np.ix_(idx, idx)]
    try:
        stat = float(beta @ np.linalg.solve(vcov, beta))
    except np.linalg.LinAlgError:
        return {"status": "singular covariance", "n_control": n_ctrl}
    dof = len(idx)
    p = float(stats.chi2.sf(stat, dof))
    return {
        "status": "ok",
        "chi2": stat,
        "dof": dof,
        "p_value": p,
        "rejects": p < REJECT_AT,
        "n_control": n_ctrl,
        "n_treated": int(df.loc[df["treated"], CLUSTER_VAR].nunique()),
        "n_obs": int(res["n_obs"]),
        "n_clusters": int(res["n_clusters"]),
    }


def build(boundary_m: float) -> dict:
    """Fit both rules on the matching window. No held-out data is touched here."""
    df = load("all")
    lo, hi = MATCH_WEEKS
    match_df = df[(df["event_week"] >= lo) & (df["event_week"] <= hi)]
    if match_df.empty:
        raise SystemExit("matching window is empty")

    treated = sorted(match_df.loc[match_df["treated"], CLUSTER_VAR].unique())
    all_controls = sorted(match_df.loc[~match_df["treated"], CLUSTER_VAR].unique())
    dropped = excluded_by_boundary(boundary_m)
    donors = [c for c in all_controls if c not in dropped]
    log.info(
        "matching window k=%d..%d: %d treated, %d controls (%d within %.0fm of the line)",
        lo,
        hi,
        len(treated),
        len(donors),
        len(all_controls) - len(donors),
        boundary_m,
    )

    feats = link_features(match_df)
    z = standardise(feats)

    keep_a = rule_nearest(z, treated, donors, N_NEIGHBOURS)

    weekly_mean = match_df.groupby([CLUSTER_VAR, "event_week"])[OUTCOME].mean()
    weekly = weekly_mean.unstack("event_week")  # noqa: PD010
    weekly = weekly.sub(weekly.mean(axis=1), axis=0).fillna(0.0)
    t_traj = weekly.loc[weekly.index.intersection(treated)].mean(axis=0)
    d_traj = weekly.loc[weekly.index.intersection(donors)]
    w, fit_loss = rule_synthetic(t_traj, d_traj)
    keep_b = list(w[w >= WEIGHT_FLOOR].index)
    log.info(
        "rule A keeps %d donors; rule B keeps %d with weight >= %.3f (fit loss %.4f)",
        len(keep_a),
        len(keep_b),
        WEIGHT_FLOOR,
        fit_loss,
    )
    return {
        "treated": treated,
        "donors": donors,
        "dropped_boundary": sorted(dropped),
        "rule_a": keep_a,
        "rule_b": keep_b,
        "weights": w,
        "fit_loss": fit_loss,
        "naive": all_controls,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--boundary-metres", type=float, default=BOUNDARY_METRES)
    ap.add_argument("--horizon", type=int, default=12)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    built = build(args.boundary_metres)
    sets = {
        "naive": set(built["naive"]),
        "rule_a_nearest": set(built["rule_a"]),
        "rule_b_synthetic": set(built["rule_b"]),
    }

    rows = []
    for name, keep in sets.items():
        for sample in SAMPLES:
            r = holdout_pretrend(sample, keep, args.horizon)
            r.update(control_set=name, sample=sample, boundary_metres=args.boundary_metres)
            rows.append(r)
            if r["status"] == "ok":
                log.info(
                    "%-17s %-8s chi2=%7.2f dof=%2d p=%.4g -> %s",
                    name,
                    sample,
                    r["chi2"],
                    r["dof"],
                    r["p_value"],
                    "REJECTS" if r["rejects"] else "does not reject",
                )
            else:
                log.warning("%-17s %-8s %s", name, sample, r["status"])

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out["run_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    cols = [
        "control_set",
        "sample",
        "status",
        "chi2",
        "dof",
        "p_value",
        "rejects",
        "n_treated",
        "n_control",
        "n_clusters",
        "n_obs",
        "boundary_metres",
        "run_at",
    ]
    out.reindex(columns=cols).round(6).to_csv(TABLES_DIR / "H004_holdout_pretrend.csv", index=False)

    built["weights"].rename("weight").rename_axis(CLUSTER_VAR).reset_index().query(
        "weight >= @WEIGHT_FLOOR"
    ).sort_values("weight", ascending=False).round(6).to_csv(
        TABLES_DIR / "H004_synthetic_weights.csv", index=False
    )
    pd.DataFrame(
        {
            CLUSTER_VAR: sorted(set(built["rule_a"]) | set(built["rule_b"])),
        }
    ).assign(
        in_rule_a=lambda t: t[CLUSTER_VAR].isin(built["rule_a"]),
        in_rule_b=lambda t: t[CLUSTER_VAR].isin(built["rule_b"]),
    ).to_csv(TABLES_DIR / "H004_control_sets.csv", index=False)

    log.info("wrote H004_holdout_pretrend.csv, H004_synthetic_weights.csv, H004_control_sets.csv")
    log.info(
        "Held-out pre-treatment diagnostics only. No post-treatment coefficient "
        "is computed here; see the hypothesis record before going further."
    )


if __name__ == "__main__":
    main()
