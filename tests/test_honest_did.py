"""H002 sensitivity: the steps where a mistake produces a plausible number.

The bound computation itself is diff_diff's. What is ours, and what would fail
quietly, is the translation: parsing event times out of dummy names, ordering
the coefficient vector and its covariance consistently, and handing diff_diff a
container whose index mapping is right. A transposed or mis-sorted covariance
still yields a breakdown value; it is just the wrong one.
"""

import numpy as np
import pytest

from src.analysis.honest_did import _event_time, to_container


def test_event_time_parsing_round_trips():
    assert _event_time("k_m12") == -12
    assert _event_time("k_m1") == -1
    assert _event_time("k_p0") == 0
    assert _event_time("k_p7") == 7


def _moments(n_pre: int = 3, n_post: int = 2) -> dict:
    ks = [k for k in range(-n_pre - 1, 0) if k != -1] + list(range(n_post))
    n = len(ks)
    rng = np.random.default_rng(0)
    a = rng.normal(size=(n, n))
    vcov = a @ a.T + np.eye(n)  # symmetric positive definite
    return {
        "sample": "test",
        "k": ks,
        "beta": np.arange(n, dtype=float),
        "vcov": vcov,
        "se": np.sqrt(np.diag(vcov)),
        "min_eigenvalue": float(np.linalg.eigvalsh(vcov).min()),
        "n_obs": 1000,
        "n_clusters": 50,
        "horizon": 12,
    }


def test_container_splits_pre_and_post_at_the_reference_period():
    """k = -1 is the omitted reference and belongs to neither side."""
    c = to_container(_moments())
    assert c.pre_periods == [-4, -3, -2]
    assert c.post_periods == [0, 1]
    assert -1 not in c.pre_periods and -1 not in c.post_periods


def test_container_index_map_matches_covariance_rows():
    """Each event time must point at its own row, or the bounds use the wrong
    variances without any error being raised."""
    m = _moments()
    c = to_container(m)
    for k, i in c.interaction_indices.items():
        assert c.period_effects[k].effect == pytest.approx(m["beta"][i])
        assert c.period_effects[k].se == pytest.approx(np.sqrt(m["vcov"][i, i]))


def test_container_carries_the_full_covariance_not_just_diagonals():
    """The restriction is on differences between adjacent coefficients, whose
    variance depends on their covariance. Dropping off-diagonals would silently
    change every bound."""
    m = _moments()
    c = to_container(m)
    np.testing.assert_allclose(c.vcov, m["vcov"])
    assert not np.allclose(c.vcov, np.diag(np.diag(c.vcov)))


def test_average_post_effect_uses_post_periods_only():
    m = _moments()
    c = to_container(m)
    idx = c.interaction_indices
    expected = np.mean([m["beta"][idx[k]] for k in c.post_periods])
    assert c.avg_att == pytest.approx(expected)
