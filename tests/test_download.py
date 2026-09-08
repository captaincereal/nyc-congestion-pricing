import json
from datetime import date

import src.data.download as dl
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


def _part(month: str, rows: int = 100) -> dict:
    return {
        "part": f"dot_speeds_{month}.parquet",
        "month": month,
        "where": "x",
        "rows": rows,
        "rows_expected": rows,
        "bytes": 1,
        "sha256": "abc",
        "pulled_at": "2025-01-01T00:00:00+00:00",
        "complete": True,
    }


def test_write_manifest_merge_keeps_earlier_months(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    monkeypatch.setattr(dl, "RAW_MANIFEST_PATH", path)

    dl.write_manifest({"2024-01": _part("2024-01")})
    parts_by_month = dl._load_existing_parts()
    parts_by_month["2024-02"] = _part("2024-02", rows=50)
    dl.write_manifest(parts_by_month)

    m = json.loads(path.read_text())
    assert [p["month"] for p in m["parts"]] == ["2024-01", "2024-02"]
    assert m["total_rows"] == 150
    assert m["coverage"] == {"first_month": "2024-01", "last_month": "2024-02"}


def test_write_manifest_all_parts_complete_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "RAW_MANIFEST_PATH", tmp_path / "manifest.json")
    short = _part("2024-03")
    short["complete"] = False
    dl.write_manifest({"2024-03": short})
    assert json.loads((tmp_path / "manifest.json").read_text())["all_parts_complete"] is False


def test_load_existing_parts_missing_and_corrupt(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    monkeypatch.setattr(dl, "RAW_MANIFEST_PATH", path)
    assert dl._load_existing_parts() == {}
    path.write_text("{not json")
    assert dl._load_existing_parts() == {}
