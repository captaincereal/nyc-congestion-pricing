"""Phase 8 event-study estimator, on a small synthetic panel (no SQL layer)."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.event_study import (
    PRETREND_METHOD,
    REFERENCE_K,
    build_dummies,
    coef_frame,
    estimate,
    pretrend_test,
    record_pretrend,
)


def _panel():
    """4 links (2 treated, 2 control) x 4 event weeks x 4 hours = 64 rows.

    Treated links get a clean +2 mph jump from event_week 0 onward; control
    links carry no jump. No noise, so the recovered post coefficients should
    land close to +2 and the pre-period ones close to 0.
    """
    rng = np.random.default_rng(0)
    rows = []
    weeks = [-2, -1, 0, 1]
    for link, treated, base in (
        ("T1", True, 10.0),
        ("T2", True, 12.0),
        ("C1", False, 20.0),
        ("C2", False, 22.0),
    ):
        for w in weeks:
            jump = 2.0 if (treated and w >= 0) else 0.0
            for h in range(4):
                ts = pd.Timestamp("2025-01-05") + pd.Timedelta(weeks=w, hours=h)
                # A little noise keeps the regression non-degenerate (an exactly
                # noiseless panel can leave zero residual variance on some
                # dummy, which makes the cluster-robust SE ill-defined - not a
                # real-data concern, just an artifact of a toy fixture).
                rows.append(
                    {
                        "link_id": link,
                        "treated": treated,
                        "ts_hour": ts,
                        "event_week": w,
                        "median_speed_mph": base + jump + rng.normal(0, 0.01),
                    }
                )
    return pd.DataFrame(rows)


def test_build_dummies_folds_control_to_reference():
    df, cols = build_dummies(_panel(), horizon=12)
    # every control row lands on the reference bin, so it gets no dummy = 1
    control_rows = df[~df["treated"]]
    assert (control_rows[cols] == 0).all().all()
    # every treated row away from k=-1 gets exactly one dummy = 1
    treated_non_ref = df[df["treated"] & (df["event_week"] != REFERENCE_K)]
    assert (treated_non_ref[cols].sum(axis=1) == 1).all()


def test_build_dummies_clips_to_horizon():
    panel = _panel()
    panel.loc[panel["event_week"] == -2, "event_week"] = -10
    df, cols = build_dummies(panel, horizon=2)
    assert "k_m10" not in cols
    assert "k_m2" in cols
    assert (df.loc[df["treated"] & df["event_week"].eq(-10), "k"] == -2).all()
    # Pooling endpoints must never absorb earlier weeks into the reference.
    assert (df.loc[df["treated"] & df["k"].eq(REFERENCE_K), "event_week"] == -1).all()


def test_horizon_cannot_pool_the_reference_week():
    with pytest.raises(ValueError, match="single-week reference"):
        build_dummies(_panel(), horizon=1)


def test_missing_treated_reference_cannot_produce_unidentified_estimates():
    panel = _panel()
    panel = panel[~(panel["treated"] & panel["event_week"].eq(-1))]
    with pytest.raises(ValueError, match="reference week"):
        build_dummies(panel, horizon=12)


def test_estimate_recovers_the_injected_post_jump():
    df, cols = build_dummies(_panel(), horizon=2)
    result = estimate(df, cols)
    coefs = coef_frame(result, cols)
    assert coefs.loc[coefs["k"] == REFERENCE_K, "coef"].item() == 0.0
    pre = coefs[coefs["k"] < REFERENCE_K]["coef"]
    post = coefs[coefs["k"] >= 0]["coef"]
    assert np.allclose(pre, 0.0, atol=0.05)
    assert np.allclose(post, 2.0, atol=0.05)


def test_estimate_raises_on_no_variation_off_reference():
    # a "sample" containing only the reference week has no dummy columns at all
    df = _panel()
    df = df[df["event_week"] == REFERENCE_K]
    with pytest.raises(SystemExit):
        build_dummies(df, horizon=12)


def test_joint_pretrend_uses_correlations_and_parameter_order():
    # Perfectly plausible shared-reference covariance: diag-only would reject
    # (chi2=8, p=.018), but the actual joint Wald does not (chi2=4.02, p=.134).
    from scipy import stats

    result = {
        "dummy_cols": ["k_p0", "k_m2", "k_m3"],
        "beta": np.array([50.0, 2.0, 2.0]),
        "vcov": np.array([[10.0, 0, 0], [0, 1, 0.99], [0, 0.99, 1]]),
    }
    coefs = pd.DataFrame({"k": [-3, -1, -2, 0]})
    stat, p, dof = pretrend_test(coefs, result)
    assert stat == pytest.approx(8 / 1.99)
    assert p == pytest.approx(stats.chi2.sf(stat, 2))
    assert p > 0.05
    assert dof == 2
    assert result["pretrend_metadata"]["covariance_rank"] == 2
    assert result["pretrend_metadata"]["test_method"] == PRETREND_METHOD


def test_singular_joint_covariance_is_untestable():
    result = {
        "dummy_cols": ["k_m2", "k_m3"],
        "beta": np.array([2.0, 2.0]),
        "vcov": np.ones((2, 2)),
    }
    assert pretrend_test(pd.DataFrame({"k": [-3, -2]}), result) is None
    assert result["pretrend_metadata"]["test_status"] == "UNTESTABLE"
    assert result["pretrend_metadata"]["covariance_rank"] == 1


def test_weather_estimate_matches_explicit_fixed_effect_regression():
    import statsmodels.api as sm

    panel = _panel()
    rng = np.random.default_rng(92)
    panel["weather_interaction"] = panel["treated"] * rng.normal(size=len(panel))
    panel["median_speed_mph"] += 3 * panel["weather_interaction"]
    # Drop cells so one-pass demeaning would fail; this also validates the
    # efficient control projection on the actual unbalanced-panel use case.
    panel = panel.drop(index=[1, 5, 19, 36, 41])
    d, cols = build_dummies(panel, horizon=2)
    result = estimate(d, cols, controls=["weather_interaction"])
    effects = pd.get_dummies(d[["link_id", "ts_hour"]].astype(str), drop_first=True)
    design = sm.add_constant(pd.concat([d[cols + ["weather_interaction"]], effects], axis=1))
    explicit = sm.OLS(d["median_speed_mph"], design.astype(float)).fit()
    np.testing.assert_allclose(result["beta"], explicit.params[cols], atol=1e-8)
    assert result["vcov"].shape == (len(cols), len(cols))


def test_pooled_tail_and_untestable_results_are_recorded(tmp_path, monkeypatch):
    import src.analysis.event_study as event_study

    monkeypatch.setattr(event_study, "TABLES_DIR", tmp_path)
    panel = _panel()
    early = panel[panel["event_week"].eq(-2)].copy()
    early["event_week"] = -10
    early["ts_hour"] -= pd.Timedelta(weeks=8)
    d, cols = build_dummies(pd.concat([panel, early], ignore_index=True), horizon=2)
    result = estimate(d, cols)
    coefs = coef_frame(result, cols)
    tail = coefs.loc[coefs["k"].eq(-2)].iloc[0]
    assert tail["pooled_tail"]
    assert tail["observed_week_min"] == -10
    assert tail["observed_week_count"] == 2
    pt = pretrend_test(coefs, result)
    record_pretrend("all", pt, d, result)
    row = pd.read_csv(tmp_path / "pretrend_tests.csv").iloc[0]
    assert row["lead_count"] == 1
    assert row["pre_weeks"] == 2
    assert row["horizon"] == 2
    assert row["pre_tail_pooled"]
    assert row["tested_bin_min"] == -2
    assert row["observed_pre_week_min"] == -10

    # Failure to test must replace a stale PASS/FAIL row, never leave it behind.
    result["vcov"] = np.zeros_like(result["vcov"])
    assert pretrend_test(coefs, result) is None
    record_pretrend("all", None, d, result)
    rows = pd.read_csv(tmp_path / "pretrend_tests.csv")
    assert len(rows) == 1
    assert rows.iloc[0]["verdict"] == "UNTESTABLE"
