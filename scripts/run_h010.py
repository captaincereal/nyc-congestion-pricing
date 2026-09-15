"""Run H010 once, on a hosted runner, and commit its artefacts.

H010 needs live Socrata aggregates and the owner will not leave a machine on, so
it runs on Actions like everything else here. It is deliberately **not** wired
into `analysis.yml`: that workflow fires on every backfill completion and on
pushes under `src/analysis/`, and a pre-registered hypothesis re-run on every
push is a fresh draw against fixed data each time. This one runs when a person
dispatches it.

Refuses to overwrite an existing answer unless told to. A silent second run
would replace the artefacts an answered record cites, with nothing in the diff
to say a second draw had been taken.

    python -m scripts.run_h010 [--allow-rerun]
"""

from __future__ import annotations

import argparse
import sys

from scripts.run_hosted_analysis import commit_results, module
from src.config import TABLES_DIR

MODULE = "src.analysis.h010_route_substitution"
OUT_PREFIX = "H010"
SENTINEL = TABLES_DIR / f"{OUT_PREFIX}_diversion_share.csv"
PATHS = ["outputs/tables", "outputs/figures"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-rerun",
        action="store_true",
        help="Overwrite existing H010 artefacts. Every rerun is another draw; "
        "say so in the record and in docs/decision_register.md.",
    )
    args = parser.parse_args()

    if SENTINEL.exists() and not args.allow_rerun:
        print(
            f"{SENTINEL.name} already exists, so H010 has been answered.\n"
            "Rerunning replaces the artefacts the record cites and is another "
            "draw against fixed data. Pass --allow-rerun deliberately, and "
            "record that you did.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    module(MODULE, "--out-prefix", OUT_PREFIX)
    commit_results(
        PATHS,
        "H010 artefacts: count-based diversion share at the 05:00 boundary\n\n"
        "Produced by scripts/run_h010.py. The record's Result and Verdict are "
        "still empty; whoever reads these fills them in.",
    )


if __name__ == "__main__":
    main()
