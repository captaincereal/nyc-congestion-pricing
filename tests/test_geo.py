"""Polyline decoding and CRZ treatment assignment.

Treatment assignment decides which segments the ATT is estimated on, so the
cases below are the ones that would silently invalidate the study if wrong.
"""

from src.data.geo import (
    classify_segment,
    decode_polyline,
    is_crossing,
    is_exempt_roadway,
    roadway_of,
)

# Real geometry from data/raw/ezpass_segments.parquet.
POLY_42ND_LEX_TO_3RD = "agvwFxmobMfCeI"  # sid 1004, in-zone surface street
POLY_OCEAN_PKWY = "qtuvFjpmbMkLcB}LeB{LeB"  # sid 100098, Brooklyn


def test_decode_polyline_matches_known_location():
    pts = decode_polyline(POLY_42ND_LEX_TO_3RD)
    lat, lon = pts[0]
    # 42nd St & Lexington Ave is about (40.7513, -73.9757)
    assert abs(lat - 40.7513) < 0.002
    assert abs(lon - -73.9757) < 0.002


def test_decode_polyline_direction_matches_name():
    # "Eastbound" -> longitude should increase along the segment
    pts = decode_polyline(POLY_42ND_LEX_TO_3RD)
    assert pts[-1][1] > pts[0][1]


def test_decode_polyline_empty_input():
    assert decode_polyline("") == []
    assert decode_polyline(None or "") == []


# --- roadway subject parsing ------------------------------------------------


def test_roadway_of_standard_delimiter():
    assert roadway_of("42nd Street - Eastbound - 3rd Ave to 2nd Ave") == "42nd Street"


def test_roadway_of_dash_without_leading_space():
    # Real name in the feed; a naive " - " split leaves "23rd Street- westbound"
    assert roadway_of("23rd Street- westbound - 3 ave to madison ave") == "23rd Street"


def test_roadway_of_mojibaked_en_dash():
    name = "14th Street � eastbound � 11 Ave/Rt 9A to 7th Ave"
    assert roadway_of(name) == "14th Street"


# --- exemption ---------------------------------------------------------------


def test_exempt_matches_roadway_subject():
    assert is_exempt_roadway("11th Avenue - Southbound - 34th St to 23rd St")
    assert is_exempt_roadway("Battery Park Underpass - West St (Southbound) to FDR Dr")


def test_crosstown_touching_exempt_highway_is_not_exempt():
    # The bug this guards: a crosstown block that merely ENDS at 11th Ave is
    # itself inside the zone and tolled. Matching the whole name exempted it.
    assert not is_exempt_roadway("23rd Street - Eastbound - 11th Ave to 10th Ave")
    assert not is_exempt_roadway("34th Street - Westbound - 10th Ave to 11th Ave")
    assert not is_exempt_roadway("14th Street � eastbound � 11 Ave/Rt 9A to 7th Ave")


def test_crossing_detection():
    assert is_crossing("Williamsburg Bridge - Eastbound - Manhattan @ Delancey to Brooklyn")
    assert not is_crossing("42nd Street - Eastbound - 3rd Ave to 2nd Ave")


# --- classification ----------------------------------------------------------


def test_in_zone_surface_street_is_treated():
    assert (
        classify_segment(
            "42nd Street - Eastbound - Lexington Ave to 3rd Ave",
            "Manhattan",
            POLY_42ND_LEX_TO_3RD,
        )
        == "treated"
    )


def test_other_borough_is_control():
    assert (
        classify_segment(
            "Ocean Pkwy - Northbound - Shore Pkwy to Avenue X", "Brooklyn", POLY_OCEAN_PKWY
        )
        == "control"
    )


def test_exempt_highway_in_zone_is_not_treated():
    assert (
        classify_segment(
            "11th Avenue - Southbound - 34th St to 23rd St", "Manhattan", POLY_42ND_LEX_TO_3RD
        )
        == "exempt_in_zone"
    )


def test_crossing_in_zone_is_separated_from_treated():
    assert (
        classify_segment("Williamsburg Bridge - Eastbound", "Manhattan", POLY_42ND_LEX_TO_3RD)
        == "crossing"
    )


def test_missing_geometry_is_unknown():
    assert classify_segment("42nd Street", "Manhattan", None) == "unknown"
    assert classify_segment("42nd Street", "Manhattan", "") == "unknown"


def test_boundary_line_follows_grid_rotation():
    """60th St is not a constant latitude, and the tilt is bigger than a block.

    A point on the east side at 40.7620 is NORTH of 60th St (which sits at
    ~40.7605 there), while the same latitude on the west side is SOUTH of it
    (60th St is ~40.7726 there). A fixed-latitude test would get one of these
    wrong, so this pins the rotation.
    """
    from src.data.geo import _south_of_60th

    assert not _south_of_60th(40.7620, -73.9585)  # east side, just north
    assert _south_of_60th(40.7620, -73.9880)  # west side, well south
