"""H007 secondary panel: the parts that would fail quietly.

Every one of these is a mistake that produces a plausible panel rather than an
error. The zero-speed rule is the load-bearing one — averaging outages in as
0 mph is exactly what contaminated the committed
``outputs/tables/spillover_secondary_monthly.csv`` — and the event-time columns
are next, because an off-by-one month silently shifts the whole event study.
"""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd
import pytest

from src.data.build_secondary_panel import (
    add_flags,
    hourly_aggregate,
    link_attributes,
    row_accounting,
)

# Real geometry, leading vertices of link 4616328's encoded_poly_line (FDR N).
POLY_FDR = "ka_wFfnsbMkA{E"


def _raw(rows: list[dict], tmp_path) -> str:
    """Write rows in the raw feed's shape — every column a VARCHAR."""
    frame = pd.DataFrame(rows).astype(str)
    path = tmp_path / "dot_speeds_test.parquet"
    frame.to_parquet(path, index=False)
    return str(path)


def _reading(link_id="1", ts="2025-01-06T09:05:00.000", speed="30", rid="1", **kw) -> dict:
    row = {
        "id": rid,
        "speed": speed,
        "travel_time": "100",
        "status": "0",
        "data_as_of": ts,
        "link_id": link_id,
        "encoded_poly_line": POLY_FDR,
        "borough": "Manhattan",
        "link_name": "FDR N Catherine Slip - 25th St",
    }
    row.update(kw)
    return row


@pytest.fixture
def con():
    connection = duckdb.connect()
    yield connection
    connection.close()


def test_zero_speed_readings_do_not_enter_the_median(con, tmp_path):
    """Zeros are outages. Medianing them in is the bug this panel exists to fix.

    Three 30 mph readings and three zeros: the honest answer is 30, not 15.
    """
    path = _raw(
        [
            _reading(ts=f"2025-01-06T09:0{i}:00.000", speed=s, rid=str(i))
            for i, s in enumerate(["30", "0", "30", "0", "30", "0"])
        ],
        tmp_path,
    )
    out = hourly_aggregate(con, path)
    assert len(out) == 1
    assert out.loc[0, "median_speed_mph"] == 30.0
    assert out.loc[0, "n_readings"] == 6
    assert out.loc[0, "n_positive"] == 3
    assert out.loc[0, "n_zero_speed"] == 3


def test_an_hour_of_nothing_but_zeros_is_null_not_zero(con, tmp_path):
    """AGENTS.md: missing numerics are NaN, never 0.

    The row survives so the availability diagnostic can count it as a present
    link-hour that yielded no speed — which is the whole first criterion.
    """
    path = _raw(
        [_reading(ts=f"2025-01-06T09:0{i}:00.000", speed="0", rid=str(i)) for i in range(4)],
        tmp_path,
    )
    out = hourly_aggregate(con, path)
    assert len(out) == 1
    assert pd.isna(out.loc[0, "median_speed_mph"])
    assert out.loc[0, "n_readings"] == 4
    assert out.loc[0, "n_positive"] == 0


def test_duplicate_link_timestamp_pairs_keep_the_highest_id(con, tmp_path):
    """The repo's secondary staging convention, inherited from 01_stage_speeds.sql."""
    path = _raw(
        [
            _reading(speed="10", rid="1"),
            _reading(speed="99", rid="2"),
        ],
        tmp_path,
    )
    out = hourly_aggregate(con, path)
    assert out.loc[0, "n_readings"] == 1
    assert out.loc[0, "median_speed_mph"] == 99.0


def test_the_ambiguous_fall_back_hour_is_excluded(con, tmp_path):
    """2025-11-02 01:00 runs twice under naive local time; 2025-11-02 02:00 does not."""
    path = _raw(
        [
            _reading(ts="2025-11-02T01:30:00.000", rid="1"),
            _reading(ts="2025-11-02T02:30:00.000", rid="2"),
        ],
        tmp_path,
    )
    out = hourly_aggregate(con, path)
    assert list(pd.to_datetime(out["ts_hour"]).dt.hour) == [2]


