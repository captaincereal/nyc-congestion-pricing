"""H003: registered temporal aggregation sensitivity on a verified fixed snapshot.

The only data-reading entry point is ``run`` (also exposed by the CLI). It checks
the strict source gate before rebuilding an isolated panel from the eight exact
registered paths. ``analyze_panel`` is an in-memory computational interface for
synthetic tests and an already-gated caller; it never loads a canonical panel.

Usage after source verification has completed:
    python -m src.analysis.aggregation_sensitivity --raw-dir data/raw

No specification selection, weather controls, H002, or owner decisions are made.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import platform
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from src.config import DATA_DIR, PROJECT_ROOT, RAW_DIR, TABLES_DIR, TREATMENT_DATE
from src.data.geo import classify_segment, roadway_of
from src.data.verification_gate import verification_summary

log = logging.getLogger(__name__)
SAMPLES = ("peak", "all", "offpeak", "weekend")
SPECIFICATIONS = ("hourly", "daily", "collapsed")
PRIMARY_SAMPLE = "peak"
LEAD_SPECIFICATION = "daily"
OUTCOME = "median_speed_mph"
PREREGISTRATION_COMMIT = "d5b4558da409c08c9706ea871647827f5869e5d7"
PRIORITY_AMENDMENT_COMMIT = "aea49fa"
# Canonical JSON hash of the committed registration, independent of line endings.
TARGETS_CANONICAL_SHA256 = "887ad1042f2368f05bf6cd18d67b5a727f324c37abcfdefd0abb9a148c08af4f"
LIMITATIONS = (
    "These are descriptive speed associations. Aggregation does not establish causality, "
    "repair failed parallel trends, or address a common cordon-level shock. Hourly and "
    "daily link-cluster covariance already allows within-link serial dependence under "
    "its asymptotic assumptions. Daily equal-link-day weighting and date effects change "
    "temporal composition; collapsed equal-link weighting also changes the estimand. "
    "The registered 0.25 mph and 1.5 SE-ratio thresholds are descriptive alarms, not "
    "calibrated tests of estimator equality. CI inclusion of zero neither establishes "
    "zero effect nor validates spatial independence. The prospectively amended peak cut "
    "determines the summary, with daily peak as the lead metric; "
    "every secondary cut and failure is retained."
)
REFERENCES = [
    {
        "citation": "Bertrand, Marianne, Esther Duflo, and Sendhil Mullainathan (2004). "
        "How Much Should We Trust Differences-In-Differences Estimates? "
        "Quarterly Journal of Economics 119(1):249–275, §IV.C and Table VI.",
        "url": "https://doi.org/10.1162/003355304772839588",
    },
    {
        "citation": "Cameron, A. Colin, and Douglas L. Miller (2015). A Practitioner's "
        "Guide to Cluster-Robust Inference. Journal of Human Resources 50(2):317–372.",
        "url": "https://doi.org/10.3368/jhr.50.2.317",
    },
    {
        "citation": "MacKinnon, James G., and Matthew D. Webb (2020). Randomization "
        "inference for difference-in-differences with few treated clusters. "
        "Journal of Econometrics 218(2):435–450.",
        "url": "https://doi.org/10.1016/j.jeconom.2020.04.024",
    },
]


class AnalysisFailure(ValueError):
    """An explicitly retained support, identification, or numerical failure."""


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _canonical_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _json_write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _failure(sample: str, specification: str, reason: str, **counts: Any) -> dict:
    return {
        "sample": sample,
        "specification": specification,
        "status": "uninformative",
        "reason": reason,
        **dict.fromkeys(
            [
                "beta_mph",
                "se_mph",
                "ci_low",
                "ci_high",
                "p_value",
                "t",
                "df_inference",
                "n_obs",
                "n_links",
                "n_treated_links",
                "n_control_links",
                "n_periods",
                "n_clusters",
                "finite_sample_correction",
                "beta_difference_mph",
                "se_ratio",
                "ci_includes_zero",
            ]
        ),
        **counts,
    }


def _inference(beta: float, variance: float, dof: int) -> dict:
    if dof <= 0 or not np.isfinite(beta) or not np.isfinite(variance) or variance <= 0:
        raise AnalysisFailure(
            "coefficient/covariance is nonfinite, nonpositive, or has no inference df"
        )
    se = float(np.sqrt(variance))
    t = beta / se
    critical = float(stats.t.ppf(0.975, dof))
    low, high = beta - critical * se, beta + critical * se
    return {
        "beta_mph": beta,
        "se_mph": se,
        "t": t,
        "p_value": float(2 * stats.t.sf(abs(t), dof)),
        "ci_low": low,
        "ci_high": high,
        "df_inference": dof,
        "ci_includes_zero": bool(low <= 0 <= high),
    }


def _absorb_checked(
    frame: pd.DataFrame, time_key: str, *, tol: float = 1e-10, max_iter: int = 200
) -> tuple[np.ndarray, int, int, int]:
    """The existing hourly alternating projection, with failure made explicit."""
    out = np.column_stack([frame[OUTCOME], (frame["treated"] & frame["post"]).astype(float)])
    out = out.astype(float)
    if not np.isfinite(out).all():
        raise AnalysisFailure("nonfinite outcome or treatment; no extra speed filtering permitted")
    unit = pd.factorize(frame["link_id"])[0]
    time = pd.factorize(frame[time_key])[0]
    groups, periods = int(unit.max() + 1), int(time.max() + 1)
    unit_n, time_n = np.bincount(unit), np.bincount(time)
    for iteration in range(1, max_iter + 1):
        previous = out.copy()
        for column in range(out.shape[1]):
            out[:, column] -= (np.bincount(unit, out[:, column]) / unit_n)[unit]
            out[:, column] -= (np.bincount(time, out[:, column]) / time_n)[time]
        delta = float(np.max(np.abs(out - previous)))
        if delta < tol:
            return out, groups, periods, iteration
    raise AnalysisFailure(f"fixed-effect absorption did not converge in {max_iter} iterations")


def _twfe(frame: pd.DataFrame, time_key: str) -> dict:
    residual, groups, periods, iterations = _absorb_checked(frame, time_key)
    y, x = residual.T
    xtx = float(x @ x)
    # Numerically null residualized treatment is an identification failure.
    scale = max(float((frame["treated"] & frame["post"]).sum()), 1.0)
    if groups < 2 or xtx <= np.finfo(float).eps * scale:
        raise AnalysisFailure("no identifying within-variation in treatment")
    beta = float(x @ y) / xtx
    errors = y - beta * x
    codes = pd.factorize(frame["link_id"])[0]
    scores = np.bincount(codes, x * errors, minlength=groups)
    n, k = len(frame), 1 + groups + periods
    # Preserve did.estimate's registered correction convention, including its floor.
    correction = (groups / (groups - 1)) * ((n - 1) / max(n - k, 1))
    variance = correction * float(scores @ scores) / xtx**2
    return {
        **_inference(beta, variance, groups - 1),
        "n_obs": n,
        "n_links": groups,
        "n_clusters": groups,
        "n_periods": periods,
        "finite_sample_correction": correction,
        "absorbed_parameter_count_convention": k,
        "absorption_iterations": iterations,
        "covariance": "link-cluster",
    }


def daily_panel(hourly: pd.DataFrame) -> pd.DataFrame:
    """Arithmetic hourly-outcome mean for each link and naive local calendar date."""
    work = hourly.assign(date=hourly["ts_hour"].dt.normalize())
    daily = work.groupby(["link_id", "treated", "date"], as_index=False, sort=True).agg(
        median_speed_mph=(OUTCOME, "mean"), n_source_hours=(OUTCOME, "size")
    )
    daily["post"] = daily["date"] >= pd.Timestamp(TREATMENT_DATE)
    return daily


def collapsed_panel(hourly: pd.DataFrame) -> pd.DataFrame:
    """Direct available-hour pre/post means; days are never equally weighted first."""
    means = hourly.pivot_table(
        index=["link_id", "treated"], columns="post", values=OUTCOME, aggfunc="mean"
    )
    if False not in means or True not in means or means.isna().any().any():
        raise AnalysisFailure("collapsed links lack a pre or post hourly mean")
    result = means.rename(columns={False: "pre_mean_mph", True: "post_mean_mph"}).reset_index()
    result["change_mph"] = result["post_mean_mph"] - result["pre_mean_mph"]
    return result


def _collapsed(frame: pd.DataFrame) -> dict:
    groups = len(frame)
    x = np.column_stack([np.ones(groups), frame["treated"].astype(float)])
    y = frame["change_mph"].to_numpy(float)
    if groups <= 2 or np.linalg.matrix_rank(x) != 2:
        raise AnalysisFailure(
            "collapsed regression lacks both groups or positive G-2 degrees of freedom"
        )
    if not np.isfinite(y).all():
        raise AnalysisFailure("collapsed outcome is nonfinite")
    bread = np.linalg.inv(x.T @ x)
    beta = bread @ x.T @ y
    errors = y - x @ beta
    scores = x * errors[:, None]
    correction = groups / (groups - 2)
    covariance = correction * bread @ scores.T @ scores @ bread
    return {
        **_inference(float(beta[1]), float(covariance[1, 1]), groups - 2),
        "n_obs": groups,
        "n_links": groups,
        "n_clusters": groups,
        "n_periods": 2,
        "finite_sample_correction": correction,
        "covariance": "HC1",
        "intercept_mph": float(beta[0]),
    }


def common_roster(panel: pd.DataFrame, sample: str) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Apply the existing sample cut and retain links with observed pre/post outcomes."""
    if sample not in SAMPLES:
        raise ValueError(f"unregistered sample: {sample}")
    work = panel[panel["treatment_group"].isin(["treated", "control"])].copy()
    group_rows = len(work)
    work["ts_hour"] = pd.to_datetime(work["ts_hour"], errors="raise")
    if work["ts_hour"].isna().any() or work["ts_hour"].dt.tz is not None:
        raise AnalysisFailure("timestamps must be nonmissing naive local wall clock")
    for flag in ("treated", "post", "is_peak", "is_weekend"):
        if work[flag].isna().any() or not work[flag].isin([True, False]).all():
            raise AnalysisFailure(f"invalid {flag} flag")
        work[flag] = work[flag].astype(bool)
    if not work["treated"].equals(work["treatment_group"].eq("treated")):
        raise AnalysisFailure("treated flag differs from frozen geometric assignment")
    if not work["post"].equals(work["ts_hour"].ge(pd.Timestamp(TREATMENT_DATE))):
        raise AnalysisFailure("post flag differs from January 5 treatment date")
    if work.duplicated(["link_id", "ts_hour"]).any() or work["link_id"].isna().any():
        raise AnalysisFailure("hourly panel contains a duplicate or null link-time key")
    if work.groupby("link_id")["treated"].nunique().gt(1).any():
        raise AnalysisFailure("a link changes treatment assignment")
    if sample == "peak":
        work = work[work["is_peak"] & ~work["is_weekend"]]
    elif sample == "offpeak":
        work = work[~work["is_peak"] & ~work["is_weekend"]]
    elif sample == "weekend":
        work = work[work["is_weekend"]]
    cut_rows = len(work)
    work = work.dropna(subset=[OUTCOME]).copy()
    observed_rows = len(work)
    roster = work.groupby(["link_id", "treated"], as_index=False).agg(
        n_hourly=(OUTCOME, "size"), n_post_hours=("post", "sum")
    )
    roster["n_pre_hours"] = roster["n_hourly"] - roster["n_post_hours"]
    roster["retained"] = roster["n_pre_hours"].gt(0) & roster["n_post_hours"].gt(0)
    roster["exclusion_reason"] = np.where(roster["retained"], "", "no observed pre/post support")
    roster["sample"] = sample
    work = work[work["link_id"].isin(roster.loc[roster["retained"], "link_id"])].copy()
    counts = {
        "sample": sample,
        "n_input_panel_hours": len(panel),
        "n_excluded_other_group_hours": len(panel) - group_rows,
        "n_excluded_sample_cut_hours": group_rows - cut_rows,
        "n_excluded_missing_outcome_hours": cut_rows - observed_rows,
        "n_excluded_no_prepost_hours": observed_rows - len(work),
        "n_excluded_no_prepost_links": int((~roster["retained"]).sum()),
        "n_common_hourly": len(work),
        "n_pre_hours": int((~work["post"]).sum()),
        "n_post_hours": int(work["post"].sum()),
        "n_treated_links": int(work.loc[work["treated"], "link_id"].nunique()),
        "n_control_links": int(work.loc[~work["treated"], "link_id"].nunique()),
    }
    log.info(
        "%s: %d panel hours -> %d group hours -> %d cut hours -> %d observed -> %d "
        "common-roster hours (drops: other groups, sample cut, null outcome, pre/post support)",
        sample,
        len(panel),
        group_rows,
        cut_rows,
        observed_rows,
        len(work),
    )
    return work, counts, roster


