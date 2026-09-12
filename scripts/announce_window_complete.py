"""Say so, once, when the archive reaches the start of the frozen window.

The backfill runs unattended for days and nobody watches the Actions tab that
long. This writes a one-line flag the workflow turns into a GitHub issue, which
is the only notification that arrives whether or not the owner's machine is on.

Prints `ready=true` to GITHUB_OUTPUT when 2023-01 is held and complete, plus a
short body for the issue. Silent otherwise, so it can run on every pass.

    python -m scripts.announce_window_complete
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.config import EZPASS_MANIFEST_PATH  # noqa: E402
from src.data.coverage_report import report  # noqa: E402

FROZEN_START = "2023-01"


def held_months() -> list[str]:
    if not EZPASS_MANIFEST_PATH.exists():
        return []
    try:
        manifest = json.loads(EZPASS_MANIFEST_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(
        p["month"] for p in manifest.get("parts", []) if p.get("complete") is True and "month" in p
    )


def main() -> None:
    months = held_months()
    ready = FROZEN_START in months
    out = os.environ.get("GITHUB_OUTPUT")

    if not ready:
        print(f"frozen window not reached: {len(months)} months held, {FROZEN_START} missing")
        if out:
            with pathlib.Path(out).open("a", encoding="utf-8") as fh:
                fh.write("ready=false\n")
        return

    body = (
        f"The backfill has reached **{FROZEN_START}**, the start of the frozen study window.\n\n"
        f"{len(months)} months held, {months[0]} .. {months[-1]}.\n\n"
        "```\n" + report() + "\n```\n\n"
        "Two registered hypotheses were waiting on this, both with their "
        "criteria already frozen:\n\n"
        "- **H002** — rerun the Rambachan-Roth sensitivity. Its breakdown values "
        "are calibrated against observed pre-period violations, and the yardstick "
        "changes now that the pre-period is longer.\n"
        "- **H004** — repeat the held-out control matching on a window that is not "
        "holiday-dominated. The previous run validated on October-December, which "
        "confounded the failure with holiday dynamics.\n\n"
        "Neither result carries over; both need rerunning before the README's "
        "conclusion is revisited.\n"
    )
    print(body)
    if out:
        with pathlib.Path(out).open("a", encoding="utf-8") as fh:
            fh.write("ready=true\n")
            fh.write("body<<ISSUE_BODY_EOF\n")
            fh.write(body)
            fh.write("\nISSUE_BODY_EOF\n")


if __name__ == "__main__":
    main()
