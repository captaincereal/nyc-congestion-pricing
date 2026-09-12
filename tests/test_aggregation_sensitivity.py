"""H003 on synthetic data only; no network or real estimators are exercised."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from src.analysis import aggregation_sensitivity as h003
from src.analysis import did


@pytest.fixture
def hourly():
    rng = np.random.default_rng(9273)
    rows = []
    for link in range(10):
        treated = link < 5
        for date in pd.date_range("2024-12-27", "2025-01-14", freq="D"):
            for hour in (7, 8, 12, 20):
                # Unbalanced support is intentional: one-shot demeaning is incorrect here.
                if rng.random() < 0.12:
                    continue
                ts = date + pd.Timedelta(hours=hour)
                post = ts >= pd.Timestamp("2025-01-05")
                y = 10 + link + date.day / 30 + hour / 7 + 0.8 * treated * post
                y += rng.normal(0, 0.7) + (link % 3) * post * 0.1
                rows.append(
                    (
                        str(link),
                        ts,
                        y,
                        treated,
                        post,
                        hour in (7, 8),
                        date.dayofweek >= 5,
                        "treated" if treated else "control",
                    )
                )
    return pd.DataFrame(
        rows,
        columns=[
            "link_id",
            "ts_hour",
            h003.OUTCOME,
            "treated",
            "post",
            "is_peak",
            "is_weekend",
            "treatment_group",
        ],
    )


def test_hourly_reference_matches_existing_estimator_and_cluster_t_inference(hourly):
    frame, _, _ = h003.common_roster(hourly, "all")
    actual = h003._twfe(frame, "ts_hour")
    expected = did.estimate(frame)
    for key in ("beta_mph", "se_mph", "ci_low", "ci_high", "p_value", "n_obs", "n_clusters"):
        assert actual[key] == pytest.approx(expected[key], abs=1e-12)
    assert actual["df_inference"] == frame.link_id.nunique() - 1


def test_daily_matches_explicit_dummy_ols_and_registered_correction(hourly):
    daily = h003.daily_panel(hourly)
    actual = h003._twfe(daily, "date")
    dummies = pd.get_dummies(daily[["link_id", "date"]].astype(str), drop_first=True, dtype=float)
    x = sm.add_constant(dummies)
    x["D"] = (daily.treated & daily.post).astype(float)
    fit = sm.OLS(daily[h003.OUTCOME], x).fit()
    assert actual["beta_mph"] == pytest.approx(fit.params["D"], abs=1e-9)
    robust = fit.get_robustcov_results(
        cov_type="cluster", groups=daily.link_id, use_correction=False
    )
    expected_se = robust.bse[-1] * np.sqrt(actual["finite_sample_correction"])
    assert actual["se_mph"] == pytest.approx(expected_se, abs=1e-9)


def test_collapse_directly_weights_hours_and_hc1_matches_statsmodels():
    rows = []
    for link, treated in enumerate((False, False, True, True)):
        for ts, y in (
            ("2025-01-03 08:00", 0),
            ("2025-01-04 07:00", 9),
            ("2025-01-04 08:00", 9),
            ("2025-01-05 08:00", 11 + link**2),
        ):
            rows.append((str(link), pd.Timestamp(ts), y, treated, ts >= "2025-01-05"))
    frame = pd.DataFrame(rows, columns=["link_id", "ts_hour", h003.OUTCOME, "treated", "post"])
    collapsed = h003.collapsed_panel(frame)
    assert collapsed.pre_mean_mph.tolist() == [6.0] * 4  # Equal-day means would be 4.5.
    assert not h003.daily_panel(frame).loc[lambda d: d.date.eq("2025-01-04"), "post"].any()
    assert h003.daily_panel(frame).loc[lambda d: d.date.eq("2025-01-05"), "post"].all()
    expected = sm.OLS(collapsed.change_mph, sm.add_constant(collapsed.treated.astype(float))).fit(
        cov_type="HC1", use_t=True
    )
    actual = h003._collapsed(collapsed)
    for key, value in (
        ("beta_mph", expected.params.iloc[1]),
        ("se_mph", expected.bse.iloc[1]),
        ("p_value", expected.pvalues.iloc[1]),
        ("ci_low", expected.conf_int().iloc[1, 0]),
    ):
        assert actual[key] == pytest.approx(value)
    assert actual["df_inference"] == 2


def test_common_roster_is_shared_and_records_preonly_exclusion(hourly):
    preonly = hourly[hourly.link_id.eq("0") & ~hourly.post].copy()
    preonly["link_id"] = "preonly"
    frame = pd.concat([hourly, preonly], ignore_index=True)
    estimates, exclusions, roster, _ = h003.analyze_panel(frame)
    assert len(estimates) == 12
    assert estimates.status.eq("ok").all()
    for sample in h003.SAMPLES:
        three = estimates[estimates["sample"].eq(sample)]
        assert three.n_links.tolist() == [10, 10, 10]
        assert three.n_treated_links.tolist() == [5, 5, 5]
        assert three.n_common_hourly.eq(three.n_common_hourly.iloc[0]).all()
        assert (
            exclusions.loc[exclusions["sample"].eq(sample), "n_excluded_no_prepost_links"].item()
            == 1
        )
    assert not roster.loc[roster.link_id.eq("preonly"), "retained"].any()


def test_nonconvergence_is_explicit(hourly):
    with pytest.raises(h003.AnalysisFailure, match="did not converge"):
        h003._absorb_checked(hourly, "ts_hour", max_iter=1, tol=1e-15)


def test_absorbed_treatment_and_zero_covariance_are_failures(hourly):
    # Both groups have pre/post observations but never share a datetime.
    shifted = hourly.copy()
    shifted.loc[shifted.treated, "ts_hour"] += pd.Timedelta(minutes=1)
    with pytest.raises(h003.AnalysisFailure, match="identifying within-variation"):
        h003._twfe(shifted, "ts_hour")
    with pytest.raises(h003.AnalysisFailure, match="nonpositive"):
        h003._inference(1, 0, 9)


def test_failures_are_preserved_and_primary_failure_overrides_thresholds(hourly):
    frame = hourly[hourly.treated].copy()
    estimates, _, _, verdict = h003.analyze_panel(frame)
    assert len(estimates) == 12
    assert estimates.status.eq("uninformative").all()
    assert verdict["verdict"] == "uninformative"
    estimates, _, _, _ = h003.analyze_panel(hourly)
    primary = estimates["sample"].eq("peak")
    estimates.loc[primary, "beta_mph"] = 1.0
    estimates.loc[primary, "beta_difference_mph"] = 0.25
    estimates.loc[primary, "se_ratio"] = 1.5
    assert h003.summarize(estimates)["verdict"] == "supports aggregation stability"
    estimates.loc[primary & estimates.specification.eq("daily"), "se_ratio"] = 1.50001
    verdict = h003.summarize(estimates)
    assert verdict["magnitude_component"] == "supports"
    assert verdict["precision_component"] == "refutes"
    estimates.loc[primary & estimates.specification.eq("daily"), "status"] = "uninformative"
    assert h003.summarize(estimates)["verdict"] == "uninformative"


def test_failed_gate_prevents_any_panel_build_or_estimation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(h003, "verification_summary", lambda *args: {"gate_passed": False})
    monkeypatch.setattr(h003, "_build_fixed_panel", lambda *args: calls.append("build"))
    monkeypatch.setattr(h003, "analyze_panel", lambda *args: calls.append("estimate"))
    monkeypatch.setattr(h003, "_code_provenance", lambda: {})
    output = tmp_path / "results"
    verdict = h003.run(raw_dir=tmp_path / "raw", work_dir=tmp_path / "work", output_dir=output)
    assert calls == []
    assert verdict["verdict"] == "uninformative"
    estimates = pd.read_csv(output / "H003_results.csv")
    assert len(estimates) == 12
    assert estimates.reason.str.contains("source verification gate failed").all()


def test_mutated_target_cannot_redefine_h003(tmp_path, monkeypatch):
    targets = tmp_path / "targets.json"
    targets.write_text('{"parts": []}')
    monkeypatch.setattr(h003, "_code_provenance", lambda: {})

    def should_not_run(*args):
        pytest.fail("altered targets must fail before gate/data access")

    monkeypatch.setattr(h003, "verification_summary", should_not_run)
    verdict = h003.run(tmp_path / "raw", targets, tmp_path / "work", tmp_path / "out")
    assert verdict["verdict"] == "uninformative"


def test_isolated_sql_build_does_not_glob_extra_parts(tmp_path):
    raw = tmp_path / "raw"
    parts = raw / "ezpass_speeds"
    parts.mkdir(parents=True)
    segments = pd.DataFrame(
        {
            "sid": ["1004"],
            "link_name": ["X St"],
            "borough": ["Queens"],
            "polyline": ["_p~iF~ps|U_ulLnnqC_mqNvxq`@"],
            "link_length_ft": [100],
        }
    )
    segments.to_parquet(raw / "ezpass_segments.parquet", index=False)
    sample = pd.DataFrame(
        {
            "sid": ["1004"],
            "median_calculation_timestamp": ["2025-01-04T08:00:00"],
            "median_speed_fps": [22],
            "median_tt_sec": [10],
            "n_samples": [10],
        }
    )
    sample.to_parquet(parts / "original.parquet", index=False)
    sample.assign(median_calculation_timestamp="2026-07-01T08:00:00").to_parquet(
        parts / "later_backfill.parquet", index=False
    )
    targets = {"parts": [{"part": "original.parquet", "rows": 1}]}
    panel, funnel = h003._build_fixed_panel(raw, targets, tmp_path / "isolated")
    assert len(panel) == 1
    assert panel.ts_hour.iloc[0] == pd.Timestamp("2025-01-04 08:00:00")
    assert not panel.post.iloc[0]
    assert panel[h003.OUTCOME].iloc[0] == pytest.approx(15)
    assert funnel["raw_rows"] == 1
    assert set(path.name for path in (tmp_path / "isolated").iterdir()) == {
        "H003_hourly_panel.parquet",
        "H003_segment_treatment.parquet",
    }


def test_h001_capture_preserves_exact_existing_bytes(tmp_path):
    source = tmp_path / "old.csv"
    content = b"sample,placebo_draws,se_ratio\nall,40,1.1\n"
    source.write_bytes(content)
    output = tmp_path / "results"
    output.mkdir()
    captured = h003._capture_h001(source, output)
    assert (output / "H003_H001_existing_result.csv").read_bytes() == content
    assert captured["sha256"] == hashlib.sha256(content).hexdigest()
    assert captured["rows"][0]["placebo_draws"] == 40
    assert "not exact randomization" in captured["note"]


def test_registered_targets_digest_is_line_ending_independent():
    target_path = Path(__file__).resolve().parents[1] / "docs/verification_targets.json"
    assert (
        h003._canonical_digest(json.loads(target_path.read_text())) == h003.TARGETS_CANONICAL_SHA256
    )


def test_report_leads_daily_peak_and_includes_all_registered_rows(hourly, tmp_path):
    estimates, _, _, verdict = h003.analyze_panel(hourly)
    h003._write_report(tmp_path, estimates, verdict, {"code_commit": "synthetic-test"})
    report = (tmp_path / "H003_report.md").read_text(encoding="utf-8")
    assert "Daily peak association:" in report
    assert report.index("## peak") < report.index("## all")
    assert report.count("CI includes zero=") == 12
    assert "synthetic-test" in report


def test_peak_priority_is_independent_of_secondary_thresholds(hourly):
    estimates, _, _, _ = h003.analyze_panel(hourly)
    primary = estimates["sample"].eq("peak")
    estimates.loc[primary, "beta_mph"] = 1.0
    estimates.loc[primary, "beta_difference_mph"] = 0.1
    estimates.loc[primary, "se_ratio"] = 1.2
    estimates.loc[~primary, "beta_mph"] = -10.0
    estimates.loc[~primary, "se_ratio"] = 20.0
    verdict = h003.summarize(estimates)
    assert verdict["verdict"] == "supports aggregation stability"
    assert verdict["primary_sample"] == "peak"
    assert verdict["lead_specification"] == "daily"