def summarize(estimates: pd.DataFrame) -> dict:
    """Apply frozen thresholds to prospectively amended peak; failures take precedence."""
    primary = estimates[estimates["sample"].eq(PRIMARY_SAMPLE)]
    failures = estimates[estimates["status"].ne("ok")][["sample", "specification", "reason"]]
    result = {
        "verdict": "uninformative",
        "primary_sample": PRIMARY_SAMPLE,
        "lead_specification": LEAD_SPECIFICATION,
        "magnitude_component": None,
        "precision_component": None,
        "failures": failures.to_dict("records"),
        "limitations": LIMITATIONS,
    }
    if len(primary) != 3 or set(primary["specification"]) != set(SPECIFICATIONS):
        result["reason"] = "peak specification rows are missing or duplicated"
        return result
    if primary["status"].ne("ok").any():
        result["reason"] = "peak support, identification, or numerical failure takes precedence"
        return result
    aggregates = primary[primary["specification"].ne("hourly")]
    magnitude = bool(
        (aggregates["beta_mph"].gt(0) & aggregates["beta_difference_mph"].abs().le(0.25)).all()
    )
    precision = bool(aggregates["se_ratio"].le(1.5).all())
    result.update(
        magnitude_component="supports" if magnitude else "refutes",
        precision_component="supports" if precision else "refutes",
        verdict=(
            "supports aggregation stability"
            if magnitude and precision
            else "refutes aggregation stability"
        ),
        reason=(
            "Prospectively amended peak descriptive criteria applied; "
            "secondary results retained separately."
        ),
    )
    return result


