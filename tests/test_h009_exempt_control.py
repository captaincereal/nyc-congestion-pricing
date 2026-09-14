"""H009's difference-in-discontinuities: what it removes, and what it does not.

The record's whole identification argument is that differencing a tolled series
against an exempt one on the same sensors cancels anything common to both — a
clock, a sensor batching at the hour, a shared jump. These tests check that
claim rather than trusting it, because an estimator that silently returned the
tolled discontinuity alone would look exactly like one that works.

`test_differential_curvature_survives_the_differencing` characterises the one
thing that does NOT cancel. That is a known limitation, documented in
`docs/hypotheses/ADJUDICATION-timing.md` and load-bearing for how the 05:00
estimate is reported, so it is pinned here to make changing it deliberate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis import h008_toll_timing as h8
from src.analysis import h009_exempt_control as h9

DATES = 60


def _planted(
    boundary_hour: int,
    tolled_jump: float,
    exempt_jump: float,
    tolled_curve: float = 0.0,
    exempt_curve: float = 0.0,
    slope: float = -0.002,
) -> pd.DataFrame:
    """Two series around a boundary, each with a known log discontinuity.

    The two differ in level by an order of magnitude, as the real ones do, and
    every date carries its own random level so the fixed effects have something
    to absorb. `*_curve` adds a quadratic in the running variable, letting a
    caller give the two series different curvature and see what the difference
    estimator makes of it.
    """
    rng = np.random.default_rng(20250105)
    rows = []
    for day in range(DATES):
        tolled_level, exempt_level = rng.normal(11.0, 0.3), rng.normal(9.0, 0.3)
        for minute_of_day in range(
            boundary_hour * 60 - 60, boundary_hour * 60 + 60, h8.BLOCK_MINUTES
        ):
            run = minute_of_day - boundary_hour * 60
            post = 1.0 if run >= 0 else 0.0
            curve = (run / 60) ** 2
            rows.append(
                {
                    "date": f"2025-01-{day + 1:03d}",
                    "minute_of_day": minute_of_day,
                    "detection_group": "FDR Drive at 60th St",
                    "year": 2025,
                    "tolled": float(
                        np.expm1(
                            tolled_level + slope * run + tolled_curve * curve + tolled_jump * post
                        )
                    ),
                    "exempt": float(
                        np.expm1(
                            exempt_level + slope * run + exempt_curve * curve + exempt_jump * post
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


def _whole_day() -> pd.DataFrame:
    """Every block of the day, so the placebo bar has all 24 boundaries to try."""
    rng = np.random.default_rng(20250105)
    rows = []
    for day in range(20):
        level = rng.normal(10.0, 0.3)
        for minute_of_day in range(0, 24 * 60, h8.BLOCK_MINUTES):
            shape = np.sin(2 * np.pi * minute_of_day / (24 * 60))
            rows.append(
                {
                    "date": f"2025-01-{day + 1:03d}",
                    "minute_of_day": minute_of_day,
                    "detection_group": "FDR Drive at 60th St",
                    "year": 2025,
                    "tolled": float(np.expm1(level + shape)),
                    "exempt": float(np.expm1(level - 1.0 + shape)),
                }
            )
    return pd.DataFrame(rows)


def test_recovers_a_planted_difference():
    result = h9.difference_in_discontinuities(_planted(21, 0.25, 0.0), boundary_hour=21)

    assert abs(result["delta"] - 0.25) < 0.01
    assert abs(result["tau_exempt"]) < 0.01
    assert result["n_dates"] == DATES


def test_reports_the_exempt_series_as_tau_exempt_not_the_tolled_one():
    """beta[0] is the control's own discontinuity and beta[1] the difference.

    Swapping them would leave every number plausible and every interpretation
    wrong, because the two series are never far apart in the reported tables.
    """
    result = h9.difference_in_discontinuities(_planted(21, 0.35, 0.10), boundary_hour=21)

    assert abs(result["tau_exempt"] - 0.10) < 0.01
    assert abs(result["delta"] - 0.25) < 0.01


def test_a_jump_shared_by_both_series_differences_out():
    """The identification claim in one test.

    A clock, a reporting convention and a sensor batching at the hour boundary
    all move both series together. If any of them survived the differencing,
    H009 would be measuring the same thing H008 did.
    """
    for shared in (0.10, 0.50, -0.30):
        result = h9.difference_in_discontinuities(_planted(21, shared, shared), boundary_hour=21)

        assert abs(result["delta"]) < 1e-6
        assert abs(result["tau_exempt"] - shared) < 0.01


def test_a_smooth_trend_alone_manufactures_no_difference():
    result = h9.difference_in_discontinuities(_planted(21, 0.0, 0.0), boundary_hour=21)

    assert abs(result["delta"]) < 1e-6


def test_opposite_signs_are_recovered_as_their_difference():
    """The 05:00 shape: tolled collapsing while the control rises."""
    result = h9.difference_in_discontinuities(_planted(5, -0.70, 0.07), boundary_hour=5)

    assert abs(result["delta"] - (-0.77)) < 0.01
    assert result["ci_high"] < 0


def test_level_differences_between_the_series_are_absorbed():
    """Fixed effects are on date x series because the two differ hugely in level.

    Nothing should be identified off that gap, so scaling one series must leave
    the difference where it was.
    """
    frame = _planted(21, 0.25, 0.0)
    scaled = frame.copy()
    scaled["exempt"] = np.expm1(np.log1p(scaled["exempt"].to_numpy()) - 4.0)

    baseline = h9.difference_in_discontinuities(frame, 21)["delta"]
    assert abs(h9.difference_in_discontinuities(scaled, 21)["delta"] - baseline) < 1e-6


def test_differential_curvature_survives_the_differencing():
    """The known limitation, pinned so that changing it has to be deliberate.

    Common curvature cancels. A GAP in curvature does not: on a +-60 minute
    window it comes through as gap/6, with no discontinuity planted anywhere.
    That is why the 05:00 estimate, which sits in the steepest ramp of the day,
    is reported as directional with an unpinned magnitude while 21:00 is not.
    See docs/hypotheses/ADJUDICATION-timing.md.
    """
    shared = h9.difference_in_discontinuities(_planted(5, 0.0, 0.0, 4.0, 4.0), boundary_hour=5)
    assert abs(shared["delta"]) < 1e-6, "curvature common to both series must cancel"

    for tolled_curve, exempt_curve in ((2.0, 0.0), (4.0, 0.0), (4.0, 2.0), (-4.0, 0.0)):
        result = h9.difference_in_discontinuities(
            _planted(5, 0.0, 0.0, tolled_curve, exempt_curve), boundary_hour=5
        )
        expected = (tolled_curve - exempt_curve) / 6

        assert abs(result["delta"] - expected) < 1e-3
        assert abs(result["delta"]) > 0.3, "a bias this size is not a rounding error"


def test_placebo_bar_excludes_exactly_the_boundaries_the_record_froze():
    """Six hours out of 24: midnight, the 05-08 curvature band, and 21:00.

    The count is the check. The record reports 18 placebo boundaries, and a
    silent change to either exclusion list would move the bar without moving
    anything a reader could see.
    """
    bar = h9.placebo_bar(_whole_day(), "tolled")

    assert bar["n_placebos"] == 18
    assert bar["series"] == "tolled"
    assert bar["p95"] >= bar["mean"]


def test_the_frozen_constants_are_what_the_record_says():
    assert h9.CURVATURE_EXCLUDED == (5, 6, 7, 8)
    assert h9.CALENDAR_EXCLUDED == (0,)
    assert h9.PLACEBO_PERCENTILE == 95
    assert len(h9.DUAL_GROUPS) == 4
    assert "FDR Drive at 60th St" in h9.DUAL_GROUPS
