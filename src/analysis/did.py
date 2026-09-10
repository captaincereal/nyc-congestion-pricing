"""Phase 7 — the difference-in-differences estimate.

Frozen specification:

    speed_{i,t} = alpha_i + gamma_t + beta * (treated_i x post_t) + eps_{i,t}

  alpha_i  link fixed effects        (absorbs every fixed difference between
                                      streets - a slow street stays slow)
  gamma_t  time fixed effects        (absorbs anything hitting the whole city in
                                      a given hour - weather, holidays, season)
  beta     the estimate: how much MORE the tolled streets changed than the
           comparison streets. This is the ATT, in mph.

Standard errors are clustered by link, because readings from the same street are
not independent of one another.

Both fixed effects are absorbed by alternating within-transformation (the
Frisch-Waugh-Lovell result) rather than by building thousands of dummy columns.
The panel is unbalanced, so a single demeaning pass is not exact; the transform
iterates to convergence.

Usage:
    python -m src.analysis.did
    python -m src.analysis.did --sample peak
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from src.config import CLUSTER_VAR, HOURLY_PANEL_PATH, RAW_DIR, TABLES_DIR, TREATMENT_DATE

log = logging.getLogger(__name__)

TIME_KEY = "ts_hour"
OUTCOME = "median_speed_mph"


def _absorb(df: pd.DataFrame, cols: list[str], unit: str, time: str, tol=1e-10, max_iter=200):
    """Absorb two-way fixed effects by alternating projections.

    For an unbalanced panel, subtracting unit means and time means once does not
    remove both effects - each subtraction reintroduces a little of the other.
    Alternating until the change falls below `tol` converges to the same
    residuals a full dummy regression would give.
    """
    out = df[cols].to_numpy(dtype=float, copy=True)
    unit_codes = pd.factorize(df[unit])[0]
    time_codes = pd.factorize(df[time])[0]
    n_unit, n_time = unit_codes.max() + 1, time_codes.max() + 1
    unit_n = np.bincount(unit_codes, minlength=n_unit)
    time_n = np.bincount(time_codes, minlength=n_time)

    for it in range(max_iter):
        prev = out.copy()
        for j in range(out.shape[1]):
            out[:, j] -= (np.bincount(unit_codes, out[:, j], n_unit) / unit_n)[unit_codes]
            out[:, j] -= (np.bincount(time_codes, out[:, j], n_time) / time_n)[time_codes]
        delta = np.max(np.abs(out - prev))
        if delta < tol:
            log.info("fixed effects absorbed in %d iterations (delta %.2e)", it + 1, delta)
            break
    else:
        log.warning("absorption hit max_iter without converging (delta %.2e)", delta)
    return out, n_unit, n_time


def estimate(df: pd.DataFrame, controls: list[str] | None = None) -> dict:
    """Two-way FE DiD with errors clustered on the link.

    `controls` adds extra regressors alongside the treatment indicator. Time
    fixed effects already absorb anything hitting the whole city in an hour, so
    the only weather that can bias beta is weather affecting treated and control
    streets DIFFERENTLY - hence the controls passed here are interactions with
    `treated`, not weather levels.
    """
    controls = controls or []
    d = df.dropna(subset=[OUTCOME]).copy()
    d["D"] = (d["treated"] & d["post"]).astype(float)

    resid, n_unit, n_time = _absorb(d, [OUTCOME, "D", *controls], CLUSTER_VAR, TIME_KEY)
    y = resid[:, 0]
    X = resid[:, 1:]  # column 0 is D, the rest are controls

    if controls:
        # Partial the controls out of both y and D, then the simple ratio below
        # recovers the same beta a joint regression would give (Frisch-Waugh).
        Z = X[:, 1:]
        ztz = Z.T @ Z
        y = y - Z @ np.linalg.solve(ztz, Z.T @ y)
        x = X[:, 0] - Z @ np.linalg.solve(ztz, Z.T @ X[:, 0])
    else:
        x = X[:, 0]

    xtx = float(x @ x)
    if xtx <= 0:
        raise SystemExit("no within-variation in the treatment indicator")
    beta = float(x @ y) / xtx
    e = y - beta * x

    # Cluster-robust variance: sum over links of (sum_i x_i e_i)^2 / (x'x)^2
    codes = pd.factorize(d[CLUSTER_VAR])[0]
    n_clusters = codes.max() + 1
    scores = np.bincount(codes, x * e, minlength=n_clusters)
    meat = float(scores @ scores)
    n, k = len(y), 1 + n_unit + n_time  # absorbed params count against dof
    dof_c = (n_clusters / (n_clusters - 1)) * ((n - 1) / max(n - k, 1))
    se = float(np.sqrt(dof_c * meat / xtx**2))

    t = beta / se
    # Cluster-robust inference uses G-1 degrees of freedom.
    from scipy import stats

    dof = n_clusters - 1
    p = float(2 * stats.t.sf(abs(t), dof))
    crit = float(stats.t.ppf(0.975, dof))

    base = float(d.loc[d["treated"] & ~d["post"], OUTCOME].mean())
    return {
        "beta_mph": beta,
        "se_mph": se,
        "t": t,
        "p_value": p,
        "ci_low": beta - crit * se,
        "ci_high": beta + crit * se,
        "pct_of_pre_treated_mean": 100 * beta / base if base else np.nan,
        "pre_treated_mean_mph": base,
        "n_obs": n,
        "n_links": int(n_unit),
        "n_periods": int(n_time),
        "n_clusters": int(n_clusters),
    }


WEATHER_FLAGS = ["is_wet", "is_snowing", "is_freezing"]


def attach_weather(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Join hourly weather and build treated x weather interactions.

    Returns the frame plus the control column names. Levels are not used: time
    fixed effects already absorb weather common to the whole city, so only the
    DIFFERENTIAL effect on treated streets can bias the estimate.
    """
    path = RAW_DIR / "weather_hourly.parquet"
    if not path.exists():
        log.warning("no weather file at %s - run src.data.download_weather", path)
        return df, []
    w = pd.read_parquet(path)[["ts_hour", *WEATHER_FLAGS]]
    w["ts_hour"] = pd.to_datetime(w["ts_hour"])
    out = df.merge(w, on="ts_hour", how="left", validate="many_to_one")
    missing = out[WEATHER_FLAGS].isna().any(axis=1).mean()
    if missing:
        log.warning("%.2f%% of link-hours have no weather match", 100 * missing)
    cols = []
    for f in WEATHER_FLAGS:
        c = f"treated_x_{f}"
        out[c] = (out["treated"] & out[f].fillna(False)).astype(float)
        cols.append(c)
    return out, cols


