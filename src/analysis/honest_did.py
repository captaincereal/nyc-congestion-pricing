"""H002 — Rambachan & Roth sensitivity: how large a violation would overturn it?

The corrected joint pre-trend tests reject in every sample, and the study has
been treating that rejection as a gate. Roth (2022) is the reason not to: such
tests are often underpowered against violations big enough to matter, and
conditioning on one can leave the surviving estimate *more* biased than not
testing at all.

Rambachan & Roth (2023) replace the binary with a magnitude. Rather than
assuming parallel trends holds exactly, allow the treated group's counterfactual
to drift after treatment, bounded by what the pre-period actually shows:

    Delta^RM(Mbar): post-treatment first differences of the violation are at most
                    Mbar times the largest pre-treatment first difference

Then invert: the **breakdown value** is the smallest Mbar at which the robust
confidence set stops excluding zero. Reporting it converts "the pre-trend test
rejected" into "the conclusion survives violations up to X times what we already
observe", which is a statement a reader can weigh.

A breakdown value near zero is a real result, not a failure. It says the design
cannot distinguish the effect from plausible differential drift, quantitatively,
and without leaning on a test the literature warns against leaning on.

The smoothness family (Delta^SD, bounding second differences of the violation
path) is reported alongside as a secondary reading. It is a weaker fit here: a
cordon toll has no obvious mechanism that would make a differential trend
accelerate smoothly.

Inputs are this project's own event-study coefficients and their FULL
cluster-robust covariance -- not the diagonal standard errors. The off-diagonal
terms matter: the restriction is on differences between adjacent event-time
coefficients, whose variance depends on their covariance.

Usage:
    python -m src.analysis.honest_did
    python -m src.analysis.honest_did --sample peak --horizon 12
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from diff_diff import HonestDiD  # noqa: E402
from diff_diff.results import MultiPeriodDiDResults, PeriodEffect  # noqa: E402

from src.analysis.descriptive import GRID, INK, INK_MUTED, SERIES_COLOR, _save  # noqa: E402
from src.analysis.did import load  # noqa: E402
from src.analysis.event_study import REFERENCE_K, build_dummies, estimate  # noqa: E402
from src.config import TABLES_DIR  # noqa: E402

log = logging.getLogger(__name__)

# Reported alongside the breakdown value so the shape of the bound is visible,
# not just the threshold where it crosses zero. Mbar = 0 is the parallel-trends
# case with no assumed violation; Mbar = 1 allows post-treatment drift as large
# as the biggest first difference already seen in the pre-period.
MBAR_GRID = (0.0, 0.5, 1.0, 2.0)

SAMPLES = ("all", "peak", "offpeak", "weekend")


def _event_time(col: str) -> int:
    """`k_m3` -> -3, `k_p7` -> 7."""
    token = col.split("_")[1]
    return -int(token[1:]) if token[0] == "m" else int(token[1:])


def event_study_moments(sample: str, horizon: int) -> dict:
    """Coefficients and full cluster-robust covariance, ordered by event time."""
    df = load(sample)
    if df.empty:
        raise SystemExit(f"sample {sample!r} is empty")
    df, dummy_cols = build_dummies(df, horizon)
    res = estimate(df, dummy_cols)

    ks = [_event_time(c) for c in res["dummy_cols"]]
    order = np.argsort(ks)
    ks = [ks[i] for i in order]
    beta = np.asarray(res["beta"], dtype=float)[order]
    vcov = np.asarray(res["vcov"], dtype=float)[np.ix_(order, order)]

    # Sensitivity analysis inverts this matrix; a singular one means the bounds
    # are not identified and the honest answer is "uninformative", not a number.
    eig = float(np.linalg.eigvalsh(vcov).min())
    return {
        "sample": sample,
        "k": ks,
        "beta": beta,
        "vcov": vcov,
        "se": np.sqrt(np.diag(vcov)),
        "min_eigenvalue": eig,
        "n_obs": int(res["n_obs"]),
        "n_clusters": int(res["n_clusters"]),
        "horizon": horizon,
    }


def to_container(m: dict) -> MultiPeriodDiDResults:
    """Wrap our own estimates in the structure diff_diff's HonestDiD consumes.

    `interaction_indices` is passed explicitly so the mapping from event time to
    covariance row is unambiguous rather than inferred from list order.
    """
    ks, beta, se = m["k"], m["beta"], m["se"]
    pre = [k for k in ks if k < REFERENCE_K]
    post = [k for k in ks if k >= 0]
    idx = {k: i for i, k in enumerate(ks)}

    effects = {
        k: PeriodEffect(
            period=k,
            effect=float(beta[idx[k]]),
            se=float(se[idx[k]]),
            t_stat=float(beta[idx[k]] / se[idx[k]]) if se[idx[k]] else np.nan,
            p_value=np.nan,
            conf_int=(
                float(beta[idx[k]] - 1.96 * se[idx[k]]),
                float(beta[idx[k]] + 1.96 * se[idx[k]]),
            ),
        )
        for k in ks
    }
    post_mean = float(np.mean([beta[idx[k]] for k in post])) if post else np.nan
    return MultiPeriodDiDResults(
        period_effects=effects,
        avg_att=post_mean,
        avg_se=np.nan,
        avg_t_stat=np.nan,
        avg_p_value=np.nan,
        avg_conf_int=(np.nan, np.nan),
        n_obs=m["n_obs"],
        n_treated=0,
        n_control=0,
        pre_periods=pre,
        post_periods=post,
        vcov=m["vcov"],
        reference_period=REFERENCE_K,
        interaction_indices=idx,
        n_clusters=m["n_clusters"],
        vcov_type="cluster",
    )


def sensitivity(m: dict) -> tuple[pd.DataFrame, dict]:
    """Robust confidence sets across the Mbar grid, plus breakdown values."""
    container = to_container(m)
    rows = []
    for method in ("relative_magnitude", "smoothness"):
        for mbar in MBAR_GRID:
            try:
                r = HonestDiD(method=method, M=mbar).fit(container)
                rows.append(
                    {
                        "sample": m["sample"],
                        "method": method,
                        "M": mbar,
                        "ci_low": float(r.ci_lb),
                        "ci_high": float(r.ci_ub),
                        "excludes_zero": not (r.ci_lb <= 0 <= r.ci_ub),
                        "original_estimate": float(r.original_estimate),
                        "original_se": float(r.original_se),
                        "status": "ok",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - a failed bound is a result
                log.warning("%s %s M=%.2f failed: %s", m["sample"], method, mbar, exc)
                rows.append(
                    {
                        "sample": m["sample"],
                        "method": method,
                        "M": mbar,
                        "ci_low": np.nan,
                        "ci_high": np.nan,
                        "excludes_zero": False,
                        "original_estimate": np.nan,
                        "original_se": np.nan,
                        "status": f"failed: {type(exc).__name__}",
                    }
                )

    breakdown = {}
    for method in ("relative_magnitude", "smoothness"):
        try:
            bv = HonestDiD(method=method).breakdown_value(container)
            # None means the bound never covers zero over the searched range.
            breakdown[method] = float(bv) if bv is not None else np.inf
        except Exception as exc:  # noqa: BLE001
            log.warning("%s breakdown (%s) failed: %s", m["sample"], method, exc)
            breakdown[method] = np.nan
    return pd.DataFrame(rows), breakdown


def plot(grid: pd.DataFrame, m: dict, breakdown: dict) -> None:
    rm = grid[(grid["method"] == "relative_magnitude") & (grid["status"] == "ok")]
    if rm.empty:
        return
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.fill_between(rm["M"], rm["ci_low"], rm["ci_high"], color=GRID, zorder=2)
    ax.plot(rm["M"], rm["ci_low"], color=INK_MUTED, linewidth=1.2, zorder=3)
    ax.plot(rm["M"], rm["ci_high"], color=INK_MUTED, linewidth=1.2, zorder=3)
    ax.axhline(0, color=SERIES_COLOR["treated"], linewidth=1.6, linestyle="--", zorder=4)
    bv = breakdown.get("relative_magnitude", np.nan)
    subtitle = (
        f"breakdown M = {bv:.2f}"
        if np.isfinite(bv)
        else ("breakdown M > searched range" if bv == np.inf else "breakdown not computed")
    )
    ax.set_xlabel("M — post-treatment violation as a multiple of the largest pre-period one")
    ax.set_ylabel("robust 95% confidence set (mph)")
    ax.set_title(
        f"Honest DiD sensitivity — {m['sample']}\n{subtitle}",
        color=INK,
        loc="left",
    )
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    _save(fig, f"H002_honest_did_{m['sample']}.png")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", default="all", choices=[*SAMPLES])
    ap.add_argument("--all-samples", action="store_true")
    ap.add_argument("--horizon", type=int, default=12, help="max |weeks| from treatment")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    samples = list(SAMPLES) if args.all_samples else [args.sample]
    grids, summary = [], []
    for s in samples:
        log.info("=== %s ===", s)
        m = event_study_moments(s, args.horizon)
        log.info(
            "%s: %d event-time bins, %s link-hours, %d clusters, min eigenvalue %.3e",
            s,
            len(m["k"]),
            f"{m['n_obs']:,}",
            m["n_clusters"],
            m["min_eigenvalue"],
        )
        grid, breakdown = sensitivity(m)
        plot(grid, m, breakdown)
        grids.append(grid)

        rm0 = grid[(grid["method"] == "relative_magnitude") & (grid["M"] == 0.0)]
        summary.append(
            {
                "sample": s,
                "breakdown_relative_magnitude": breakdown.get("relative_magnitude", np.nan),
                "breakdown_smoothness": breakdown.get("smoothness", np.nan),
                "n_pre_bins": sum(1 for k in m["k"] if k < REFERENCE_K),
                "n_post_bins": sum(1 for k in m["k"] if k >= 0),
                "min_eigenvalue": m["min_eigenvalue"],
                "n_obs": m["n_obs"],
                "n_clusters": m["n_clusters"],
                "ci_low_at_M0": float(rm0["ci_low"].iloc[0]) if len(rm0) else np.nan,
                "ci_high_at_M0": float(rm0["ci_high"].iloc[0]) if len(rm0) else np.nan,
                "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )
        log.info(
            "%s: breakdown M(relative magnitude) = %s | M(smoothness) = %s",
            s,
            f"{breakdown.get('relative_magnitude', float('nan')):.3f}",
            f"{breakdown.get('smoothness', float('nan')):.3f}",
        )

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    pd.concat(grids, ignore_index=True).round(6).to_csv(
        TABLES_DIR / "H002_honest_did_grid.csv", index=False
    )
    pd.DataFrame(summary).round(6).to_csv(TABLES_DIR / "H002_honest_did.csv", index=False)
    log.info("wrote H002_honest_did.csv and H002_honest_did_grid.csv")
    log.info(
        "A low breakdown value is a finding about this design, not a causal null. "
        "It does not establish that the effect is zero."
    )


if __name__ == "__main__":
    main()
