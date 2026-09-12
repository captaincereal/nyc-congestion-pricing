"""Legacy verification flags must not become current replay evidence."""

import json

import pytest

from src.analysis import provenance as p


@pytest.mark.parametrize(
    ("method", "complete", "matching_hash", "expected"),
    [
        (None, True, True, False),
        (p.VERIFICATION_METHOD, False, True, False),
        (p.VERIFICATION_METHOD, True, False, False),
        (p.VERIFICATION_METHOD, True, True, True),
    ],
)
def test_only_complete_hash_bound_current_method_is_verified(
    tmp_path, monkeypatch, method, complete, matching_hash, expected
):
    part = tmp_path / "ezpass_speeds_2024-06.parquet"
    part.write_bytes(b"immutable test fixture")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "parts": [
                    {
                        "part": part.name,
                        "sha256": p.digest(part) if matching_hash else "wrong",
                        "verified": True,
                        "complete": complete,
                        "verification_method": method,
                    }
                ]
            }
        )
    )
    for name in ("PROJECT_ROOT", "TABLES_DIR", "EZPASS_PARTS_DIR"):
        monkeypatch.setattr(p, name, tmp_path)
    for name in ("HOURLY_PANEL_PATH", "EZPASS_SEGMENTS_PATH"):
        monkeypatch.setattr(p, name, part)
    monkeypatch.setattr(p, "EZPASS_MANIFEST_PATH", manifest)
    p.main()
    result = json.loads((tmp_path / "analysis_provenance.json").read_text())
    assert result["all_primary_parts_verified"] is expected
