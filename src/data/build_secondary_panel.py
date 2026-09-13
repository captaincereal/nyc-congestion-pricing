"""H007 — build the link x hour panel from the SECONDARY feed (i4gi-tjb9).

This is the spillover panel. It carries the same schema as
``data/processed/hourly_panel.parquet`` so that ``src.analysis.did``,
``src.analysis.event_study``, ``src.analysis.placebo_space`` and
``src.analysis.honest_did`` run against it as a library without modification.
One difference of meaning, not of shape: ``treated`` here flags the nine
toll-EXEMPT in-zone links (FDR Drive, 12th/11th Ave, West St, the Brooklyn
Battery Tunnel Manhattan approaches), because the question this panel answers is
whether traffic diverted ONTO them. The tolled surface streets are not in this
feed at all.

**Zero-speed readings are outages and are dropped as missing.** 9,128,628 of the
9,129,474 zero-speed rows also carry ``travel_time = 0``, every one carries
``status = -101``, and their frequency peaks overnight (56% at 03:00 against 38%
through the afternoon) — the inverse of a congestion pattern. A standstill has a
large travel time, not a zero one. ``AGENTS.md`` requires missing numerics to be
``NaN``, never ``0``, so the hourly median is taken over readings with
``speed > 0`` and an hour with no positive reading carries a null outcome rather
than 0 mph. ``src/analysis/spillover_diagnostics.py`` filters only
``speed_mph IS NOT NULL`` and therefore averages those zeros in; its output
``outputs/tables/spillover_secondary_monthly.csv`` is superseded by this panel.

The link-hours with readings but no positive reading are KEPT with a null
outcome instead of being dropped, because the availability diagnostic needs them
as its denominator: the share of present link-hours that yield a usable speed is
exactly the quantity H007's first acceptance criterion is written on. Every
estimator in this project drops null outcomes, so their presence changes no
estimate.

Window: 2023-01-01 through 2026-05-31. The feed holds 2023-01 .. 2026-07 but
2026-06 is missing, so the window stops at 2026-05 to stay contiguous rather
than leaving a hole mid-panel.

Staging conventions are inherited from ``sql/01_stage_speeds.sql``: naive
``America/New_York`` timestamps with no conversion, one row per
``(link_id, ts)`` keeping the highest ``id``, the ambiguous DST fall-back hour
excluded, and no value cleaning beyond the zero-speed rule above.

Usage:
    python -m src.data.build_secondary_panel
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

import duckdb
import pandas as pd

from src.config import RAW_DIR, SECONDARY_HOURLY_PANEL_PATH, TABLES_DIR, TREATMENT_DATE
from src.data.geo import classify_segment, roadway_of

log = logging.getLogger(__name__)

# 2026-06 is absent from the feed. Stopping at 2026-05 keeps the panel
# contiguous; 2026-07 is dropped rather than left floating past a hole.
WINDOW_START = date(2023, 1, 1)
WINDOW_END_EXCLUSIVE = date(2026, 6, 1)

# `classify_segment` trusts the `borough` label. On this feed that mislabels the
# two BQE bridge approaches, which carry `borough = Manhattan` but lie
# geometrically in Brooklyn, as in-zone tolled links. They are neither clean
# diversion receivers nor clean controls, so they are held out of both groups
# and the exclusion is reported. A geometric fix in geo.py was measured and
# ruled out on 2026-09-13: no bounding box separates lower Manhattan from
# downtown Brooklyn, so it leaves both of these `treated` while moving two of
# the nine treated links into the control group. Holding the ids here is the fix.
HELD_OUT_LINK_IDS = ("4616339", "4616340")

# The group whose speeds would fall if drivers rerouted onto the exempt roads.
TREATED_GROUP = "exempt_in_zone"

DEFAULT_PARTS_GLOB = str(RAW_DIR / "dot_speeds" / "*.parquet")

# Groups held out of the estimation entirely, with the reason recorded on the
# panel so a reader can count them without re-deriving the geometry.
HOLD_OUT_REASONS = {
    "boundary": "geometry crosses the 60th St line",
    "crossing": "measures the queue to enter the zone, a different behaviour",
    "unknown": "geometry missing or undecodable",
}


def link_attributes(con: duckdb.DuckDBPyConnection, parts_glob: str) -> pd.DataFrame:
    """One attribute row per link: the MODAL name, borough and geometry.

    The feed re-emits a link's ``encoded_poly_line`` with small encoding
    differences over time (67 of 138 links carry more than one variant), and a
    handful of rows are truncated to garbage such as ``"LINCOLN\\\\\\\\"``. Taking
    the most frequently published combination is deterministic and immune to
    both: measured across every distinct combination in the feed, only one link
    classifies differently under any variant, and that is the single corrupt row.
    ``any_value`` would be neither deterministic nor immune.
    """
    return con.execute(
        """
        WITH combos AS (
            SELECT CAST(link_id AS VARCHAR)                          AS link_id,
                   CAST(link_name AS VARCHAR)                        AS link_name,
                   nullif(trim(lower(CAST(borough AS VARCHAR))), '') AS borough,
                   nullif(trim(CAST(encoded_poly_line AS VARCHAR)), '') AS encoded_poly_line,
                   count(*)                                          AS n_rows
            FROM read_parquet(?, union_by_name => true)
            WHERE link_id IS NOT NULL
            GROUP BY 1, 2, 3, 4
        )
        SELECT link_id, link_name, borough, encoded_poly_line, n_rows
        FROM (
            SELECT *, row_number() OVER (
                       PARTITION BY link_id ORDER BY n_rows DESC, link_name, encoded_poly_line
                   ) AS rn
            FROM combos
        )
        WHERE rn = 1
        ORDER BY link_id
        """,
        [parts_glob],
    ).df()


def classify_links(attrs: pd.DataFrame) -> pd.DataFrame:
    """Attach the geometric treatment group and the H007 analysis group."""
    out = attrs.copy()
    out["treatment_group"] = [
        classify_segment(name, borough, poly)
        for name, borough, poly in zip(
            out["link_name"], out["borough"], out["encoded_poly_line"], strict=True
        )
    ]
    out["roadway"] = [roadway_of(name) for name in out["link_name"]]

    held = out["link_id"].isin(HELD_OUT_LINK_IDS)
    out["analysis_group"] = out["treatment_group"].where(
        ~(out["treatment_group"] == TREATED_GROUP), "treated_exempt"
    )
    out.loc[held, "analysis_group"] = "held_out_geo"
    out["hold_out_reason"] = out["treatment_group"].map(HOLD_OUT_REASONS).fillna("")
    out.loc[held, "hold_out_reason"] = "borough label says Manhattan, geometry is in Brooklyn"
    out["treated"] = out["analysis_group"] == "treated_exempt"
    return out.drop(columns=["encoded_poly_line", "n_rows"])


def hourly_aggregate(
    con: duckdb.DuckDBPyConnection,
    parts_glob: str,
    start: date = WINDOW_START,
    end_exclusive: date = WINDOW_END_EXCLUSIVE,
) -> pd.DataFrame:
    """Collapse raw readings to one row per (link_id, ts_hour).

    ``median_speed_mph`` is the median over readings with ``speed > 0`` and is
    null when the hour has none. ``n_readings`` counts every deduplicated
    reading present in the hour, so ``n_positive / n_readings`` and
    ``n_positive >= 1`` are both computable downstream without a second scan.
    """
    return con.execute(
        """
        WITH typed AS (
            SELECT CAST(link_id AS VARCHAR)        AS link_id,
                   try_cast(data_as_of AS TIMESTAMP) AS ts,
                   try_cast(speed AS DOUBLE)       AS speed_mph,
                   CAST(id AS VARCHAR)             AS reading_id
            FROM read_parquet(?, union_by_name => true)
        ), windowed AS (
            SELECT * FROM typed
            WHERE link_id IS NOT NULL
              AND ts IS NOT NULL
              AND ts >= ? AND ts < ?
              -- The fall-back hour runs twice under naive local time and
              -- de-duplication already discarded one pass, so the cell would
              -- mix two different real hours.
              AND NOT (month(ts) = 11 AND day(ts) <= 7 AND dayofweek(ts) = 0 AND hour(ts) = 1)
        ), deduped AS (
            SELECT * EXCLUDE (rn) FROM (
                SELECT *, row_number() OVER (
                           PARTITION BY link_id, ts ORDER BY reading_id DESC) AS rn
                FROM windowed
            ) WHERE rn = 1
        )
        SELECT link_id,
               date_trunc('hour', ts)                                AS ts_hour,
               median(speed_mph) FILTER (WHERE speed_mph > 0)        AS median_speed_mph,
               avg(speed_mph)    FILTER (WHERE speed_mph > 0)        AS mean_speed_mph,
               min(speed_mph)    FILTER (WHERE speed_mph > 0)        AS min_speed_mph,
               max(speed_mph)    FILTER (WHERE speed_mph > 0)        AS max_speed_mph,
               count(*)                                              AS n_readings,
               count(*) FILTER (WHERE speed_mph > 0)                 AS n_positive,
               count(*) FILTER (WHERE speed_mph = 0)                 AS n_zero_speed,
               count(*) FILTER (WHERE speed_mph IS NULL)             AS n_unparsed_speed,
               count(*) FILTER (WHERE speed_mph > 80)                AS n_over_80
        FROM deduped
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        [parts_glob, start, end_exclusive],
    ).df()


