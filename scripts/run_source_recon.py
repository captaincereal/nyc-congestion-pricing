"""Run the source survey on a hosted runner and commit what it found.

Safe to repeat, unlike `run_h010.py`. This takes no draw against fixed data: it
asks which datasets exist and what they cover, and the answer changes as
agencies publish. Re-running it refreshes an inventory rather than re-rolling a
result, so there is no rerun guard here.

    python -m scripts.run_source_recon
"""

from __future__ import annotations

from scripts.run_hosted_analysis import commit_results, module

MODULE = "src.data.source_recon"
PATHS = ["outputs/tables/source_recon.json", "docs/source_recon.md"]


def main() -> None:
    module(MODULE)
    commit_results(
        PATHS,
        "Source reconnaissance: what alternative data actually exists\n\n"
        "Facts only, from src/data/source_recon.py. Datasets were found by "
        "searching Socrata's discovery API rather than by asserting ids, and no "
        "source is endorsed here -- suitability belongs to a registered "
        "hypothesis, not to a probe.",
    )


if __name__ == "__main__":
    main()
