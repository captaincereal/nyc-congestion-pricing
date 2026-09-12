"""Independent raw counts and replay must justify every verification flag."""

import json
import sys
import time
from dataclasses import asdict
from datetime import date

import pandas as pd
import pytest

import src.data.download_ezpass as dl
from src.config import EZPASS_TIME_COL


@pytest.fixture
def archive(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "EZPASS_PARTS_DIR", tmp_path / "parts")
    monkeypatch.setattr(dl, "EZPASS_DAYS_DIR", tmp_path / "days")
    monkeypatch.setattr(dl, "EZPASS_MANIFEST_PATH", tmp_path / "manifest.json")
    days = [date(2024, 1, 1), date(2024, 1, 2)]
    monkeypatch.setattr(dl, "_days_in_month", lambda month: iter(days))
    return days


def raw_day(day):
    return pd.DataFrame(
        {
            "sid": ["1004", "1004"],
            EZPASS_TIME_COL: [f"{day}T08:00:00", f"{day}T08:01:00"],
            "median_speed_fps": ["10.0", "20.0"],
            "median_tt_sec": ["30.0", "30.0"],
            "n_samples": ["5", "10"],
        }
    )


def seed_part(days):
    part = dl.EZPASS_PARTS_DIR / "ezpass_speeds_2024-01.parquet"
    dl._write_parquet_atomic(pd.concat([dl._downsample(raw_day(d)) for d in days]), part)
    return part


def fake_api(monkeypatch):
    calls = []

    def replay(session, day, datasets, **kwargs):
        assert kwargs["check_count"]
        calls.append(day)
        return dl._downsample(raw_day(day)), 2

    monkeypatch.setattr(dl, "_read_day", replay)
    return calls


def manifest_part():
    return dl._load_existing_parts(dl.EZPASS_MANIFEST_PATH)["2024-01"]


def test_count_compares_raw_pages_before_downsample(monkeypatch):
    monkeypatch.setattr(dl, "_count", lambda *args, **kwargs: 2)
    monkeypatch.setattr(dl, "_fetch_pages", lambda *args, **kwargs: [raw_day(date(2024, 1, 1))])
    sampled, source_rows = dl._read_day(None, date(2024, 1, 1), ["old"], check_count=True)
    assert source_rows == 2
    assert len(sampled) == 1
    assert sampled.iloc[0]["n_samples"] == "10"


def test_raw_count_mismatch_cannot_be_hidden_by_sampling(monkeypatch):
    monkeypatch.setattr(dl, "_count", lambda *args, **kwargs: 3)
    monkeypatch.setattr(dl, "_fetch_pages", lambda *args, **kwargs: [raw_day(date(2024, 1, 1))])
    with pytest.raises(dl.VerificationError, match="2 raw rows fetched; expected 3"):
        dl._read_day(None, date(2024, 1, 1), ["old"], check_count=True)


def test_verify_upgrades_manifest_preserves_provenance_and_raw(archive, monkeypatch):
    part = seed_part(archive)
    original = part.read_bytes()
    prior = asdict(dl.download_month(None, archive[0], force=False))
    prior.update(pulled_at="original pull", note="preserve me")
    other = {**prior, "month": "2023-12", "part": "old.parquet"}
    dl._write({"2023-12": other, "2024-01": prior})
    calls = fake_api(monkeypatch)

    dl.verify(None, archive[0], archive[0])

    rec = manifest_part()
    assert rec["verified"] and rec["complete"]
    assert rec["rows"] == rec["rows_expected"] == 2
    assert rec["source_rows"] == 4
    assert rec["verification_method"] == dl.VERIFICATION_METHOD
    assert rec["verified_at"]
    assert rec["pulled_at"] == "original pull" and rec["note"] == "preserve me"
    assert dl._load_existing_parts(dl.EZPASS_MANIFEST_PATH)["2023-12"] == other
    assert part.read_bytes() == original
    assert calls == archive
    dl.verify(None, archive[0], archive[0])
    assert calls == archive, "a hash-identical verified part resumes its completed audit"


