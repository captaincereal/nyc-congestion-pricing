"""Report whether a fresh hosted runner can build a pre/post primary panel."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

from src.config import EZPASS_TIME_COL, RAW_DIR, TREATMENT_DATE
from src.data.verification_gate import StateIntegrityError, verification_summary


def readiness(raw_dir: Path) -> tuple[bool, str]:
    """Require the geometry and actual observations on both sides of treatment.

    An absent release or a pre-only backfill is expected during bootstrap.
    Corrupt existing parts remain an error rather than looking like a wait.
    """
    parts = sorted((raw_dir / "ezpass_speeds").glob("ezpass_speeds_*.parquet"))
    if not parts:
        return False, "Waiting for the backfill: no primary month parts have been published."
    if not (raw_dir / "ezpass_segments.parquet").is_file():
        return False, "Waiting for the backfill: the segment geometry asset is missing."
    with duckdb.connect() as con:
        first, last = con.execute(
            f'SELECT min(CAST("{EZPASS_TIME_COL}" AS TIMESTAMP)), '
            f'max(CAST("{EZPASS_TIME_COL}" AS TIMESTAMP)) '
            "FROM read_parquet(?, union_by_name=true)",
            [[str(part) for part in parts]],
        ).fetchone()
    if first is None or last is None:
        return False, "Waiting for the backfill: primary parts contain no dated observations."
    if not (first.date() < TREATMENT_DATE <= last.date()):
        return False, (
            "Waiting for pre- and post-treatment data: "
            f"available observations span {first} to {last}."
        )
    try:
        gate = verification_summary(raw_dir, None)
    except StateIntegrityError as exc:
        return False, f"Waiting for valid source-verification metadata: {exc}"
    if not gate["gate_passed"]:
        return False, (
            f"Waiting for source verification: {gate['verified_months']}/"
            f"{gate['target_months']} inputs verified; "
            f"{gate['days_checked']}/{gate['total_days']} daily receipts."
        )
    return True, (
        f"Primary inputs available from {first} to {last}. "
        "Every input has complete source receipts; identifying assumptions still gate claims."
    )


def main() -> None:
    ready, message = readiness(RAW_DIR)
    print(message)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"ready={str(ready).lower()}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")


if __name__ == "__main__":
    main()
