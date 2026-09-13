"""H007 — can the secondary feed identify diversion onto the toll-exempt routes?

Runs the pre-registered specification in
``docs/hypotheses/H007-secondary-feed-diversion.md`` against
``data/processed/secondary_hourly_panel.parquet``. Nine treated links (FDR
Drive, 12th/11th Ave, West St, the Brooklyn Battery Tunnel Manhattan approaches
— every one of them exempt from the toll and inside the zone) against 116
control links in the other boroughs.

The three diagnostics run in a fixed order, because an earlier one failing makes
the later ones unreadable:

1. **Availability**, which is a GATE. Per group per month, the share of
   link-hours that yield at least one positive speed reading, out of the
   link-hours present in the feed at all, and the number of links reporting.
   The pre-to-post difference in differences of those shares is criterion 1. If
   the two groups' observation sets move apart, the comparison is between
   different samples of hours rather than different roads, and no fixed-effects
   estimator repairs that.
2. **Event study** by month over +/-12 months, then the joint Wald test that
   every pre-treatment lead is zero, via ``event_study.pretrend_test`` — the
   corrected test that uses the full cluster covariance, never the superseded
   sum of squared individual t statistics.
3. **Rambachan & Roth (2023)** breakdown value at the same horizon.

**Randomization inference is the primary inference here, not a supplement.**
Nine treated clusters is far below where cluster-robust asymptotics can be
trusted — MacKinnon, James G., and Matthew D. Webb (2020), "Randomization
inference for difference-in-differences with few treated clusters", Journal of
Econometrics 218(2):435-450 — and H001 already measured this project's clustered
standard errors running up to 1.5x too tight on a 333-cluster panel. Treatment
is reassigned at random among the control links, nine at a time, 500 draws. The
clustered standard errors are reported alongside and are the weaker of the two.

Event time is monthly. ``event_study.build_dummies`` reads its bins from a
column named ``event_week``, so the monthly index is written into that column
before the call and the output is relabelled; the alternative, weekly bins over
41 months, would ask the joint pre-trend test to carry more than a hundred
restrictions on nine clusters.

Every artefact is namespaced ``H007_``. The pre-trend verdict is NOT written
through ``event_study.record_pretrend``, which upserts into the primary study's
shared ``outputs/tables/pretrend_tests.csv``; this record gets its own file.

Usage:
    python -m src.analysis.h007_diversion
    python -m src.analysis.h007_diversion --draws 100   # faster smoke run
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis import honest_did  # noqa: E402
from src.analysis.descriptive import (  # noqa: E402
    GRID,
    INK,
    INK_MUTED,
    SERIES_COLOR,
    SURFACE,
    _save,
)
from src.analysis.did import OUTCOME, TIME_KEY, _absorb, estimate  # noqa: E402
from src.analysis.event_study import (  # noqa: E402
    PRETREND_METHOD,
    REFERENCE_K,
    build_dummies,
    coef_frame,
    pretrend_test,
)
from src.analysis.event_study import estimate as es_estimate  # noqa: E402
from src.analysis.placebo_space import _cluster_se, _p, placebo_draws  # noqa: E402
from src.config import (  # noqa: E402
    CLUSTER_VAR,
    RANDOM_SEED,
    SECONDARY_HOURLY_PANEL_PATH,
    TABLES_DIR,
    TREATMENT_DATE,
)

log = logging.getLogger(__name__)

PREFIX = "H007"
SAMPLES = ("all", "peak", "offpeak", "weekend")
HORIZON_MONTHS = 12
DEFAULT_DRAWS = 500
# Nine treated links is the whole design. Each draw labels exactly nine control
# links treated, so the placebo design has the same treated cluster count as the
# real one rather than the same treated SHARE, which is what placebo_space.py
# preserves for the 148-link primary panel.
TREATED_CLUSTERS = 9
# The frozen bar: a differential availability shift of this size or more
# disqualifies the design (criterion 1). Stated here so the code cannot drift
# from the record.
AVAILABILITY_BAR_PP = 5.0
ALPHA = 0.05
# Below this, criterion 3 of "refutes" fires: the estimate survives only
# violations smaller than half of what the pre-period already shows.
BREAKDOWN_BAR = 0.5

ANALYSIS_GROUPS = ("treated_exempt", "control")


# --- loading -----------------------------------------------------------------


def load(sample: str = "all", path=SECONDARY_HOURLY_PANEL_PATH) -> pd.DataFrame:
    """The two estimation groups, restricted to one hour-of-week sample.

    Rows with no usable speed are KEPT. Every estimator drops them; the
    availability diagnostic needs them as its denominator.
    """
    df = pd.read_parquet(path)
    df = df[df["analysis_group"].isin(ANALYSIS_GROUPS)].copy()
    df[TIME_KEY] = pd.to_datetime(df[TIME_KEY])
    if sample == "peak":
        df = df[df["is_peak"] & ~df["is_weekend"]]
    elif sample == "offpeak":
        df = df[~df["is_peak"] & ~df["is_weekend"]]
    elif sample == "weekend":
        df = df[df["is_weekend"]]
    return df


def estimation_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the unusable hours, leaving what the estimators actually see."""
    return df[df["median_speed_mph"].notna()].copy()


