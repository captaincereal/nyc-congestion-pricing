from datetime import date

from src.data.download import _iter_months, _month_bounds


def test_month_bounds_is_half_open():
    lo, hi = _month_bounds(date(2024, 1, 15))
    assert lo == "2024-01-01T00:00:00"
    assert hi == "2024-02-01T00:00:00"


def test_month_bounds_year_rollover():
    lo, hi = _month_bounds(date(2024, 12, 1))
    assert lo == "2024-12-01T00:00:00"
    assert hi == "2025-01-01T00:00:00"


def test_iter_months_inclusive_and_ordered():
    months = list(_iter_months(date(2023, 11, 20), date(2024, 2, 3)))
    assert months == [date(2023, 11, 1), date(2023, 12, 1), date(2024, 1, 1), date(2024, 2, 1)]


def test_iter_months_single_month():
    assert list(_iter_months(date(2024, 6, 10), date(2024, 6, 28))) == [date(2024, 6, 1)]
