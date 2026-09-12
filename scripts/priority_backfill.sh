#!/usr/bin/env bash
# Priority-ordered E-Z Pass backfill.
#
# Ranges run in order of analytical value rather than chronology, so partial
# progress banks the months that matter most. What matters most is the
# PRE-period: the study is blocked on a pre-trend test that currently runs on
# Thanksgiving-through-New-Year, and no post-period month fixes that.
#
# Every range is a separate invocation because download_ezpass skips months
# already on disk, so re-running is always safe and resumable.
#
# Budget (BACKFILL_BUDGET_MIN, minutes) is shared across the whole sequence:
# each invocation gets whatever is left, and the run stops cleanly once too
# little remains to finish a month. Unset or 0 means run to completion.
#
#   scripts/priority_backfill.sh                       # local, no limit
#   BACKFILL_BUDGET_MIN=300 scripts/priority_backfill.sh   # CI, 5 hours
set -euo pipefail

PY="${PYTHON:-python}"
BUDGET_MIN="${BACKFILL_BUDGET_MIN:-0}"
MONTH_BUDGET_MIN="${MONTH_BUDGET_MIN:-50}"

# start-date  end-date (exclusive; blank = through the present)
#
# The union covers the whole frozen window, so a fresh environment with no
# data at all converges on complete coverage without anyone listing what is
# missing. Months already on disk cost one skip each.
RANGES=(
  "2024-07-01 2024-10-01"  # closes the hole; makes 2024-06..2025-04 contiguous
  "2024-01-01 2024-07-01"  # deepens the pre-period to 2024-01
  "2023-07-01 2024-01-01"  # deepens to 2023-07, skipping COVID-recovery H1 2023
  "2024-10-01 2025-05-01"  # the priority window; a no-op where it is already held
  "2025-05-01 2026-01-01"  # extends the post period
  "2026-01-01 "            # post period through the present
  "2023-01-01 2023-07-01"  # completes the frozen window back to 2023-01
)

deadline=0
if [[ "$BUDGET_MIN" -gt 0 ]]; then
  deadline=$(( $(date +%s) + BUDGET_MIN * 60 ))
fi

for range in "${RANGES[@]}"; do
  read -r start end <<<"$range"

  args=(--start "$start")
  [[ -n "${end:-}" ]] && args+=(--end "$end")

  if [[ "$deadline" -gt 0 ]]; then
    left=$(( (deadline - $(date +%s)) / 60 ))
    if [[ "$left" -lt "$MONTH_BUDGET_MIN" ]]; then
      echo "budget spent (${left}m left, a month needs ${MONTH_BUDGET_MIN}m) - stopping before $start"
      break
    fi
    args+=(--max-runtime "$left" --month-budget "$MONTH_BUDGET_MIN")
  fi

  echo "=== $start .. ${end:-present} ==="
  "$PY" -m src.data.download_ezpass "${args[@]}"
done

echo "backfill pass complete"