def test_equal_counts_different_value_fails_verification(archive, monkeypatch):
    part = seed_part(archive)
    original = part.read_bytes()

    def wrong_replay(session, day, datasets, **kwargs):
        replay = dl._downsample(raw_day(day))
        replay["median_speed_fps"] = "99"
        return replay, 2

    monkeypatch.setattr(dl, "_read_day", wrong_replay)
    with pytest.raises(SystemExit, match="1 problem month"):
        dl.verify(None, archive[0], archive[0])
    rec = manifest_part()
    assert not rec["verified"] and not rec["complete"]
    assert "retained sample differs" in rec["verification_error"]
    assert part.read_bytes() == original


def test_budget_receipts_resume_only_successful_days(archive, monkeypatch):
    seed_part(archive)
    clock = {"now": 0}
    monkeypatch.setattr(dl.time, "monotonic", lambda: clock["now"])
    calls = []

    def replay(session, day, datasets, **kwargs):
        calls.append(day)
        clock["now"] += 2
        return dl._downsample(raw_day(day)), 2

    monkeypatch.setattr(dl, "_read_day", replay)
    dl.verify(None, archive[0], archive[0], deadline=1)
    assert not manifest_part()["verified"]
    receipt = json.loads(dl._receipt_path(archive[0]).read_text())
    assert list(receipt["days"]) == [str(archive[0])]
    dl.verify(None, archive[0], archive[0], deadline=10)
    assert manifest_part()["verified"]
    assert calls == archive


@pytest.mark.parametrize("changed", ["hash", "method"])
def test_stale_receipts_require_replay(archive, monkeypatch, changed):
    part = seed_part(archive)
    calls = fake_api(monkeypatch)
    dl.verify(None, archive[0], archive[0])
    rec = manifest_part()
    rec["verified"] = False
    dl._write({"2024-01": rec})
    if changed == "hash":
        # Change physical row order while retaining exactly the same sample.
        dl._write_parquet_atomic(pd.read_parquet(part).iloc[::-1], part)
    else:
        monkeypatch.setattr(dl, "VERIFICATION_METHOD", "revised-method")
    dl.verify(None, archive[0], archive[0])
    assert calls == archive + archive
    assert manifest_part()["verified"]


def test_missing_parts_fail_explicit_range_and_downgrade_manifest(archive):
    seed_part(archive)
    rec = asdict(dl.download_month(None, archive[0], force=False))
    missing = {**rec, "month": "2024-02", "verified": True}
    dl._write({"2024-02": missing})
    with pytest.raises(SystemExit, match="2024-02"):
        dl.verify(None, date(2024, 2, 1), date(2024, 2, 1))
    assert not dl._load_existing_parts(dl.EZPASS_MANIFEST_PATH)["2024-02"]["verified"]
    dl.verify(None, date(2024, 2, 1), date(2024, 2, 1), existing_only=True)


def test_preexisting_and_legacy_flags_require_actual_verification(archive):
    seed_part(archive)
    rec = dl.download_month(None, archive[0], force=False)
    assert not rec.verified
    old = {**asdict(rec), "verified": True}
    old.pop("verification_method")
    assert not dl.download_month(None, archive[0], force=False, prior=old).verified


def test_counted_download_and_checkpoint_replay_use_compatible_units(archive, monkeypatch):
    dl._write_parquet_atomic(dl._downsample(raw_day(archive[0])), dl._day_part_path(archive[0]))
    calls = fake_api(monkeypatch)
    rec = dl.download_month(None, archive[0], force=False, do_count=True)
    assert rec.verified and rec.complete
    assert rec.rows == rec.rows_expected == 2
    assert rec.source_rows == 4
    assert calls == archive, "a checkpoint without raw-count evidence needs independent replay"
    receipt = json.loads(dl._receipt_path(archive[0]).read_text())
    assert receipt["part_sha256"] == rec.sha256
    assert receipt["verification_method"] == dl.VERIFICATION_METHOD
    assert set(receipt["days"]) == {str(day) for day in archive}
    assert sum(day["source_rows"] for day in receipt["days"].values()) == rec.source_rows
    assert sum(day["sample_rows"] for day in receipt["days"].values()) == rec.rows
    assert not list(dl.EZPASS_DAYS_DIR.glob("*.receipt.json"))