def analyze_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Evaluate all frozen cuts on a caller-supplied, already-gated panel (or synthetic fixture)."""
    rows, exclusions, rosters = [], [], []
    for sample in SAMPLES:
        try:
            hourly, counts, roster = common_roster(panel, sample)
        except (AnalysisFailure, ValueError, KeyError, TypeError) as exc:
            rows.extend(_failure(sample, spec, str(exc)) for spec in SPECIFICATIONS)
            continue
        exclusions.append(counts)
        rosters.append(roster)
        count_fields = {
            k: counts[k]
            for k in (
                "n_common_hourly",
                "n_treated_links",
                "n_control_links",
                "n_pre_hours",
                "n_post_hours",
            )
        }
        if counts["n_treated_links"] == 0 or counts["n_control_links"] == 0:
            rows.extend(
                _failure(
                    sample,
                    spec,
                    "common pre/post roster lacks treated or control links",
                    **count_fields,
                )
                for spec in SPECIFICATIONS
            )
            continue
        for spec in SPECIFICATIONS:
            try:
                if spec == "hourly":
                    estimate = _twfe(hourly, "ts_hour")
                elif spec == "daily":
                    estimate = _twfe(daily_panel(hourly), "date")
                else:
                    estimate = _collapsed(collapsed_panel(hourly))
                rows.append(
                    {
                        "sample": sample,
                        "specification": spec,
                        "status": "ok",
                        "reason": "",
                        **count_fields,
                        **estimate,
                    }
                )
            except (AnalysisFailure, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                rows.append(_failure(sample, spec, str(exc), **count_fields))
    estimates = pd.DataFrame(rows)
    estimates["beta_difference_mph"] = np.nan
    estimates["se_ratio"] = np.nan
    for sample in SAMPLES:
        reference = estimates[
            estimates["sample"].eq(sample) & estimates["specification"].eq("hourly")
        ].iloc[0]
        if reference["status"] == "ok":
            matched = estimates["sample"].eq(sample) & estimates["status"].eq("ok")
            estimates.loc[matched, "beta_difference_mph"] = (
                estimates.loc[matched, "beta_mph"] - reference["beta_mph"]
            )
            estimates.loc[matched, "se_ratio"] = (
                estimates.loc[matched, "se_mph"] / reference["se_mph"]
            )
    return (
        estimates,
        pd.DataFrame(exclusions),
        pd.concat(rosters, ignore_index=True) if rosters else pd.DataFrame(),
        summarize(estimates),
    )


def _build_fixed_panel(raw_dir: Path, targets: dict, work_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Existing SQL and geometry, bound to exact paths in an isolated in-memory database."""
    work_dir.mkdir(parents=True, exist_ok=True)
    segments_path = raw_dir / "ezpass_segments.parquet"
    segments = pd.read_parquet(segments_path)
    segments["treatment_group"] = [
        classify_segment(name, borough, polyline)
        for name, borough, polyline in zip(
            segments.link_name, segments.borough, segments.polyline, strict=True
        )
    ]
    segments["roadway"] = [roadway_of(name) for name in segments.link_name]
    assignment_path = work_dir / "H003_segment_treatment.parquet"
    segments.to_parquet(assignment_path, index=False)
    paths = [str(raw_dir / "ezpass_speeds" / part["part"]) for part in targets["parts"]]
    with duckdb.connect() as con:
        con.execute(
            (PROJECT_ROOT / "sql/01_stage_ezpass.sql").read_text(),
            {
                "parts_glob": paths,
                "segments_path": str(segments_path),
            },
        )
        staged = con.execute("SELECT count(*) FROM stg_speed_readings").fetchone()[0]
        null_speed, ambiguous, union = con.execute(
            "SELECT count(*) FILTER (WHERE speed_mph IS NULL), "
            "count(*) FILTER (WHERE is_dst_ambiguous_hour), "
            "count(*) FILTER (WHERE speed_mph IS NULL OR is_dst_ambiguous_hour) "
            "FROM stg_speed_readings"
        ).fetchone()
        con.execute(
            (PROJECT_ROOT / "sql/03_hourly_panel.sql").read_text(),
            {
                "treatment_path": str(assignment_path),
            },
        )
        panel = con.execute("SELECT * FROM hourly_panel ORDER BY link_id, ts_hour").df()
    panel_path = work_dir / "H003_hourly_panel.parquet"
    panel.to_parquet(panel_path, index=False)
    raw_rows = sum(part["rows"] for part in targets["parts"])
    funnel = {
        "raw_rows": raw_rows,
        "staged_rows": staged,
        "null_key_or_window_dedup_drops": raw_rows - staged,
        "null_speed_readings": null_speed,
        "dst_ambiguous_readings": ambiguous,
        "null_speed_or_dst_reading_drops": union,
        "retained_readings": staged - union,
        "hourly_panel_rows": len(panel),
        "panel_sha256": _digest(panel_path),
        "assignment_sha256": _digest(assignment_path),
    }
    log.info(
        "fixed snapshot: %d raw -> %d staged (null keys/window dedup) -> %d usable "
        "(null speed/DST ambiguity) -> %d hourly median cells",
        raw_rows,
        staged,
        staged - union,
        len(panel),
    )
    return panel, funnel


