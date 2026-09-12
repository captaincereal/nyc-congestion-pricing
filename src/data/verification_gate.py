"""Strict input and receipt checks for the explicitly frozen verification targets."""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src.config import EZPASS_TIME_COL
from src.data.download_ezpass import VERIFICATION_METHOD

PART_NAME = re.compile(r"ezpass_speeds_(\d{4}-\d{2})\.parquet\Z")
RECEIPT_NAME = re.compile(r"ezpass_verify_(\d{4}-\d{2})\.json\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class StateIntegrityError(ValueError):
    """Stored evidence is absent, inconsistent, or malformed."""


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateIntegrityError(f"cannot read valid JSON from {path.name}") from exc
    if not isinstance(value, dict):
        raise StateIntegrityError(f"{path.name}: expected a JSON object")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise StateIntegrityError(f"{label}: expected a nonnegative integer")
    return value


def _timestamp(value: object, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError as exc:
        raise StateIntegrityError(f"{label}: invalid check timestamp") from exc
    if parsed is None or parsed.tzinfo is None:
        raise StateIntegrityError(f"{label}: check timestamp must include a timezone")


def month_days(month: str) -> list[str]:
    try:
        first = date.fromisoformat(f"{month}-01")
    except (TypeError, ValueError) as exc:
        raise StateIntegrityError(f"invalid calendar month: {month}") from exc
    return [
        f"{month}-{day:02d}"
        for day in range(1, calendar.monthrange(first.year, first.month)[1] + 1)
    ]


def validate_part_identity(part: dict) -> None:
    name = part.get("part")
    match = PART_NAME.fullmatch(name) if isinstance(name, str) else None
    if match is None or match[1] != part.get("month"):
        raise StateIntegrityError("part name does not match its calendar month")
    month_days(part["month"])
    if not isinstance(part.get("sha256"), str) or SHA256.fullmatch(part["sha256"]) is None:
        raise StateIntegrityError(f"{name}: invalid SHA256")
    _integer(part.get("rows"), f"{name} rows")


def validate_manifest(manifest: dict) -> dict[str, dict]:
    """Validate structure without treating an unreadable manifest as an empty archive."""
    if not isinstance(manifest, dict):
        raise StateIntegrityError("manifest must be an object")
    entries = manifest.get("parts")
    if not isinstance(entries, list) or not entries:
        raise StateIntegrityError("manifest must contain a nonempty parts list")
    parts: dict[str, dict] = {}
    for part in entries:
        if not isinstance(part, dict):
            raise StateIntegrityError("manifest part must be an object")
        validate_part_identity(part)
        name = part["part"]
        if name in parts:
            raise StateIntegrityError(f"duplicate manifest part: {name}")
        _integer(part.get("rows_expected"), f"{name} rows_expected")
        _integer(part.get("bytes"), f"{name} bytes")
        if type(part.get("complete")) is not bool:
            raise StateIntegrityError(f"{name}: complete must be a boolean")
        if "verified" in part and type(part["verified"]) is not bool:
            raise StateIntegrityError(f"{name}: verified must be a boolean")
        parts[name] = part
    for field, source in (("total_rows", "rows"), ("total_rows_expected", "rows_expected")):
        if field in manifest:
            _integer(manifest[field], field)
        if field in manifest and manifest[field] != sum(p[source] for p in parts.values()):
            raise StateIntegrityError(f"manifest {field} disagrees with part records")
    return parts


def validate_local_parts(raw_dir: Path, manifest: dict) -> dict[str, dict]:
    parts = validate_manifest(manifest)
    for name, part in parts.items():
        path = raw_dir / "ezpass_speeds" / name
        if not path.is_file():
            raise StateIntegrityError(f"missing part: {name}")
        if path.stat().st_size != part["bytes"] or digest(path) != part["sha256"]:
            raise StateIntegrityError(f"part bytes or SHA256 mismatch: {name}")
        try:
            rows = pq.ParquetFile(path).metadata.num_rows
        except Exception as exc:  # noqa: BLE001 - invalid parquet is a provenance failure
            raise StateIntegrityError(f"cannot read parquet metadata: {name}") from exc
        if rows != part["rows"]:
            raise StateIntegrityError(f"parquet row count disagrees with manifest: {name}")
    return parts


def validate_receipt(receipt: dict, part: dict, *, method: str | None = None) -> dict:
    """Check partial receipt structure; completeness is separately required by the gate."""
    if receipt.get("month") != part["month"] or receipt.get("part_sha256") != part["sha256"]:
        raise StateIntegrityError(f"{part['part']}: receipt is bound to another part")
    recorded_method = receipt.get("verification_method")
    if not isinstance(recorded_method, str) or not recorded_method:
        raise StateIntegrityError(f"{part['part']}: receipt has no verification method")
    if method is not None and recorded_method != method:
        raise StateIntegrityError(f"{part['part']}: receipt uses a different verification method")
    days = receipt.get("days")
    if not isinstance(days, dict):
        raise StateIntegrityError(f"{part['part']}: receipt days must be an object")
    allowed = set(month_days(part["month"]))
    raw_rows = sampled_rows = 0
    for day, entry in days.items():
        if day not in allowed or not isinstance(entry, dict):
            raise StateIntegrityError(f"{part['part']}: invalid receipt day {day}")
        raw = _integer(entry.get("source_rows"), f"{day} source_rows")
        sampled = _integer(entry.get("sample_rows"), f"{day} sample_rows")
        if raw < sampled:
            raise StateIntegrityError(f"{day}: retained rows exceed raw rows")
        _timestamp(entry.get("checked_at"), day)
        raw_rows += raw
        sampled_rows += sampled
    if sampled_rows > part["rows"]:
        raise StateIntegrityError(f"{part['part']}: receipt contains too many retained rows")
    return {
        "days_checked": len(days),
        "total_days": len(allowed),
        "source_rows": raw_rows,
        "sample_rows": sampled_rows,
    }


def verification_summary(raw_dir: Path, targets_path: Path | None = None) -> dict:
    """Report a fail-closed gate for every named immutable target, without running analysis."""
    raw_dir = Path(raw_dir)
    if targets_path is None:
        try:
            targets = {
                "schema_version": 1,
                "parts": list(
                    validate_manifest(load_json(raw_dir / "ezpass_manifest.json")).values()
                ),
            }
        except StateIntegrityError as exc:
            return {
                "gate_passed": False,
                "target_months": 0,
                "verified_months": 0,
                "days_checked": 0,
                "total_days": 0,
                "parts": [],
                "errors": [str(exc)],
            }
    else:
        targets = load_json(Path(targets_path))
    entries = targets.get("parts")
    if targets.get("schema_version") != 1 or not isinstance(entries, list) or not entries:
        raise StateIntegrityError(
            "verification targets require schema_version 1 and nonempty parts"
        )
    names = set()
    for target in entries:
        if not isinstance(target, dict):
            raise StateIntegrityError("verification target must be an object")
        validate_part_identity(target)
        if target["part"] in names:
            raise StateIntegrityError(f"duplicate verification target: {target['part']}")
        names.add(target["part"])
    errors: list[str] = []
    try:
        records = validate_manifest(load_json(raw_dir / "ezpass_manifest.json"))
    except StateIntegrityError as exc:
        errors.append(str(exc))
        records = {}
    if targets_path is None:
        unrecorded = {path.name for path in (raw_dir / "ezpass_speeds").glob("*.parquet")} - set(
            records
        )
        if unrecorded:
            errors.append(f"unrecorded primary input files: {', '.join(sorted(unrecorded))}")
    results = []
    for target in entries:
        result = {
            "month": target["month"],
            "part": target["part"],
            "expected_sha256": target["sha256"],
            "expected_rows": target["rows"],
            "verified": False,
            "days_checked": 0,
            "total_days": len(month_days(target["month"])),
            "errors": [],
        }
        try:
            record = records.get(target["part"])
            if record is None:
                raise StateIntegrityError("target is missing from the manifest")
            if record["sha256"] != target["sha256"] or record["rows"] != target["rows"]:
                raise StateIntegrityError("manifest differs from the frozen target identity")
            path = raw_dir / "ezpass_speeds" / target["part"]
            if not path.is_file() or digest(path) != target["sha256"]:
                raise StateIntegrityError("target file is missing or has a different SHA256")
            if path.stat().st_size != record["bytes"]:
                raise StateIntegrityError("target byte size differs from manifest")
            result["sha256"] = target["sha256"]
            timestamps = pd.read_parquet(path, columns=[EZPASS_TIME_COL])[EZPASS_TIME_COL]
            ts = pd.to_datetime(timestamps, errors="raise")
            if ts.isna().any() or ts.dt.tz is not None:
                raise StateIntegrityError("target contains missing or timezone-aware timestamps")
            actual = {
                str(day.date()): int(count)
                for day, count in ts.dt.normalize().value_counts().items()
            }
            if len(ts) != target["rows"] or set(actual) - set(month_days(target["month"])):
                raise StateIntegrityError(
                    "retained row count or calendar month differs from target"
                )
            receipt = load_json(
                raw_dir / "ezpass_verification" / f"ezpass_verify_{target['month']}.json"
            )
            progress = validate_receipt(receipt, target, method=VERIFICATION_METHOD)
            for day, evidence in receipt["days"].items():
                if evidence["sample_rows"] != actual.get(day, 0):
                    raise StateIntegrityError(f"{day}: receipt count differs from retained rows")
            result.update(progress)
            if progress["days_checked"] != progress["total_days"]:
                raise StateIntegrityError("daily verification is incomplete")
            if progress["sample_rows"] != target["rows"]:
                raise StateIntegrityError("receipt total differs from retained rows")
            if not record.get("verified") or not record["complete"]:
                raise StateIntegrityError("manifest does not record completed verification")
            if record.get("verification_method") != VERIFICATION_METHOD:
                raise StateIntegrityError("manifest uses a different verification method")
            if record["rows_expected"] != target["rows"]:
                raise StateIntegrityError("manifest expected rows differs from retained rows")
            _timestamp(record.get("verified_at"), "verified_at")
            if _integer(record.get("source_rows"), "source_rows") != progress["source_rows"]:
                raise StateIntegrityError("manifest raw count differs from receipts")
            result["verified"] = True
        except (StateIntegrityError, OSError, ValueError, KeyError, TypeError) as exc:
            result["errors"].append(str(exc))
            errors.append(f"{target['month']}: {exc}")
        results.append(result)
    return {
        "gate_passed": not errors and all(part["verified"] for part in results),
        "target_months": len(results),
        "verified_months": sum(part["verified"] for part in results),
        "days_checked": sum(part["days_checked"] for part in results),
        "total_days": sum(part["total_days"] for part in results),
        "parts": results,
        "errors": errors,
    }
