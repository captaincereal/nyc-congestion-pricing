"""Check source priority, the fixed window and durable failure publication."""

from datetime import date

import pytest

from src.data import hosted_backfill as hosted


def test_fixed_window_and_contiguous_pre_priority():
    months = hosted.priority_months()
    assert len(months) == len(set(months)) == 44
    assert months[:3] == [date(2024, 12, 1), date(2024, 11, 1), date(2024, 10, 1)]
    assert months[23] == date(2023, 1, 1)
    assert months[24] == date(2025, 1, 1)
    assert months[-1] == date(2026, 8, 1)
    with pytest.raises(ValueError):
        hosted.priority_months(date(2026, 10, 1))


def test_coverage_leads_with_preperiod_adjoining_treatment():
    parts = {m: {"complete": True} for m in ["2024-06", "2024-10", "2024-11", "2024-12"]}
    report = hosted.coverage(parts)
    assert report["held_months"] == 4
    assert report["contiguous_pre_months_ending_2024_12"] == 3
    assert report["contiguous_pre_start"] == "2024-10"


def test_verification_failure_is_published_and_never_falls_through_to_download(monkeypatch):
    events = []

    class Store:
        def restore(self, _):
            events.append("restore")

        def publish(self, _):
            events.append("publish")

    monkeypatch.setattr(hosted, "_session", lambda: object())
    monkeypatch.setattr(hosted, "_load_existing_parts", lambda _: {"2024-06": {}})
    monkeypatch.setattr(
        hosted,
        "verification_summary",
        lambda *args: {
            "gate_passed": False,
            "parts": [{"month": "2024-06", "verified": False, "sha256": "checked"}],
        },
    )

    def fail(*_):
        events.append("verify")
        raise RuntimeError("source replay disagrees")

    monkeypatch.setattr(hosted, "verify_month", fail)
    monkeypatch.setattr(hosted, "write_status", lambda **kw: events.append(kw))
    monkeypatch.setattr(
        hosted.download, "download_month", lambda *a, **k: pytest.fail("downloaded")
    )
    with pytest.raises(RuntimeError, match="source replay"):
        hosted.run_pass(Store(), 1, 1)
    assert events[:3] == ["restore", "verify", "publish"]
    assert "source replay disagrees" in events[-1]["error"]


def test_failed_restore_cannot_publish_partial_state(monkeypatch):
    class Store:
        def restore(self, _):
            raise RuntimeError("corrupt release")

        def publish(self, _):
            pytest.fail("must not publish failed restore")

    with pytest.raises(RuntimeError, match="corrupt release"):
        hosted.run_pass(Store(), 1, 1)