def test_counted_download_resumes_checked_checkpoint_without_second_replay(archive, monkeypatch):
    clock = {"now": 0}
    monkeypatch.setattr(dl.time, "monotonic", lambda: clock["now"])
    calls = []

    def replay(session, day, datasets, **kwargs):
        calls.append(day)
        clock["now"] += 2
        return dl._downsample(raw_day(day)), 2

    monkeypatch.setattr(dl, "_read_day", replay)
    with pytest.raises(dl.TimeBudgetExceeded):
        dl.download_month(None, archive[0], force=False, do_count=True, deadline=1)
    checkpoint = dl._day_part_path(archive[0])
    original = checkpoint.read_bytes()
    evidence = json.loads(dl._day_receipt_path(archive[0]).read_text())
    assert evidence["checkpoint_sha256"] == dl._sha256(checkpoint)
    assert evidence["sample_rows"] == 1 and evidence["source_rows"] == 2
    rec = dl.download_month(None, archive[0], force=False, do_count=True, deadline=10)
    assert calls == archive, "a counted checkpoint must survive a budget-limited hosted pass"
    assert rec.verified and rec.source_rows == 4
    assert original, "the first checkpoint was durable before the next pass"


@pytest.mark.parametrize("changed", ["hash", "method", "count"])
def test_stale_checkpoint_evidence_requires_replay(archive, monkeypatch, changed):
    first = archive[0]
    checkpoint = dl._day_part_path(first)
    sample = dl._downsample(raw_day(first))
    dl._write_parquet_atomic(sample, checkpoint)
    evidence = dl._record_checked_day(first, checkpoint, sample, 2)
    if changed == "hash":
        evidence["checkpoint_sha256"] = "old hash"
    elif changed == "method":
        evidence["verification_method"] = "old method"
    else:
        evidence["source_rows"] = -1
    dl._save_receipt(dl._day_receipt_path(first), evidence)
    calls = fake_api(monkeypatch)
    rec = dl.download_month(None, first, force=False, do_count=True)
    assert calls == archive
    assert rec.verified


def test_existing_verified_flag_without_receipts_still_replays(archive, monkeypatch):
    seed_part(archive)
    rec = asdict(dl.download_month(None, archive[0], force=False))
    rec.update(verified=True, verification_method=dl.VERIFICATION_METHOD)
    dl._write({"2024-01": rec})
    calls = fake_api(monkeypatch)
    dl.verify(None, archive[0], archive[0])
    assert calls == archive
    receipt = json.loads(dl._receipt_path(archive[0]).read_text())
    assert len(receipt["days"]) == len(archive)


@pytest.mark.parametrize("invalid", [{"source_rows": -1}, {"checked_at": "bad timestamp"}])
def test_malformed_monthly_day_evidence_requires_replay(archive, monkeypatch, invalid):
    seed_part(archive)
    calls = fake_api(monkeypatch)
    dl.verify(None, archive[0], archive[0])
    receipt = json.loads(dl._receipt_path(archive[0]).read_text())
    receipt["days"][str(archive[0])].update(invalid)
    dl._save_receipt(dl._receipt_path(archive[0]), receipt)
    dl.verify(None, archive[0], archive[0])
    assert calls == archive + archive[:1]


def test_malformed_receipt_shape_is_rebuilt(archive, monkeypatch):
    seed_part(archive)
    calls = fake_api(monkeypatch)
    dl._save_receipt(dl._receipt_path(archive[0]), ["broken shape"])
    dl.verify(None, archive[0], archive[0])
    assert calls == archive
    assert manifest_part()["verified"]


