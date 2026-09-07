"""Phase 4 — validate the analysis panel before modelling.  NOT YET WIRED.

Checks panel shape (unique keys, balanced groups, event-time coverage, post
flag consistent with TREATMENT_DATE). The panel it validates does not exist
until ``sql/03_hourly_panel.sql`` is activated in Phase 4; the expected columns
below track the current plan in ``docs/data_dictionary.md`` and will be
finalised then.

Usage:
    python -m src.data.validate [--panel PATH]
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from src.config import HOURLY_PANEL_PATH, TREATMENT_DATE

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "link_id",
    "ts_hour",
    "date",
    "hour",
    "dow",
    "is_weekend",
    "is_peak",
    "median_speed_mph",
    "n_obs",
    "treated",
    "post",
    "treated_post",
    "event_time",
}


class ValidationError(Exception):
    """Raised when the panel fails a hard check."""


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)
        log.error("FAIL %s", message)
    else:
        log.info("ok   %s", message)


def validate(df: pd.DataFrame) -> None:
    errors: list[str] = []

    missing = REQUIRED_COLUMNS - set(df.columns)
    _check(not missing, f"all required columns present (missing: {sorted(missing)})", errors)
    if missing:
        raise ValidationError("; ".join(errors))

    _check(df["link_id"].notna().all(), "no null link_id", errors)
    _check(df["ts_hour"].notna().all(), "no null ts_hour", errors)
    _check(
        not df.duplicated(["link_id", "ts_hour"]).any(),
        "unique on (link_id, ts_hour)",
        errors,
    )

    spd = df["median_speed_mph"].dropna()
    _check(spd.between(0, 100).all(), "median_speed_mph within [0, 100]", errors)
    _check((df["n_obs"] > 0).all(), "n_obs > 0 for every cell", errors)

    ts_date = pd.to_datetime(df["ts_hour"]).dt.date
    post_flag = df["post"].astype(bool)
    _check(
        (post_flag == (ts_date >= TREATMENT_DATE)).all(),
        "post flag matches TREATMENT_DATE",
        errors,
    )
    _check(
        (df["treated_post"].astype(bool) == (df["treated"].astype(bool) & post_flag)).all(),
        "treated_post == treated & post",
        errors,
    )

    _check(df["treated"].nunique() == 2, "both treated and control links present", errors)
    _check(
        df.loc[df["treated"].astype(bool), "post"].nunique() == 2,
        "treated group observed pre and post",
        errors,
    )
    _check(
        df.loc[~df["treated"].astype(bool), "post"].nunique() == 2,
        "control group observed pre and post",
        errors,
    )

    if errors:
        raise ValidationError(f"{len(errors)} check(s) failed:\n  - " + "\n  - ".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=str(HOURLY_PANEL_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = pd.read_parquet(args.panel)
    log.info("loaded %s rows from %s", f"{len(df):,}", args.panel)

    try:
        validate(df)
    except ValidationError as exc:
        log.error("%s", exc)
        sys.exit(1)
    log.info("panel OK")


if __name__ == "__main__":
    main()
