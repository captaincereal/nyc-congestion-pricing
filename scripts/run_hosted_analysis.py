"""Run already specified analysis using Python orchestration and a source gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import requests

from scripts.check_analysis_inputs import readiness
from src.config import PROJECT_ROOT, RAW_DIR
from src.data.release_store import ReleaseStore
from src.data.verification_gate import verification_summary


def command(*args: str) -> None:
    subprocess.run(list(args), cwd=PROJECT_ROOT, check=True)


def module(name: str, *args: str) -> None:
    command(sys.executable, "-m", name, *args)


def commit_results(paths: list[str], message: str) -> None:
    branch = os.environ.get("RESULTS_BRANCH", "main")
    command("git", "config", "user.name", "github-actions[bot]")
    command("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    command("git", "add", "-A", "--", *paths)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=PROJECT_ROOT, check=False)
    if diff.returncode == 0:
        print("Results unchanged", flush=True)
        return
    if diff.returncode != 1:
        raise RuntimeError("Cannot inspect staged result changes")
    command("git", "commit", "-m", message)
    command("git", "pull", "--rebase", "--autostash", "origin", branch)
    command("git", "push", "origin", f"HEAD:{branch}")


def publish_panel() -> None:
    # Derived panel is replaceable; raw assets and audit snapshots are immutable.
    api = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}"
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {os.environ['GH_TOKEN']}"})
    response = session.get(api + "/releases/tags/data-raw", timeout=60)
    response.raise_for_status()
    release = response.json()
    path = PROJECT_ROOT / "data/processed/hourly_panel.parquet"
    for asset in release["assets"]:
        if asset["name"] == path.name:
            response = session.delete(asset["url"], timeout=60)
            response.raise_for_status()
    with path.open("rb") as stream:
        response = session.post(
            release["upload_url"].split("{")[0],
            params={"name": path.name},
            headers={"Content-Type": "application/octet-stream"},
            data=stream,
            timeout=180,
        )
    response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis", choices=["H003"])
    args = parser.parse_args()
    store = ReleaseStore(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    store.restore(RAW_DIR)
    if args.hypothesis:
        gate = verification_summary(RAW_DIR, PROJECT_ROOT / "docs/verification_targets.json")
        if not gate["gate_passed"]:
            print(f"H003 waits: {gate['verified_months']}/8 original inputs verified", flush=True)
            return
        if (PROJECT_ROOT / "outputs/tables/H003_results.csv").exists():
            print("H003 already executed; preserving registered results", flush=True)
            return
        module("src.analysis.aggregation_sensitivity")
        commit_results(
            [
                "outputs/tables/H003_*",
                "docs/hypotheses/H003-temporal-aggregation.md",
                "docs/hypotheses/REGISTER.md",
            ],
            "Report preregistered H003 aggregation sensitivity after source verification",
        )
        return
    ready, message = readiness(RAW_DIR)
    print(message, flush=True)
    if not ready:
        return
    for name in ("build_staging", "geo", "build_panel", "quality_report"):
        module(f"src.data.{name}")
    module("src.analysis.descriptive")
    module("src.analysis.did")
    if (RAW_DIR / "weather_hourly.parquet").exists():
        module("src.analysis.did", "--weather")
    else:
        (PROJECT_ROOT / "outputs/tables/did_estimates_weather.csv").unlink(missing_ok=True)
    for sample in ("all", "peak", "offpeak", "weekend"):
        module("src.analysis.event_study", "--sample", sample)
    module("src.analysis.robustness")
    module("src.analysis.provenance")
    publish_panel()
    commit_results(
        ["outputs", "docs/data_quality_report.md"], "Rerun existing diagnostics on verified inputs"
    )


if __name__ == "__main__":
    main()
