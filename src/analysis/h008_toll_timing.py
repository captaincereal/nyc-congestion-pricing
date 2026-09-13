"""H008 — do drivers retime zone entries to avoid the peak toll rate?

Bunching at a price notch, not a conventional regression discontinuity. The
running variable is clock time, drivers manipulate it perfectly, and that
manipulation is the effect being measured — the McCrary logic is inverted, so
excess mass at the boundary is the finding rather than the threat to it.

The estimate at each hour boundary is the log discontinuity in entries, from
blocks within a bandwidth either side, with date fixed effects absorbed so it
comes from within-day variation. Toll boundaries are judged against the spread
of the non-toll ones rather than against a nominal p-value: the series has
structure at every hour, and a t-statistic against zero would overstate things.

Record: docs/hypotheses/H008-toll-timing-bunching.md, committed first.

    python -m src.analysis.h008_toll_timing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from src.config import FIGURES_DIR, RAW_DIR, TABLES_DIR

log = logging.getLogger(__name__)

DATASET = "t6yz-b64h"
DOMAIN = "data.ny.gov"
CACHE_DIR = RAW_DIR / "mta_crz"
BLOCK_MINUTES = 10

# Derived from the feed's own `time_period`, not from the published tariff:
# Peak covers hours 05-20 Mon-Fri and 09-20 Sat-Sun, Overnight otherwise.
WEEKDAY_TOLL_BOUNDARIES = (5, 21)
WEEKEND_TOLL_BOUNDARIES = (9, 21)
# Excluded from the placebo set in advance, in the record: a calendar rollover,
# not a price change, and behaviourally a boundary in its own right.
EXCLUDED_PLACEBO = 0

BANDWIDTH_MINUTES = 60
POLY_ORDER = 1
WEEKEND = ("Saturday", "Sunday")


def _fetch(select: str, group: str, where: str | None = None) -> pd.DataFrame:
    """One Socrata aggregate, paged. Cached by query so reruns are free."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # hashlib, not hash(): string hashing is salted per process, so a built-in
    # hash would give a new filename every run and the cache would never hit.
    key = hashlib.sha256(f"{select}|{group}|{where}".encode()).hexdigest()[:16]
    cache = CACHE_DIR / f"agg_{key}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows: list[dict] = []
    offset, page = 0, 50_000
    while True:
        params = {"$select": select, "$group": group, "$limit": page, "$offset": offset}
        if where:
            params["$where"] = where
        url = f"https://{DOMAIN}/resource/{DATASET}.json?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=180) as response:
            batch = json.load(response)
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    frame = pd.DataFrame(rows)
    frame.to_parquet(cache, index=False)
    log.info("fetched %s rows for %s", f"{len(frame):,}", group)
    return frame


def load_blocks() -> pd.DataFrame:
    """Entries per date x 10-minute block, the panel the main estimate uses."""
    frame = _fetch(
        "toll_date,hour_of_day,minute_of_hour,day_of_week,sum(crz_entries) as entries",
        "toll_date,hour_of_day,minute_of_hour,day_of_week",
    )
    frame["date"] = pd.to_datetime(frame["toll_date"]).dt.date
    for column in ("hour_of_day", "minute_of_hour", "entries"):
        frame[column] = pd.to_numeric(frame[column])
    frame["minute_of_day"] = frame["hour_of_day"] * 60 + frame["minute_of_hour"]
    frame["is_weekend"] = frame["day_of_week"].isin(WEEKEND)
    return frame


def _signed_minutes(minute_of_day: np.ndarray, boundary_hour: int) -> np.ndarray:
    """Minutes from the boundary, wrapping the day so midnight behaves."""
    delta = minute_of_day - boundary_hour * 60
    return (delta + 720) % 1440 - 720


def estimate_discontinuity(
    frame: pd.DataFrame,
    boundary_hour: int,
    bandwidth: int = BANDWIDTH_MINUTES,
    order: int = POLY_ORDER,
) -> dict:
    """Log discontinuity at one boundary, date fixed effects absorbed.

    Date effects are removed by within-date demeaning rather than dummies: there
    are ~600 dates and the estimate is meant to come from the shape of the day,
    not from differences in level between days.
    """
    run = _signed_minutes(frame["minute_of_day"].to_numpy(), boundary_hour)
    keep = (run >= -bandwidth) & (run < bandwidth)
    window = frame.loc[keep].copy()
    window["run"] = run[keep]
    window["post"] = (window["run"] >= 0).astype(float)
    if window.empty or window["post"].nunique() < 2:
        return {"boundary_hour": boundary_hour, "tau": np.nan, "se": np.nan, "n_obs": 0}

    y = np.log1p(window["entries"].to_numpy(dtype=float))
    design = [window["post"].to_numpy()]
    for power in range(1, order + 1):
        design.append(window["run"].to_numpy() ** power)
        design.append((window["run"].to_numpy() ** power) * window["post"].to_numpy())
    X = np.column_stack(design)

    codes, _ = pd.factorize(window["date"])
    # Absorb date effects from y and X together.
    for matrix in (y, X):
        means = np.zeros((codes.max() + 1,) + matrix.shape[1:])
        counts = np.bincount(codes, minlength=codes.max() + 1)
        np.add.at(means, codes, matrix)
        means = (means.T / counts).T
        matrix -= means[codes]

    XtX = X.T @ X
    beta = np.linalg.solve(XtX, X.T @ y)
    resid = y - X @ beta
    inverse = np.linalg.inv(XtX)
    n_clusters = codes.max() + 1
    meat = np.zeros_like(XtX)
    for cluster in range(n_clusters):
        rows = codes == cluster
        score = X[rows].T @ resid[rows]
        meat += np.outer(score, score)
    scale = n_clusters / max(n_clusters - 1, 1)
    vcov = inverse @ meat @ inverse * scale
    return {
        "boundary_hour": boundary_hour,
        "tau": float(beta[0]),
        "se": float(np.sqrt(vcov[0, 0])),
        "pct_change": float(np.expm1(beta[0]) * 100),
        "n_obs": int(len(window)),
        "n_dates": int(n_clusters),
        "bandwidth_min": bandwidth,
        "poly_order": order,
    }


