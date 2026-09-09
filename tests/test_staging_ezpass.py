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

_COLS = ["sid", "median_calculation_timestamp", "median_speed_fps", "median_tt_sec", "n_samples"]
_SEG_COLS = ["sid", "link_name", "borough", "polyline", "link_length_ft"]

# 14.6667 fps == exactly 10 mph, which makes the conversion assertions readable.
_RAW_ROWS = [
    # same 15-min window -> one row kept, the better-sampled one (30 beats 12)
    ("1004", "2025-01-06T08:00:10.000", "14.6667", "228", "12"),
    ("1004", "2025-01-06T08:01:07.000", "29.3333", "200", "30"),
    # next window -> separate row
    ("1004", "2025-01-06T08:15:07.000", "14.6667", "240", "20"),
    # absurd speed preserved (no cleaning here)
    ("2001", "2025-01-06T08:30:00.000", "20662.24", "1", "5"),
    # zero speed preserved
    ("2001", "2025-01-06T08:45:00.000", "0", "0", "7"),
    # null keys dropped
    (None, "2025-01-06T08:00:00.000", "10", "1", "1"),
    ("3001", None, "10", "1", "1"),
    # fall-back date: 01:xx is the ambiguous repeated hour
    ("1004", "2024-11-03T01:30:00.000", "14.6667", "100", "9"),
    ("1004", "2024-11-03T03:30:00.000", "14.6667", "100", "9"),
    # reading for a segment absent from the segments table -> kept, attrs null
    ("9999", "2025-01-06T09:00:00.000", "14.6667", "100", "4"),
]
_SEG_ROWS = [
    ("1004", "42nd St", "Manhattan", "abc", "3781.9"),
    ("2001", "Lex Ave", "MANHATTAN ", "def", "900.0"),
]


@pytest.fixture
def raw_part(tmp_path: Path) -> str:
    d = tmp_path / "ezpass_speeds"
    d.mkdir()
    pd.DataFrame(_RAW_ROWS, columns=_COLS).to_parquet(
        d / "ezpass_speeds_2025-01.parquet", index=False
    )
    seg = tmp_path / "ezpass_segments.parquet"
    pd.DataFrame(_SEG_ROWS, columns=_SEG_COLS).to_parquet(seg, index=False)
    return str(d / "*.parquet"), str(seg)


def _stage(fixture) -> pd.DataFrame:
    parts_glob, segments_path = fixture
    con = duckdb.connect()
    con.execute(SQL, {"parts_glob": parts_glob, "segments_path": segments_path})
    df = con.execute("SELECT * FROM stg_speed_readings ORDER BY link_id, ts").df()
    con.close()
    return df


def test_null_keys_dropped(raw_part):
    df = _stage(raw_part)
    assert df["link_id"].notna().all()
    assert df["ts"].notna().all()
    assert set(df["link_id"]) == {"1004", "2001", "9999"}


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
    # "MANHATTAN " and "Manhattan" both fold to "manhattan"; the orphan sid
    # (no segments row) is null.
    assert set(df["borough"].dropna()) == {"manhattan"}


def test_reading_without_segment_row_is_kept_with_null_attrs(raw_part):
    df = _stage(raw_part)
    orphan = df[df["link_id"] == "9999"]
    # LEFT join: the reading survives so the quality report can count it,
    # rather than vanishing from the panel unnoticed.
    assert len(orphan) == 1
    assert pd.isna(orphan.iloc[0]["borough"])


def test_fall_back_hour_is_flagged_ambiguous(raw_part):
    """01:00-01:59 runs twice on a US fall-back date under naive local time.

    Both passes floor to the same 15-minute windows, so de-dup keeps one and
    discards the other - the hour is ambiguous and under-counted. Verified
    against the raw feed on 2024-11-03: 103 readings in hour 01 vs 51 in
    neighbouring hours. Staging flags rather than drops.
    """
    df = _stage(raw_part)
    flagged = df[df["is_dst_ambiguous_hour"]]
    assert len(flagged) == 1
    assert str(flagged.iloc[0]["ts"]).startswith("2024-11-03 01:")
    # the 03:00 reading on the same date is NOT ambiguous
    same_day = df[df["ts"].astype(str).str.startswith("2024-11-03")]
    assert len(same_day) == 2
    assert same_day["is_dst_ambiguous_hour"].sum() == 1
