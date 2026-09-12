"""Placebo-in-space: is the estimated effect larger than chance reassignment?

The frozen specification clusters standard errors by link, which treats the 148
tolled links as 148 independent draws. They are not. One cordon began tolling on
one date, so every treated link shares a single shock, and the effective number
of independent treated clusters is far closer to one. Cluster-robust t tests
over-reject badly in that situation (MacKinnon & Webb 2020), which is the most
likely reason the Phase 7 DiD returns p = 0.0004 on a 7-month window.

This module answers the question the analytic standard error cannot: how often
does a randomly chosen set of CONTROL links, switched on at the real tolling
date, produce an estimate as large as the one the real treated set produces?

    beta_placebo(b) = DiD estimated on control links only, with k of them
                      labelled "treated" at random, k chosen to preserve the
                      real treated share (see `placebo_k`)

The reference distribution of those placebo estimates is the null. It inherits
the panel's serial correlation, its spatial correlation, and the single-common-
shock structure, because each draw reassigns a whole SET of links at one date
rather than shuffling rows. That is what makes it a fair yardstick and the
analytic SE not one.

Two p-values are reported. The coefficient-based one compares |beta| directly.
The t-based one compares |beta/se|, and is the more reliable of the two when the
treated group is atypical of the pool -- which here it is, since treated links
sit near 7.9 mph against a control pool near 15.6 (MacKinnon & Webb 2020,
section on randomization inference with few treated clusters).

Reading the result: `se_ratio` is the placebo distribution's spread divided by
the analytic clustered standard error. A ratio well above one is a direct
measurement of how much the frozen specification's inference overstates its own
precision.

This does not test parallel trends and does not repair a rejected pre-period.
It bounds how impressed anyone should be by the magnitude.

Usage:
    python -m src.analysis.placebo_space
    python -m src.analysis.placebo_space --sample peak --draws 2000
"""

from __future__ import annotations

import argparse
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.descriptive import GRID, INK, INK_MUTED, SERIES_COLOR, _save  # noqa: E402
from src.analysis.did import OUTCOME, TIME_KEY, _absorb, estimate, load  # noqa: E402
from src.config import CLUSTER_VAR, RANDOM_SEED, TABLES_DIR  # noqa: E402

log = logging.getLogger(__name__)

# Placebo D columns absorbed per call. The alternating projection is the
# expensive part and it converges on every column at once, so batching amortises
# it across draws. Bounded because each column holds one float per row.
BATCH = 20


def _cluster_se(x: np.ndarray, y: np.ndarray, codes: np.ndarray, n_clusters: int) -> tuple:
    """Beta and its cluster-robust SE for an already-residualised regressor.

    Mirrors did.estimate's algebra on pre-absorbed columns. The finite-sample
    correction is deliberately omitted: it is a constant across draws and the
    real estimate's t is recomputed the same way for comparability.
    """
    xtx = float(x @ x)
    if xtx <= 0:
        return np.nan, np.nan
    beta = float(x @ y) / xtx
    e = y - beta * x
    scores = np.bincount(codes, x * e, minlength=n_clusters)
    se = float(np.sqrt(float(scores @ scores) / xtx**2))
    return beta, se


def placebo_k(n_treated: int, n_control: int) -> int:
    """How many control links to label placebo-treated in each draw.

    Not `n_treated`. The real design is 148 treated against 177 controls, so
    drawing 148 from the 177-link control pool would leave 29 links as the
    placebo comparison group and make every draw nearly the same set. The draws
    would be neither independent of one another nor shaped like the estimate
    they are meant to benchmark.

    Preserving the real treated SHARE instead splits the control pool in the
    same proportion, keeping each placebo DiD's design balance comparable to the
    real one. Both placebo groups are necessarily smaller than their real
    counterparts, so placebo estimates are noisier than the real estimator and
    the resulting null is a little too wide. That makes the test conservative:
    it under-rejects rather than over-rejects.

    Clamped so each side keeps at least one link; below that the DiD has no
    within-variation to estimate from. A pool that small cannot support a
    meaningful placebo test anyway, and `placebo_draws` rejects it.
    """
    share = n_treated / (n_treated + n_control)
    k = round(share * n_control)
    return int(min(max(k, 1), n_control - 1))


