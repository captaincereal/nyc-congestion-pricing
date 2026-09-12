"""Measure distances to the existing 60th-St boundary without changing assignment.

This is a geometry diagnostic, not a selected spillover-buffer rule. Distances
are to the infinite line already used by geo.py, in a local equirectangular
projection at 40.767 degrees latitude (111,320 metres per degree latitude).
Positive signed distance means north/outside; negative means south/inside.

    python -m src.analysis.assignment_audit
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import INTERIM_DIR, TABLES_DIR
from src.data.geo import SIXTIETH_ST_EAST, SIXTIETH_ST_WEST, decode_polyline


def boundary_distances(segments: pd.DataFrame) -> pd.DataFrame:
    """Return signed segment extents and minimum distance to the boundary line."""
    scale = np.array([111_320.0, 111_320.0 * np.cos(np.deg2rad(40.767))])
    origin = np.array(SIXTIETH_ST_WEST) * scale
    direction = np.array(SIXTIETH_ST_EAST) * scale - origin
    rows = []
    for segment in segments.itertuples(index=False):
        if str(segment.borough).strip().lower() != "manhattan":
            continue
        vertices = np.array(decode_polyline(segment.polyline))
        if len(vertices) == 0:
            continue
        relative = vertices * scale - origin
        signed = (direction[1] * relative[:, 0] - direction[0] * relative[:, 1]) / np.linalg.norm(
            direction
        )
        low, high = float(signed.min()), float(signed.max())
        distance = 0.0 if low <= 0 <= high else float(np.abs(signed).min())
        rows.append(
            {
                "sid": segment.sid,
                "link_name": segment.link_name,
                "borough": segment.borough,
                "treatment_group": segment.treatment_group,
                "signed_min_distance_m": low,
                "signed_max_distance_m": high,
                "nearest_boundary_line_m": distance,
                "wholly_north_of_boundary": low > 0,
                "geometry_source": "E-Z Pass segment polyline; existing geo.py 60th-St anchors",
                "metric": "local equirectangular 40.767deg; infinite 60th-St line; north positive",
                "polyline": segment.polyline,
            }
        )
    return pd.DataFrame(rows).sort_values("nearest_boundary_line_m").reset_index(drop=True)


def main() -> None:
    assignments = pd.read_parquet(INTERIM_DIR / "segment_treatment.parquet")
    distances = boundary_distances(assignments)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / "boundary_distance_audit.csv"
    distances.to_csv(path, index=False)
    controls = distances[distances["treatment_group"].eq("control")]
    for metres in (250, 500, 1000):
        count = int(controls["nearest_boundary_line_m"].le(metres).sum())
        print(f"Wholly outside Manhattan controls within {metres} m of 60th-St line: {count}")
    print(f"Wrote {path}; classification unchanged.")


if __name__ == "__main__":
    main()