# --- 1. availability, the gate ----------------------------------------------


def availability_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Per group per month: usable share of present link-hours, links reporting."""
    d = df.copy()
    d["month"] = d[TIME_KEY].dt.to_period("M").dt.to_timestamp()
    d["group"] = np.where(d["treated"], "treated", "control")
    out = (
        d.groupby(["group", "month"])
        .agg(
            link_hours_present=("has_speed", "size"),
            link_hours_usable=("has_speed", "sum"),
            links_reporting=(CLUSTER_VAR, "nunique"),
            readings=("n_readings", "sum"),
            positive_readings=("n_positive", "sum"),
        )
        .reset_index()
    )
    out["availability"] = out["link_hours_usable"] / out["link_hours_present"]
    out["positive_reading_share"] = out["positive_readings"] / out["readings"]
    out["post"] = out["month"] >= pd.Timestamp(TREATMENT_DATE).to_period("M").to_timestamp()
    return out


def availability_by_link(df: pd.DataFrame) -> pd.DataFrame:
    """Per link per month: is this link contributing a usable speed at all?

    The group-level gate says the two observation sets moved apart. This says
    which links moved them, which is what distinguishes a feed that degraded
    everywhere from a handful of sensors that died.
    """
    d = df.copy()
    d["month"] = d[TIME_KEY].dt.to_period("M").dt.to_timestamp()
    d["group"] = np.where(d["treated"], "treated", "control")
    out = (
        d.groupby([CLUSTER_VAR, "link_name", "group", "month"])
        .agg(
            link_hours_present=("has_speed", "size"),
            link_hours_usable=("has_speed", "sum"),
        )
        .reset_index()
    )
    out["availability"] = out["link_hours_usable"] / out["link_hours_present"]
    out["contributes"] = out["link_hours_usable"] > 0
    return out.sort_values(["group", CLUSTER_VAR, "month"]).reset_index(drop=True)


def contributing_links(by_link: pd.DataFrame) -> pd.DataFrame:
    """How many links in each group actually feed the estimator, by period.

    A link present in the feed but emitting nothing but outages is not a unit of
    analysis, however many rows it publishes.
    """
    d = by_link.copy()
    d["post"] = d["month"] >= pd.Timestamp(TREATMENT_DATE).to_period("M").to_timestamp()
    return (
        d.groupby(["group", "post"])
        .agg(
            links_present=(CLUSTER_VAR, "nunique"),
            links_contributing=(CLUSTER_VAR, lambda s: s[d.loc[s.index, "contributes"]].nunique()),
        )
        .reset_index()
    )


def availability_gate(monthly: pd.DataFrame, sample: str) -> dict:
    """Pre-to-post difference in differences of the usable-hour share.

    Two versions of each group mean are reported. The pooled one weights months
    by how many link-hours they contain and is the headline, because "share of
    link-hours" is itself a pooled quantity. The unweighted mean of monthly
    shares is carried alongside so that a reader can see whether the verdict
    depends on the choice; on this panel it does not.
    """
    row: dict = {"sample": sample}
    for group in ("treated", "control"):
        for post in (False, True):
            cell = monthly[(monthly["group"] == group) & (monthly["post"] == post)]
            tag = f"{group}_{'post' if post else 'pre'}"
            pooled = cell["link_hours_usable"].sum() / cell["link_hours_present"].sum()
            row[f"{tag}_availability"] = float(pooled)
            row[f"{tag}_availability_monthly_mean"] = float(cell["availability"].mean())
            row[f"{tag}_link_hours"] = int(cell["link_hours_present"].sum())
    for suffix in ("", "_monthly_mean"):
        t = row[f"treated_post_availability{suffix}"] - row[f"treated_pre_availability{suffix}"]
        c = row[f"control_post_availability{suffix}"] - row[f"control_pre_availability{suffix}"]
        row[f"treated_change_pp{suffix}"] = 100 * t
        row[f"control_change_pp{suffix}"] = 100 * c
        row[f"differential_change_pp{suffix}"] = 100 * (t - c)
    row["bar_pp"] = AVAILABILITY_BAR_PP
    row["criterion_1_passes"] = bool(abs(row["differential_change_pp"]) < AVAILABILITY_BAR_PP)
    return row


# --- 2. monthly event study --------------------------------------------------


def to_monthly_event_time(df: pd.DataFrame) -> pd.DataFrame:
    """Put the monthly event index where ``build_dummies`` looks for its bins.

    ``event_study.build_dummies`` is hard-wired to a column called
    ``event_week``. Rather than fork it, the monthly index is written there and
    the resulting coefficient frame is relabelled. ``event_week_true`` keeps the
    weekly index so nothing is silently lost.
    """
    out = df.copy()
    out["event_week_true"] = out["event_week"]
    out["event_week"] = out["event_month"]
    return out


def run_event_study(df: pd.DataFrame, horizon: int = HORIZON_MONTHS) -> dict:
    """Monthly event study plus the joint zero-lead Wald test."""
    monthly = to_monthly_event_time(estimation_frame(df))
    monthly, dummy_cols = build_dummies(monthly, horizon)
    result = es_estimate(monthly, dummy_cols)
    coefs = coef_frame(result, dummy_cols).rename(
        columns={
            "observed_week_min": "observed_month_min",
            "observed_week_max": "observed_month_max",
            "observed_week_count": "observed_month_count",
        }
    )
    pt = pretrend_test(coefs, result)
    return {"coefs": coefs, "result": result, "pretrend": pt, "dummy_cols": dummy_cols}


def pretrend_row(sample: str, es: dict) -> dict:
    stat, p, dof = es["pretrend"] if es["pretrend"] is not None else (np.nan, np.nan, 0)
    result = es["result"]
    meta = result.get("pretrend_metadata", {})
    return {
        "sample": sample,
        "event_time_unit": "month",
        "horizon_months": result.get("horizon"),
        "chi2": stat,
        "dof": dof,
        "p_value": p,
        "verdict": ("UNTESTABLE" if es["pretrend"] is None else "PASS" if p > ALPHA else "FAIL"),
        "reference_k": REFERENCE_K,
        "test_method": meta.get("test_method", PRETREND_METHOD),
        "test_status": meta.get("test_status"),
        "test_reason": meta.get("test_reason"),
        "covariance_rank": meta.get("covariance_rank"),
        "n_obs": int(result["n_obs"]),
        "n_clusters": int(result["n_clusters"]),
        "n_periods": int(result["n_periods"]),
        "pooled_endpoint_bins": bool(es["coefs"]["pooled_tail"].any()),
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


# --- 3. randomization inference ---------------------------------------------


def significance_threshold(null: np.ndarray, draws: int) -> float:
    """Smallest |ATT| that ``_p`` would score at or below 5%.

    ``_p`` is ``(1 + #{|b| >= |obs|}) / (1 + B)``, so p <= 0.05 needs at most
    ``floor(0.05 * (1 + B)) - 1`` draws to match or beat the observation. The
    threshold is therefore the magnitude sitting at that rank in the null.
    """
    finite = np.sort(np.abs(null[np.isfinite(null)]))[::-1]
    if not len(finite):
        return float("nan")
    max_hits = int(np.floor(ALPHA * (1 + draws))) - 1
    if max_hits < 0:
        return float("inf")
    return float(finite[min(max_hits, len(finite) - 1)])


def minimum_detectable_effect(null: np.ndarray, draws: int, power: float = 0.80) -> float:
    """Smallest true effect this design would catch at 5% with 80% power.

    A constant additive effect of delta on the treated links in the post period
    shifts the DiD coefficient by exactly delta, so the distribution of the
    estimator under that alternative is the null distribution shifted by delta.
    Power is then the share of null draws whose shifted magnitude clears the
    significance threshold — computed on the empirical null, with no normal
    approximation anywhere.
    """
    finite = null[np.isfinite(null)]
    threshold = significance_threshold(null, draws)
    if not len(finite) or not np.isfinite(threshold):
        return float("nan")

    def achieved(delta: float) -> float:
        return float(np.mean(np.abs(finite + delta) >= threshold))

    lo, hi = 0.0, max(threshold * 4, float(np.max(np.abs(finite))) * 4, 1e-6)
    if achieved(hi) < power:
        return float("inf")
    for _ in range(80):
        mid = (lo + hi) / 2
        if achieved(mid) >= power:
            hi = mid
        else:
            lo = mid
    return float(hi)


def run_randomization(df: pd.DataFrame, draws: int, real: dict) -> dict:
    """Reassign treatment among control links, nine at a time."""
    d = estimation_frame(df)
    controls = d[~d["treated"]]
    n_control = controls[CLUSTER_VAR].nunique()
    rng = np.random.default_rng(RANDOM_SEED)
    betas, ts, _, _ = placebo_draws(controls, TREATED_CLUSTERS, draws, rng)

    # Recompute the real estimate without the finite-sample correction so its t
    # sits on the same scale as the draws'.
    work = d.copy()
    work["D"] = (work["treated"] & work["post"]).astype(float)
    resid, _, _ = _absorb(work, [OUTCOME, "D"], CLUSTER_VAR, TIME_KEY)
    codes = pd.factorize(work[CLUSTER_VAR])[0]
    real_beta, real_se = _cluster_se(resid[:, 1], resid[:, 0], codes, int(codes.max() + 1))
    real_t = real_beta / real_se if real_se else np.nan

    finite = betas[np.isfinite(betas)]
    p_beta = _p(betas, real_beta)
    return {
        "beta_mph": real["beta_mph"],
        "clustered_se_mph": real["se_mph"],
        "clustered_p_value": real["p_value"],
        "clustered_ci_low": real["ci_low"],
        "clustered_ci_high": real["ci_high"],
        "ri_draws": int(len(finite)),
        "ri_treated_per_draw": TREATED_CLUSTERS,
        "ri_control_pool": int(n_control),
        "ri_null_sd": float(np.std(finite, ddof=1)) if len(finite) > 1 else np.nan,
        "ri_null_mean": float(np.mean(finite)) if len(finite) else np.nan,
        "ri_null_q025": float(np.quantile(finite, 0.025)) if len(finite) else np.nan,
        "ri_null_q975": float(np.quantile(finite, 0.975)) if len(finite) else np.nan,
        "se_ratio_ri_over_clustered": (
            float(np.std(finite, ddof=1)) / real["se_mph"]
            if len(finite) > 1 and real["se_mph"]
            else np.nan
        ),
        "p_randomisation_beta": p_beta,
        "p_randomisation_t": _p(ts, real_t),
        "criterion_3_passes": bool(np.isfinite(p_beta) and p_beta < ALPHA),
        "significance_threshold_mph": significance_threshold(betas, draws),
        "mde_80_power_mph": minimum_detectable_effect(betas, draws),
        "pre_treated_mean_mph": real["pre_treated_mean_mph"],
        "_betas": betas,
        "_real_beta": real_beta,
    }


# --- 4. Rambachan & Roth -----------------------------------------------------


def honest_moments(sample: str, es: dict) -> dict:
    """Event-study coefficients and their full cluster covariance, by event time.

    Same shape ``honest_did.event_study_moments`` returns, built from the
    monthly event study above rather than from the primary panel its own
    ``load()`` would read.
    """
    result = es["result"]
    ks = [honest_did._event_time(c) for c in result["dummy_cols"]]
    order = np.argsort(ks)
    beta = np.asarray(result["beta"], dtype=float)[order]
    vcov = np.asarray(result["vcov"], dtype=float)[np.ix_(order, order)]
    return {
        "sample": sample,
        "k": [ks[i] for i in order],
        "beta": beta,
        "vcov": vcov,
        "se": np.sqrt(np.diag(vcov)),
        "min_eigenvalue": float(np.linalg.eigvalsh(vcov).min()),
        "n_obs": int(result["n_obs"]),
        "n_clusters": int(result["n_clusters"]),
        "horizon": result.get("horizon", HORIZON_MONTHS),
    }


# --- figures -----------------------------------------------------------------


def plot_availability(monthly: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for group, colour in (("treated", "exempt_in_zone"), ("control", "control")):
        s = monthly[monthly["group"] == group].sort_values("month")
        ax.plot(
            s["month"],
            100 * s["availability"],
            color=SERIES_COLOR[colour],
            linewidth=2,
            zorder=3,
        )
        ax.annotate(
            "9 exempt in-zone links" if group == "treated" else "116 control links",
            xy=(s["month"].iloc[-1], 100 * s["availability"].iloc[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            color=SERIES_COLOR[colour],
            fontsize=9,
            va="center",
        )
    ax.axvline(pd.Timestamp(TREATMENT_DATE), color=INK, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.set_ylim(0, 102)
    # Room for the direct labels, which are the required relief for series that
    # would otherwise need a legend.
    last = monthly["month"].max()
    ax.set_xlim(monthly["month"].min(), last + pd.Timedelta(days=195))
    ax.set_facecolor(SURFACE)
    fig.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.set_ylabel("% of present link-hours yielding a speed", color=INK_MUTED, fontsize=10)
    ax.set_title(
        "Usable-hour availability, secondary feed",
        color=INK,
        fontsize=13,
        fontweight="bold",
        loc="left",
        pad=26,
    )
    ax.text(
        0,
        1.02,
        "Zero-speed readings are outages (travel_time = 0, status = -101) and count as missing. "
        "Dashed line: tolling begins.",
        transform=ax.transAxes,
        color=INK_MUTED,
        fontsize=9,
        va="bottom",
    )
    fig.autofmt_xdate()
    _save(fig, f"{PREFIX}_availability_monthly.png")


def plot_event_study(coefs: pd.DataFrame, sample: str, n_clusters: int) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.axhline(0, color=GRID, linewidth=1, zorder=1)
    ax.errorbar(
        coefs["k"],
        coefs["coef"],
        yerr=[coefs["coef"] - coefs["ci_low"], coefs["ci_high"] - coefs["coef"]],
        fmt="o-",
        color=SERIES_COLOR["exempt_in_zone"],
        linewidth=2,
        markersize=4.5,
        capsize=3,
        ecolor=INK_MUTED,
        elinewidth=1,
        zorder=3,
    )
    ax.axvline(-0.5, color=INK, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)
    ax.set_facecolor(SURFACE)
    fig.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.set_xlabel("months relative to 2025-01", color=INK_MUTED, fontsize=10)
    ax.set_ylabel("exempt - control gap (mph), rel. to month -1", color=INK_MUTED, fontsize=10)
    ax.set_title(
        f"H007 event study, monthly — {sample}",
        color=INK,
        fontsize=13,
        fontweight="bold",
        loc="left",
        pad=26,
    )
    ax.text(
        0,
        1.02,
        f"95% CI clustered on the {n_clusters} links that contribute a usable speed. "
        "Endpoint bins pool the months beyond +/-12.",
        transform=ax.transAxes,
        color=INK_MUTED,
        fontsize=9,
        va="bottom",
    )
    _save(fig, f"{PREFIX}_event_study_{sample}.png")


def plot_randomization(res: dict, sample: str) -> None:
    betas = res["_betas"][np.isfinite(res["_betas"])]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(betas, bins=40, color=GRID, edgecolor=INK_MUTED, linewidth=0.6, zorder=2)
    ax.axvline(
        res["_real_beta"],
        color=SERIES_COLOR["exempt_in_zone"],
        linewidth=2.4,
        zorder=4,
        label=f"9 exempt in-zone links ({res['_real_beta']:+.2f} mph)",
    )
    ax.axvline(0, color=INK_MUTED, linewidth=1, linestyle=":", zorder=3)
    ax.set_xlabel("DiD estimate (mph)")
    ax.set_ylabel(f"placebo draws (n={len(betas)})")
    ax.set_title(
        f"H007 randomization inference — {sample}\n"
        f"random sets of {res['ri_treated_per_draw']} control links, tolling date unchanged  ·  "
        f"p = {res['p_randomisation_beta']:.3f}",
        color=INK,
        loc="left",
    )
    ax.legend(frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    _save(fig, f"{PREFIX}_randomization_{sample}.png")


# --- roster ------------------------------------------------------------------


def link_roster(path=SECONDARY_HOURLY_PANEL_PATH) -> pd.DataFrame:
    """Every link in the feed with its group, and when it reported."""
    df = pd.read_parquet(
        path,
        columns=[
            CLUSTER_VAR,
            TIME_KEY,
            "link_name",
            "borough",
            "treatment_group",
            "analysis_group",
            "hold_out_reason",
            "has_speed",
        ],
    )
    df[TIME_KEY] = pd.to_datetime(df[TIME_KEY])
    df["month"] = df[TIME_KEY].dt.to_period("M")
    out = (
        df.groupby(
            [
                CLUSTER_VAR,
                "link_name",
                "borough",
                "treatment_group",
                "analysis_group",
                "hold_out_reason",
            ]
        )
        .agg(
            first_hour=(TIME_KEY, "min"),
            last_hour=(TIME_KEY, "max"),
            link_hours_present=(TIME_KEY, "size"),
            link_hours_usable=("has_speed", "sum"),
            months_reporting=("month", "nunique"),
        )
        .reset_index()
    )
    out["availability"] = out["link_hours_usable"] / out["link_hours_present"]
    return out.sort_values(["analysis_group", CLUSTER_VAR]).reset_index(drop=True)


# --- driver ------------------------------------------------------------------


def verdict(gate: dict, pretrend: dict, ri: dict, breakdown: float) -> tuple[str, str]:
    """Apply the frozen acceptance criteria mechanically.

    The criteria are frozen in the record and are not reinterpreted here. Any
    one of the three refutation conditions is enough; support needs all three of
    its conditions; everything else is uninformative. A refutation condition
    that could not be evaluated is reported as unevaluated rather than passed.
    """
    refutes = []
    if not gate["criterion_1_passes"]:
        refutes.append(
            f"availability (differential change {gate['differential_change_pp']:+.2f} pp, "
            f"bar {AVAILABILITY_BAR_PP:.0f} pp)"
        )
    if pretrend["verdict"] == "FAIL":
        refutes.append(f"joint pre-trend test rejects (p = {pretrend['p_value']:.3g})")
    if np.isfinite(breakdown) and breakdown < BREAKDOWN_BAR:
        refutes.append(f"Rambachan-Roth breakdown value {breakdown:.3f} < {BREAKDOWN_BAR}")

    if refutes:
        return "REFUTES", "; ".join(refutes)
    if pretrend["verdict"] == "UNTESTABLE":
        return "UNINFORMATIVE", f"pre-trend untestable: {pretrend['test_reason']}"
    if np.isnan(breakdown):
        return (
            "UNINFORMATIVE",
            "the Rambachan-Roth breakdown value could not be computed, so the third "
            "refutation condition is unevaluated and support cannot be claimed",
        )
    if ri["criterion_3_passes"]:
        return "SUPPORTS", f"randomization p = {ri['p_randomisation_beta']:.4f} < {ALPHA}"
    return (
        "UNINFORMATIVE",
        f"randomization p = {ri['p_randomisation_beta']:.4f} >= {ALPHA}; "
        f"80%-power MDE {ri['mde_80_power_mph']:.3f} mph",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    ap.add_argument("--horizon", type=int, default=HORIZON_MONTHS, help="event-time bins, months")
    ap.add_argument("--skip-honest", action="store_true", help="skip the R&R sensitivity step")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    roster = link_roster()
    roster.to_csv(TABLES_DIR / f"{PREFIX}_link_roster.csv", index=False)
    log.info(
        "roster: %s",
        ", ".join(
            f"{n} {g}" for g, n in roster["analysis_group"].value_counts().sort_index().items()
        ),
    )

    availability_rows, gate_rows, pretrend_rows, did_rows, ri_rows = [], [], [], [], []
    honest_grids, honest_summary = [], []
    verdicts = {}

    for sample in SAMPLES:
        log.info("=== %s ===", sample)
        df = load(sample)
        est = estimation_frame(df)
        log.info(
            "  %s link-hours present, %s usable, %d links (%d treated)",
            f"{len(df):,}",
            f"{len(est):,}",
            df[CLUSTER_VAR].nunique(),
            df.loc[df["treated"], CLUSTER_VAR].nunique(),
        )

        # 1 — availability gate
        monthly = availability_monthly(df)
        monthly.insert(0, "sample", sample)
        availability_rows.append(monthly)
        gate = availability_gate(monthly, sample)
        gate_rows.append(gate)
        log.info(
            "  [1] availability: treated %+.2f pp, control %+.2f pp, differential %+.2f pp "
            "(bar %.0f pp) -> %s",
            gate["treated_change_pp"],
            gate["control_change_pp"],
            gate["differential_change_pp"],
            AVAILABILITY_BAR_PP,
            "PASS" if gate["criterion_1_passes"] else "FAIL",
        )
        if sample == "all":
            plot_availability(monthly)
            by_link = availability_by_link(df)
            by_link["availability"] = by_link["availability"].round(6)
            by_link.to_csv(TABLES_DIR / f"{PREFIX}_availability_by_link.csv", index=False)
            contributing = contributing_links(by_link)
            contributing.to_csv(TABLES_DIR / f"{PREFIX}_contributing_links.csv", index=False)
            for _, r in contributing.iterrows():
                log.info(
                    "      %s %s: %d links present, %d contributing a usable speed",
                    r["group"],
                    "post" if r["post"] else "pre ",
                    r["links_present"],
                    r["links_contributing"],
                )

        # the estimator itself
        real = estimate(est)
        real["sample"] = sample
        did_rows.append(real)
        log.info(
            "  ATT %+.4f mph (clustered SE %.4f, p %.4g, 95%% CI [%+.4f, %+.4f]) = %+.2f%% "
            "of the %.2f mph pre-treatment exempt mean",
            real["beta_mph"],
            real["se_mph"],
            real["p_value"],
            real["ci_low"],
            real["ci_high"],
            real["pct_of_pre_treated_mean"],
            real["pre_treated_mean_mph"],
        )

        # 2 — event study and the joint pre-trend test
        es = run_event_study(df, args.horizon)
        es["coefs"].insert(0, "sample", sample)
        es["coefs"].to_csv(TABLES_DIR / f"{PREFIX}_event_study_{sample}.csv", index=False)
        plot_event_study(es["coefs"], sample, int(es["result"]["n_clusters"]))
        pt = pretrend_row(sample, es)
        pretrend_rows.append(pt)
        log.info(
            "  [2] pre-trend: chi2 = %.2f on %d leads, p = %.4g -> %s",
            pt["chi2"],
            pt["dof"],
            pt["p_value"],
            pt["verdict"],
        )

        # 3 — Rambachan & Roth
        breakdown = float("nan")
        if not args.skip_honest:
            moments = honest_moments(sample, es)
            grid, bvals = honest_did.sensitivity(moments)
            honest_did.plot(grid, moments, bvals, PREFIX)
            honest_grids.append(grid)
            breakdown = bvals.get("relative_magnitude", float("nan"))
            honest_summary.append(
                {
                    "sample": sample,
                    "horizon_months": args.horizon,
                    "breakdown_relative_magnitude": breakdown,
                    "breakdown_smoothness": bvals.get("smoothness", float("nan")),
                    "min_eigenvalue": moments["min_eigenvalue"],
                    "n_obs": moments["n_obs"],
                    "n_clusters": moments["n_clusters"],
                }
            )
            log.info("  [3] Rambachan-Roth breakdown M = %.4f", breakdown)

        # inference — randomization first, clustered second
        ri = run_randomization(df, args.draws, real)
        plot_randomization(ri, sample)
        ri_rows.append({"sample": sample, **{k: v for k, v in ri.items() if not k.startswith("_")}})
        log.info(
            "  RI: p(beta) = %.4f, p(t) = %.4f | null SD %.4f vs clustered SE %.4f (%.2fx) | "
            "5%% threshold %.3f mph, 80%%-power MDE %.3f mph",
            ri["p_randomisation_beta"],
            ri["p_randomisation_t"],
            ri["ri_null_sd"],
            ri["clustered_se_mph"],
            ri["se_ratio_ri_over_clustered"],
            ri["significance_threshold_mph"],
            ri["mde_80_power_mph"],
        )

        label, reason = verdict(gate, pt, ri, breakdown)
        verdicts[sample] = (label, reason)
        log.info("  VERDICT (%s): %s — %s", sample, label, reason)

    pd.concat(availability_rows, ignore_index=True).round(6).to_csv(
        TABLES_DIR / f"{PREFIX}_availability_monthly.csv", index=False
    )
    pd.DataFrame(gate_rows).round(6).to_csv(
        TABLES_DIR / f"{PREFIX}_availability_gate.csv", index=False
    )
    pd.DataFrame(pretrend_rows).round(6).to_csv(TABLES_DIR / f"{PREFIX}_pretrend.csv", index=False)
    pd.DataFrame(did_rows).round(6).to_csv(TABLES_DIR / f"{PREFIX}_did_estimates.csv", index=False)
    pd.DataFrame(ri_rows).round(6).to_csv(TABLES_DIR / f"{PREFIX}_randomization.csv", index=False)
    if honest_summary:
        stem = f"{PREFIX}_honest_did_h{args.horizon}"
        pd.concat(honest_grids, ignore_index=True).round(6).to_csv(
            TABLES_DIR / f"{stem}_grid.csv", index=False
        )
        pd.DataFrame(honest_summary).round(6).to_csv(TABLES_DIR / f"{stem}.csv", index=False)

    pd.DataFrame(
        [{"sample": s, "verdict": v, "reason": r} for s, (v, r) in verdicts.items()]
    ).to_csv(TABLES_DIR / f"{PREFIX}_verdict.csv", index=False)

    log.info("")
    log.info("Verdict on the all-hours sample: %s — %s", *verdicts["all"])
    log.info(
        "Randomization inference is the primary inference. The clustered standard errors "
        "are reported alongside and are the weaker of the two."
    )


if __name__ == "__main__":
    main()