def placebo_draws(df: pd.DataFrame, k: int, draws: int, rng: np.random.Generator) -> tuple:
    """Reference distribution of DiD estimates under random reassignment.

    `df` must contain control links ONLY. Including the real treated links would
    leak the effect being tested into its own null distribution.
    """
    d = df.dropna(subset=[OUTCOME]).copy()
    links = d[CLUSTER_VAR].to_numpy()
    pool = np.unique(links)
    if len(pool) <= k:
        raise SystemExit(f"control pool has {len(pool)} links, cannot draw {k} placebo-treated")
    post = d["post"].to_numpy(dtype=float)

    # Absorb the outcome once. The panel does not change between draws, so only
    # the treatment column has to be re-absorbed.
    y_res, n_unit, n_time = _absorb(d, [OUTCOME], CLUSTER_VAR, TIME_KEY)
    y = y_res[:, 0]
    codes = pd.factorize(d[CLUSTER_VAR])[0]
    n_clusters = int(codes.max() + 1)
    log.info(
        "placebo pool: %s control links, %s link-hours; each draw labels %d treated vs %d control",
        f"{len(pool):,}",
        f"{len(d):,}",
        k,
        len(pool) - k,
    )

    betas, ts = [], []
    for start in range(0, draws, BATCH):
        size = min(BATCH, draws - start)
        cols = []
        for b in range(size):
            chosen = rng.choice(pool, size=k, replace=False)
            treated_i = np.isin(links, chosen).astype(float)
            name = f"_D{b}"
            d[name] = treated_i * post
            cols.append(name)
        resid, _, _ = _absorb(d, cols, CLUSTER_VAR, TIME_KEY)
        for j in range(size):
            beta, se = _cluster_se(resid[:, j], y, codes, n_clusters)
            betas.append(beta)
            ts.append(beta / se if se and np.isfinite(se) and se > 0 else np.nan)
        d = d.drop(columns=cols)
        log.info("  %d / %d draws", min(start + size, draws), draws)

    return np.array(betas, dtype=float), np.array(ts, dtype=float), n_unit, n_time


def _p(null: np.ndarray, observed: float) -> float:
    """Two-sided randomisation p-value.

    The (1 + hits) / (1 + draws) form keeps the test valid in finite samples:
    the observed assignment is itself one of the equally likely assignments
    under the null, so it belongs in the count.
    """
    null = null[np.isfinite(null)]
    if not len(null) or not np.isfinite(observed):
        return np.nan
    return float((1 + np.sum(np.abs(null) >= abs(observed))) / (1 + len(null)))


