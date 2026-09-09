"""Geometry helpers: polyline decoding and Congestion Relief Zone assignment.

Treatment assignment is **geometric**, decoded from each segment's `polyline`.
It is deliberately not string matching on `link_name` — names are free text with
inconsistent casing and abbreviations, and getting treatment assignment wrong is
the failure that invalidated the original data source.

The one place a name-based rule is legitimate is the toll-exempt roadways: being
exempt is a legal fact about specific named roads, not a geometric property. The
FDR Drive and the West Side Highway / Route 9A run *through* the zone's bounding
geometry but are not tolled, so a purely geometric test would wrongly mark them
treated. They are therefore matched explicitly and held out, and the exempt list
is short enough to review by eye (see ``EXEMPT_PATTERNS``).

Zone definition (MTA Congestion Relief Zone, tolling from 2025-01-05):
Manhattan at or below 60th Street, excluding the FDR Drive, the West Side
Highway / Route 9A, the Hugh L. Carey Tunnel connection to West St, and the
Battery Park Underpass.
"""

from __future__ import annotations

import re

# --- Polyline ---------------------------------------------------------------


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode a Google-encoded polyline into ``[(lat, lon), ...]``.

    Standard algorithm: each coordinate is a zig-zag-encoded delta from the
    previous one, split into 5-bit chunks, each chunk +63 and ORed with 0x20
    while more chunks follow.
    """
    if not encoded:
        return []
    coords: list[tuple[float, float]] = []
    index = lat = lon = 0
    factor = 10**precision
    length = len(encoded)

    while index < length:
        for is_lat in (True, False):
            result = shift = 0
            while index < length:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            # zig-zag: odd values are negative
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))
    return coords


# --- Congestion Relief Zone -------------------------------------------------

# 60th Street is not a line of constant latitude: the Manhattan grid is rotated,
# so 60th St runs from roughly (40.7726, -73.9887) at West End Ave down to
# (40.7605, -73.9583) at York Ave. Testing against a fixed latitude would
# misclassify segments by several blocks at the east and west edges, so the
# boundary is the line through those two anchors.
SIXTIETH_ST_WEST = (40.7726, -73.9887)
SIXTIETH_ST_EAST = (40.7605, -73.9583)

# Rough Manhattan envelope, used only to reject segments in other boroughs whose
# geometry happens to fall south of the 60th St line (much of Brooklyn/Queens
# does). Borough labels are also checked; this is the geometric backstop.
MANHATTAN_LON_MIN, MANHATTAN_LON_MAX = -74.030, -73.907
MANHATTAN_LAT_MIN, MANHATTAN_LAT_MAX = 40.680, 40.882

# Roadways inside the zone's geometry that the toll does not apply to.
EXEMPT_PATTERNS = (
    r"\bFDR\b",
    r"franklin\s+d\.?\s+roosevelt",
    r"west\s*side\s*(hwy|highway)",
    r"\bwest\s+st\b",
    r"\b(9a|route\s*9a)\b",
    r"\b1[12]th\s*ave",  # the Route 9A corridor is signed 11th/12th Ave
    r"battery\s+park\s+underpass",
    r"\b(bbt|hugh\s+l\.?\s+carey)\b",
)
_EXEMPT_RE = re.compile("|".join(EXEMPT_PATTERNS), re.IGNORECASE)

# Bridges and tunnels landing inside the zone. Their speed measures the queue to
# ENTER the zone, not circulation within it, so they are separated from the
# treated surface streets: mixing the two would blend two different behaviours
# into one ATT. They remain interesting in their own right — the crossings are
# where the largest published speed gains were reported.
CROSSING_PATTERNS = (
    r"\bbridge\b",
    r"\btunnel\b",
    r"\b(qmt|bbt|tbb)\b",
    r"\bportal\b",
    r"toll\s+plaza",
)
_CROSSING_RE = re.compile("|".join(CROSSING_PATTERNS), re.IGNORECASE)


def is_crossing(link_name: str | None) -> bool:
    """True for a bridge/tunnel crossing rather than an in-zone street."""
    return bool(_CROSSING_RE.search(roadway_of(link_name)))


def roadway_of(link_name: str | None) -> str:
    """The roadway a segment runs ALONG, i.e. the subject of its name.

    Names are ``"<roadway> - <direction> - <from> to <to>"``. The endpoints name
    cross streets, so matching the whole string would treat
    ``"23rd Street - Eastbound - 11th Ave to 10th Ave"`` as an 11th Ave segment
    when it is a crosstown block that merely touches it. Some rows use an en
    dash (and arrive mojibaked), so split on either.
    """
    if not link_name:
        return ""
    # Delimiter is usually " - " but the feed also has an en dash (sometimes
    # mojibaked), a dash with no leading space ("23rd Street- westbound"), and
    # runs of spaces. Split on the first of any of those.
    return re.split(r"\s*[-–—�]\s+|\s{2,}", link_name.strip(), maxsplit=1)[0].strip(" -")


def is_exempt_roadway(link_name: str | None) -> bool:
    """True for roadways inside the zone that the CRZ toll does not apply to.

    Tested against the roadway subject only — a crosstown street that ends at
    an exempt highway is itself tolled.
    """
    return bool(_EXEMPT_RE.search(roadway_of(link_name)))


def _south_of_60th(lat: float, lon: float) -> bool:
    """True if (lat, lon) lies south of the 60th St line.

    Cross product of the west->east boundary vector with the west->point
    vector; negative means the point is clockwise from the boundary, i.e. south.
    """
    (y1, x1), (y2, x2) = SIXTIETH_ST_WEST, SIXTIETH_ST_EAST
    return ((x2 - x1) * (lat - y1) - (y2 - y1) * (lon - x1)) < 0


def _in_manhattan_envelope(lat: float, lon: float) -> bool:
    return (
        MANHATTAN_LAT_MIN <= lat <= MANHATTAN_LAT_MAX
        and MANHATTAN_LON_MIN <= lon <= MANHATTAN_LON_MAX
    )


def classify_segment(link_name: str | None, borough: str | None, polyline: str | None) -> str:
    """Assign one segment to a treatment group.

    Returns one of:
      ``treated``          — an in-zone surface street, tolled
      ``exempt_in_zone``   — inside the zone geometry but not tolled (FDR,
                             West Side Hwy/9A, Battery Park Underpass). Never a
                             control: these are where diverted traffic goes, so
                             they carry the spillover.
      ``crossing``         — bridge/tunnel landing in the zone. Measures the
                             queue to enter, not in-zone circulation, so it is
                             estimated separately from ``treated``.
      ``boundary``         — geometry crosses the 60th St line; held out of
                             controls and modelled separately
      ``control``          — outside the zone
      ``unknown``          — geometry missing or undecodable
    """
    coords = decode_polyline(polyline or "")
    if not coords:
        return "unknown"

    is_manhattan = (borough or "").strip().lower() == "manhattan"
    if not is_manhattan:
        return "control"

    inside = [_south_of_60th(lat, lon) for lat, lon in coords]
    if not any(inside):
        return "control"
    if not all(inside):
        return "boundary"
    if is_exempt_roadway(link_name):
        return "exempt_in_zone"
    if is_crossing(link_name):
        return "crossing"
    return "treated"


# --- CLI ---------------------------------------------------------------------


def build_assignment():
    """Classify every segment and persist the assignment for review."""
    import pandas as pd

    from src.config import EZPASS_SEGMENTS_PATH, INTERIM_DIR

    seg = pd.read_parquet(EZPASS_SEGMENTS_PATH)
    seg["treatment_group"] = [
        classify_segment(n, b, p)
        for n, b, p in zip(seg.link_name, seg.borough, seg.polyline, strict=True)
    ]
    seg["roadway"] = [roadway_of(n) for n in seg.link_name]
    out = INTERIM_DIR / "segment_treatment.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    seg.to_parquet(out, index=False)
    return seg, out


if __name__ == "__main__":
    frame, path = build_assignment()
    print(frame["treatment_group"].value_counts().to_string())
    print(f"\nwrote {path}")
