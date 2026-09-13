"""H007: the acceptance criteria, and the quantities they are read off.

The record's Prediction and Acceptance criteria are frozen. `verdict` is where
they get applied, so it is pinned here against each branch rather than checked
by eye on one run — a criterion quietly reinterpreted is the exact failure
`docs/hypotheses/README.md` exists to prevent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.h007_diversion import (
    ALPHA,
    availability_gate,
    availability_monthly,
    estimation_frame,
    minimum_detectable_effect,
    significance_threshold,
    to_monthly_event_time,
    verdict,
)
from src.analysis.placebo_space import _p


def _avail_panel(treated_usable: dict, control_usable: dict, per_month: int = 100):
    """A panel whose usable-hour share per group per month is set by hand."""
    rows = []
    for group, schedule in (("treated", treated_usable), ("control", control_usable)):
        for month, share in schedule.items():
            usable = round(share * per_month)
            for i in range(per_month):
                rows.append(
                    {
                        "link_id": f"{group}_1",
                        "ts_hour": pd.Timestamp(month) + pd.Timedelta(hours=i),
                        "treated": group == "treated",
                        "has_speed": i < usable,
                        "n_readings": 10,
                        "n_positive": 10 if i < usable else 0,
                    }
                )
    return pd.DataFrame(rows)


def test_availability_gate_is_a_difference_in_differences_of_shares():
    """Treated 90% -> 60% while control 80% -> 75% is -30 against -5, i.e. -25 pp."""
    panel = _avail_panel(
        {"2024-12-01": 0.90, "2025-01-01": 0.60},
        {"2024-12-01": 0.80, "2025-01-01": 0.75},
    )
    gate = availability_gate(availability_monthly(panel), "all")
    assert gate["treated_change_pp"] == pytest.approx(-30.0)
    assert gate["control_change_pp"] == pytest.approx(-5.0)
    assert gate["differential_change_pp"] == pytest.approx(-25.0)
    assert gate["criterion_1_passes"] is False


def test_availability_gate_passes_when_the_groups_move_together():
    """Both groups losing the same share is not a selection problem."""
    panel = _avail_panel(
        {"2024-12-01": 0.90, "2025-01-01": 0.60},
        {"2024-12-01": 0.85, "2025-01-01": 0.56},
    )
    gate = availability_gate(availability_monthly(panel), "all")
    assert abs(gate["differential_change_pp"]) < 5
    assert gate["criterion_1_passes"] is True


def test_availability_bar_is_exclusive_at_five_points():
    """The record says 'under 5 percentage points' supports and '5 or more'
    refutes, so a differential of exactly 5 refutes."""
    panel = _avail_panel(
        {"2024-12-01": 0.90, "2025-01-01": 0.85},
        {"2024-12-01": 0.90, "2025-01-01": 0.90},
    )
    gate = availability_gate(availability_monthly(panel), "all")
    assert gate["differential_change_pp"] == pytest.approx(-5.0)
    assert gate["criterion_1_passes"] is False
    just_inside = _avail_panel(
        {"2024-12-01": 0.90, "2025-01-01": 0.86},
        {"2024-12-01": 0.90, "2025-01-01": 0.90},
    )
    assert availability_gate(availability_monthly(just_inside), "all")["criterion_1_passes"] is True


def test_availability_counts_hours_not_readings():
    """One positive reading in an hour makes that hour usable.

    The reading-level zero rate and the hour-level availability are different
    statistics, and criterion 1 is written on the second. A group can lose most
    of its readings without losing a single hour.
    """
    panel = _avail_panel({"2024-12-01": 1.0}, {"2024-12-01": 1.0})
    panel.loc[panel["treated"], "n_positive"] = 1  # 1 of 10 readings, still usable
    monthly = availability_monthly(panel)
    treated = monthly[monthly["group"] == "treated"].iloc[0]
    assert treated["availability"] == 1.0
    assert treated["positive_reading_share"] == 0.1


def _es_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_week": [-4, -1, 0, 3],
            "event_month": [-1, 0, 0, 1],
            "median_speed_mph": [30.0, 31.0, 29.0, 28.0],
        }
    )


def test_monthly_event_time_is_written_where_build_dummies_looks():
    """`event_study.build_dummies` reads `event_week`. Monthly bins get put
    there, and the weekly index is kept so nothing is lost silently."""
    out = to_monthly_event_time(_es_frame())
    assert list(out["event_week"]) == [-1, 0, 0, 1]
    assert list(out["event_week_true"]) == [-4, -1, 0, 3]
    assert list(out["event_month"]) == [-1, 0, 0, 1]


def test_estimation_frame_drops_the_unusable_hours():
    df = pd.DataFrame({"median_speed_mph": [30.0, np.nan, 28.0], "link_id": ["a", "a", "b"]})
    assert len(estimation_frame(df)) == 2


def test_significance_threshold_matches_the_randomisation_p_value():
    """The threshold is only meaningful if `_p` agrees with it at the boundary.

    `_p` is (1 + hits) / (1 + draws), so with 500 draws p <= 0.05 needs at most
    24 draws matching or beating the observation. An estimate just above the
    threshold must score at or below 0.05 and one just below it must not.
    """
    rng = np.random.default_rng(0)
    null = rng.normal(size=500)
    threshold = significance_threshold(null, 500)
    assert _p(null, threshold + 1e-9) <= ALPHA
    assert _p(null, threshold - 1e-9) > ALPHA


def test_significance_threshold_needs_enough_draws_to_reject_at_all():
    """With 18 draws the smallest attainable p is 1/19 = 0.053, so nothing can
    reach 5% and the honest threshold is infinite rather than some number."""
    null = np.linspace(-1, 1, 18)
    assert significance_threshold(null, 18) == float("inf")
    assert significance_threshold(null, 500) < float("inf")


def test_minimum_detectable_effect_clears_the_threshold_with_the_stated_power():
    """A constant effect shifts the estimator by exactly that amount, so power
    is the share of the null distribution that clears the threshold once
    shifted. At the MDE it is 80%; a shade below, less."""
    rng = np.random.default_rng(1)
    null = rng.normal(scale=2.0, size=500)
    threshold = significance_threshold(null, 500)
    mde = minimum_detectable_effect(null, 500, power=0.80)
    assert np.mean(np.abs(null + mde) >= threshold) >= 0.80
    assert np.mean(np.abs(null + mde * 0.9) >= threshold) < 0.80


def test_minimum_detectable_effect_grows_with_a_wider_null():
    """A noisier design catches less. This is the number that makes an
    uninformative verdict readable."""
    rng = np.random.default_rng(2)
    tight = minimum_detectable_effect(rng.normal(scale=0.5, size=500), 500)
    wide = minimum_detectable_effect(rng.normal(scale=5.0, size=500), 500)
    assert wide > tight


# --- the frozen acceptance criteria -----------------------------------------


def _gate(differential_pp: float) -> dict:
    return {
        "differential_change_pp": differential_pp,
        "criterion_1_passes": abs(differential_pp) < 5.0,
    }


def _pretrend(p: float | None) -> dict:
    if p is None:
        return {"verdict": "UNTESTABLE", "p_value": np.nan, "test_reason": "singular covariance"}
    return {"verdict": "PASS" if p > ALPHA else "FAIL", "p_value": p, "test_reason": ""}


def _ri(p: float) -> dict:
    return {
        "criterion_3_passes": p < ALPHA,
        "p_randomisation_beta": p,
        "mde_80_power_mph": 2.5,
    }


def test_all_three_conditions_holding_supports():
    label, _ = verdict(_gate(1.0), _pretrend(0.40), _ri(0.01), breakdown=1.2)
    assert label == "SUPPORTS"


def test_availability_alone_refutes():
    """Criterion 1 is a gate. It refutes on its own, whatever the estimate says."""
    label, reason = verdict(_gate(-21.2), _pretrend(0.40), _ri(0.001), breakdown=3.0)
    assert label == "REFUTES"
    assert "availability" in reason


def test_a_rejected_pre_trend_alone_refutes():
    label, reason = verdict(_gate(1.0), _pretrend(1e-13), _ri(0.001), breakdown=3.0)
    assert label == "REFUTES"
    assert "pre-trend" in reason


def test_a_low_breakdown_value_alone_refutes():
    label, reason = verdict(_gate(1.0), _pretrend(0.40), _ri(0.001), breakdown=0.2)
    assert label == "REFUTES"
    assert "breakdown" in reason


def test_every_failed_condition_is_named_not_just_the_first():
    """Which conditions failed is the finding. Reporting only the first would
    lose the difference between one broken diagnostic and three."""
    label, reason = verdict(_gate(-21.2), _pretrend(1e-13), _ri(0.9), breakdown=0.1)
    assert label == "REFUTES"
    assert "availability" in reason and "pre-trend" in reason and "breakdown" in reason


def test_clean_diagnostics_with_a_null_estimate_are_uninformative_not_refuting():
    """Nine treated links is a small design. Failing to find an effect in it is
    not evidence that none occurred, and the MDE has to come with the verdict."""
    label, reason = verdict(_gate(1.0), _pretrend(0.40), _ri(0.62), breakdown=1.2)
    assert label == "UNINFORMATIVE"
    assert "MDE" in reason


def test_an_untestable_pre_trend_is_uninformative_not_supporting():
    label, reason = verdict(_gate(1.0), _pretrend(None), _ri(0.001), breakdown=1.2)
    assert label == "UNINFORMATIVE"
    assert "untestable" in reason


def test_an_uncomputed_breakdown_value_cannot_be_read_as_support():
    """One of the three refutation conditions is then unevaluated, so support
    would be claiming a check that never ran."""
    label, reason = verdict(_gate(1.0), _pretrend(0.40), _ri(0.001), breakdown=float("nan"))
    assert label == "UNINFORMATIVE"
    assert "unevaluated" in reason


def test_the_breakdown_bar_is_exclusive_at_half():
    """'below 0.5' refutes, so exactly 0.5 does not."""
    assert verdict(_gate(1.0), _pretrend(0.4), _ri(0.01), breakdown=0.5)[0] == "SUPPORTS"
    assert verdict(_gate(1.0), _pretrend(0.4), _ri(0.01), breakdown=0.49)[0] == "REFUTES"
