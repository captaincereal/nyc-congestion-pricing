"""H010's count-based diversion share: what it recovers, and where it breaks.

The estimand is a ratio of vehicle counts, so the tests plant a known deficit
and a known surplus and check f comes back exactly. They also pin the behaviour
of the flat counterfactual on a rising series, which the record assumed was a
conservative floor and is not — see `test_flat_counterfactual_inverts_on_a_ramp`
and the 2026-09-15 entry in docs/decision_register.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis import h010_route_substitution as h10

RAMP_INTERCEPT = np.log(12000.0)
RAMP_SLOPE = 0.011  # a rising morning ramp, log-linear in log1p space


def _planted(
    deficit_per_block: float = 2000.0,
    surplus_per_block: float = 200.0,
    slope: float = RAMP_SLOPE,
    dates: int = 40,
    groups: tuple[str, ...] = ("FDR Drive at 60th St", "Brooklyn Bridge"),
    responder_fraction: float = 0.8,
    surplus_responder_fraction: float | None = None,
    boundary_hour: int = 5,
) -> pd.DataFrame:
    """Both series on a log-linear ramp, with a known deficit and surplus planted.

    Split across two vehicle classes so the concentration cut has something to
    find: `responder_fraction` of the exempt surplus lands on the responder
    class.
    """
    if surplus_responder_fraction is None:
        surplus_responder_fraction = responder_fraction
    runs = np.arange(-h10.PRE_BLOCKS, h10.POST_BLOCKS) * h10.BLOCK_MINUTES
    base = np.expm1(RAMP_INTERCEPT + slope * runs)
    rows = []
    for day in range(dates):
        for group in groups:
            for label, responder, share, surplus_share in (
                (
                    "1 - Cars, Pickups and Vans",
                    True,
                    responder_fraction,
                    surplus_responder_fraction,
                ),
                (
                    "3 - Multi-Unit Trucks",
                    False,
                    1.0 - responder_fraction,
                    1.0 - surplus_responder_fraction,
                ),
            ):
                for index, run in enumerate(runs):
                    post = index >= h10.PRE_BLOCKS
                    rows.append(
                        {
                            "date": f"2025-01-{day + 1:03d}",
                            "year": 2025,
                            "detection_group": group,
                            "vehicle_class": label,
                            "is_responder": responder,
                            "minute_of_day": boundary_hour * 60 + run,
                            "tolled": base[index] * share
                            - (deficit_per_block * share if post else 0.0),
                            "exempt": base[index] * share
                            + (surplus_per_block * surplus_share if post else 0.0),
                        }
                    )
    return pd.DataFrame(rows)


def _shares(frame: pd.DataFrame, boundary_hour: int = 5) -> pd.DataFrame:
    """The table `main` feeds to `evaluate_criteria`, built the same way."""
    rows = []
    for method in h10.COUNTERFACTUALS:
        result = h10.diversion_share(h10.deficit_and_surplus(frame, boundary_hour, method))
        result["counterfactual"] = method
        rows.append(result)
    return pd.DataFrame(rows)


def _f(frame: pd.DataFrame, method: str, boundary_hour: int = 5) -> dict:
    return h10.diversion_share(h10.deficit_and_surplus(frame, boundary_hour, method))


def test_loglinear_recovers_the_planted_share():
    """f is a ratio of totals, so planting 200 against 2000 must give 0.10."""
    result = _f(_planted(2000.0, 200.0), "loglinear")

    assert abs(result["f"] - 0.10) < 1e-6
    assert result["deficit"] > 0
    assert result["n_dates"] == 40


def test_quadratic_recovers_it_too():
    """A quadratic through an exactly log-linear ramp returns the ramp."""
    assert abs(_f(_planted(2000.0, 200.0), "quadratic")["f"] - 0.10) < 1e-6


def test_the_share_tracks_the_planted_ratio_rather_than_the_levels():
    for deficit, surplus, want in ((4000.0, 200.0, 0.05), (1000.0, 250.0, 0.25)):
        assert abs(_f(_planted(deficit, surplus), "loglinear")["f"] - want) < 1e-6


def test_flat_counterfactual_inverts_on_a_ramp():
    """The record called this a model-free floor. On a rising series it is not.

    Holding the last pre-boundary block level puts the counterfactual BELOW the
    true ramp, which shrinks the measured deficit until it goes negative and
    inflates the measured surplus. Both biases push f in the same direction, so
    the flat figure is not conservative and cannot serve as the safeguard the
    frozen criterion 1 asks it to be.

    Pinned here so that changing it has to be deliberate, and so the defect
    cannot quietly disappear from the record's Method.
    """
    frame = _planted(2000.0, 200.0)
    loglinear = _f(frame, "loglinear")
    flat = _f(frame, "flat")

    assert abs(loglinear["f"] - 0.10) < 1e-6
    assert flat["deficit"] < 0, "a rising ramp drives the flat deficit negative"
    assert flat["surplus"] > loglinear["surplus"] * 5, "and inflates the surplus"
    assert np.isnan(flat["f"])
    assert "undefined" in flat["note"]


def test_a_nonpositive_deficit_reports_undefined_rather_than_dividing():
    result = h10.diversion_share(
        pd.DataFrame({"date": ["a", "b"], "deficit": [-5.0, -1.0], "surplus": [10.0, 2.0]})
    )

    assert np.isnan(result["f"])
    assert result["note"]


def test_the_bootstrap_is_deterministic_and_brackets_the_point_estimate():
    per_date = h10.deficit_and_surplus(_planted(2000.0, 200.0), 5, "loglinear")
    first = h10.diversion_share(per_date)
    second = h10.diversion_share(per_date)

    assert first["ci_low"] == second["ci_low"]
    assert first["ci_high"] == second["ci_high"]
    assert first["ci_low"] <= first["f"] <= first["ci_high"]


def test_responder_concentration_recovers_a_planted_split():
    """80% of the surplus on a class that is 80% of baseline volume gives 1.0.

    Looser tolerance than the f tests above, for a fixture reason rather than a
    code one: splitting a log-linear ramp additively across classes leaves each
    class very slightly non-linear in log1p space, so the per-class fit carries
    about 2e-4 of relative error. It cancels in the ratio f, which is why the
    recovery tests hold at 1e-6, and it does not cancel in a share.
    """
    result = h10.responder_concentration(_planted(responder_fraction=0.8), 5, "loglinear")

    assert abs(result["baseline_responder_share"] - 0.8) < 1e-6
    assert abs(result["surplus_responder_share"] - 0.8) < 1e-3
    assert abs(result["ratio"] - 1.0) < 1e-3
    assert result["testable"] is True
    assert result["verdict_input"] == "neither"


def test_the_feasibility_gate_fires_above_the_declared_ceiling():
    """Declared in advance: a baseline share over 0.90 makes 1.10 unreachable."""
    result = h10.responder_concentration(_planted(responder_fraction=0.95), 5, "loglinear")

    assert result["baseline_responder_share"] > h10.FEASIBILITY_CEILING
    assert result["testable"] is False
    assert result["verdict_input"] == "untestable"


def test_exempt_populated_by_class_is_detected_rather_than_assumed():
    frame = _planted()
    assert h10.exempt_is_populated_by_class(frame)["populated_by_class"] is True

    collapsed = frame.copy()
    collapsed.loc[collapsed["vehicle_class"] != "1 - Cars, Pickups and Vans", "exempt"] = 0.0
    assert h10.exempt_is_populated_by_class(collapsed)["populated_by_class"] is False


def test_cells_missing_blocks_are_dropped_not_interpolated():
    frame = _planted(dates=6)
    trimmed = frame[
        ~(
            (frame["date"] == "2025-01-001")
            & (frame["minute_of_day"] == 5 * 60 - 3 * h10.BLOCK_MINUTES)
        )
    ]

    assert h10.deficit_and_surplus(frame, 5, "loglinear").shape[0] == 6
    assert h10.deficit_and_surplus(trimmed, 5, "loglinear").shape[0] == 5


def test_the_thresholds_are_what_the_record_says():
    assert h10.SUPPORT_F == 0.05
    assert h10.REFUTE_F == 0.02
    assert h10.SUPPORT_RATIO == 1.10
    assert h10.REFUTE_RATIO == 0.95
    assert h10.FEASIBILITY_CEILING == 0.90
    assert h10.COUNTERFACTUAL_SPREAD == 2.0
    assert h10.BOOTSTRAP_DRAWS == 500
    assert h10.FROZEN_COUNTERFACTUAL == "loglinear"
    assert h10.COUNTERFACTUALS == ("loglinear", "flat", "quadratic")
    # The 2026-09-15 amendment: reported, scored on nothing.
    assert h10.FITTED_COUNTERFACTUALS == ("loglinear", "quadratic")
    assert not hasattr(h10, "SUPPORT_F_FLOOR")


# --- Satisfiability. The check that was missing when these criteria were frozen.
#
# Three criteria failures in this project shared one shape: a bar a true effect
# could not clear. The cheap defence is mechanical rather than intentional —
# plant a true effect of the size the record predicts and confirm the criterion
# actually fires. These are that check, and they are the reason the amendment
# can be trusted where the original could not.


def _criteria(frame: pd.DataFrame) -> dict:
    return h10.evaluate_criteria(
        _shares(frame), h10.responder_concentration(frame, 5, h10.FROZEN_COUNTERFACTUAL)
    )


def test_a_true_effect_the_size_the_record_predicts_reaches_support():
    """The record predicts f between 0.05 and 0.25. Plant 0.10 and check."""
    verdict = _criteria(_planted(2000.0, 200.0, surplus_responder_fraction=0.95))

    assert verdict["support_1_f_clears_bars"] is True
    assert verdict["support_2_responders_concentrated"] is True
    assert verdict["refute_1_f_below_floor"] is False
    assert verdict["refute_2_f_negative_somewhere"] is False
    assert verdict["refute_3_responders_absent"] is False
    assert verdict["uninformative"] is False


def test_support_is_reachable_across_the_whole_predicted_range():
    for deficit, surplus in ((4000.0, 200.0), (2000.0, 200.0), (1000.0, 250.0)):
        verdict = _criteria(_planted(deficit, surplus, surplus_responder_fraction=0.95))
        assert verdict["support_1_f_clears_bars"] is True, f"{surplus}/{deficit} should clear"


def test_a_negligible_share_refutes():
    """f = 0.01, an order of magnitude below the bar."""
    verdict = _criteria(_planted(20000.0, 200.0))

    assert verdict["refute_1_f_below_floor"] is True
    assert verdict["support_1_f_clears_bars"] is False


def test_a_share_between_the_bars_is_uninformative():
    """f = 0.03 sits in the declared gap between refuting and supporting."""
    verdict = _criteria(_planted(10000.0, 300.0))

    assert verdict["uninformative"] is True
    assert verdict["support_1_f_clears_bars"] is False
    assert verdict["refute_1_f_below_floor"] is False


def test_the_flat_counterfactual_no_longer_decides_anything():
    """The amendment in one assertion.

    Flat returns an undefined f on this rising fixture, as it will at 05:00.
    Before the amendment that made support unreachable and fired refutation 2
    automatically. Now it is reported and scored on nothing, so a true effect
    reaches support with flat exactly as broken as it was.
    """
    frame = _planted(2000.0, 200.0, surplus_responder_fraction=0.95)
    shares = _shares(frame)

    assert np.isnan(shares.set_index("counterfactual").loc["flat", "f"])
    verdict = _criteria(frame)
    assert verdict["support_1_f_clears_bars"] is True
    assert verdict["refute_2_f_negative_somewhere"] is False
    assert verdict["spread_over"] == "loglinear/quadratic"
