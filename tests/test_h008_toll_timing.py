"""H008 boundary estimation: the parts that would be wrong without saying so.

The running variable wraps at midnight, and a discontinuity estimator that
silently recovers the wrong magnitude looks exactly like one that works.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis import h008_toll_timing as h8


def test_signed_minutes_wraps_around_midnight():
    """23:50 is ten minutes BEFORE the midnight boundary, not 1430 after it.

    Without the wrap, every estimate at hour 0 would be fitted on a window that
    is entirely one-sided and the boundary would silently estimate nothing.
    """
    minute_of_day = np.array([23 * 60 + 50, 0, 10, 12 * 60])
    got = h8._signed_minutes(minute_of_day, 0)

    assert list(got[:3]) == [-10, 0, 10]
    assert -720 <= got[3] <= 720


def test_signed_minutes_is_centred_on_the_boundary():
    minute_of_day = np.array([20 * 60 + 50, 21 * 60, 21 * 60 + 10])
    assert list(h8._signed_minutes(minute_of_day, 21)) == [-10, 0, 10]


def _planted(jump: float, slope: float = -0.002, dates: int = 40) -> pd.DataFrame:
    """Blocks around 21:00 with a known log discontinuity and a smooth trend."""
    rows = []
    rng = np.random.default_rng(20250105)
    for day in range(dates):
        level = rng.normal(10.0, 0.3)  # a day effect the estimator must absorb
        for minute_of_day in range(20 * 60, 22 * 60, h8.BLOCK_MINUTES):
            run = minute_of_day - 21 * 60
            log_entries = level + slope * run + (jump if run >= 0 else 0.0)
            rows.append(
                {
                    "date": f"2025-01-{day + 1:02d}",
                    "minute_of_day": minute_of_day,
                    "entries": float(np.expm1(log_entries)),
                }
            )
    return pd.DataFrame(rows)


def test_estimate_recovers_a_planted_discontinuity():
    result = h8.estimate_discontinuity(_planted(jump=0.25), boundary_hour=21)

    assert result["tau"] == np.float64(result["tau"])  # not nan
    assert abs(result["tau"] - 0.25) < 0.01
    assert result["n_dates"] == 40


def test_estimate_returns_zero_where_no_discontinuity_was_planted():
    """The smooth trend alone must not manufacture a jump."""
    result = h8.estimate_discontinuity(_planted(jump=0.0), boundary_hour=21)

    assert abs(result["tau"]) < 0.01


def test_day_effects_are_absorbed_not_fitted():
    """Large between-day level differences must not move the estimate.

    The panel has ~600 dates whose overall traffic varies a lot; the
    discontinuity is meant to come from the shape of the day.
    """
    frame = _planted(jump=0.25)
    noisy = frame.copy()
    shift = {date: i * 0.5 for i, date in enumerate(sorted(noisy["date"].unique()))}
    noisy["entries"] = [
        float(np.expm1(np.log1p(e) + shift[d]))
        for e, d in zip(noisy["entries"], noisy["date"], strict=True)
    ]

    assert abs(h8.estimate_discontinuity(noisy, 21)["tau"] - 0.25) < 0.01


def test_toll_boundaries_match_the_feeds_own_schedule():
    """Derived from `time_period`, not from the published tariff. Weekends start
    the peak four hours later, and that difference is H008's identifying test."""
    assert h8.WEEKDAY_TOLL_BOUNDARIES == (5, 21)
    assert h8.WEEKEND_TOLL_BOUNDARIES == (9, 21)
    assert h8.EXCLUDED_PLACEBO == 0
