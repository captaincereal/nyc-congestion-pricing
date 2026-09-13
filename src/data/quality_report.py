"""Phase 3 — generate docs/data_quality_report.md from stg_speed_readings.

Runs every named block in ``sql/02_quality_checks.sql`` against the persisted
DuckDB database and renders the results into one Markdown report. Blocks whose
name starts with ``hard_`` are assertions: a non-empty result is flagged as a
FAIL in the report (and the process exits non-zero) so it cannot be ignored.

Observed problems are reported here; *chosen* handling strategies live in a
separate "Proposed handling" section that a human edits — this script never
decides to drop data.

Usage:
    python -m src.data.quality_report
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import UTC, datetime

import duckdb

from src.config import DOCS_DIR, DUCKDB_PATH, EZPASS_MANIFEST_PATH, PROJECT_ROOT

log = logging.getLogger(__name__)

SQL_PATH = PROJECT_ROOT / "sql" / "02_quality_checks.sql"
REPORT_PATH = DOCS_DIR / "data_quality_report.md"

_NAME_RE = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)

# Blocks that are too large to inline; summarised instead of dumped.
LARGE_BLOCKS = {"daily_link_count"}

PROPOSED_HANDLING = """\
## Handling decisions

D1 in `docs/decision_register.md` remains open. The primary panel applies no
speed ceiling or probe-depth threshold. Separate robustness specifications
exclude low-depth hours and hours containing readings above 80 mph; they do not
alter the raw data or the primary outcome. A zero speed alone is not evidence
of an invalid reading. See `outputs/tables/robustness_comparison.csv`.
"""


def parse_blocks(sql: str) -> list[tuple[str, str]]:
    marks = list(_NAME_RE.finditer(sql))
    blocks = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(sql)
        body = sql[start:end].strip().rstrip(";").strip()
        if body:
            blocks.append((m.group(1), body))
    return blocks


def render(con: duckdb.DuckDBPyConnection) -> tuple[str, bool, list]:
    blocks = parse_blocks(SQL_PATH.read_text())
    now = datetime.now(UTC).isoformat(timespec="seconds")

    parts = [
        "# Data-quality report — E-Z Pass local-street staging\n",
        f"Generated: {now}",
        f"Source DB: `{DUCKDB_PATH.name}`  ·  raw manifest: "
        f"`{EZPASS_MANIFEST_PATH.name}` "
        f"({'present' if EZPASS_MANIFEST_PATH.exists() else 'MISSING'}; "
        "presence alone does not establish verification)\n",
        "> Observed problems only. Handling decisions are in the last section "
        "and are applied elsewhere, never by this script.\n",
    ]

    any_hard_fail = False
    failures: list[tuple[str, object]] = []
    for name, body in blocks:
        df = con.execute(body).df()
        is_hard = name.startswith("hard_")
        status = ""
        if is_hard:
            failed = len(df) > 0
            any_hard_fail |= failed
            if failed:
                failures.append((name, df))
            status = "  ❌ **FAIL**" if failed else "  ✅ pass"

        parts.append(f"## `{name}`{status}\n")
        if name in LARGE_BLOCKS:
            parts.append(f"{len(df):,} rows (series; not inlined — plot separately).")
            if not df.empty:
                parts.append("\nHead / tail:\n")
                parts.append(df.head(3).to_markdown(index=False))
                parts.append("…")
                parts.append(df.tail(3).to_markdown(index=False))
        elif df.empty:
            parts.append("_(no rows)_")
        else:
            parts.append(df.to_markdown(index=False))
        parts.append("")

    parts.append(PROPOSED_HANDLING)
    return "\n".join(parts), any_hard_fail, failures


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not DUCKDB_PATH.exists():
        sys.exit(f"{DUCKDB_PATH} not found - run `python -m src.data.build_staging` first")

    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        report, hard_fail, failures = render(con)
    finally:
        con.close()

    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("wrote %s", REPORT_PATH)

    if hard_fail:
        # Print the offending rows, not just a pointer to a file the runner
        # discards on failure. On 2026-09-13 this exit said only "see the
        # report" and the report never left the runner, so which segment was
        # unmatched had to be hunted from outside the build.
        for name, df in failures:
            print(f"\n{name}: {len(df)} row(s)", file=sys.stderr)
            print(df.head(25).to_string(index=False), file=sys.stderr)
        sys.exit("HARD data-quality check(s) failed - see the rows above and the report")


if __name__ == "__main__":
    main()
