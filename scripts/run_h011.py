"""Run an H011 stage on a hosted runner and commit what it produces.

Two stages, because the record will not let an estimate run against an assumed
treatment classification. `roster` fetches the facility list and stops;
`estimate` refuses to start until `docs/h011_facility_classification.csv` is
committed. See src/analysis/h011_crossing_volume.py.

    python -m scripts.run_h011 --stage roster
"""

from __future__ import annotations

import argparse

from scripts.run_hosted_analysis import commit_results, module

MODULE = "src.analysis.h011_crossing_volume"
PATHS = ["outputs/tables"]

MESSAGES = {
    "roster": (
        "H011 stage one: the facility roster\n\n"
        "The list the treatment classification has to be written against. No "
        "estimate is computed here and none can be until "
        "docs/h011_facility_classification.csv exists."
    ),
    "estimate": (
        "H011 stage two: the crossing-volume estimate\n\n"
        "Run against the committed facility classification. The record's Result "
        "and Verdict are still empty; whoever reads these fills them in."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("roster", "estimate"), required=True)
    parser.add_argument("--inbound", default="")
    args = parser.parse_args()

    extra = ["--inbound", args.inbound] if args.stage == "estimate" and args.inbound else []
    module(MODULE, "--stage", args.stage, *extra)
    commit_results(PATHS, MESSAGES[args.stage])


if __name__ == "__main__":
    main()
