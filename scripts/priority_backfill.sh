#!/bin/bash
# Priority-ordered EZ Pass backfill: analytically highest-value ranges first,
# so partial progress (this is a rate-limited, multi-session pull) banks the
# months that matter most rather than whatever's chronologically next.
# Each range is a separate invocation because src.data.download_ezpass skips
# months already on disk, so re-running is always safe/resumable.
set -x
cd "C:\Users\hanup\OneDrive\Documents\nyc-congestion-pricing"
PY=".venv/Scripts/python.exe"
$PY -m src.data.download_ezpass --start 2024-06-01 --end 2024-10-01   # 4 mo: bridges to a contiguous 2024-06..2025-04 window
$PY -m src.data.download_ezpass --start 2025-05-01 --end 2025-09-01   # 4 mo: extends the post period
$PY -m src.data.download_ezpass --start 2024-01-01 --end 2024-06-01   # 5 mo: deepens pre-period to 2024-01
$PY -m src.data.download_ezpass --start 2025-09-01 --end 2026-01-01   # 4 mo: more post period
$PY -m src.data.download_ezpass --start 2023-07-01 --end 2024-01-01   # 6 mo: deepens pre-period to 2023-07 (skips COVID-recovery H1 2023)
$PY -m src.data.download_ezpass --start 2026-01-01                    # to present: remaining post period
$PY -m src.data.download_ezpass --start 2023-01-01 --end 2023-07-01   # 6 mo: fills the full frozen window back to 2023-01
echo "PRIORITY BACKFILL SEQUENCE COMPLETE"