def run(sample: str, draws: int) -> dict:
    df = load(sample)
    if df.empty:
        raise SystemExit(f"sample {sample!r} is empty")

    real = estimate(df)
    treated_links = df.loc[df["treated"], CLUSTER_VAR].nunique()
    controls = df[~df["treated"]]

    n_control = controls[CLUSTER_VAR].nunique()
    k = placebo_k(treated_links, n_control)
    rng = np.random.default_rng(RANDOM_SEED)
    betas, ts, _, _ = placebo_draws(controls, k, draws, rng)

    # The real t is recomputed without the finite-sample correction so it is
    # measured on the same scale as the placebo t statistics.
    d = df.dropna(subset=[OUTCOME]).copy()
    d["D"] = (d["treated"] & d["post"]).astype(float)
    resid, _, _ = _absorb(d, [OUTCOME, "D"], CLUSTER_VAR, TIME_KEY)
    codes = pd.factorize(d[CLUSTER_VAR])[0]
    real_beta, real_se = _cluster_se(resid[:, 1], resid[:, 0], codes, int(codes.max() + 1))
    real_t = real_beta / real_se if real_se else np.nan

    finite = betas[np.isfinite(betas)]
    return {
        "sample": sample,
        "beta_mph": real["beta_mph"],
        "analytic_se": real["se_mph"],
        "analytic_p": real["p_value"],
        "placebo_draws": int(len(finite)),
        "placebo_sd": float(np.std(finite, ddof=1)) if len(finite) > 1 else np.nan,
        "placebo_mean": float(np.mean(finite)) if len(finite) else np.nan,
        "placebo_q025": float(np.quantile(finite, 0.025)) if len(finite) else np.nan,
        "placebo_q975": float(np.quantile(finite, 0.975)) if len(finite) else np.nan,
        # How far the analytic SE is from the spread chance reassignment produces.
        "se_ratio": (
            float(np.std(finite, ddof=1)) / real["se_mph"]
            if len(finite) > 1 and real["se_mph"]
            else np.nan
        ),
        "p_randomisation_beta": _p(betas, real_beta),
        "p_randomisation_t": _p(ts, real_t),
        "n_treated_links": int(treated_links),
        "n_control_links": int(n_control),
        "placebo_k": int(k),
        "_betas": betas,
        "_real_beta": real_beta,
    }


def plot(res: dict) -> None:
    betas = res["_betas"][np.isfinite(res["_betas"])]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(betas, bins=40, color=GRID, edgecolor=INK_MUTED, linewidth=0.6, zorder=2)
    ax.axvline(
        res["_real_beta"],
        color=SERIES_COLOR["treated"],
        linewidth=2.4,
        zorder=4,
        label=f"actual CRZ links ({res['_real_beta']:+.2f} mph)",
    )
    ax.axvline(0, color=INK_MUTED, linewidth=1, linestyle=":", zorder=3)
    ax.set_xlabel("DiD estimate (mph)")
    ax.set_ylabel(f"placebo draws (n={len(betas)})")
    ax.set_title(
        f"Placebo-in-space — {res['sample']}\n"
        f"random sets of {res['placebo_k']} control links, "
        f"tolling date unchanged  ·  p = {res['p_randomisation_t']:.3f}",
        color=INK,
        loc="left",
    )
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    _save(fig, f"placebo_space_{res['sample']}.png")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", default="all", choices=["all", "peak", "offpeak", "weekend"])
    ap.add_argument("--draws", type=int, default=500, help="placebo reassignments per sample")
    ap.add_argument("--all-samples", action="store_true", help="run every sample")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    samples = ["all", "peak", "offpeak", "weekend"] if args.all_samples else [args.sample]
    rows = []
    for s in samples:
        log.info("=== %s ===", s)
        res = run(s, args.draws)
        plot(res)
        log.info(
            "%s: beta %+.3f mph | analytic SE %.3f (p=%.4g) | placebo SD %.3f "
            "(%.1fx) | randomisation p: beta %.3f, t %.3f",
            s,
            res["beta_mph"],
            res["analytic_se"],
            res["analytic_p"],
            res["placebo_sd"],
            res["se_ratio"],
            res["p_randomisation_beta"],
            res["p_randomisation_t"],
        )
        rows.append({k: v for k, v in res.items() if not k.startswith("_")})

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLES_DIR / "placebo_space.csv"
    df = pd.DataFrame(rows)
    if out.exists():
        prior = pd.read_csv(out)
        prior = prior[~prior["sample"].isin(df["sample"])]
        df = pd.concat([prior, df], ignore_index=True)
    df.sort_values("sample").round(6).to_csv(out, index=False)
    log.info("wrote %s", out)
    log.info(
        "This bounds how surprising the magnitude is. It does not test parallel "
        "trends and does not repair the rejected pre-period leads."
    )


if __name__ == "__main__":
    main()
