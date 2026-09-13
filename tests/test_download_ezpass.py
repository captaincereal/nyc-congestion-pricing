import time
from datetime import date

import pandas as pd
import pytest

import src.data.download_ezpass as dl
from src.config import EZPASS_TIME_COL
from src.data.download_ezpass import (
    DATASET_AFTER_SPLIT,
    DATASET_BEFORE_SPLIT,
    _datasets_for_month,
    _days_in_month,
    _downsample,
    _where,
)


def test_month_wholly_before_split_uses_old_dataset():
    assert _datasets_for_month(date(2023, 5, 1)) == [DATASET_BEFORE_SPLIT]


def test_month_wholly_after_split_uses_new_dataset():
    assert _datasets_for_month(date(2024, 8, 1)) == [DATASET_AFTER_SPLIT]


def test_june_2024_is_last_old_only_month():
    # erdf-2akx runs to 2024-07-07, so June is still entirely on the old feed.
    assert _datasets_for_month(date(2024, 6, 1)) == [DATASET_BEFORE_SPLIT]


def test_straddling_month_uses_both_datasets():
    # July 2024 spans the 2024-07-08 handover and needs both feeds.
    assert _datasets_for_month(date(2024, 7, 1)) == [DATASET_BEFORE_SPLIT, DATASET_AFTER_SPLIT]


def test_where_filters_month_and_aggregation_period():
    w = _where(date(2025, 1, 1))
    assert "median_calculation_timestamp >= '2025-01-01T00:00:00'" in w
    assert "median_calculation_timestamp < '2025-02-01T00:00:00'" in w
    # The feed also emits 0-second rows; only 15-minute aggregates are usable.
    assert "aggregation_period_sec = 900" in w


def test_where_stays_index_friendly():
    # A function on the timestamp column (date_extract_mm) defeated Socrata's
    # index: a 50k page at offset 500,000 took 255.8s vs 3.7s without it.
    # Downsampling is client-side now, so the filter must stay a plain range.
    w = _where(date(2025, 1, 1))
    assert "date_extract" not in w


def test_days_in_month_covers_every_day():
    days = list(_days_in_month(date(2024, 2, 1)))
    assert days[0] == date(2024, 2, 1)
    assert days[-1] == date(2024, 2, 29)  # leap year
    assert len(days) == 29


def test_days_in_month_rolls_over_year():
    days = list(_days_in_month(date(2024, 12, 1)))
    assert len(days) == 31
    assert days[-1] == date(2024, 12, 31)


def _reading(sid, ts, n, fps):
    return {
        "sid": sid,
        "median_calculation_timestamp": ts,
        "median_speed_fps": fps,
        "median_tt_sec": "100",
        "n_samples": n,
    }


def test_downsample_keeps_one_row_per_window_preferring_more_samples():
    df = pd.DataFrame(
        [
            _reading("1004", "2025-01-06T08:00:10", "12", "20.5"),
            _reading("1004", "2025-01-06T08:01:07", "30", "21.5"),  # same window, better
            _reading("1004", "2025-01-06T08:14:59", "5", "22.5"),  # same window, worse
            _reading("1004", "2025-01-06T08:15:07", "20", "18.4"),  # next window
            _reading("2001", "2025-01-06T08:00:30", "9", "10.0"),  # other segment
        ]
    )
    out = _downsample(df)
    assert len(out) == 3
    kept = out[out.sid == "1004"].sort_values("median_calculation_timestamp")
    assert list(kept["n_samples"]) == ["30", "20"]


def test_downsample_drops_unparseable_timestamps():
    df = pd.DataFrame(
        [
            _reading("1004", "not-a-timestamp", "5", "10"),
            _reading("1004", "2025-01-06T08:00:10", "5", "10"),
        ]
    )
    assert len(_downsample(df)) == 1


def test_downsample_handles_empty_frame():
    assert _downsample(pd.DataFrame()).empty


