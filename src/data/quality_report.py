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

from src.config import DOCS_DIR, DUCKDB_PATH, PROJECT_ROOT, RAW_MANIFEST_PATH

log = logging.getLogger(__name__)

SQL_PATH = PROJECT_ROOT / "sql" / "02_quality_checks.sql"
REPORT_PATH = DOCS_DIR / "data_quality_report.md"

_NAME_RE = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)

# Blocks that are too large to inline; summarised instead of dumped.
LARGE_BLOCKS = {"daily_link_count"}

PROPOSED_HANDLING = """\
## Proposed handling (human-edited — not yet applied)

_Fill in after reviewing the observed problems above. Each row: problem →
proposed rule → why → where it will be applied. Nothing here is applied until
it is written down and reviewed._

| Problem | Proposed rule | Rationale | Applied in |
|---|---|---|---|
| _e.g._ zero speeds | treat as missing | 0 mph is an artifact | `sql/03_hourly_panel.sql` |
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


def render(con: duckdb.DuckDBPyConnection) -> tuple[str, bool]:
    blocks = parse_blocks(SQL_PATH.read_text())
    now = datetime.now(UTC).isoformat(timespec="seconds")

    parts = [
        "# Data-quality report — DOT Traffic Speeds staging\n",
        f"Generated: {now}",
        f"Source DB: `{DUCKDB_PATH.name}`  ·  raw manifest: "
        f"`{'present' if RAW_MANIFEST_PATH.exists() else 'MISSING'}`\n",
        "> Observed problems only. Handling decisions are in the last section "
        "and are applied elsewhere, never by this script.\n",
    ]

    any_hard_fail = False
    for name, body in blocks:
        df = con.execute(body).df()
        is_hard = name.startswith("hard_")
        status = ""
        if is_hard:
            failed = len(df) > 0
            any_hard_fail |= failed
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
    return "\n".join(parts), any_hard_fail


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not DUCKDB_PATH.exists():
        sys.exit(f"{DUCKDB_PATH} not found - run `python -m src.data.build_staging` first")

    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        report, hard_fail = render(con)
    finally:
        con.close()

    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("wrote %s", REPORT_PATH)

    if hard_fail:
        sys.exit("HARD data-quality check(s) failed - see the report")


if __name__ == "__main__":
    main()
