"""HTTP retries must share the phase budget instead of multiplying it."""

from datetime import date

import pandas as pd
import pytest
import requests

import src.data.download_ezpass as dl


class Response:
    def __init__(self):
        self.closed = False

    def raise_for_status(self):
        pass

    def json(self):
        return [{"n": "2"}]

    def close(self):
        self.closed = True


class Session:
    def __init__(self, callback):
        self.callback = callback

    def get(self, *args, **kwargs):
        return self.callback(*args, **kwargs)


@pytest.fixture
def clock(monkeypatch):
    state = {"now": 0.0, "sleeps": []}
    monkeypatch.setattr(dl.time, "monotonic", lambda: state["now"])

    def sleep(seconds):
        state["sleeps"].append(seconds)
        state["now"] += seconds

    monkeypatch.setattr(dl.time, "sleep", sleep)
    return state


@pytest.mark.parametrize("fetch", [dl._count, dl._get_page])
def test_expired_budget_never_starts_http_request(clock, fetch):
    session = Session(lambda *args, **kwargs: pytest.fail("expired budget started HTTP request"))
    with pytest.raises(dl.TimeBudgetExceeded):
        fetch(session, "dataset", {}, deadline=0)


def test_retry_timeout_uses_time_left_after_failed_attempt_and_backoff(clock):
    timeouts = []

    def get(*args, timeout, **kwargs):
        timeouts.append(timeout.total)
        if len(timeouts) == 1:
            clock["now"] += 3
            raise requests.Timeout("first attempt")
        return Response()

    assert dl._count(Session(get), "dataset", "where", deadline=10) == 2
    assert timeouts == [10, 5]
    assert clock["sleeps"] == [2]


def test_timeout_exhausting_shared_budget_does_not_start_more_attempts(clock):
    timeouts = []

    def get(*args, timeout, **kwargs):
        timeouts.append(timeout.total)
        clock["now"] += 3 if len(timeouts) == 1 else timeout.total
        raise requests.Timeout("socket wait exhausted")

    with pytest.raises(dl.TimeBudgetExceeded):
        dl._get_page(Session(get), "dataset", {}, deadline=10)
    assert timeouts == [10, 5]
    assert clock["now"] == 10 and clock["sleeps"] == [2]


def test_backoff_cannot_run_past_budget(clock):
    def get(*args, **kwargs):
        clock["now"] += 1
        raise requests.ConnectionError("throttled")

    with pytest.raises(dl.TimeBudgetExceeded, match="insufficient budget"):
        dl._get_page(Session(get), "dataset", {}, deadline=2)
    assert not clock["sleeps"]


def test_response_that_arrives_after_deadline_is_not_treated_as_timely(clock):
    response = Response()

    def get(*args, **kwargs):
        clock["now"] = 11
        return response

    with pytest.raises(dl.TimeBudgetExceeded):
        dl._get_page(Session(get), "dataset", {}, deadline=10)
    assert response.closed
    assert not clock["sleeps"]


def test_without_deadline_retry_count_still_has_five_attempt_cap(clock):
    attempts = []

    def get(*args, timeout, **kwargs):
        attempts.append(timeout.total)
        raise requests.ConnectionError("unavailable")

    with pytest.raises(requests.ConnectionError):
        dl._get_page(Session(get), "dataset", {})
    assert attempts == [dl.HTTP_TIMEOUT] * 5
    assert clock["sleeps"] == [2, 4, 8, 16]


def test_zero_live_count_skips_raw_page_fetch(monkeypatch):
    deadlines = []

    def count(*args, deadline):
        deadlines.append(("count", deadline))
        return 0

    def pages(*args, deadline, **kwargs):
        deadlines.append(("pages", deadline))
        return []

    monkeypatch.setattr(dl, "_count", count)
    monkeypatch.setattr(dl, "_fetch_pages", pages)
    deadline = dl.time.monotonic() + 100
    sample, rows = dl._read_day(
        None, date(2024, 1, 1), ["dataset"], check_count=True, deadline=deadline
    )
    assert sample.empty and rows == 0
    assert deadlines == [("count", deadline)]


def test_uncounted_day_fetch_also_preserves_deadline(monkeypatch):
    received = []

    def read(*args, deadline):
        received.append(deadline)
        return pd.DataFrame(), 0

    monkeypatch.setattr(dl, "_read_day", read)
    dl._fetch_day(None, date(2024, 1, 1), ["dataset"], deadline=123)
    assert received == [123]


@pytest.mark.parametrize("failing_offset", [0, 4])
def test_large_page_failure_downgrades_at_same_offset_without_truncation(
    monkeypatch, clock, failing_offset
):
    monkeypatch.setattr(dl, "PAGE_SIZE", 2)
    calls = []
    raw = pd.DataFrame(
        {
            "sid": ["1004"] * 7,
            dl.EZPASS_TIME_COL: [f"2024-01-01T08:0{i}:00" for i in range(7)],
            "n_samples": [str(i) for i in range(7)],
        }
    )

    def get(*args, params, **kwargs):
        size, offset = params["$limit"], params["$offset"]
        calls.append((size, offset))
        if size == 4 and offset == failing_offset:
            raise requests.Timeout("large response throttled")
        response = Response()
        response.content = raw.iloc[offset : offset + size].to_csv(index=False).encode()
        return response

    pages = dl._fetch_pages(Session(get), "dataset", "where", page_size=4, deadline=100)
    combined = pd.concat(pages, ignore_index=True)
    pd.testing.assert_frame_equal(combined, raw)
    assert calls.count((4, failing_offset)) == 1
    failure = calls.index((4, failing_offset))
    assert calls[failure + 1] == (2, failing_offset)
    assert dl._downsample(combined).iloc[0]["n_samples"] == "6"
    assert clock["sleeps"] == [], "large pages must downgrade immediately after one attempt"


def test_nonzero_count_and_pages_share_deadline(monkeypatch):
    received = []
    frame = pd.DataFrame(
        {"sid": ["1004"], dl.EZPASS_TIME_COL: ["2024-01-01T08:00:00"], "n_samples": ["1"]}
    )

    def count(*args, deadline):
        received.append(("count", deadline))
        return 1

    def pages(*args, deadline, **kwargs):
        received.append(("pages", deadline))
        return [frame]

    monkeypatch.setattr(dl, "_count", count)
    monkeypatch.setattr(dl, "_fetch_pages", pages)
    deadline = dl.time.monotonic() + 100
    sample, rows = dl._read_day(
        None, date(2024, 1, 1), ["dataset"], check_count=True, deadline=deadline
    )
    assert len(sample) == rows == 1
    assert received == [("count", deadline), ("pages", deadline)]
