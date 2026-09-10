<#
.SYNOPSIS
    Backfill the EZ Pass pre-period NEAREST-TO-TREATMENT FIRST.

.DESCRIPTION
    The plain `--start 2023-01-01` backfill walks forward chronologically, which
    fetches the months that matter LEAST first: 2023-01 is 24 months from the
    2025-01-05 toll and contributes almost nothing to a parallel-trends test,
    while 2024-09 sits immediately before it and contributes most.

    This walks backwards month by month from the treatment date, so every hour
    of downloading strengthens the estimate as early as possible and the
    analysis can be re-run at any point on a longer, better-placed pre-period.

    Each month is a separate resumable invocation; the ingest skips months
    already on disk, so re-running is safe and cheap.

.NOTES
    Added 2026-09-09 after measuring that the full backfill is a ~48 hour pull.
#>
[CmdletBinding()]
param(
    # Walk back from the month before treatment to this month inclusive.
    [string]$FirstMonth = '2023-01',
    [string]$LastMonth = '2024-09'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "venv python not found at $python" }

$logDir = Join-Path $repo 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("backfill_near_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))

function Write-Log([string]$m) {
    Write-Host $m
    Add-Content -Path $log -Value $m -Encoding utf8
}

# Build the month list newest-first.
$months = @()
$cur = [datetime]::ParseExact("$LastMonth-01", 'yyyy-MM-dd', $null)
$stop = [datetime]::ParseExact("$FirstMonth-01", 'yyyy-MM-dd', $null)
while ($cur -ge $stop) {
    $months += $cur
    $cur = $cur.AddMonths(-1)
}

Write-Log "=== nearest-first backfill $(Get-Date -Format o) ==="
Write-Log "$($months.Count) months, $LastMonth back to $FirstMonth"

foreach ($m in $months) {
    $start = $m.ToString('yyyy-MM-dd')
    $end = $m.AddMonths(1).ToString('yyyy-MM-dd')
    Write-Log "--- $($m.ToString('yyyy-MM')) ---"
    # Python's logging writes to stderr; with ErrorActionPreference='Stop'
    # PowerShell would abort on the first log line, so drop to Continue.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $python -m src.data.download_ezpass --start $start --end $end 2>&1 |
            ForEach-Object { Add-Content -Path $log -Value "$_" -Encoding utf8 }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($code -ne 0) { Write-Log "  $($m.ToString('yyyy-MM')) exited $code - continuing" }
}

Write-Log "=== done $(Get-Date -Format o) ==="