def test_corrupt_checkpoint_is_never_silently_replaced(archive, monkeypatch):
    checkpoint = dl._downsample(raw_day(archive[0]))
    checkpoint["median_speed_fps"] = "99"
    path = dl._day_part_path(archive[0])
    dl._write_parquet_atomic(checkpoint, path)
    original = path.read_bytes()
    fake_api(monkeypatch)
    with pytest.raises(dl.VerificationError, match="retained sample differs"):
        dl.download_month(None, archive[0], force=False, do_count=True)
    assert path.read_bytes() == original
    assert not dl.EZPASS_PARTS_DIR.exists()


def test_duplicate_retained_rows_and_out_of_window_timestamps_fail(archive, monkeypatch):
    part = seed_part(archive)
    duplicate = pd.concat([pd.read_parquet(part), pd.read_parquet(part).iloc[:1]])
    dl._write_parquet_atomic(duplicate, part)
    calls = fake_api(monkeypatch)
    with pytest.raises(SystemExit):
        dl.verify(None, archive[0], archive[0])
    assert not manifest_part()["verified"]
    duplicate.loc[:, EZPASS_TIME_COL] = "2024-02-01T00:00:00"
    dl._write_parquet_atomic(duplicate, part)
    before = list(calls)
    with pytest.raises(SystemExit):
        dl.verify(None, archive[0], archive[0])
    assert calls == before, "invalid local timestamps fail before any network read"


def test_expired_segments_budget_stops_before_request(monkeypatch):
    monkeypatch.setattr(dl, "_get_page", lambda *args: pytest.fail("budget should stop request"))
    with pytest.raises(dl.TimeBudgetExceeded):
        dl.fetch_segments(None, sample_days=(date(2024, 1, 1),), deadline=time.monotonic() - 1)


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 12)


@pytest.mark.parametrize("verify_mode", [False, True])
@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2025-01-01", "2025-03-01", [date(2025, 1, 1), date(2025, 2, 1)]),
        ("2026-08-01", None, [date(2026, 8, 1)]),
        ("2026-08-01", "2027-01-01", [date(2026, 8, 1)]),
    ],
)
def test_cli_end_is_exclusive_and_never_freezes_current_month(
    tmp_path, monkeypatch, verify_mode, start, end, expected
):
    monkeypatch.setattr(dl, "date", FixedDate)
    segments = tmp_path / "segments.parquet"
    segments.touch()
    monkeypatch.setattr(dl, "EZPASS_SEGMENTS_PATH", segments)
    monkeypatch.setattr(dl, "_session", lambda: None)
    monkeypatch.setattr(dl, "_load_existing_parts", lambda *args: {})
    monkeypatch.setattr(dl, "_write", lambda *args: None)
    seen = []

    def fake_download(session, month, **kwargs):
        seen.append(month)
        return dl.EzpassPartRecord("part", str(month), "", 1, 1, 1, "hash", "pull", True)

    def fake_verify(session, first, last, **kwargs):
        seen.extend(dl._iter_months(first, last))

    monkeypatch.setattr(dl, "download_month", fake_download)
    monkeypatch.setattr(dl, "verify", fake_verify)
    argv = ["download_ezpass", "--start", start]
    if end:
        argv += ["--end", end]
    if verify_mode:
        argv += ["--verify"]
    monkeypatch.setattr(sys, "argv", argv)
    dl.main()
    assert seen == expected


@pytest.mark.parametrize("month", [date(2026, 9, 1), date(2026, 10, 1)])
def test_direct_calls_reject_current_and_future_months(monkeypatch, month):
    monkeypatch.setattr(dl, "date", FixedDate)
    with pytest.raises(ValueError, match="only completed calendar months"):
        dl.download_month(None, month, force=False)
    with pytest.raises(ValueError, match="only completed calendar months"):
        dl._verify_part(None, month)