def _code_provenance() -> dict:
    source = sorted([*PROJECT_ROOT.glob("src/**/*.py"), *PROJECT_ROOT.glob("sql/*.sql")])
    source += [PROJECT_ROOT / "docs/hypotheses/H003-temporal-aggregation.md"]

    def git(*args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=PROJECT_ROOT, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"

    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "code_commit": git("rev-parse", "HEAD"),
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "priority_amendment_commit": PRIORITY_AMENDMENT_COMMIT,
        "git_status": git("status", "--porcelain"),
        "source_sha256": {
            str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): _digest(path) for path in source
        },
        "python": platform.python_version(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("pandas", "numpy", "duckdb", "scipy", "pyarrow")
        },
    }


def _capture_h001(path: Path | None, output_dir: Path) -> dict:
    note = (
        "H001 is the completed control-only placebo exercise, read without rerunning it. "
        "It probes a different sampling distribution: pseudo-treatment group sizes and "
        "geographically dispersed partitions may alter the spread. Its empirical tail "
        "fractions are not exact randomization p-values. H003 instead changes temporal "
        "aggregation, weights and fixed effects. Neither establishes causal identification."
    )
    if path is None or not path.is_file():
        return {"status": "unavailable", "note": note}
    destination = output_dir / "H003_H001_existing_result.csv"
    shutil.copyfile(path, destination)
    return {
        "status": "saved existing artifact; not rerun",
        "source_path": str(path.resolve()),
        "source_mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "source_bytes": path.stat().st_size,
        "sha256": _digest(destination),
        "rows": pd.read_csv(destination).replace({np.nan: None}).to_dict("records"),
        "note": note,
    }


