"""The panel build (sql/03_hourly_panel.sql) on a synthetic staging table."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

SQL = (Path(__file__).resolve().parents[1] / "sql" / "03_hourly_panel.sql").read_text()


def _rows():
    # two readings in one hour for a treated link, plus a fall-back-hour row
    # that must be excluded, plus a link with no treatment assignment
    return pd.DataFrame(
        [
            ("1004", "2025-01-06 08:00:00", 10.0, 20, False),
            ("1004", "2025-01-06 08:15:00", 20.0, 30, False),
            ("1004", "2024-12-02 08:00:00", 12.0, 25, False),
            ("1004", "2024-11-03 01:15:00", 99.0, 5, True),  # DST-ambiguous
            ("9999", "2025-01-06 08:00:00", 30.0, 10, False),  # unassigned
        ],
        columns=["link_id", "ts", "speed_mph", "n_samples", "is_dst_ambiguous_hour"],
    )


@pytest.fixture
def con(tmp_path):
    c = duckdb.connect()
    df = _rows()
    df["ts"] = pd.to_datetime(df["ts"])
    c.register("src", df)
    c.execute(
        "CREATE TABLE stg_speed_readings AS SELECT link_id, ts, "
        "date_trunc('hour', ts) AS ts_hour, speed_mph, n_samples, "
        "is_dst_ambiguous_hour, 'manhattan' AS borough, 'X St' AS link_name FROM src"
    )
    tp = tmp_path / "seg.parquet"
    pd.DataFrame(
        [("1004", "treated", "X St")], columns=["sid", "treatment_group", "roadway"]
    ).to_parquet(tp, index=False)
    c.execute(SQL, {"treatment_path": str(tp)})
    return c


def test_dst_ambiguous_hour_excluded(con):
    df = con.execute("SELECT * FROM hourly_panel").df()
    assert not df["date"].astype(str).eq("2024-11-03").any()


def test_hourly_median_is_median_not_mean(con):
    row = con.execute(
        "SELECT median_speed_mph, mean_speed_mph, n_obs FROM hourly_panel "
        "WHERE link_id='1004' AND ts_hour = TIMESTAMP '2025-01-06 08:00:00'"
    ).fetchone()
    assert row[0] == pytest.approx(15.0)  # median of 10, 20
    assert row[2] == 2


def test_unassigned_links_are_kept_and_labelled(con):
    g = dict(con.execute("SELECT link_id, treatment_group FROM hourly_panel").fetchall())
    assert g["9999"] == "unassigned"
    assert g["1004"] == "treated"


def test_post_and_treated_post_flags(con):
    df = con.execute(
        "SELECT date, post, treated, treated_post FROM hourly_panel "
        "WHERE link_id='1004' ORDER BY date"
    ).df()
    # 2024-12-02 is pre, 2025-01-06 is post (tolling began 2025-01-05)
    assert list(df["post"]) == [False, True]
    assert list(df["treated_post"]) == [False, True]


def test_peak_flags(con):
    hours = con.execute(
        "SELECT DISTINCT hour, is_peak, is_am_peak FROM hourly_panel"
    ).fetchall()
    for hour, is_peak, is_am in hours:
        assert is_peak == (7 <= hour <= 9 or 16 <= hour <= 18)
        assert is_am == (7 <= hour <= 9)