def load(sample: str) -> pd.DataFrame:
    df = pd.read_parquet(HOURLY_PANEL_PATH)
    # Treated vs control only. Boundary, exempt and crossings are modelled
    # separately - boundary because diversion there violates the no-spillover
    # assumption, exempt and crossings because they are different behaviours.
    df = df[df["treatment_group"].isin(["treated", "control"])].copy()
    df[TIME_KEY] = pd.to_datetime(df[TIME_KEY])
    if sample == "peak":
        df = df[df["is_peak"] & ~df["is_weekend"]]
    elif sample == "offpeak":
        df = df[~df["is_peak"] & ~df["is_weekend"]]
    elif sample == "weekend":
        df = df[df["is_weekend"]]
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", default="all", choices=["all", "peak", "offpeak", "weekend"])
    ap.add_argument(
        "--weather",
        action="store_true",
        help="add treated x weather interactions as a robustness check",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = []
    samples = ["all", "peak", "offpeak", "weekend"] if args.sample == "all" else [args.sample]
    for s in samples:
        df = load(s)
        if df.empty:
            log.warning("sample %s is empty - skipping", s)
            continue
        controls: list[str] = []
        if args.weather:
            df, controls = attach_weather(df)
        log.info(
            "--- sample: %s (%s link-hours%s) ---",
            s, f"{len(df):,}", ", weather-controlled" if controls else "",
        )
        r = estimate(df, controls)
        r["weather_controls"] = bool(controls)
        r["sample"] = s
        rows.append(r)
        log.info(
            "  ATT %+.4f mph  (SE %.4f, t %+.2f, p %.4g)  95%% CI [%+.4f, %+.4f]  = %+.2f%%",
            r["beta_mph"], r["se_mph"], r["t"], r["p_value"],
            r["ci_low"], r["ci_high"], r["pct_of_pre_treated_mean"],
        )

    out = pd.DataFrame(rows)
    cols = ["sample", "weather_controls", "beta_mph", "se_mph", "t", "p_value",
            "ci_low", "ci_high", "pct_of_pre_treated_mean", "pre_treated_mean_mph",
            "n_obs", "n_links", "n_clusters", "n_periods"]
    out = out[cols]
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / ("did_estimates_weather.csv" if args.weather else "did_estimates.csv")
    out.round(6).to_csv(path, index=False)
    log.info("wrote %s", path)
    log.info(
        "\nTreatment date %s. Errors clustered by %s. "
        "Pre-period is short - see docs/decision_register.md before quoting these.",
        TREATMENT_DATE, CLUSTER_VAR,
    )


if __name__ == "__main__":
    main()
