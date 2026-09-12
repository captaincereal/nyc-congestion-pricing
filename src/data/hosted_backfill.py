"""Verification-first source work with durable checkpoints on free runners."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import time
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from src.config import EZPASS_MANIFEST_PATH, PROJECT_ROOT, RAW_DIR
from src.data import download_ezpass as download
from src.data.download import _iter_months, _load_existing_parts, _session
from src.data.release_store import ReleaseStore
from src.data.verification_gate import verification_summary

log = logging.getLogger(__name__)
TARGETS = PROJECT_ROOT / "docs" / "verification_targets.json"
FROZEN_END = date(2026, 9, 1)  # 44 complete months at the owner's instruction


def priority_months(end: date = FROZEN_END) -> list[date]:
    """Deepen the contiguous pre-period first; then finish the frozen post window."""
    if end > FROZEN_END:
        raise ValueError("This pass is frozen at August 2026")
    months = [m for m in _iter_months(date(2023, 1, 1), end) if m < end]
    return sorted((m for m in months if m < date(2025, 1, 1)), reverse=True) + [
        m for m in months if m >= date(2025, 1, 1)
    ]


def coverage(parts: dict[str, dict]) -> dict:
    wanted = [f"{m:%Y-%m}" for m in priority_months()]
    held = {tag for tag in wanted if parts.get(tag, {}).get("complete") is True}
    pre = sorted(tag for tag in held if tag < "2025-01")
    depth = 0
    for month in sorted((m for m in priority_months() if m.year < 2025), reverse=True):
        if f"{month:%Y-%m}" not in held:
            break
        depth += 1
    return {
        "contiguous_pre_months_ending_2024_12": depth,
        "contiguous_pre_start": pre[-depth] if depth else None,
        "required_pre_months": 24,
        "held_months": len(held),
        "target_months": len(wanted),
        "frozen_start": "2023-01",
        "frozen_end": "2026-08",
        "missing_months": sorted(set(wanted) - held),
    }


def write_status(*, error: str | None = None) -> dict:
    status = {
        "checked_at": datetime.now(UTC).isoformat(),
        "run_url": (
            f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/"
            f"{os.environ['GITHUB_RUN_ID']}"
            if os.environ.get("GITHUB_RUN_ID")
            else None
        ),
        "coverage": coverage(_load_existing_parts(EZPASS_MANIFEST_PATH)),
        "original_eight": verification_summary(RAW_DIR, TARGETS),
        "all_held_inputs": verification_summary(RAW_DIR, None),
        "error": error,
    }
    dest = PROJECT_ROOT / "outputs" / "tables" / "source_status.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    c, gate = status["coverage"], status["original_eight"]
    message = (
        f"Contiguous pre-period: {c['contiguous_pre_months_ending_2024_12']}/24 months; "
        f"coverage: {c['held_months']}/{c['target_months']}. "
        f"Original inputs verified: {gate['verified_months']}/{gate['target_months']}; "
        f"daily receipts: {gate['days_checked']}/{gate['total_days']}."
    )
    log.info(message)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(message + (f" Error: {error}" if error else "") + "\n\n")
    return status


def verify_month(session, tag: str, deadline: float) -> None:
    # A legacy flag without receipts must not short-circuit deterministic replay.
    parts = _load_existing_parts(EZPASS_MANIFEST_PATH)
    parts[tag].update(verified=False, verified_at=None)
    download._write(parts)
    month = date.fromisoformat(tag + "-01")
    download.verify(session, month, month, deadline=deadline, existing_only=False)


def _on_termination(signum, _frame) -> None:
    raise download.TimeBudgetExceeded(f"Runner shutdown ({signum}); checkpointing")


def run_pass(store: ReleaseStore, budget_minutes: float, slice_minutes: float) -> dict:
    if not 1 <= budget_minutes <= 300 or not 1 <= slice_minutes <= 30:
        raise ValueError("budget must be 1..300 minutes; checkpoint slice 1..30 minutes")
    deadline = time.monotonic() + budget_minutes * 60
    # Never publish a partial restore over the last good snapshot.
    store.restore(RAW_DIR)
    session = _session()
    error = None
    try:
        while time.monotonic() < deadline:
            gate = verification_summary(RAW_DIR, TARGETS)
            parts = _load_existing_parts(EZPASS_MANIFEST_PATH)
            slice_end = min(deadline, time.monotonic() + slice_minutes * 60)
            if not gate["gate_passed"]:
                pending = [p for p in gate["parts"] if not p["verified"]]
                tag = pending[0]["month"]
                if tag not in parts:
                    raise RuntimeError(f"Pinned original part missing: {tag}; no substitution")
                if "sha256" not in pending[0]:
                    raise RuntimeError(f"Pinned original identity failed: {pending[0]['errors']}")
                log.info("Original-input verification priority: %s", tag)
                verify_month(session, tag, slice_end)
            else:
                all_inputs = verification_summary(RAW_DIR, None)
                unchecked = [p["month"] for p in all_inputs["parts"] if not p["verified"]]
                if unchecked:
                    verify_month(session, unchecked[0], slice_end)
                else:
                    missing = [
                        m
                        for m in priority_months()
                        if f"{m:%Y-%m}" not in parts
                        or parts[f"{m:%Y-%m}"].get("complete") is not True
                    ]
                    if not missing:
                        log.info("Frozen 44-month archive complete; no extension requested")
                        break
                    month = missing[0]
                    log.info("Contiguous-pre-period backfill priority: %s", month)
                    try:
                        rec = download.download_month(
                            session,
                            month,
                            force=False,
                            prior=parts.get(f"{month:%Y-%m}"),
                            do_count=True,
                            deadline=slice_end,
                        )
                        parts[rec.month] = asdict(rec)
                        download._write(parts)
                    except download.TimeBudgetExceeded as exc:
                        log.info("%s", exc)
            store.publish(RAW_DIR)
            write_status()
    except download.TimeBudgetExceeded as exc:
        log.info("%s", exc)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        store.publish(RAW_DIR)
        status = write_status(error=error)
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budget-minutes", type=float, default=float(os.environ.get("SOURCE_BUDGET_MIN", "285"))
    )
    parser.add_argument(
        "--slice-minutes", type=float, default=float(os.environ.get("SOURCE_SLICE_MIN", "12"))
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _on_termination)
    store = ReleaseStore(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    run_pass(store, args.budget_minutes, args.slice_minutes)


if __name__ == "__main__":
    main()
