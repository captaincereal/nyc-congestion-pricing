#!/usr/bin/env bash
# Move raw data parts between a CI runner and the GitHub release that stores
# them.
#
# A runner's disk is wiped when the job ends, so the release IS the durable
# state of the backfill: what it holds is exactly what the next run skips.
# Raw parts stay out of git (they are gitignored, and 225MB of parquet does
# not belong in history), but they have to live somewhere free and permanent.
# Release assets are both.
#
#   scripts/data_release.sh pull            # runner <- release
#   scripts/data_release.sh push [marker]   # runner -> release
#
# `push` uploads only files newer than `marker` (a file touched before the
# download started), so an unchanged 45-month archive is not re-uploaded every
# run. The manifest always goes up; it changes whenever a month lands.
#
# Needs `gh` authenticated - on GitHub Actions set GH_TOKEN to the job token.
set -euo pipefail

TAG="${DATA_TAG:-data-raw}"
PARTS_DIR="data/raw/ezpass_speeds"
RAW_DIR="data/raw"
LOOSE=(ezpass_manifest.json ezpass_segments.parquet weather_hourly.parquet)

release_exists() { gh release view "$TAG" >/dev/null 2>&1; }

pull() {
  mkdir -p "$PARTS_DIR"
  if ! release_exists; then
    echo "no '$TAG' release yet - starting from an empty data tree"
    return 0
  fi
  gh release download "$TAG" --dir "$PARTS_DIR" \
    --pattern 'ezpass_speeds_*.parquet' --clobber || true
  for f in "${LOOSE[@]}"; do
    gh release download "$TAG" --dir "$RAW_DIR" --pattern "$f" --clobber || true
  done
  echo "pulled $(find "$PARTS_DIR" -name '*.parquet' | wc -l) month part(s) from '$TAG'"
}

push() {
  local marker="${1:-}"
  if ! release_exists; then
    gh release create "$TAG" \
      --title "Raw data parts" \
      --notes "Month-partitioned E-Z Pass speed parts, the segment attribute table and the ingestion manifest. Written by the backfill workflow; this is the resume state it reads on its next run, not a software release."
  fi

  local find_args=()
  if [[ -n "$marker" && -f "$marker" ]]; then
    find_args=(-newer "$marker")
  fi

  local files=()
  while IFS= read -r f; do files+=("$f"); done < <(
    find "$PARTS_DIR" -name 'ezpass_speeds_*.parquet' "${find_args[@]}" 2>/dev/null || true
  )
  # The manifest and segment table are small and change as months land, so
  # they always go up rather than being diffed.
  for f in "${LOOSE[@]}"; do
    [[ -f "$RAW_DIR/$f" ]] && files+=("$RAW_DIR/$f")
  done

  if [[ ${#files[@]} -eq 0 ]]; then
    echo "nothing new to publish"
    return 0
  fi
  gh release upload "$TAG" "${files[@]}" --clobber
  echo "published ${#files[@]} file(s) to '$TAG'"
}

case "${1:-}" in
  pull) pull ;;
  push) push "${2:-}" ;;
  *) echo "usage: $0 {pull|push [marker]}" >&2; exit 2 ;;
esac
