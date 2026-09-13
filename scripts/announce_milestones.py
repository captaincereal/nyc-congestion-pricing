"""Say so, once, when the backfill crosses a milestone worth knowing about.

The backfill runs unattended for days and nobody watches the Actions tab that
long. This writes a title and body per reached milestone into
``outputs/milestones/``; the workflow turns each into a GitHub issue, which is
the one notification that arrives whether or not the owner's machine is on.

Two milestones, because they unblock different things and arrive days apart.
The priority order fetches the pre-period backwards first and only then walks
the post-period forward, so the pre-period milestone lands well before the
archive is complete:

    pre_period_complete   2023-01 is held -> H002 and H004 can be rerun
    post_period_complete  every month from 2025-01 to 2026-08 is held

Writing files rather than GITHUB_OUTPUT keeps multi-line bodies simple and lets
the workflow loop over whatever is present. The script is silent when nothing
has been crossed, so it can run on every pass.

    python -m scripts.announce_milestones
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.config import EZPASS_MANIFEST_PATH, OUTPUTS_DIR  # noqa: E402
from src.data.coverage_report import report  # noqa: E402
from src.data.hosted_backfill import priority_months  # noqa: E402

FROZEN_START = "2023-01"
POST_START = "2025-01"
MILESTONE_DIR = OUTPUTS_DIR / "milestones"

NEXT_STEPS = (
    "Two registered hypotheses were waiting on a longer pre-period, both with "
    "their criteria already frozen:\n\n"
    "- **H002** rerun the Rambachan-Roth sensitivity. Its breakdown values are "
    "calibrated against observed pre-period violations, so the yardstick moves "
    "once the pre-period is longer.\n"
    "- **H004** repeat the held-out control matching on a window that is not "
    "holiday-dominated. The previous run validated on October-December, which "
    "confounded the failure with holiday dynamics.\n\n"
    "Neither result carries over. Both need rerunning before the README's "
    "conclusion is revisited.\n"
)


def held_months() -> list[str]:
    """Months with a complete part on disk, from the manifest."""
    if not EZPASS_MANIFEST_PATH.exists():
        return []
    try:
        manifest = json.loads(EZPASS_MANIFEST_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(
        p["month"] for p in manifest.get("parts", []) if p.get("complete") is True and "month" in p
    )


def target_months() -> list[str]:
    return sorted(f"{m:%Y-%m}" for m in priority_months())


def milestones(held: list[str], targets: list[str]) -> list[dict]:
    """Which milestones the current archive has crossed."""
    have = set(held)
    reached = []

    if FROZEN_START in have:
        reached.append(
            {
                "key": "pre_period_complete",
                "title": "Backfill reached 2023-01 - frozen window pre-period complete",
                "summary": (
                    f"The backfill has reached **{FROZEN_START}**, the start of the frozen "
                    "study window. The pre-period is now as deep as the design asks for.\n\n"
                    "The post-period is still filling; the priority order walks the "
                    "pre-period backwards first. A separate notice follows when it finishes.\n\n"
                    + NEXT_STEPS
                ),
            }
        )

    post_targets = [m for m in targets if m >= POST_START]
    missing_post = [m for m in post_targets if m not in have]
    if post_targets and not missing_post:
        reached.append(
            {
                "key": "post_period_complete",
                "title": "Backfill complete - post-period holds every frozen month",
                "summary": (
                    f"Every post-treatment month from **{post_targets[0]}** to "
                    f"**{post_targets[-1]}** is now held.\n\n"
                    + (
                        "The full 44-month frozen archive is complete.\n\n"
                        if not [m for m in targets if m not in have]
                        else "Some pre-period months are still outstanding; see the "
                        "coverage report below.\n\n"
                    )
                    + "This lengthens the post-treatment path the event study traces. It does "
                    "not address the identification problem: post-treatment months do not "
                    "bear on the pre-trend test, and the README's conclusion turns on that.\n"
                ),
            }
        )
    return reached


def main() -> None:
    held, targets = held_months(), target_months()
    reached = milestones(held, targets)

    MILESTONE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in MILESTONE_DIR.glob("*"):
        stale.unlink()

    if not reached:
        missing = [m for m in targets if m not in set(held)]
        print(f"no milestone crossed: {len(held)} months held, {len(missing)} still missing")
        return

    coverage = report()
    for item in reached:
        body = item["summary"] + "\n```\n" + coverage + "\n```\n"
        (MILESTONE_DIR / f"{item['key']}.title").write_text(item["title"], encoding="utf-8")
        (MILESTONE_DIR / f"{item['key']}.md").write_text(body, encoding="utf-8")
        print(f"milestone reached: {item['key']} -> {item['title']}")


if __name__ == "__main__":
    main()
