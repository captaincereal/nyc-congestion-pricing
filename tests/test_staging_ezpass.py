"""The EZ Pass staging transform (sql/01_stage_ezpass.sql) on a synthetic part.

Covers the non-trivial logic: fps->mph conversion, the 15-minute window floor,
de-duplication to one reading per (link, window) preferring the better-sampled
median, and the deliberate absence of value cleaning.
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

SQL = (Path(__file__).resolve().parents[1] / "sql" / "01_stage_ezpass.sql").read_text()

_COLS = [
    "sid",
    "link_name",
    "borough",
    "polyline",
    "link_length_ft",
    "aggregation_period_sec",
    "n_samples",
    "median_calculation_timestamp",
    "median_tt_sec",
    "median_speed_fps",
]
# 14.6667 fps == exactly 10 mph, which makes the conversion assertions readable.
_RAW_ROWS = [
    # same 15-min window (08:00 and its 08:01 backup) -> one row kept, the one
    # with more probe samples (n_samples 30 beats 12)
    (
        "1004",
        "42nd St",
        "Manhattan",
        "abc",
        "3781.9",
        "900",
        "12",
        "2025-01-06T08:00:10.000",
        "228",
        "14.6667",
    ),
    (
        "1004",
        "42nd St",
        "Manhattan",
        "abc",
        "3781.9",
        "900",
        "30",
        "2025-01-06T08:01:07.000",
        "200",
        "29.3333",
    ),
    # next window -> separate row
    (
        "1004",
        "42nd St",
        "Manhattan",
        "abc",
        "3781.9",
        "900",
        "20",
        "2025-01-06T08:15:07.000",
        "240",
        "14.6667",
    ),
    # absurd speed preserved (no cleaning here)
    (
        "2001",
        "Lex Ave",
        "MANHATTAN ",
        "def",
        "900.0",
        "900",
        "5",
        "2025-01-06T08:30:00.000",
        "1",
        "20662.24",
    ),
    # zero speed preserved
    (
        "2001",
        "Lex Ave",
        "Manhattan",
        "def",
        "900.0",
        "900",
        "7",
        "2025-01-06T08:45:00.000",
        "0",
        "0",
    ),
    # null keys dropped
    (None, "X", "Queens", "g", "1", "900", "1", "2025-01-06T08:00:00.000", "1", "10"),
    ("3001", "Y", "Queens", "h", "1", "900", "1", None, "1", "10"),
]


@pytest.fixture
def raw_part(tmp_path: Path) -> str:
    d = tmp_path / "ezpass_speeds"
    d.mkdir()
    pd.DataFrame(_RAW_ROWS, columns=_COLS).to_parquet(
        d / "ezpass_speeds_2025-01.parquet", index=False
    )
    return str(d / "*.parquet")


def _stage(parts_glob: str) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute(SQL, {"parts_glob": parts_glob})
    df = con.execute("SELECT * FROM stg_speed_readings ORDER BY link_id, ts").df()
    con.close()
    return df


def test_null_keys_dropped(raw_part):
    df = _stage(raw_part)
    assert df["link_id"].notna().all()
    assert df["ts"].notna().all()
    assert set(df["link_id"]) == {"1004", "2001"}


def test_fps_converted_to_mph(raw_part):
    df = _stage(raw_part)
    row = df[(df["link_id"] == "1004") & (df["ts_window"].astype(str).str.endswith("08:15:00"))]
    assert row.iloc[0]["speed_mph"] == pytest.approx(10.0, abs=1e-3)


def test_one_reading_per_link_and_window(raw_part):
    df = _stage(raw_part)
    assert not df.duplicated(["link_id", "ts_window"]).any()
    # 08:00 and 08:01 collapse to one window; the better-sampled row wins
    win = df[(df["link_id"] == "1004") & (df["ts_window"].astype(str).str.endswith("08:00:00"))]
    assert len(win) == 1
    assert win.iloc[0]["n_samples"] == 30
    assert win.iloc[0]["speed_mph"] == pytest.approx(20.0, abs=1e-3)


def test_window_floor_is_quarter_hour(raw_part):
    df = _stage(raw_part)
    minutes = pd.to_datetime(df["ts_window"]).dt.minute.unique()
    assert set(minutes) <= {0, 15, 30, 45}


def test_values_not_cleaned(raw_part):
    df = _stage(raw_part)
    speeds = df["speed_mph"].tolist()
    assert any(s > 10000 for s in speeds)  # the impossible 20,662 fps survives staging
    assert any(s == 0 for s in speeds)  # zero speed survives staging


def test_borough_normalised(raw_part):
    df = _stage(raw_part)
    assert set(df["borough"]) <= {"manhattan", "queens"}
