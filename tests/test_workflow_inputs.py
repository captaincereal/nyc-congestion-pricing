"""Bootstrap must wait for both periods, without hiding broken existing parts."""

from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from scripts.check_analysis_inputs import readiness
from src.config import EZPASS_TIME_COL


def write_inputs(raw_dir: Path, timestamps: list[datetime]) -> None:
    parts = raw_dir / "ezpass_speeds"
    parts.mkdir()
    pd.DataFrame({EZPASS_TIME_COL: timestamps}).to_parquet(parts / "ezpass_speeds_2025-01.parquet")
    pd.DataFrame({"sid": [1]}).to_parquet(raw_dir / "ezpass_segments.parquet")


def test_empty_release_waits(tmp_path: Path) -> None:
    ready, message = readiness(tmp_path)
    assert not ready
    assert "no primary month parts" in message


@pytest.mark.parametrize(
    "timestamps",
    [
        [datetime(2025, 1, 1), datetime(2025, 1, 4, 23)],
        [datetime(2025, 1, 5), datetime(2025, 1, 31)],
    ],
)
def test_one_sided_observations_wait(tmp_path: Path, timestamps: list[datetime]) -> None:
    write_inputs(tmp_path, timestamps)
    assert not readiness(tmp_path)[0]


def test_january_with_both_sides_still_requires_source_verification(tmp_path: Path) -> None:
    write_inputs(tmp_path, [datetime(2025, 1, 4, 23), datetime(2025, 1, 5)])
    assert not readiness(tmp_path)[0]


def test_verified_january_with_both_sides_can_run(tmp_path: Path, monkeypatch) -> None:
    write_inputs(tmp_path, [datetime(2025, 1, 4, 23), datetime(2025, 1, 5)])
    monkeypatch.setattr(
        "scripts.check_analysis_inputs.verification_summary",
        lambda *args: {"gate_passed": True},
    )
    assert readiness(tmp_path)[0]


def test_missing_geometry_waits(tmp_path: Path) -> None:
    write_inputs(tmp_path, [datetime(2025, 1, 4), datetime(2025, 1, 5)])
    (tmp_path / "ezpass_segments.parquet").unlink()
    assert not readiness(tmp_path)[0]


def test_corrupt_part_is_an_error(tmp_path: Path) -> None:
    write_inputs(tmp_path, [datetime(2025, 1, 4), datetime(2025, 1, 5)])
    (tmp_path / "ezpass_speeds" / "ezpass_speeds_2025-01.parquet").write_text("broken")
    with pytest.raises(duckdb.Error):
        readiness(tmp_path)
