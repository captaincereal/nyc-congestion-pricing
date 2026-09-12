"""Exercise release transfer failure paths without network or GitHub credentials."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "data_release.sh"
MOCK_GH = """#!/usr/bin/env bash
set -eu
echo "$*" >> "$MOCK_LOG"
case "$1 $2" in
  'release list')
    [[ "$MOCK_MODE" != catalogue_failure ]] || exit 41
    [[ "$MOCK_MODE" != missing ]] || exit 0
    echo data-raw ;;
  'release view')
    echo ezpass_speeds_2025-01.parquet
    echo ezpass_manifest.json
    echo ezpass_segments.parquet
    echo ezpass_verify_2025-01.json ;;
  'release download')
    [[ "$MOCK_MODE" != download_failure ]] || exit 43 ;;
  'release create'|'release upload') : ;;
  *) exit 99 ;;
esac
"""


@pytest.fixture
def release_runner(tmp_path: Path):
    # Windows' System32 bash is WSL and cannot run without a configured distro.
    bash = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    if not bash or not Path(bash).exists():
        pytest.skip("bash is required for the hosted-runner transfer tests")
    commands = tmp_path / "bin"
    commands.mkdir()
    gh = commands / "gh"
    gh.write_text(MOCK_GH, encoding="utf-8", newline="\n")
    gh.chmod(0o755)
    call_log = tmp_path / "calls.txt"

    def run(mode: str, action: str = "pull"):
        env = {
            **os.environ,
            "PATH": str(commands) + os.pathsep + os.environ["PATH"],
            "MOCK_MODE": mode,
            "MOCK_LOG": call_log.as_posix(),
        }
        result = subprocess.run(
            [str(bash), SCRIPT.as_posix(), action],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        calls = call_log.read_text() if call_log.exists() else ""
        return result, calls

    return run


def test_absent_release_is_expected_bootstrap(release_runner) -> None:
    result, calls = release_runner("missing")
    assert result.returncode == 0, result.stderr
    assert "starting from an empty data tree" in result.stdout
    assert "release download" not in calls


@pytest.mark.parametrize("action", ["pull", "push"])
def test_catalogue_error_never_becomes_missing_release(release_runner, action: str) -> None:
    result, calls = release_runner("catalogue_failure", action)
    assert result.returncode != 0
    assert "release create" not in calls
    assert "release upload" not in calls


def test_existing_asset_download_failure_is_fatal(release_runner) -> None:
    result, calls = release_runner("download_failure")
    assert result.returncode == 43, result.stderr
    assert "release download" in calls


def test_receipts_are_restored_and_absent_weather_is_optional(release_runner) -> None:
    result, calls = release_runner("normal")
    assert result.returncode == 0, result.stderr
    assert "--dir data/raw/ezpass_verification --pattern ezpass_verify_*.json" in calls
    assert "weather_hourly.parquet" not in calls


def test_verification_receipts_are_published(release_runner, tmp_path: Path) -> None:
    receipts = tmp_path / "data/raw/ezpass_verification"
    receipts.mkdir(parents=True)
    (receipts / "ezpass_verify_2025-01.json").write_text("{}")
    result, calls = release_runner("normal", "push")
    assert result.returncode == 0, result.stderr
    receipt = "data/raw/ezpass_verification/ezpass_verify_2025-01.json"
    assert f"release upload data-raw {receipt}" in calls