def test_the_window_stops_before_the_missing_month(con, tmp_path):
    """2026-06 is absent from the feed, so 2026-07 is dropped rather than
    left floating on the far side of a hole."""
    path = _raw(
        [
            _reading(ts="2022-12-31T23:30:00.000", rid="1"),
            _reading(ts="2023-01-01T00:30:00.000", rid="2"),
            _reading(ts="2026-05-31T23:30:00.000", rid="3"),
            _reading(ts="2026-07-01T00:30:00.000", rid="4"),
        ],
        tmp_path,
    )
    out = hourly_aggregate(con, path)
    kept = pd.to_datetime(out["ts_hour"]).dt.date.tolist()
    assert kept == [date(2023, 1, 1), date(2026, 5, 31)]


def test_link_attributes_take_the_modal_geometry(con, tmp_path):
    """A link's polyline is re-emitted with encoding variants and the odd
    truncated row. Picking the most-published one is deterministic and keeps a
    single corrupt row from deciding a link's treatment group."""
    rows = [_reading(rid=str(i), ts=f"2025-01-06T09:{i:02d}:00.000") for i in range(5)]
    rows.append(_reading(rid="9", ts="2025-01-06T10:00:00.000", encoded_poly_line="LINCOLN\\\\"))
    out = link_attributes(con, _raw(rows, tmp_path))
    assert len(out) == 1
    assert out.loc[0, "encoded_poly_line"] == POLY_FDR


def test_row_accounting_is_a_partition(con, tmp_path):
    """Every raw row is either dropped for a named reason or kept."""
    path = _raw(
        [
            _reading(rid="1"),
            _reading(rid="2"),  # duplicate of the above
            _reading(ts="2026-07-01T00:30:00.000", rid="3"),  # out of window
            _reading(ts="2025-11-02T01:30:00.000", rid="4"),  # fall-back hour
            _reading(ts="not a timestamp", rid="5"),  # unparseable
        ],
        tmp_path,
    )
    funnel = row_accounting(con, path).set_index("step")["rows"]
    raw = funnel.loc[funnel.index[0]]
    kept = funnel.loc["readings kept"]
    drops = funnel.iloc[1:-1].sum()
    assert raw == 5
    assert kept == 1
    assert raw - drops == kept


def _hours(stamps: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"ts_hour": pd.to_datetime(stamps)})


def test_post_starts_on_the_tolling_date_not_the_month():
    """Tolling began 2025-01-05. The first four days of January are pre."""
    out = add_flags(_hours(["2025-01-04T23:00:00", "2025-01-05T00:00:00"]))
    assert list(out["post"]) == [False, True]


def test_event_month_is_indexed_on_the_tolling_month():
    """k = 0 is 2025-01, k = -1 is 2024-12, and the endpoints of the window
    are -24 and +16."""
    out = add_flags(
        _hours(
            [
                "2023-01-01T00:00:00",
                "2024-12-31T23:00:00",
                "2025-01-05T00:00:00",
                "2026-05-31T23:00:00",
            ]
        )
    )
    assert list(out["event_month"]) == [-24, -1, 0, 16]


def test_event_month_and_event_week_disagree_inside_january_2025():
    """The first four days of January 2025 are event month 0 but event week -1.

    Monthly bins cannot separate them, which is why the reference bin k = -1 is
    December and the contamination is four days of thirty-one. Weekly bins can,
    and the panel keeps both columns so the choice stays visible.
    """
    out = add_flags(_hours(["2025-01-02T12:00:00"]))
    assert out.loc[0, "event_month"] == 0
    assert out.loc[0, "event_week"] == -1
    assert not out.loc[0, "post"]


def test_event_week_matches_the_primary_panel_convention():
    """sql/03_hourly_panel.sql floors elapsed days, including negative ones."""
    out = add_flags(
        _hours(
            [
                "2025-01-05T00:00:00",
                "2025-01-11T23:00:00",
                "2025-01-12T00:00:00",
                "2024-12-29T00:00:00",
            ]
        )
    )
    assert list(out["event_week"]) == [0, 0, 1, -1]


def test_weekend_and_peak_flags_use_local_wall_clock():
    """Timestamps are naive America/New_York; 2025-01-11 is a Saturday."""
    out = add_flags(_hours(["2025-01-06T08:00:00", "2025-01-06T12:00:00", "2025-01-11T08:00:00"]))
    assert list(out["is_weekend"]) == [False, False, True]
    assert list(out["is_peak"]) == [True, False, True]
    assert list(out["dow"]) == [1, 1, 6]
