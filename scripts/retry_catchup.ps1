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

function Write-Log([string]$msg) {
    # utf8 explicitly: Tee-Object/Out-File default to UTF-16 here, which makes
    # the log unreadable to grep and to the Python tooling.
    Write-Host $msg
    Add-Content -Path $log -Value $msg -Encoding utf8
}

function Invoke-Pull([string]$label, [string]$module) {
    Write-Log "--- $label ---"
    # The downloaders log via Python's `logging`, which writes to STDERR. With
    # $ErrorActionPreference='Stop' PowerShell treats native stderr as a
    # terminating error and aborts the script on the first log line, so drop to
    # 'Continue' around the native call. This is what silently killed the
    # 2026-09-09 05:56 run before it fetched anything.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $python -m $module --start 2023-01-01 2>&1 |
            ForEach-Object { Add-Content -Path $log -Value "$_" -Encoding utf8 }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    Write-Log "$label exit code: $code"
    return $code
}

Write-Log "=== catch-up run $(Get-Date -Format o) ==="

# PRIMARY source first (EZ Pass local-street speeds). This is a large multi-night
# pull; it is resumable and the manifest is rewritten after every month, so a
# throttled or interrupted run simply resumes where it left off.
Invoke-Pull 'ezpass (primary)' 'src.data.download_ezpass' | Out-Null

# SECONDARY source (DOT highway speeds, for the spillover analysis). Nearly
# complete - only a few tail months outstanding.
$exit = Invoke-Pull 'dot speeds (secondary)' 'src.data.download'

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
        Write-Log "$($pair.name): no manifest yet"
        $done = $false
        continue
    }
    $m = Get-Content $mf -Raw | ConvertFrom-Json
    $last = $m.coverage.last_month
    "$($pair.name): $($m.coverage.first_month)..$last  ($($m.parts.Count) parts, complete=$($m.all_parts_complete))" |
        ForEach-Object { Write-Log $_ }
    if (-not ($last -ge $TargetLastMonth -and $m.all_parts_complete)) { $done = $false }
}

if ($done) {
    "both sources reached $TargetLastMonth - unregistering scheduled task '$TaskName'" |
        ForEach-Object { Write-Log $_ }
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false } catch {
        Write-Log "  (could not unregister: $_)"
    }
}

exit $exit