def row_accounting(
    con: duckdb.DuckDBPyConnection,
    parts_glob: str,
    start: date = WINDOW_START,
    end_exclusive: date = WINDOW_END_EXCLUSIVE,
) -> pd.DataFrame:
    """The funnel from raw rows to kept readings, one row per drop reason.

    ``AGENTS.md`` asks for rows in -> rows out and the reason for every drop.
    The log carries it too, but a reader auditing the panel months later should
    not have to find the log.
    """
    counts = (
        con.execute(
            """
        WITH typed AS (
            SELECT CAST(link_id AS VARCHAR)          AS link_id,
                   try_cast(data_as_of AS TIMESTAMP) AS ts,
                   CAST(id AS VARCHAR)               AS reading_id
            FROM read_parquet(?, union_by_name => true)
        ), keyed AS (
            SELECT * FROM typed WHERE link_id IS NOT NULL AND ts IS NOT NULL
        ), windowed AS (
            SELECT * FROM keyed WHERE ts >= ? AND ts < ?
        ), undst AS (
            SELECT * FROM windowed
            WHERE NOT (month(ts) = 11 AND day(ts) <= 7 AND dayofweek(ts) = 0 AND hour(ts) = 1)
        )
        SELECT (SELECT count(*) FROM typed)                              AS raw_rows,
               (SELECT count(*) FROM keyed)                              AS after_keys,
               (SELECT count(*) FROM windowed)                           AS after_window,
               (SELECT count(*) FROM undst)                              AS after_dst,
               (SELECT count(*) FROM (SELECT DISTINCT link_id, ts FROM undst)) AS after_dedup
        """,
            [parts_glob, start, end_exclusive],
        )
        .df()
        .iloc[0]
    )

    steps = [
        ("raw rows in data/raw/dot_speeds/*.parquet", int(counts["raw_rows"]), ""),
        (
            "null link_id or unparseable timestamp",
            int(counts["raw_rows"] - counts["after_keys"]),
            "no key to aggregate on",
        ),
        (
            f"outside {start} .. {end_exclusive - pd.Timedelta(days=1)}",
            int(counts["after_keys"] - counts["after_window"]),
            "2026-06 is missing from the feed, so the window stops at 2026-05 and 2026-07 goes",
        ),
        (
            "ambiguous DST fall-back hour",
            int(counts["after_window"] - counts["after_dst"]),
            "that hour runs twice under naive local time; the cell would mix two real hours",
        ),
        (
            "duplicate (link_id, ts)",
            int(counts["after_dst"] - counts["after_dedup"]),
            "one reading kept per link and timestamp, the highest id",
        ),
        ("readings kept", int(counts["after_dedup"]), ""),
    ]
    return pd.DataFrame(steps, columns=["step", "rows", "reason"])


