"""The staging transform (sql/01_stage_speeds.sql) on a tiny synthetic raw part.

Covers the only non-trivial logic in staging: type casting, null-key drop, and
de-duplication on (link_id, ts) — without cleaning any values.
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

SQL = (Path(__file__).resolve().parents[1] / "sql" / "01_stage_speeds.sql").read_text()

_COLS = ["link_id", "data_as_of", "speed", "travel_time", "status", "borough", "link_name", "id"]
_RAW_ROWS = [
    ("1", "2024-06-01T08:00:03.000", "23.5", "40", "0", "Manhattan", "A", "100"),
    ("1", "2024-06-01T08:00:03.000", "24.9", "38", "0", "Manhattan", "A", "101"),  # dup key
    ("2", "2024-06-01T08:05:00.000", "0", "0", "0", "MANHATTAN ", "B", "102"),  # zero kept
    ("2", "2024-06-01T08:10:00.000", "-5", "1", "1", "Bronx", "B", "103"),  # negative kept
    (None, "2024-06-01T08:10:00.000", "30", "20", "0", "Queens", "C", "104"),  # null link dropped
    ("3", None, "31", "20", "0", "Queens", "D", "105"),  # null ts dropped
]


@pytest.fixture
def raw_part(tmp_path: Path) -> str:
    d = tmp_path / "dot_speeds"
    d.mkdir()
    pd.DataFrame(_RAW_ROWS, columns=_COLS).to_parquet(d / "dot_speeds_2024-06.parquet", index=False)
    return str(d / "*.parquet")


def _stage(parts_glob: str) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute(SQL, {"parts_glob": parts_glob})
    df = con.execute("SELECT * FROM stg_dot_highway_readings ORDER BY link_id, ts").df()
    con.close()
    return df


def test_null_keys_dropped(raw_part):
    df = _stage(raw_part)
    assert df["link_id"].notna().all()
    assert df["ts"].notna().all()
    assert set(df["link_id"]) == {"1", "2"}


def test_unique_on_link_ts(raw_part):
    df = _stage(raw_part)
    assert not df.duplicated(["link_id", "ts"]).any()
    # dedup keeps the row with the lexicographically-largest reading id => 24.9
    kept = df[df["link_id"] == "1"].iloc[0]
    assert kept["speed_mph"] == pytest.approx(24.9)


def test_values_not_cleaned(raw_part):
    df = _stage(raw_part)
    speeds = set(df["speed_mph"].round(1))
    assert 0.0 in speeds  # zero speed preserved
    assert -5.0 in speeds  # negative speed preserved


def test_borough_normalised(raw_part):
    df = _stage(raw_part)
    assert set(df["borough"]) <= {"manhattan", "bronx", "queens"}


def test_ts_hour_truncation(raw_part):
    df = _stage(raw_part)
    row = df[df["link_id"] == "1"].iloc[0]
    assert str(row["ts_hour"]) == "2024-06-01 08:00:00"
