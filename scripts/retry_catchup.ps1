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

# PRIMARY source first (EZ Pass local-street speeds). This is a large multi-night
# pull; it is resumable and the manifest is rewritten after every month, so a
# throttled or interrupted run simply resumes where it left off.
"--- ezpass (primary) ---" | Tee-Object -FilePath $log -Append
& $python -m src.data.download_ezpass --start 2023-01-01 *>> $log
"ezpass exit code: $LASTEXITCODE" | Tee-Object -FilePath $log -Append

# SECONDARY source (DOT highway speeds, for the spillover analysis). Nearly
# complete - only a few tail months outstanding.
"--- dot speeds (secondary) ---" | Tee-Object -FilePath $log -Append
& $python -m src.data.download --start 2023-01-01 *>> $log
$exit = $LASTEXITCODE
"dot speeds exit code: $exit" | Tee-Object -FilePath $log -Append

# Report coverage for both sources. Self-disable only when BOTH have reached the
# target month - the primary pull spans many nights, so finishing the secondary
# alone must not stop the task.
$done = $true
foreach ($pair in @(
    @{ name = 'ezpass (primary)';    path = 'data\raw\ezpass_manifest.json' },
    @{ name = 'dot speeds (secondary)'; path = 'data\raw\manifest.json' }
)) {
    $mf = Join-Path $repo $pair.path
    if (-not (Test-Path $mf)) {
        "$($pair.name): no manifest yet" | Tee-Object -FilePath $log -Append
        $done = $false
        continue
    }
    $m = Get-Content $mf -Raw | ConvertFrom-Json
    $last = $m.coverage.last_month
    "$($pair.name): $($m.coverage.first_month)..$last  ($($m.parts.Count) parts, complete=$($m.all_parts_complete))" |
        Tee-Object -FilePath $log -Append
    if (-not ($last -ge $TargetLastMonth -and $m.all_parts_complete)) { $done = $false }
}

if ($done) {
    "both sources reached $TargetLastMonth - unregistering scheduled task '$TaskName'" |
        Tee-Object -FilePath $log -Append
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false } catch {
        "  (could not unregister: $_)" | Tee-Object -FilePath $log -Append
    }
}

exit $exit