def test_segment_sample_days_span_both_datasets_and_study_window():
    from src.data.download_ezpass import SEGMENT_SAMPLE_DAYS, _datasets_for_month

    # A single sample day left 32 sids (7.9% of Oct-2024 readings) with no
    # geometry, because the active segment roster changes over time.
    assert len(SEGMENT_SAMPLE_DAYS) >= 5
    covered = {ds for d in SEGMENT_SAMPLE_DAYS for ds in _datasets_for_month(d)}
    assert covered == {DATASET_BEFORE_SPLIT, DATASET_AFTER_SPLIT}
    assert min(SEGMENT_SAMPLE_DAYS) <= date(2023, 3, 1)  # covers the study start
    assert max(SEGMENT_SAMPLE_DAYS) >= date(2026, 1, 1)  # and the recent end


# --- Day checkpointing and the wall-clock budget -----------------------------
# A month takes 30-40 minutes to pull and the process can die at any moment.
# These cover the two guarantees that makes survivable: a killed run resumes
# from the last completed day, and a run given a budget stops cleanly rather
# than being hard-killed partway through writing a part.


def _fake_day_frame(day: date, rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sid": ["1004"] * rows,
            EZPASS_TIME_COL: [f"{day:%Y-%m-%d}T0{i}:00:00" for i in range(rows)],
            "median_speed_fps": ["12.0"] * rows,
            "median_tt_sec": ["30.0"] * rows,
            "n_samples": ["5"] * rows,
        }
    )


def test_download_month_resumes_from_day_checkpoints(tmp_path, monkeypatch):
    """Days already on disk are reused instead of refetched."""
    monkeypatch.setattr(dl, "EZPASS_DAYS_DIR", tmp_path / "days")
    monkeypatch.setattr(dl, "EZPASS_PARTS_DIR", tmp_path / "parts")

    month = date(2024, 1, 1)
    days = list(dl._days_in_month(month))
    # Pre-seed the first ten days, as an interrupted run would have left them.
    for day in days[:10]:
        dl._write_parquet_atomic(_fake_day_frame(day), dl._day_part_path(day))

    fetched: list[date] = []

    def _fake_fetch_day(session, day, datasets, **kwargs):
        fetched.append(day)
        return _fake_day_frame(day)

    monkeypatch.setattr(dl, "_fetch_day", _fake_fetch_day)

    rec = dl.download_month(session=None, month=month, force=False)

    assert fetched == days[10:], "only the un-checkpointed days should be refetched"
    assert rec.rows == 3 * len(days), "resumed days must still land in the month part"


def test_completed_month_clears_its_day_checkpoints(tmp_path, monkeypatch):
    """Checkpoints are scaffolding; the month part makes them redundant."""
    monkeypatch.setattr(dl, "EZPASS_DAYS_DIR", tmp_path / "days")
    monkeypatch.setattr(dl, "EZPASS_PARTS_DIR", tmp_path / "parts")
    monkeypatch.setattr(dl, "_fetch_day", lambda s, day, ds, **kwargs: _fake_day_frame(day))

    dl.download_month(session=None, month=date(2024, 1, 1), force=False)

    assert not list((tmp_path / "days").glob("*.parquet"))
    assert (tmp_path / "parts" / "ezpass_speeds_2024-01.parquet").exists()


def test_expired_budget_stops_before_writing_a_partial_month(tmp_path, monkeypatch):
    """An exhausted budget raises rather than writing a truncated part.

    A short month part that looked complete would poison the manifest, so the
    run has to abort and leave the day checkpoints for the next one.
    """
    monkeypatch.setattr(dl, "EZPASS_DAYS_DIR", tmp_path / "days")
    monkeypatch.setattr(dl, "EZPASS_PARTS_DIR", tmp_path / "parts")
    monkeypatch.setattr(dl, "_fetch_day", lambda s, day, ds, **kwargs: _fake_day_frame(day))

    with pytest.raises(dl.TimeBudgetExceeded):
        dl.download_month(
            session=None,
            month=date(2024, 1, 1),
            force=False,
            deadline=time.monotonic() - 1,  # already spent
        )

    assert not (tmp_path / "parts" / "ezpass_speeds_2024-01.parquet").exists()


