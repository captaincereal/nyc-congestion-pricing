"""Coverage reporting: month counting is trivial, gap detection is not.

The manifest's `coverage` field reports only first and last month, which is how
a three-month hole (2024-07..09) sat unnoticed inside a window that looked
contiguous. These cover the part that catches that.
"""

from datetime import date

from src.data.coverage_report import _span_months, contiguous_runs, target_months


def test_unbroken_months_collapse_to_one_run():
    months = [date(2024, 10, 1), date(2024, 11, 1), date(2024, 12, 1)]
    assert contiguous_runs(months) == [(date(2024, 10, 1), date(2024, 12, 1))]


def test_a_gap_splits_the_run():
    # The real shape of the archive: 2024-06 alone, then 2024-10 onward.
    months = [date(2024, 6, 1), date(2024, 10, 1), date(2024, 11, 1)]
    assert contiguous_runs(months) == [
        (date(2024, 6, 1), date(2024, 6, 1)),
        (date(2024, 10, 1), date(2024, 11, 1)),
    ]


def test_run_spanning_a_year_boundary_stays_one_run():
    months = [date(2024, 11, 1), date(2024, 12, 1), date(2025, 1, 1)]
    assert contiguous_runs(months) == [(date(2024, 11, 1), date(2025, 1, 1))]


def test_no_months_is_not_an_error():
    assert contiguous_runs([]) == []


def test_span_counts_inclusively():
    assert _span_months((date(2024, 10, 1), date(2024, 12, 1))) == 3
    assert _span_months((date(2024, 6, 1), date(2024, 6, 1))) == 1
    assert _span_months((date(2024, 11, 1), date(2025, 1, 1))) == 3


def test_target_window_starts_at_the_frozen_date_and_excludes_this_month():
    want = target_months(today=date(2025, 3, 14))
    assert want[0] == date(2023, 1, 1)
    assert want[-1] == date(2025, 2, 1), "the in-progress month is not a target"