def _write_report(
    output_dir: Path, estimates: pd.DataFrame, verdict: dict, provenance: dict
) -> None:
    lines = [
        "# H003 temporal aggregation sensitivity",
        "",
        f"Verdict: **{verdict['verdict']}**. Peak is the primary sample under the "
        f"prospective amendment ({PRIORITY_AMENDMENT_COMMIT}); daily peak is the lead metric.",
        "",
    ]
    lead = estimates[
        estimates["sample"].eq(PRIMARY_SAMPLE) & estimates["specification"].eq(LEAD_SPECIFICATION)
    ].iloc[0]
    if lead["status"] == "ok":
        lines += [
            f"Daily peak association: **{lead['beta_mph']:+.4f} mph**, SE {lead['se_mph']:.4f}; "
            f"95% CI [{lead['ci_low']:+.4f}, {lead['ci_high']:+.4f}], "
            f"two-sided p={lead['p_value']:.6g}, inference df={int(lead['df_inference'])}. "
            f"CI includes zero: {bool(lead['ci_includes_zero'])}. "
            f"Magnitude component: {verdict['magnitude_component']}; "
            f"precision component: {verdict['precision_component']}.",
            "",
        ]
    else:
        lines += [f"Daily peak is uninformative: {lead['reason']}.", ""]
    lines += [
        LIMITATIONS,
        "",
        "All registered results are retained in H003_results.csv. "
        "H003_exclusions.csv and H003_link_roster.csv account for the common roster.",
        "",
    ]
    for sample in SAMPLES:
        lines += [f"## {sample}", ""]
        for spec in ("daily", "hourly", "collapsed"):
            row = estimates[
                estimates["sample"].eq(sample) & estimates["specification"].eq(spec)
            ].iloc[0]
            if row["status"] != "ok":
                lines.append(f"- {spec}: uninformative — {row['reason']}.")
            else:
                lines.append(
                    f"- {spec}: beta {row['beta_mph']:+.4f} mph; SE {row['se_mph']:.4f}; "
                    f"95% CI [{row['ci_low']:+.4f}, {row['ci_high']:+.4f}]; "
                    f"p={row['p_value']:.6g}; n={int(row['n_obs'])}; "
                    f"links treated/control={int(row['n_treated_links'])}/"
                    f"{int(row['n_control_links'])}; df={int(row['df_inference'])}; "
                    f"beta-reference={row['beta_difference_mph']:+.4f}; "
                    f"SE/reference={row['se_ratio']:.4f}; "
                    f"CI includes zero={bool(row['ci_includes_zero'])}."
                )
        lines.append("")
    h001 = provenance.get("h001_existing_result", {})
    lines += [
        "## Completed H001 comparison",
        "",
        h001.get("note", "Existing H001 artifact unavailable for this attempt."),
        "",
    ]
    for row in h001.get("rows", []):
        lines.append(
            f"- {row['sample']}: {row['placebo_draws']} saved draws; placebo SD/analytic SE "
            f"{row['se_ratio']}; empirical coefficient tail fraction "
            f"{row.get('p_randomisation_beta', 'unavailable')}; pseudo-treated group size "
            f"{row.get('placebo_k', 'unavailable')}."
        )
    if h001.get("sha256"):
        lines += [
            "",
            f"Existing H001 bytes SHA256: {h001['sha256']}. Source: {h001['source_path']}.",
        ]
    lines += [
        "",
        "## Provenance and references",
        "",
        f"Code commit: {provenance.get('code_commit', 'unavailable')}. "
        f"Registration: {PREREGISTRATION_COMMIT}; priority amendment: {PRIORITY_AMENDMENT_COMMIT}. "
        "H003_provenance.json records input, receipt, code and output hashes and the source gate.",
        "",
    ]
    lines += [f"- {ref['citation']} {ref['url']}" for ref in REFERENCES]
    (output_dir / "H003_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    raw_dir: Path = RAW_DIR,
    targets_path: Path = PROJECT_ROOT / "docs/verification_targets.json",
    work_dir: Path = DATA_DIR / "H003_snapshot",
    output_dir: Path = TABLES_DIR,
    h001_result: Path | None = TABLES_DIR / "placebo_space.csv",
) -> dict:
    """Gate, rebuild, estimate once, and write H003 artifacts; failures remain explicit."""
    raw_dir, targets_path = Path(raw_dir).resolve(), Path(targets_path).resolve()
    work_dir, output_dir = Path(work_dir).resolve(), Path(output_dir).resolve()
    if any(path == raw_dir or raw_dir in path.parents for path in (work_dir, output_dir)):
        raise ValueError("H003 artifacts cannot be written into immutable raw data")
    output_dir.mkdir(parents=True, exist_ok=True)
    provenance = _code_provenance()
    written_paths: set[Path] = set()
    exclusions = pd.DataFrame(columns=["sample", "reason"])
    roster = pd.DataFrame(columns=["sample", "link_id", "retained", "exclusion_reason"])
    try:
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
        if _canonical_digest(targets) != TARGETS_CANONICAL_SHA256:
            raise AnalysisFailure(
                "verification targets differ from the committed H003 registration"
            )
        gate = verification_summary(raw_dir, targets_path)
        provenance["source_gate"] = gate
        if gate.get("gate_passed") is not True:
            raise AnalysisFailure("original-eight strict source verification gate failed")
        # Geometry is required even if an older implementation of the gate omits it.
        if _digest(raw_dir / "ezpass_segments.parquet") != targets["segments_sha256"]:
            raise AnalysisFailure("segment geometry SHA256 differs from registration")
        input_paths = [raw_dir / "ezpass_speeds" / part["part"] for part in targets["parts"]]
        input_paths += [raw_dir / "ezpass_segments.parquet", raw_dir / "ezpass_manifest.json"]
        input_paths += [
            raw_dir / "ezpass_verification" / f"ezpass_verify_{part['month']}.json"
            for part in targets["parts"]
        ]
        provenance["input_sha256"] = {
            str(path.relative_to(raw_dir)): _digest(path) for path in input_paths
        }
        provenance["targets_canonical_sha256"] = _canonical_digest(targets)
        shutil.copyfile(targets_path, output_dir / "H003_verification_targets.json")
        shutil.copyfile(raw_dir / "ezpass_manifest.json", output_dir / "H003_source_manifest.json")
        written_paths.update(
            output_dir / name
            for name in ("H003_verification_targets.json", "H003_source_manifest.json")
        )
        for part in targets["parts"]:
            shutil.copyfile(
                raw_dir / "ezpass_verification" / f"ezpass_verify_{part['month']}.json",
                output_dir / f"H003_receipt_{part['month']}.json",
            )
            written_paths.add(output_dir / f"H003_receipt_{part['month']}.json")
        panel, provenance["panel_build"] = _build_fixed_panel(raw_dir, targets, work_dir)
        # Refuse a mixed snapshot if an input changed while staging.
        if any(
            _digest(path) != provenance["input_sha256"][str(path.relative_to(raw_dir))]
            for path in input_paths
        ):
            raise AnalysisFailure(
                "an input or source receipt changed during the isolated panel rebuild"
            )
        estimates, exclusions, roster, verdict = analyze_panel(panel)
        provenance["h001_existing_result"] = _capture_h001(h001_result, output_dir)
        if provenance["h001_existing_result"].get("sha256"):
            written_paths.add(output_dir / "H003_H001_existing_result.csv")
    except (AnalysisFailure, OSError, ValueError, KeyError, TypeError, duckdb.Error) as exc:
        log.error("H003 uninformative: %s", exc)
        estimates = pd.DataFrame(
            [_failure(sample, spec, str(exc)) for sample in SAMPLES for spec in SPECIFICATIONS]
        )
        verdict = summarize(estimates)
        provenance["execution_failure"] = str(exc)
    exclusions.to_csv(output_dir / "H003_exclusions.csv", index=False)
    roster.to_csv(output_dir / "H003_link_roster.csv", index=False)
    estimates.to_csv(output_dir / "H003_results.csv", index=False)
    verdict["references"] = REFERENCES
    _json_write(output_dir / "H003_verdict.json", verdict)
    _write_report(output_dir, estimates, verdict, provenance)
    written_paths.update(
        output_dir / name
        for name in (
            "H003_exclusions.csv",
            "H003_link_roster.csv",
            "H003_results.csv",
            "H003_verdict.json",
            "H003_report.md",
        )
    )
    provenance["output_sha256"] = {path.name: _digest(path) for path in sorted(written_paths)}
    _json_write(output_dir / "H003_provenance.json", provenance)
    # Every completed attempt survives later reruns, including failed/null attempts.
    attempt_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    attempt_dir = output_dir / "H003_attempts" / attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=False)
    written_paths.add(output_dir / "H003_provenance.json")
    for path in written_paths:
        shutil.copyfile(path, attempt_dir / path.name)
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--targets", type=Path, default=PROJECT_ROOT / "docs/verification_targets.json"
    )
    parser.add_argument("--work-dir", type=Path, default=DATA_DIR / "H003_snapshot")
    parser.add_argument("--output-dir", type=Path, default=TABLES_DIR)
    parser.add_argument(
        "--h001-result",
        type=Path,
        default=TABLES_DIR / "placebo_space.csv",
        help="saved H001 CSV to capture without rerunning",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    verdict = run(args.raw_dir, args.targets, args.work_dir, args.output_dir, args.h001_result)
    log.info("H003 verdict: %s", verdict["verdict"])
    # A retained uninformative result is successful scientific work; the hosted
    # caller must commit it just as it commits support or refutation.


if __name__ == "__main__":
    main()