def test_budget_checked_between_days_so_finished_work_survives(tmp_path, monkeypatch):
    """Days completed before the budget expired stay on disk as checkpoints."""
    monkeypatch.setattr(dl, "EZPASS_DAYS_DIR", tmp_path / "days")
    monkeypatch.setattr(dl, "EZPASS_PARTS_DIR", tmp_path / "parts")

    # Fake clock: each day costs 30 units against a 100-unit budget, so the
    # check before day 5 is the one that trips.
    clock = {"now": 0.0}
    monkeypatch.setattr(dl.time, "monotonic", lambda: clock["now"])

    def _fetch_and_spend(session, day, datasets, **kwargs):
        clock["now"] += 30.0
        return _fake_day_frame(day)

    monkeypatch.setattr(dl, "_fetch_day", _fetch_and_spend)

    with pytest.raises(dl.TimeBudgetExceeded):
        dl.download_month(session=None, month=date(2024, 1, 1), force=False, deadline=100.0)

    survived = sorted((tmp_path / "days").glob("*.parquet"))
    assert len(survived) == 4, "completed days must outlive the run that fetched them"


# --- Segment roster reconciliation -------------------------------------------
# Day sampling cannot find a sparse sensor. sid 33024, the westbound Belt Pkwy
# east of JFK, carries 2,325 readings across the 44-month archive and reported
# on none of the ten sampled days, so it reached staging with no borough or
# geometry and hard_unmatched_segments stopped the analysis on 2026-09-13.


def _segment_frame(sid: str, name: str = "Belt Pkwy - Westbound") -> pd.DataFrame:
    # Every column is a string on disk, as fetch_segments writes it.
    return pd.DataFrame(
        [
            {
                "sid": sid,
                "link_name": name,
                "borough": "Queens",
                "polyline": "abc",
                "link_length_ft": "1.0",
            }
        ]
    )


def test_missing_segment_sids_reports_only_what_the_table_lacks(tmp_path, monkeypatch):
    parts = tmp_path / "ezpass_speeds"
    parts.mkdir(parents=True)
    pd.DataFrame({dl.EZPASS_SEGMENT_COL: ["100", "200", "33024"]}).to_parquet(
        parts / "ezpass_speeds_2026-08.parquet", index=False
    )
    table = tmp_path / "segments.parquet"
    pd.concat([_segment_frame("100"), _segment_frame("200")]).to_parquet(table, index=False)
    monkeypatch.setattr(dl, "EZPASS_SEGMENTS_PATH", table)

    assert dl.missing_segment_sids(tmp_path) == ["33024"]


def test_top_up_segments_looks_the_gap_up_by_id_and_merges_it(tmp_path, monkeypatch):
    table = tmp_path / "segments.parquet"
    _segment_frame("100").to_parquet(table, index=False)
    monkeypatch.setattr(dl, "EZPASS_SEGMENTS_PATH", table)
    asked = []

    class Response:
        text = _segment_frame("33024").to_csv(index=False)

    def _fake_page(session, dataset_id, params, **kwargs):
        asked.append(params["$where"])
        return Response()

    monkeypatch.setattr(dl, "_get_page", _fake_page)

    assert dl.top_up_segments(None, ["33024"]) == 1
    assert asked == ["sid='33024'"]
    merged = pd.read_parquet(table)
    assert set(merged["sid"].astype(str)) == {"100", "33024"}


def test_top_up_segments_refuses_a_sid_that_is_not_an_identifier(tmp_path, monkeypatch):
    """The sids come from our own parquet, but they are interpolated into SoQL."""
    table = tmp_path / "segments.parquet"
    _segment_frame("100").to_parquet(table, index=False)
    monkeypatch.setattr(dl, "EZPASS_SEGMENTS_PATH", table)
    monkeypatch.setattr(
        dl, "_get_page", lambda *a, **k: pytest.fail("must not query for a malformed sid")
    )

    assert dl.top_up_segments(None, ["33024' OR '1'='1"]) == 0
