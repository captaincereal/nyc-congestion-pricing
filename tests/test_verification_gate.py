import json
from pathlib import Path

import pandas as pd
import pytest

from src.config import EZPASS_TIME_COL
from src.data.download_ezpass import VERIFICATION_METHOD
from src.data.verification_gate import (
    StateIntegrityError,
    digest,
    month_days,
    verification_summary,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_archive(root: Path) -> tuple[Path, Path, dict, dict]:
    raw = root / "raw"
    path = raw / "ezpass_speeds" / "ezpass_speeds_2024-06.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({EZPASS_TIME_COL: ["2024-06-01T08:00:00"]}).to_parquet(path, index=False)
    part = {
        "month": "2024-06",
        "part": path.name,
        "sha256": digest(path),
        "bytes": path.stat().st_size,
        "rows": 1,
        "rows_expected": 1,
        "complete": True,
        "verified": True,
        "verification_method": VERIFICATION_METHOD,
        "verified_at": "2026-09-12T12:00:00+00:00",
        "source_rows": 2,
        "where": "the original query",
        "pulled_at": "2026-09-01T12:00:00+00:00",
    }
    receipt = {
        "month": "2024-06",
        "part_sha256": part["sha256"],
        "verification_method": VERIFICATION_METHOD,
        "days": {
            day: {
                "source_rows": 2 if day.endswith("-01") else 0,
                "sample_rows": 1 if day.endswith("-01") else 0,
                "checked_at": "2026-09-12T11:59:00+00:00",
            }
            for day in month_days("2024-06")
        },
    }
    write_json(raw / "ezpass_manifest.json", {"parts": [part], "total_rows": 1})
    write_json(raw / "ezpass_verification" / "ezpass_verify_2024-06.json", receipt)
    targets = root / "targets.json"
    write_json(targets, {"schema_version": 1, "parts": [part]})
    return raw, targets, part, receipt


def test_gate_requires_every_calendar_day_even_when_row_totals_already_match(tmp_path):
    raw, targets, _, receipt = make_archive(tmp_path)
    assert verification_summary(raw, targets)["gate_passed"]
    receipt["days"].pop("2024-06-02")  # this zero-row day still needs an independent check
    write_json(raw / "ezpass_verification" / "ezpass_verify_2024-06.json", receipt)
    result = verification_summary(raw, targets)
    assert not result["gate_passed"]
    assert result["days_checked"] == 29 and result["total_days"] == 30


@pytest.mark.parametrize("failure", ["hash", "method", "flag", "raw_total", "bytes"])
def test_gate_rejects_stale_or_inconsistent_manifest_evidence(tmp_path, failure):
    raw, targets, part, _ = make_archive(tmp_path)
    if failure == "hash":
        part["sha256"] = "0" * 64
    elif failure == "method":
        part["verification_method"] = "a weaker check"
    elif failure == "flag":
        part["verified"] = False
    elif failure == "raw_total":
        part["source_rows"] = 3
    else:
        part["bytes"] += 1
    write_json(raw / "ezpass_manifest.json", {"parts": [part]})
    result = verification_summary(raw, targets)
    assert not result["gate_passed"]
    assert result["errors"]


@pytest.mark.parametrize("bad_count", [-1, True, "2"])
def test_receipt_count_schema_is_strict(tmp_path, bad_count):
    raw, targets, _, receipt = make_archive(tmp_path)
    receipt["days"]["2024-06-01"]["source_rows"] = bad_count
    write_json(raw / "ezpass_verification" / "ezpass_verify_2024-06.json", receipt)
    result = verification_summary(raw, targets)
    assert not result["gate_passed"]
    assert "nonnegative integer" in " ".join(result["errors"])


def test_equal_receipt_totals_cannot_hide_wrong_day_counts(tmp_path):
    raw, targets, _, receipt = make_archive(tmp_path)
    receipt["days"]["2024-06-01"]["sample_rows"] = 0
    receipt["days"]["2024-06-02"].update(sample_rows=1, source_rows=2)
    write_json(raw / "ezpass_verification" / "ezpass_verify_2024-06.json", receipt)
    result = verification_summary(raw, targets)
    assert not result["gate_passed"]
    assert result["days_checked"] == 0
    assert "receipt count differs" in " ".join(result["errors"])


def test_missing_receipt_is_not_replaced_by_verified_flag(tmp_path):
    raw, targets, _, _ = make_archive(tmp_path)
    (raw / "ezpass_verification" / "ezpass_verify_2024-06.json").unlink()
    assert not verification_summary(raw, targets)["gate_passed"]


def test_gate_checks_original_raw_bytes(tmp_path):
    raw, targets, part, _ = make_archive(tmp_path)
    (raw / "ezpass_speeds" / part["part"]).write_bytes(b"different raw bytes")
    assert not verification_summary(raw, targets)["gate_passed"]


def test_corrupt_or_missing_manifest_never_passes_as_an_empty_archive(tmp_path):
    raw, targets, _, _ = make_archive(tmp_path)
    (raw / "ezpass_manifest.json").write_text("{corrupt", encoding="utf-8")
    assert not verification_summary(raw, targets)["gate_passed"]
    assert not verification_summary(raw)["gate_passed"]


def test_empty_targets_are_invalid_and_generic_gate_checks_all_current_parts(tmp_path):
    raw, targets, _, _ = make_archive(tmp_path)
    result = verification_summary(raw)
    assert result["gate_passed"] and result["target_months"] == 1
    write_json(targets, {"schema_version": 1, "parts": []})
    with pytest.raises(StateIntegrityError, match="nonempty"):
        verification_summary(raw, targets)


def test_generic_analysis_gate_rejects_inputs_absent_from_manifest(tmp_path):
    raw, targets, part, _ = make_archive(tmp_path)
    source = raw / "ezpass_speeds" / part["part"]
    (source.parent / "ezpass_speeds_2024-07.parquet").write_bytes(source.read_bytes())
    assert verification_summary(raw, targets)[
        "gate_passed"
    ], "the explicit original target still passes"
    result = verification_summary(raw)
    assert not result["gate_passed"]
    assert "unrecorded primary" in " ".join(result["errors"])
