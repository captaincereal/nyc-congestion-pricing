"""Placebo-in-space: the parts that would fail quietly.

The estimator itself is covered by test_did. What is specific here is the
construction of the null distribution, where a mistake produces a plausible
p-value rather than an error: a draw size that leaves no comparison group, a
pool that leaks the real treated links into their own null, or a p-value
formula that can return zero.
"""

import numpy as np
import pandas as pd

from src.analysis.placebo_space import _p, placebo_draws, placebo_k


def test_draw_size_preserves_the_real_treated_share():
    # The real design is 148 treated against 177 controls, a 45.5% share.
    # Splitting 177 in the same proportion gives 81 vs 96.
    assert placebo_k(148, 177) == 81


def test_draw_size_never_starves_the_comparison_group():
    """A draw must leave links on both sides or the DiD is not identified."""
    for n_treated, n_control in [(1000, 10), (5, 4), (1, 3), (148, 177)]:
        k = placebo_k(n_treated, n_control)
        assert 1 <= k <= n_control - 1, (n_treated, n_control, k)


def test_p_value_counts_the_observed_assignment():
    """(1 + hits) / (1 + draws) — never zero, because the real draw counts too.

    A bare hits/draws would report p = 0 when no placebo exceeds the estimate,
    which claims more than a finite set of draws can support.
    """
    null = np.array([0.1, -0.2, 0.3])
    assert _p(null, 99.0) == 0.25  # nothing exceeds it: 1/4, not 0
    assert _p(null, 0.0) == 1.0  # everything does: 4/4


def test_p_value_is_two_sided():
    """Sign should not matter; a large negative placebo counts against a
    large positive estimate."""
    null = np.array([-5.0, -5.0, -5.0])
    assert _p(null, 4.0) == 1.0


def test_p_value_ignores_failed_draws():
    null = np.array([0.1, np.nan, 0.2])
    assert _p(null, 99.0) == 1 / 3  # two usable draws, none exceeding


def _panel(n_links: int = 12, n_hours: int = 8, seed: int = 0) -> pd.DataFrame:
    """A small control-only panel with no treatment effect in it."""
    rng = np.random.default_rng(seed)
    hours = pd.date_range("2024-12-30", periods=n_hours, freq="D")
    rows = []
    for link in range(n_links):
        for h in hours:
            rows.append(
                {
                    "link_id": f"L{link}",
                    "ts_hour": h,
                    "median_speed_mph": 15 + rng.normal(0, 1),
                    "post": h >= pd.Timestamp("2025-01-05"),
                }
            )
    return pd.DataFrame(rows)


def test_draws_vary_and_centre_near_zero_on_data_with_no_effect():
    """The null must actually be a distribution, not a constant.

    If every draw returned the same number the p-value would be meaningless,
    and on data containing no effect the draws should straddle zero.
    """
    betas, ts, _, _ = placebo_draws(_panel(), k=5, draws=24, rng=np.random.default_rng(20250105))
    usable = betas[np.isfinite(betas)]
    assert len(usable) >= 20
    assert usable.std() > 0, "every draw produced the same estimate"
    assert abs(np.median(usable)) < 1.0, "null is not centred near zero"
    assert np.isfinite(ts).sum() >= 20


def test_draws_are_reproducible_from_the_seed():
    a, _, _, _ = placebo_draws(_panel(), k=5, draws=8, rng=np.random.default_rng(7))
    b, _, _, _ = placebo_draws(_panel(), k=5, draws=8, rng=np.random.default_rng(7))
    np.testing.assert_allclose(a, b)
