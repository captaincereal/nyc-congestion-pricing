"""H007 group assignment on the secondary feed.

`classify_segment` trusts the `borough` label, which mislabels the two BQE
bridge approaches on this feed. The holdout below is what keeps that out of the
estimate, so it is pinned here rather than left to the classifier.
"""

import pandas as pd

from src.data.build_secondary_panel import HELD_OUT_LINK_IDS, classify_links

# Real geometry from data/raw/dot_speeds/*.parquet, leading vertices of each
# link's encoded_poly_line.
POLY_BQE_BKN_BRIDGE = "oqjwFt}sbMwCn@gABo"  # 4616339, near (40.6916, -73.9992)
POLY_BQE_MAN_BRIDGE = "gplwFnkrbMJ}CZ"  # 4616340, near (40.7016, -73.9911)
POLY_FDR_CATHERINE_SLIP = "w~mwFjisbMXnEX"  # 4616341, near (40.7091, -73.9959)
POLY_BQE_GOWANUS = "kngwFzjtbM{CjBi"  # 4616229, near (40.6757, -74.0013)


def _attrs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (
                "4616339",
                "BQE N Atlantic Ave - BKN Bridge Manhattan Side",
                "manhattan",
                POLY_BQE_BKN_BRIDGE,
                100,
            ),
            (
                "4616340",
                "BQE N Atlantic Ave - MAN Bridge Manhattan Side",
                "manhattan",
                POLY_BQE_MAN_BRIDGE,
                100,
            ),
            (
                "4616341",
                "FDR S Catherine Slip - BKN Bridge Manhattan Side",
                "manhattan",
                POLY_FDR_CATHERINE_SLIP,
                100,
            ),
            (
                "4616229",
                "BQE S - GOW S ALTANTIC AVENUE - 9TH STREET",
                "brooklyn",
                POLY_BQE_GOWANUS,
                100,
            ),
        ],
        columns=["link_id", "link_name", "borough", "encoded_poly_line", "n_rows"],
    )


def test_bqe_approaches_are_held_out_of_both_groups():
    """The invariant H007 rests on, independent of what `classify_segment` says.

    Links 4616339 and 4616340 carry `borough = Manhattan` with geometry in
    Brooklyn, so the classifier calls them `treated`. An approach to a tolled
    crossing is toll-exposed, making that wrong, and `control` would be wrong
    too — so they belong to neither group. If a later change to `geo.py` gives
    them a group of their own, this holdout has to be revisited with it.
    """
    links = classify_links(_attrs()).set_index("link_id")
    for link_id in HELD_OUT_LINK_IDS:
        assert links.loc[link_id, "treatment_group"] == "treated"
        assert links.loc[link_id, "analysis_group"] == "held_out_geo"
        assert not links.loc[link_id, "treated"]
        assert links.loc[link_id, "hold_out_reason"]


def test_exempt_in_zone_links_are_the_treated_group():
    """`treated` here means a toll-exempt in-zone road, not a tolled street."""
    links = classify_links(_attrs()).set_index("link_id")
    assert links.loc["4616341", "treatment_group"] == "exempt_in_zone"
    assert links.loc["4616341", "analysis_group"] == "treated_exempt"
    assert links.loc["4616341", "treated"]


def test_other_borough_links_are_controls():
    links = classify_links(_attrs()).set_index("link_id")
    assert links.loc["4616229", "analysis_group"] == "control"
    assert not links.loc["4616229", "treated"]
    assert links.loc["4616229", "hold_out_reason"] == ""
