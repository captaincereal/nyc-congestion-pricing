"""Bounded, sequential Socrata throughput probes; never lands the full export."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests


def main() -> None:
    base = "https://data.cityofnewyork.us"
    results = []
    for dataset in ("erdf-2akx", "6a2s-2t65"):
        day = "2024-06-11" if dataset == "erdf-2akx" else "2024-10-09"
        next_day = "2024-06-12" if dataset == "erdf-2akx" else "2024-10-10"
        where = (
            f"median_calculation_timestamp >= '{day}T00:00:00' AND "
            f"median_calculation_timestamp < '{next_day}T00:00:00' AND "
            "aggregation_period_sec = 900"
        )
        for mode in ("export", "timestamp_sid", "internal_id"):
            url = f"{base}/api/views/{dataset}/rows.csv?accessType=DOWNLOAD"
            params = None
            if mode != "export":
                url = f"{base}/resource/{dataset}.csv"
                params = {
                    "$select": (
                        "sid,median_calculation_timestamp,median_speed_fps,median_tt_sec,n_samples"
                    ),
                    "$where": where,
                    "$order": (
                        "median_calculation_timestamp,sid" if mode == "timestamp_sid" else ":id"
                    ),
                    "$limit": 50000,
                    "$offset": 0,
                }
            start = time.monotonic()
            record = {"dataset": dataset, "mode": mode, "bytes": 0, "auth": "anonymous"}
            try:
                with requests.get(url, params=params, stream=True, timeout=(15, 35)) as response:
                    record["status"] = response.status_code
                    response.raise_for_status()
                    record["content_length"] = response.headers.get("Content-Length")
                    for chunk in response.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        if not record["bytes"]:
                            record["first_byte_seconds"] = time.monotonic() - start
                        record["bytes"] += len(chunk)
                        if record["bytes"] >= 16 * 1024 * 1024 or time.monotonic() - start >= 45:
                            record["stopped_at_cap"] = True
                            break
            except requests.RequestException as exc:
                # No credentials are used or printed by this experiment.
                record["error"] = str(exc)
            record["elapsed_seconds"] = time.monotonic() - start
            record["mb_per_second"] = record["bytes"] / 1e6 / record["elapsed_seconds"]
            results.append(record)
            print(json.dumps(record), flush=True)
    path = Path("outputs/tables/socrata_benchmark.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"run_at": datetime.now(UTC).isoformat(), "probes": results}, indent=2)
    )


if __name__ == "__main__":
    main()
