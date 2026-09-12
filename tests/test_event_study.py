"""Phase 8 event-study estimator, on a small synthetic panel (no SQL layer)."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.event_study import REFERENCE_K, build_dummies, coef_frame, estimate


def _panel():
    """4 links (2 treated, 2 control) x 4 event weeks x 4 hours = 64 rows.

    Treated links get a clean +2 mph jump from event_week 0 onward; control
    links carry no jump. No noise, so the recovered post coefficients should
    land close to +2 and the pre-period ones close to 0.
    """
    rng = np.random.default_rng(0)
    rows = []
    weeks = [-2, -1, 0, 1]
    for link, treated, base in (("T1", True, 10.0), ("T2", True, 12.0),
                                 ("C1", False, 20.0), ("C2", False, 22.0)):
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
    df, cols = build_dummies(_panel(), horizon=1)
    # event week -2 exists in the data but must clip into the k=-1 (reference,
    # no column) bin rather than getting its own k_m2 dummy
    assert "k_m2" not in cols
    assert set(cols) <= {"k_m1", "k_p0", "k_p1"}


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
