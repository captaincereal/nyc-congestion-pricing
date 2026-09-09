from datetime import date

from src.data.download_ezpass import (
    DATASET_AFTER_SPLIT,
    DATASET_BEFORE_SPLIT,
    _datasets_for_month,
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
