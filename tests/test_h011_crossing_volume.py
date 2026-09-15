"""H011: the estimator, and the gate that stops it running on a guess.

The record requires the treatment classification to be read off the data and
written down before anything is estimated, because assuming which crossings
enter the zone is the D3 error in a new place. Half these tests are about that
refusal, and they matter as much as the arithmetic.

No network: every fixture is synthetic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis import h011_crossing_volume as h11

# Ten, matching the roster the feed actually returned. The RFK Bridge appears
# twice, as Bronx and Manhattan plazas with distinct facility ids.
FACILITIES = [f"Crossing {letter}" for letter in "ABCDEFGHIJ"]
TREATED = FACILITIES[:2]


def _classification(treated=None, source="project_brief.md") -> pd.DataFrame:
    treated = TREATED if treated is None else treated
    return pd.DataFrame(
        {
            "facility": FACILITIES,
            "is_crz_entry": [f in treated for f in FACILITIES],
            "source": source,
        }
    )


def _panel(effect: float = -0.06, noise: float = 0.0, seed: int = 7) -> pd.DataFrame:
    """Nine facilities, 24 pre months and 8 post, with a planted log effect."""
    rng = np.random.default_rng(seed)
    months = [f"2023-{m:02d}" for m in range(1, 13)]
    months += [f"2024-{m:02d}" for m in range(1, 13)]
    months += [f"2025-{m:02d}" for m in range(2, 10)]
    rows = []
    for facility in FACILITIES:
        level = rng.normal(13.0, 0.4)
        for month in months:
            post = month >= h11.POST_START
            treated = facility in TREATED
            value = level + rng.normal(0, noise) + (effect if (post and treated) else 0.0)
            rows.append(
                {
                    "facility": facility,
                    "month": month,
                    "is_crz_entry": treated,
                    "post": post,
                    "log_crossings": value,
                }
            )
    return pd.DataFrame(rows)


def test_missing_classification_refuses_to_estimate(tmp_path):
    with pytest.raises(SystemExit) as refusal:
        h11.load_classification(tmp_path / "nope.csv")

    assert "D3" in str(refusal.value), "the refusal should say why, not just fail"


def test_classification_without_a_source_column_is_refused(tmp_path):
    path = tmp_path / "c.csv"
    _classification().drop(columns=["source"]).to_csv(path, index=False)

    with pytest.raises(SystemExit, match="missing columns"):
        h11.load_classification(path)


def test_a_blank_source_is_refused(tmp_path):
    path = tmp_path / "c.csv"
    _classification(source="   ").to_csv(path, index=False)

    with pytest.raises(SystemExit, match="source"):
        h11.load_classification(path)


def test_all_treated_or_none_treated_is_refused(tmp_path):
    every = tmp_path / "every.csv"
    _classification(treated=FACILITIES).to_csv(every, index=False)
    none = tmp_path / "none.csv"
    _classification(treated=[]).to_csv(none, index=False)

    with pytest.raises(SystemExit, match="no control"):
        h11.load_classification(every)
    with pytest.raises(SystemExit, match="CRZ entry"):
        h11.load_classification(none)


def test_a_well_formed_classification_loads(tmp_path):
    path = tmp_path / "c.csv"
    _classification().to_csv(path, index=False)

    loaded = h11.load_classification(path)

    assert loaded["is_crz_entry"].sum() == 2
    assert len(loaded) == 10


def test_the_estimator_recovers_a_planted_effect():
    assert abs(h11.did_estimate(_panel(effect=-0.06)) - (-0.06)) < 1e-9


def test_no_planted_effect_returns_zero():
    assert abs(h11.did_estimate(_panel(effect=0.0))) < 1e-9


def test_facility_and_month_levels_are_absorbed_not_fitted():
    """Facilities differ in size by an order of magnitude and months move
    together. Neither should touch the estimate."""
    panel = _panel(effect=-0.06)
    shifted = panel.copy()
    bump = {month: 0.3 * i for i, month in enumerate(sorted(panel["month"].unique()))}
    shifted["log_crossings"] = [
        value + bump[month] + (2.0 if facility == FACILITIES[0] else 0.0)
        for value, month, facility in zip(
            shifted["log_crossings"], shifted["month"], shifted["facility"], strict=True
        )
    ]

    assert abs(h11.did_estimate(shifted) - (-0.06)) < 1e-9


def test_randomization_enumerates_every_assignment_and_reports_its_ceiling():
    drawn = h11.randomization(_panel(effect=-0.06, noise=0.01))

    assert drawn["n_assignments"] == 45, "C(10,2), from the real roster"
    assert abs(drawn["finest_one_sided_p"] - 1 / 45) < 1e-12
    assert drawn["band_low"] <= drawn["band_high"]


def test_a_real_effect_lands_outside_the_randomization_band():
    drawn = h11.randomization(_panel(effect=-0.10, noise=0.005))

    assert drawn["observed"] < drawn["band_low"]
    assert drawn["outside_band"] is True


# --- Satisfiability, checked before the criteria were frozen. See the record.


def test_a_true_effect_of_the_predicted_size_reaches_support():
    """The record predicts a fall of 2% to 12%. Plant 6% and check support fires."""
    drawn = h11.randomization(_panel(effect=-0.06, noise=0.005))
    verdict = h11.evaluate_criteria(breakdown_value=2.44, effect=drawn["observed"], drawn=drawn)

    assert verdict["supports"] is True
    assert verdict["uninformative"] is False
    assert verdict["refute_1_breakdown_below_floor"] is False
    assert verdict["refute_2_effect_negligible"] is False
    assert verdict["refute_3_wrong_signed_and_not_noise"] is False


def test_a_negligible_effect_refutes():
    drawn = h11.randomization(_panel(effect=-0.002, noise=0.005))
    verdict = h11.evaluate_criteria(breakdown_value=0.5, effect=drawn["observed"], drawn=drawn)

    assert verdict["refute_2_effect_negligible"] is True
    assert verdict["supports"] is False


def test_a_weak_breakdown_value_refutes_however_large_the_effect():
    verdict = h11.evaluate_criteria(breakdown_value=0.1, effect=-0.09, drawn={"outside_band": True})

    assert verdict["refute_1_breakdown_below_floor"] is True
    assert verdict["supports"] is False


def test_a_middling_breakdown_value_is_uninformative():
    verdict = h11.evaluate_criteria(breakdown_value=0.6, effect=-0.06, drawn={"outside_band": True})

    assert verdict["uninformative"] is True
    assert verdict["supports"] is False


def test_the_frozen_constants_are_what_the_record_says():
    assert h11.SUPPORT_M == 1.0
    assert h11.REFUTE_M == 0.3
    assert h11.SUPPORT_EFFECT == 0.02
    assert h11.REFUTE_EFFECT == 0.01
    assert h11.PRE_START == "2023-01"
    assert h11.PRE_END == "2024-12"
    assert h11.TREATMENT_MONTH == "2025-01"
    assert h11.POST_START == "2025-02"
    assert h11.RANDOMIZATION_BAND == 0.90


def test_the_event_study_recovers_a_flat_pre_period_and_the_planted_step():
    """Pre-period coefficients near zero, post ones at the planted effect."""
    moments = h11.event_study(_panel(effect=-0.06, noise=0.0))
    beta = dict(zip(moments["k"], moments["beta"], strict=True))

    assert max(abs(v) for k, v in beta.items() if k < 0) < 1e-9
    assert all(abs(v - (-0.06)) < 1e-9 for k, v in beta.items() if k > 0)
    assert moments["n_clusters"] == 10
    assert moments["vcov"].shape[0] == len(moments["k"])


def test_the_committed_classification_covers_the_real_roster():
    """The gate is only as good as the file it loads."""
    from src.config import PROJECT_ROOT

    roster = pd.read_csv(PROJECT_ROOT / "outputs/tables/H011_facility_roster.csv")
    committed = h11.load_classification()

    assert set(committed["facility"]) == set(roster["facility"])
    assert sorted(committed.loc[committed["is_crz_entry"], "facility"]) == [
        "Hugh L. Carey Tunnel",
        "Queens Midtown Tunnel",
    ]
