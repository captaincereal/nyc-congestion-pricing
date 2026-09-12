"""Phase 8 — event-study estimation of dynamic congestion-pricing effects.

    median_speed_mph_{i,t} = alpha_i + gamma_t
        + sum_{k != -1} theta_k * treated_i * 1[event_week_{i,t} = k] + eps_{i,t}

  - event_week (weeks relative to 2025-01-05) is already on the panel
    (sql/03_hourly_panel.sql), clipped here to +/- --horizon weeks.
  - reference period k = -1 (the week immediately before tolling), omitted.
  - CONTROL links are folded to k = -1 for every week, not given their own
    leads/lags. Tolling has one start date for everyone (it is not staggered),
    so a bare 1[event_week=k] dummy would be identical for treated and control
    links in the same week and collinear with the time fixed effects gamma_t.
    Interacting with `treated` is what makes theta_k the treated-vs-control gap
    at k, i.e. an event-time-disaggregated version of did.py's beta. Control
    links still matter here: they anchor alpha_i / gamma_t.
  - Flat, near-zero pre-period thetas (k < -1) support parallel trends; the
    post-period path (k >= 0) traces the dynamic adjustment. This is the
    formal version of the pre-trend picture in descriptive.py's gap figure.

Two-way fixed effects are absorbed exactly as in src.analysis.did (alternating
within-transformation / Frisch-Waugh-Lovell over unit and time), reused from
there rather than reimplemented. What's new here is solving a small (K
dummies) multivariate OLS on the residualized columns and a multivariate
cluster-robust covariance matrix, instead of did.py's single-beta case. No new
dependency (e.g. linearmodels) - same house style as Phase 7.

Usage:
    python -m src.analysis.event_study
    python -m src.analysis.event_study --sample weekend --horizon 8
    python -m src.analysis.event_study --weather   # treated x weather controls, Phase 9 robustness
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
from scipy import stats  # noqa: E402

from src.analysis.descriptive import (  # noqa: E402
    GRID,
    INK,
    INK_MUTED,
    SERIES_COLOR,
    SURFACE,
    _save,
)
from src.analysis.did import OUTCOME, TIME_KEY, _absorb, attach_weather, load  # noqa: E402
from src.config import CLUSTER_VAR, TABLES_DIR, TREATMENT_DATE  # noqa: E402

log = logging.getLogger(__name__)

REFERENCE_K = -1
PRETREND_METHOD = "cluster_robust_wald_chi2"


def build_dummies(df: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, list[str]]:
    """Add one dummy column per non-reference week, treated-interacted."""
    if horizon < 2:
        raise ValueError("horizon must be at least 2 to preserve the single-week reference k=-1")
    d = df.copy()
    reference = d["treated"] & d["event_week"].eq(REFERENCE_K) & d[OUTCOME].notna()
    if not reference.any():
        raise ValueError("no treated observations with an outcome in reference week k=-1")
    k = d["event_week"].clip(-horizon, horizon)
    k = np.where(d["treated"].to_numpy(dtype=bool), k, REFERENCE_K)
    d["k"] = k.astype(int)
    d.attrs["event_horizon"] = horizon

    ks = sorted(x for x in d["k"].unique() if x != REFERENCE_K)
    names = []
    for kk in ks:
        col = f"k_{'m' if kk < 0 else 'p'}{abs(kk)}"
        d[col] = (d["k"] == kk).astype(float)
        names.append(col)
    if not names:
        raise SystemExit("no non-reference event weeks in this sample/horizon")
    return d, names


def estimate(df: pd.DataFrame, dummy_cols: list[str], controls: list[str] | None = None) -> dict:
    """Two-way FE event study; cluster-robust inference on G-1 dof.

    Generalizes did.estimate() from one treatment dummy (D) to K event-time
    dummies: absorb unit/time effects on all of them at once, partial out any
    extra controls (weather interactions), then solve the small K x K OLS and
    its cluster-robust sandwich covariance directly.
    """
    controls = controls or []
    d = df.dropna(subset=[OUTCOME]).copy()

    resid, n_unit, n_time = _absorb(d, [OUTCOME, *dummy_cols, *controls], CLUSTER_VAR, TIME_KEY)
    y = resid[:, 0]
    X = resid[:, 1 : 1 + len(dummy_cols)]

    if controls:
        Z = resid[:, 1 + len(dummy_cols) :]
        # Project only the columns needed. Constructing Z (Z'Z)^-1 Z' would
        # allocate an N x N matrix (terabytes on the real hourly panel).
        ztz = Z.T @ Z
        y = y - Z @ np.linalg.solve(ztz, Z.T @ y)
        X = X - Z @ np.linalg.solve(ztz, Z.T @ X)

    xtx = X.T @ X
    beta = np.linalg.solve(xtx, X.T @ y)
    e = y - X @ beta

    codes = pd.factorize(d[CLUSTER_VAR])[0]
    n_clusters = codes.max() + 1
    k_dim = X.shape[1]
    scores = np.zeros((n_clusters, k_dim))
    for j in range(k_dim):
        scores[:, j] = np.bincount(codes, X[:, j] * e, minlength=n_clusters)
    meat = scores.T @ scores

    xtx_inv = np.linalg.inv(xtx)
    n = len(y)
    k_params = k_dim + len(controls) + n_unit + n_time
    dof_c = (n_clusters / (n_clusters - 1)) * ((n - 1) / max(n - k_params, 1))
    vcov = dof_c * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.diag(vcov))

    dof = n_clusters - 1
    crit = float(stats.t.ppf(0.975, dof))
    p = 2 * stats.t.sf(np.abs(beta / se), dof)

    return {
        "beta": beta,
        "se": se,
        "p": p,
        "crit": crit,
        "n_obs": n,
        "n_links": int(n_unit),
        "n_periods": int(n_time),
        "n_clusters": int(n_clusters),
        "vcov": vcov,
        "dummy_cols": list(dummy_cols),
        "horizon": df.attrs.get("event_horizon"),
        "event_bins": (
            d.loc[d["treated"]]
            .groupby("k")["event_week"]
            .agg(["min", "max", "nunique"])
            .to_dict(orient="index")
        ),
    }


def coef_frame(result: dict, dummy_cols: list[str]) -> pd.DataFrame:
    rows = [
        {"k": REFERENCE_K, "coef": 0.0, "se": 0.0, "p_value": np.nan, "ci_low": 0.0, "ci_high": 0.0}
    ]
    crit = result["crit"]
    for col, b, s, p in zip(dummy_cols, result["beta"], result["se"], result["p"], strict=True):
        sign, mag = col.split("_")[1][0], int(col.split("_")[1][1:])
        kk = -mag if sign == "m" else mag
        rows.append(
            {
                "k": kk,
                "coef": b,
                "se": s,
                "p_value": p,
                "ci_low": b - crit * s,
                "ci_high": b + crit * s,
            }
        )
    frame = pd.DataFrame(rows).sort_values("k").reset_index(drop=True)
    bins = result.get("event_bins", {})
    frame["observed_week_min"] = [bins.get(k, {}).get("min", k) for k in frame["k"]]
    frame["observed_week_max"] = [bins.get(k, {}).get("max", k) for k in frame["k"]]
    frame["observed_week_count"] = [bins.get(k, {}).get("nunique", 1) for k in frame["k"]]
    frame["pooled_tail"] = (frame["observed_week_min"] != frame["k"]) | (
        frame["observed_week_max"] != frame["k"]
    )
    return frame


def pretrend_test(coefs: pd.DataFrame, result: dict) -> tuple[float, float, int] | None:
    """Joint zero-lead Wald test using the full link-cluster covariance.

    Shared reference periods make lead estimates correlated; summing their
    squared individual t statistics does not have a chi-square null law.
    Singular covariance cannot test all requested leads and is recorded as
    untestable, never as a pass with a silently reduced hypothesis.
    """
    pre = coefs[coefs["k"] < REFERENCE_K]
    lead_names = [f"k_m{abs(int(k))}" for k in pre["k"]]
    info = {
        "test_method": PRETREND_METHOD,
        "lead_count": len(lead_names),
        "covariance_rank": 0,
        "test_status": "UNTESTABLE",
        "test_reason": "no pre-reference event bins",
    }
    result["pretrend_metadata"] = info
    if not lead_names:
        return None
    positions = [result["dummy_cols"].index(name) for name in lead_names]
    beta = np.asarray(result["beta"])[positions]
    covariance = np.asarray(result["vcov"])[np.ix_(positions, positions)]
    covariance = (covariance + covariance.T) / 2
    if not np.isfinite(beta).all() or not np.isfinite(covariance).all():
        info["test_reason"] = "nonfinite lead estimates or covariance"
        return None
    rank = int(np.linalg.matrix_rank(covariance))
    info["covariance_rank"] = rank
    if rank != len(lead_names) or np.linalg.eigvalsh(covariance).min() <= 0:
        info["test_reason"] = "lead covariance is singular or not positive definite"
        return None
    stat = float(beta @ np.linalg.solve(covariance, beta))
    dof = len(lead_names)
    p = float(stats.chi2.sf(stat, dof))
    info.update(test_status="VALID", test_reason="")
    return stat, p, dof


def record_pretrend(
    sample: str,
    pt: tuple[float, float, int] | None,
    df: pd.DataFrame,
    result: dict,
) -> None:
    """Append this run's pre-trend verdict to ``outputs/tables/pretrend_tests.csv``.

    The pre-trend test is what gates the study: until it clears on a real
    pre-period, nothing here is quotable. Logging it is not enough when the
    pipeline runs unattended, so each run upserts a row keyed on the sample.
    One file answers "can we quote a number yet, and on how much data".
    """
    stat, p, dof = pt if pt is not None else (np.nan, np.nan, 0)
    dates = pd.to_datetime(df[TIME_KEY] if TIME_KEY in df else df["date"])
    observed = df[df[OUTCOME].notna() & df["treated"]]
    pre = observed[observed["event_week"] < REFERENCE_K]
    pre_dates = pd.to_datetime(pre[TIME_KEY] if TIME_KEY in pre else pre["date"])
    horizon = result.get("horizon")
    pre_tail = pre[pre["event_week"] <= -horizon] if horizon else pre.iloc[:0]
    row = {
        "sample": sample,
        "chi2": stat,
        "dof": dof,
        "p_value": p,
        "verdict": "UNTESTABLE" if pt is None else "PASS" if p > 0.05 else "FAIL",
        "pre_weeks": int(pre["event_week"].nunique()) if not pre.empty else 0,
        "reference_week": REFERENCE_K,
        "horizon": horizon,
        "tested_bin_min": int(pre["k"].min()) if not pre.empty else None,
        "tested_bin_max": int(pre["k"].max()) if not pre.empty else None,
        "observed_pre_week_min": int(pre["event_week"].min()) if not pre.empty else None,
        "observed_pre_week_max": int(pre["event_week"].max()) if not pre.empty else None,
        "tested_pre_start": str(pre_dates.min().date()) if not pre.empty else None,
        "tested_pre_end": str(pre_dates.max().date()) if not pre.empty else None,
        "pre_tail_pooled": bool(horizon and (pre["event_week"] < -horizon).any()),
        "pre_tail_observed_weeks": int(pre_tail["event_week"].nunique()),
        "post_tail_pooled": bool(horizon and (observed["event_week"] > horizon).any()),
        **result.get("pretrend_metadata", {}),
        "panel_start": str(dates.min().date()),
        "panel_end": str(dates.max().date()),
        "n_obs": int(result["n_obs"]),
        "n_clusters": int(result["n_clusters"]),
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / "pretrend_tests.csv"
    if path.exists():
        prior = pd.read_csv(path)
        prior = prior[prior["sample"] != sample]
        out = pd.concat([prior, pd.DataFrame([row])], ignore_index=True)
    else:
        out = pd.DataFrame([row])
    out.sort_values("sample").to_csv(path, index=False)
    log.info("recorded pre-trend verdict for %s in %s", sample, path)


def plot(coefs: pd.DataFrame, sample: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.axhline(0, color=GRID, linewidth=1, zorder=1)
    ax.errorbar(
        coefs["k"],
        coefs["coef"],
        yerr=[coefs["coef"] - coefs["ci_low"], coefs["ci_high"] - coefs["coef"]],
        fmt="o-",
        color=SERIES_COLOR["treated"],
        linewidth=2,
        markersize=4.5,
        capsize=3,
        ecolor=INK_MUTED,
        elinewidth=1,
        zorder=3,
    )
    ax.axvline(-0.5, color=INK, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)
    ax.annotate(
        "tolling begins",
        xy=(-0.5, ax.get_ylim()[1]),
        xytext=(6, -4),
        textcoords="offset points",
        color=INK,
        fontsize=8.5,
        va="top",
    )
    ax.set_facecolor(SURFACE)
    fig.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.set_xlabel("weeks relative to 2025-01-05", color=INK_MUTED, fontsize=10)
    ax.set_ylabel("treated - control gap (mph), rel. to week -1", color=INK_MUTED, fontsize=10)
    ax.set_title(
        f"Event study: {sample}", color=INK, fontsize=13, fontweight="bold", loc="left", pad=24
    )
    ax.text(
        0,
        1.02,
        "95% CI, clustered by link. Endpoint bins pool earlier/later weeks when present.",
        transform=ax.transAxes,
        color=INK_MUTED,
        fontsize=9.5,
        va="bottom",
    )
    _save(fig, f"event_study_{sample}.png")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--sample", default="all", choices=["all", "peak", "offpeak", "weekend"])
    ap.add_argument(
        "--horizon",
        type=int,
        default=12,
        help="endpoint bins (>=2); earlier/later weeks are pooled, not dropped",
    )
    ap.add_argument(
        "--weather", action="store_true", help="add treated x weather controls (Phase 9)"
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    df = load(args.sample)
    if df.empty:
        raise SystemExit(f"sample {args.sample!r} is empty")
    controls: list[str] = []
    if args.weather:
        df, controls = attach_weather(df)

    df, dummy_cols = build_dummies(df, args.horizon)
    log.info(
        "sample %s: %s link-hours, %d event-week dummies, horizon +/-%d weeks%s",
        args.sample,
        f"{len(df):,}",
        len(dummy_cols),
        args.horizon,
        ", weather-controlled" if controls else "",
    )

    result = estimate(df, dummy_cols, controls)
    coefs = coef_frame(result, dummy_cols)

    pt = pretrend_test(coefs, result)
    if pt:
        stat, p, dof = pt
        verdict = (
            "PASS (fail to reject flat pre-trend)" if p > 0.05 else "FAIL (pre-trend not flat)"
        )
        log.info(
            "pre-trend joint test (full cluster covariance): chi2=%.2f, dof=%d, p=%.4f -> %s",
            stat,
            dof,
            p,
            verdict,
        )
    else:
        log.warning("pre-trend UNTESTABLE: %s", result["pretrend_metadata"]["test_reason"])

    tag = f"{args.sample}{'_weather' if controls else ''}"
    record_pretrend(tag, pt, df, result)
    out_csv = TABLES_DIR / f"event_study_{tag}.csv"
    coefs.to_csv(out_csv, index=False)
    plot(coefs, tag)
    log.info("wrote %s and outputs/figures/event_study_%s.png", out_csv, tag)
    log.info(
        "Treatment date %s. %s clusters, %s link-hours. See docs/decision_register.md "
        "before quoting - pre-period length and D2 (control selection) both bear on this.",
        TREATMENT_DATE,
        result["n_clusters"],
        f"{result['n_obs']:,}",
    )


if __name__ == "__main__":
    main()