def add_flags(hourly: pd.DataFrame) -> pd.DataFrame:
    """Date, hour-of-day, peak, post and event-time columns.

    ``event_week`` reproduces ``sql/03_hourly_panel.sql`` exactly, so a frame
    from this panel is interchangeable with one from the primary panel.
    ``event_month`` is added because H007's event study is monthly: 41 months of
    data support monthly bins, and weekly bins over the same span would ask the
    joint pre-trend test to carry more than a hundred restrictions on nine
    treated clusters.
    """
    out = hourly.copy()
    ts = pd.to_datetime(out["ts_hour"])
    out["ts_hour"] = ts
    out["date"] = ts.dt.date
    out["hour"] = ts.dt.hour.astype("int32")
    # Match DuckDB's date_part('dow'), where Sunday is 0.
    out["dow"] = ((ts.dt.dayofweek + 1) % 7).astype("int32")
    out["is_weekend"] = out["dow"].isin([0, 6])
    out["is_am_peak"] = out["hour"].between(7, 9)
    out["is_pm_peak"] = out["hour"].between(16, 18)
    out["is_peak"] = out["is_am_peak"] | out["is_pm_peak"]

    toll_start = pd.Timestamp(TREATMENT_DATE)
    out["post"] = ts >= toll_start
    elapsed_days = (ts.dt.normalize() - toll_start).dt.days
    out["event_week"] = (elapsed_days // 7).astype("int32")
    out["event_month"] = (
        (ts.dt.year - toll_start.year) * 12 + (ts.dt.month - toll_start.month)
    ).astype("int32")
    return out


def build(
    parts_glob: str = DEFAULT_PARTS_GLOB, memory_limit: str = "4GB"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw parts -> the analysis panel and its row accounting.

    Logs rows in -> rows out with the reason for every drop, and returns the
    same funnel as a frame so it can be written next to the panel.
    """
    con = duckdb.connect(config={"memory_limit": memory_limit, "threads": "4"})
    try:
        funnel = row_accounting(con, parts_glob)
        attrs = link_attributes(con, parts_glob)
        hourly = hourly_aggregate(con, parts_glob)
    finally:
        con.close()
    raw_rows = int(funnel.loc[funnel["step"].str.startswith("raw rows"), "rows"].iloc[0])
    for _, step in funnel.iloc[1:-1].iterrows():
        log.info("  drop %s rows: %s (%s)", f"{step['rows']:,}", step["step"], step["reason"])

    links = classify_links(attrs)
    counts = links["analysis_group"].value_counts().to_dict()
    log.info(
        "links: %d total -> %d treated (exempt in zone), %d control, %d held out (%s)",
        len(links),
        counts.get("treated_exempt", 0),
        counts.get("control", 0),
        len(links) - counts.get("treated_exempt", 0) - counts.get("control", 0),
        ", ".join(
            f"{n} {g}" for g, n in sorted(counts.items()) if g not in ("treated_exempt", "control")
        ),
    )

    kept_readings = int(hourly["n_readings"].sum())
    log.info(
        "readings: %s raw rows -> %s in window %s..%s, deduplicated on (link_id, ts), "
        "DST fall-back hour excluded (drops: out-of-window incl. all of 2026-07, "
        "null link_id or timestamp, duplicate (link_id, ts), ambiguous fall-back hour)",
        f"{raw_rows:,}",
        f"{kept_readings:,}",
        WINDOW_START,
        WINDOW_END_EXCLUSIVE - pd.Timedelta(days=1),
    )
    zero = int(hourly["n_zero_speed"].sum())
    unparsed = int(hourly["n_unparsed_speed"].sum())
    log.info(
        "speeds: %s readings -> %s positive (%s zero-speed outages and %s unparseable "
        "dropped as missing, never averaged in as 0 mph)",
        f"{kept_readings:,}",
        f"{int(hourly['n_positive'].sum()):,}",
        f"{zero:,}",
        f"{unparsed:,}",
    )

    panel = add_flags(hourly).merge(links, on="link_id", how="left", validate="many_to_one")
    panel["treatment_group"] = panel["treatment_group"].fillna("unassigned")
    panel["analysis_group"] = panel["analysis_group"].fillna("unassigned")
    panel["treated"] = panel["treated"].fillna(False).astype(bool)
    panel["treated_post"] = panel["treated"] & panel["post"]
    panel["has_speed"] = panel["median_speed_mph"].notna()

    log.info(
        "panel: %s link-hours present -> %s with a usable hourly median "
        "(%s hours had readings but no positive speed; kept with a null outcome so the "
        "availability diagnostic has its denominator, dropped by every estimator)",
        f"{len(panel):,}",
        f"{int(panel['has_speed'].sum()):,}",
        f"{int((~panel['has_speed']).sum()):,}",
    )
    hours = pd.DataFrame(
        [
            ("link-hours present in the feed", len(panel), ""),
            (
                "link-hours with no positive reading",
                int((~panel["has_speed"]).sum()),
                "kept with a null outcome; every estimator drops them, the availability "
                "diagnostic needs them as its denominator",
            ),
            ("link-hours with a usable hourly median", int(panel["has_speed"].sum()), ""),
        ],
        columns=["step", "rows", "reason"],
    )
    speeds = pd.DataFrame(
        [
            (
                "zero-speed readings",
                zero,
                "outages, not standstills: travel_time = 0, status = -101, frequency peaks "
                "overnight; treated as missing, never averaged in as 0 mph",
            ),
            ("unparseable speeds", unparsed, "try_cast returned null"),
            ("positive readings behind the hourly medians", int(hourly["n_positive"].sum()), ""),
        ],
        columns=["step", "rows", "reason"],
    )
    return panel, pd.concat([funnel, speeds, hours], ignore_index=True)


COLUMNS = [
    "link_id",
    "ts_hour",
    "median_speed_mph",
    "mean_speed_mph",
    "min_speed_mph",
    "max_speed_mph",
    "n_readings",
    "n_positive",
    "n_zero_speed",
    "n_unparsed_speed",
    "n_over_80",
    "has_speed",
    "borough",
    "link_name",
    "date",
    "hour",
    "dow",
    "is_weekend",
    "is_am_peak",
    "is_pm_peak",
    "is_peak",
    "post",
    "event_week",
    "event_month",
    "treatment_group",
    "analysis_group",
    "hold_out_reason",
    "treated",
    "treated_post",
    "roadway",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parts-glob", default=DEFAULT_PARTS_GLOB)
    ap.add_argument("--out", default=str(SECONDARY_HOURLY_PANEL_PATH))
    ap.add_argument("--memory-limit", default="4GB")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    panel, accounting = build(args.parts_glob, args.memory_limit)
    panel[COLUMNS].to_parquet(args.out, index=False)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    accounting_path = TABLES_DIR / "H007_row_accounting.csv"
    accounting.to_csv(accounting_path, index=False)
    log.info("wrote %s (%s rows) and %s", args.out, f"{len(panel):,}", accounting_path)


if __name__ == "__main__":
    main()
