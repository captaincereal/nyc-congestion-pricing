"""Record exact primary inputs, source code and output hashes for an analysis snapshot."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from src.config import (
    EZPASS_MANIFEST_PATH,
    EZPASS_PARTS_DIR,
    EZPASS_SEGMENTS_PATH,
    HOURLY_PANEL_PATH,
    PROJECT_ROOT,
    TABLES_DIR,
)
from src.data.download_ezpass import VERIFICATION_METHOD


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    manifest = json.loads(EZPASS_MANIFEST_PATH.read_text())
    recorded = {p["part"]: p for p in manifest["parts"]}
    parts = []
    for path in sorted(EZPASS_PARTS_DIR.glob("*.parquet")):
        sha = digest(path)
        entry = recorded.get(path.name, {})
        parts.append(
            {
                "part": path.name,
                "sha256": sha,
                "rows": entry.get("rows"),
                "manifest_sha_matches": sha == entry.get("sha256"),
                "verified": bool(
                    entry.get("verified")
                    and entry.get("complete")
                    and entry.get("verification_method") == VERIFICATION_METHOD
                    and sha == entry.get("sha256")
                ),
                "verification_method": entry.get("verification_method"),
            }
        )
    source = [*PROJECT_ROOT.glob("src/**/*.py"), *PROJECT_ROOT.glob("sql/*.sql")]
    result = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "interpretation": "Exploratory diagnostics; no causal attribution established.",
        "panel_sha256": digest(HOURLY_PANEL_PATH),
        "segments_sha256": digest(EZPASS_SEGMENTS_PATH),
        "manifest_sha256": digest(EZPASS_MANIFEST_PATH),
        "primary_parts": parts,
        "all_primary_parts_verified": bool(parts) and all(p["verified"] for p in parts),
        "source_sha256": {
            p.relative_to(PROJECT_ROOT).as_posix(): digest(p) for p in sorted(source)
        },
        "table_sha256": {p.name: digest(p) for p in sorted(TABLES_DIR.glob("*.csv"))},
    }
    (TABLES_DIR / "analysis_provenance.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
