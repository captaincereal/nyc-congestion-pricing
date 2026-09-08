<#
.SYNOPSIS
    Resume the raw DOT-speeds pull, meant to be run unattended by Task Scheduler.

.DESCRIPTION
    Runs `python -m src.data.download --start 2023-01-01`, which skips every month
    already on disk and only fetches what is missing. Socrata rate-limits sustained
    bulk pulls, so this is scheduled off-peak and is safe to re-run: each attempt
    chips away at the remaining months and the manifest is rewritten after every one.

    Logs to logs/catchup_<timestamp>.log. When coverage reaches TARGET_LAST_MONTH
    the scheduled task unregisters itself (best effort).

.NOTES
    Set up by Claude on 2026-09-08 after the initial bulk pull was throttled at
    2026-04. See docs/data_dictionary.md and the "fix/download-manifest-resilience"
    commit.
#>
[CmdletBinding()]
param(
    [string]$TargetLastMonth = '2026-09',
    [string]$TaskName = 'nyc-cp-catchup-download'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "venv python not found at $python" }

$logDir = Join-Path $repo 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("catchup_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))

"=== catch-up run $(Get-Date -Format o) ===" | Tee-Object -FilePath $log
& $python -m src.data.download --start 2023-01-01 *>> $log
$exit = $LASTEXITCODE
"downloader exit code: $exit" | Tee-Object -FilePath $log -Append

# Report current coverage and self-disable once the target month is in hand.
$manifest = Join-Path $repo 'data\raw\manifest.json'
if (Test-Path $manifest) {
    $m = Get-Content $manifest -Raw | ConvertFrom-Json
    $last = $m.coverage.last_month
    "coverage: $($m.coverage.first_month)..$last  ($($m.parts.Count) parts, complete=$($m.all_parts_complete))" |
        Tee-Object -FilePath $log -Append
    if ($last -ge $TargetLastMonth -and $m.all_parts_complete) {
        "target $TargetLastMonth reached - unregistering scheduled task '$TaskName'" |
            Tee-Object -FilePath $log -Append
        try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false } catch {
            "  (could not unregister: $_)" | Tee-Object -FilePath $log -Append
        }
    }
}

exit $exit
