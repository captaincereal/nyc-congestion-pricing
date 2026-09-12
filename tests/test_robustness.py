"""Sensitivity transformations that could silently change the counterfactual."""

import pandas as pd
import pytest

from src.analysis.robustness import TOLL_START, prepare_spec


@pytest.fixture
def panel():
    rows = []
    for link, group, borough, roadway in [
        ("T", "treated", "Manhattan", "42nd Street"),
        ("M", "control", "Manhattan", "125th Street"),
        ("Q", "control", "Queens", "Queens Boulevard"),
        ("E", "exempt_in_zone", "Manhattan", "11th Avenue"),
        ("B", "boundary", "Manhattan", "Broadway"),
    ]:
        for date in [
            "2024-06-01",
            "2024-10-01",
            "2024-11-20",
            "2024-12-25",
            "2025-01-10",
            "2025-02-01",
        ]:
            rows.append(
                {
                    "link_id": link,
                    "treatment_group": group,
                    "borough": borough,
                    "roadway": roadway,
                    "ts_hour": pd.Timestamp(date),
                    "median_speed_mph": 10.0,
                    "mean_speed_mph": 20.0,
                    "n_obs": 4,
                    "min_n_samples": 5,
                    "n_over_80": 0,
                }
            )
    return pd.DataFrame(rows)


def test_placebo_uses_only_actual_preperiod_and_rebuilds_flags(panel):
    d, metadata = prepare_spec(panel, "placebo_2024_11_17")
    assert d["ts_hour"].max() < TOLL_START
    assert d["post"].equals(d["ts_hour"].ge(pd.Timestamp("2024-11-17")))
    assert d["treated_post"].equals(d["treated"] & d["post"])
    assert (d.loc[d["ts_hour"].eq(pd.Timestamp("2024-10-01")), "event_week"] == -7).all()
    assert metadata["treatment_date"] == "2024-11-17"


def test_control_restrictions_keep_treated_and_exclude_boundary(panel):
    m, _ = prepare_spec(panel, "manhattan_controls")
    q, _ = prepare_spec(panel, "outer_borough_controls")
    assert set(m["link_id"]) == {"T", "M"}
    assert set(q["link_id"]) == {"T", "Q"}


def test_separate_d3_and_mean_variants_do_not_mutate_panel(panel):
    original = panel.copy(deep=True)
    d, metadata = prepare_spec(panel, "eleventh_as_treated")
    assert d.loc[d["link_id"].eq("E"), "treated"].all()
    assert metadata["reassigned_links"] == 1
    means, metadata = prepare_spec(panel, "mean_outcome")
    assert means["median_speed_mph"].eq(20).all()
    assert metadata["outcome"] == "mean_speed_mph"
    pd.testing.assert_frame_equal(panel, original)


def test_transition_drops_exact_half_open_window(panel):
    d, _ = prepare_spec(panel, "drop_transition")
    assert (
        not d["ts_hour"]
        .between(
            TOLL_START - pd.Timedelta(days=14), TOLL_START + pd.Timedelta(days=14), inclusive="left"
        )
        .any()
    )


def test_quality_and_common_roster_filters_are_explicit(panel):
    panel.loc[panel["link_id"].eq("T"), "min_n_samples"] = 3
    d, _ = prepare_spec(panel, "quality")
    assert "T" not in set(d["link_id"])
    panel = panel[~(panel["link_id"].eq("Q") & panel["ts_hour"].ge(TOLL_START))]
    d, _ = prepare_spec(panel, "common_link_roster")
    assert set(d["link_id"]) == {"T", "M"}