def all_boundaries(
    frame: pd.DataFrame, label: str, toll_hours: tuple[int, ...], **kwargs
) -> pd.DataFrame:
    rows = []
    for hour in range(24):
        result = estimate_discontinuity(frame, hour, **kwargs)
        result["sample"] = label
        result["is_toll_boundary"] = hour in toll_hours
        result["is_placebo"] = (hour not in toll_hours) and hour != EXCLUDED_PLACEBO
        rows.append(result)
    return pd.DataFrame(rows)


def _by_group(blocks: pd.DataFrame, select: str, group: str, column: str) -> pd.DataFrame:
    """Boundary estimates split by vehicle class or detection group."""
    frame = _fetch(select, group)
    for numeric in ("hour_of_day", "minute_of_hour", "entries"):
        frame[numeric] = pd.to_numeric(frame[numeric])
    frame["minute_of_day"] = frame["hour_of_day"] * 60 + frame["minute_of_hour"]
    frame["date"] = frame["day_of_week"]  # pooled: dow stands in for the cluster
    frame["is_weekend"] = frame["day_of_week"].isin(WEEKEND)
    out = []
    for value, part in frame[~frame["is_weekend"]].groupby(column):
        for hour in WEEKDAY_TOLL_BOUNDARIES:
            result = estimate_discontinuity(part, hour)
            result[column] = value
            result["sample"] = "weekday"
            out.append(result)
    return pd.DataFrame(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-prefix", default="H008")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    blocks = load_blocks()
    log.info(
        "blocks: %s rows -> %s dates, %s entries total",
        f"{len(blocks):,}",
        f"{blocks['date'].nunique():,}",
        f"{int(blocks['entries'].sum()):,}",
    )

    weekday = blocks[~blocks["is_weekend"]]
    weekend = blocks[blocks["is_weekend"]]
    main_table = pd.concat(
        [
            all_boundaries(weekday, "weekday", WEEKDAY_TOLL_BOUNDARIES),
            all_boundaries(weekend, "weekend", WEEKEND_TOLL_BOUNDARIES),
        ],
        ignore_index=True,
    )
    main_table.to_csv(TABLES_DIR / f"{args.out_prefix}_boundaries.csv", index=False)

    sens = []
    for bandwidth in (30, 60, 90):
        for order in (1, 2):
            part = pd.concat(
                [
                    all_boundaries(
                        weekday,
                        "weekday",
                        WEEKDAY_TOLL_BOUNDARIES,
                        bandwidth=bandwidth,
                        order=order,
                    ),
                    all_boundaries(
                        weekend,
                        "weekend",
                        WEEKEND_TOLL_BOUNDARIES,
                        bandwidth=bandwidth,
                        order=order,
                    ),
                ],
                ignore_index=True,
            )
            sens.append(part)
    pd.concat(sens, ignore_index=True).to_csv(
        TABLES_DIR / f"{args.out_prefix}_sensitivity.csv", index=False
    )

    _by_group(
        blocks,
        "day_of_week,hour_of_day,minute_of_hour,vehicle_class,sum(crz_entries) as entries",
        "day_of_week,hour_of_day,minute_of_hour,vehicle_class",
        "vehicle_class",
    ).to_csv(TABLES_DIR / f"{args.out_prefix}_by_vehicle_class.csv", index=False)

    _by_group(
        blocks,
        "day_of_week,hour_of_day,minute_of_hour,detection_group,sum(crz_entries) as entries",
        "day_of_week,hour_of_day,minute_of_hour,detection_group",
        "detection_group",
    ).to_csv(TABLES_DIR / f"{args.out_prefix}_by_detection_group.csv", index=False)

    profile = (
        blocks.groupby(["is_weekend", "hour_of_day", "minute_of_hour"], as_index=False)["entries"]
        .sum()
        .sort_values(["is_weekend", "hour_of_day", "minute_of_hour"])
    )
    profile.to_csv(TABLES_DIR / f"{args.out_prefix}_block_profile.csv", index=False)

    for sample in ("weekday", "weekend"):
        part = main_table[main_table["sample"] == sample]
        placebo = part[part["is_placebo"]]["tau"].abs()
        log.info(
            "%s: toll boundaries %s | placebo max |tau| = %.4f, sd = %.4f",
            sample,
            {
                int(r.boundary_hour): round(r.tau, 4)
                for r in part[part.is_toll_boundary].itertuples()
            },
            placebo.max(),
            placebo.std(),
        )
    log.info("wrote %s_* tables", args.out_prefix)


if __name__ == "__main__":
    main()
