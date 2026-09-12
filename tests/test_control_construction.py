"""H004 control construction: the properties that make the verdict trustworthy.

The headline number is a chi-squared statistic, and almost any bug here still
produces one. What has to hold is structural: the matching window and the
window used to judge it must not overlap, features must carry trajectory shape
and not level, and the synthetic weights must be an actual convex combination.
Break any of those and the exercise silently becomes the circular one it was
designed to avoid.
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.control_construction import (
    HOLDOUT_WEEKS,
    MATCH_WEEKS,
    link_features,
    rule_nearest,
    rule_synthetic,
    standardise,
)


def test_matching_and_holdout_windows_are_disjoint():
    """The integrity property of the whole design.

    If these overlapped, the rule would be judged partly on weeks it was fitted
    on, which is the circularity Roth (2022) warns about and the reason the
    split exists at all.
    """
    match = set(range(MATCH_WEEKS[0], MATCH_WEEKS[1] + 1))
    holdout = set(range(HOLDOUT_WEEKS[0], HOLDOUT_WEEKS[1] + 1))
    assert not (match & holdout)
    assert max(match) < min(holdout), "matching must come before the held-out window"


def _panel(n_links: int = 6, offset_per_link: float = 5.0) -> pd.DataFrame:
    """Links with identical trajectory shape but very different levels."""
    rows = []
    for i in range(n_links):
        for wk in range(MATCH_WEEKS[0], MATCH_WEEKS[1] + 1):
            for hour in (8, 17):
                rows.append(
                    {
                        "link_id": f"L{i}",
                        "event_week": wk,
                        "hour": hour,
                        "is_weekend": False,
                        "median_speed_mph": 10.0 + i * offset_per_link + 0.1 * wk,
                    }
                )
    return pd.DataFrame(rows)


def test_features_carry_shape_not_level():
    """Treated links sit near 7.9 mph and controls near 15.6. If level leaked
    into the features, every distance would be dominated by that gap and the
    matching would be geography by another name."""
    feats = link_features(_panel())
    wk_cols = [c for c in feats.columns if c.startswith("wk_")]
    block = feats[wk_cols].to_numpy()
    # Same shape, different levels -> identical rows after demeaning.
    assert np.allclose(block, block[0], atol=1e-9)


def test_standardise_survives_a_constant_feature():
    feats = pd.DataFrame({"varies": [1.0, 2.0, 3.0], "constant": [7.0, 7.0, 7.0]})
    z = standardise(feats)
    assert np.isfinite(z.to_numpy()).all()
    assert (z["constant"] == 0).all()


def test_nearest_rule_picks_from_donors_only_and_respects_the_count():
    z = pd.DataFrame(
        {"f": [0.0, 0.1, 5.0, 5.1, 0.05]},
        index=["t1", "d_close", "d_far", "d_farther", "d_closest"],
    )
    keep = rule_nearest(z, treated=["t1"], donors=["d_close", "d_far", "d_farther"], n=2)
    assert len(keep) == 2
    assert "t1" not in keep, "a treated link must never enter the donor pool"
    assert "d_closest" not in keep, "only listed donors are eligible"
    assert keep == ["d_close", "d_far"]


def test_synthetic_weights_form_a_convex_combination():
    """Non-negative and summing to one. Negative or unbounded weights would
    extrapolate outside the donor pool rather than interpolate within it."""
    donors = pd.DataFrame(
        [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0], [0.0, 0.0, 0.0]],
        index=["a", "b", "c"],
    )
    target = pd.Series([2.0, 2.0, 2.0])
    w, loss = rule_synthetic(target, donors)
    assert (w >= -1e-9).all()
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    assert loss >= 0


def test_synthetic_weights_recover_an_exact_donor_match():
    donors = pd.DataFrame([[1.0, 2.0, 3.0], [9.0, 9.0, 9.0]], index=["match", "other"])
    w, loss = rule_synthetic(pd.Series([1.0, 2.0, 3.0]), donors)
    assert w["match"] > 0.95
    assert loss == pytest.approx(0.0, abs=1e-6)
