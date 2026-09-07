"""Phase 2 — inspect the *real* schema of the raw DOT speeds pull.

Answers the Phase 2 validation questions without changing any data:
  - what columns / dtypes actually arrived
  - date range and timestamp cadence of ``data_as_of``
  - is ``data_as_of`` really America/New_York?  (DST-boundary probe)
  - how many distinct ``link_id`` (the analysis unit); is ``id`` per-reading?
  - duplicate rate on (link_id, data_as_of)
  - value distributions for ``speed``, ``status``, ``borough``
  - null rates per column

Prints a report to stdout and writes ``docs/schema_report.md``.

Usage:
    python -m src.data.inspect_schema
"""

from __future__ import annotations

import logging
import textwrap

import duckdb

from src.config import DOCS_DIR, RAW_DIR

log = logging.getLogger(__name__)

PARTS_GLOB = str(RAW_DIR / "dot_speeds" / "*.parquet")
REPORT_PATH = DOCS_DIR / "schema_report.md"

# Columns downstream code depends on; inspection fails loudly if any is absent.
EXPECTED_COLUMNS = {
    "id",
    "speed",
    "travel_time",
    "status",
    "data_as_of",
    "link_id",
    "link_points",
    "borough",
    "link_name",
}


def build_report(con: duckdb.DuckDBPyConnection) -> str:
    src = f"read_parquet('{PARTS_GLOB}', union_by_name=true)"
    out: list[str] = ["# Schema report — raw DOT speeds\n", f"Source: `{PARTS_GLOB}`\n"]

    cols_df = con.execute(f"DESCRIBE SELECT * FROM {src}").df()
    present = set(cols_df["column_name"])
    out += ["## Columns and types\n", cols_df.to_markdown(index=False), ""]

    missing = EXPECTED_COLUMNS - present
    unexpected = present - EXPECTED_COLUMNS
    out.append(f"- Expected columns missing: **{sorted(missing) or 'none'}**")
    out.append(f"- Columns beyond the expected set: {sorted(unexpected) or 'none'}\n")

    n = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    out.append(f"## Row count: **{n:,}**\n")

    # Null rates
    null_exprs = ", ".join(
        f"round(100.0 * sum(CASE WHEN {c} IS NULL OR {c} = '' THEN 1 ELSE 0 END)"
        f' / count(*), 3) AS "{c}"'
        for c in present
    )
    nulls = con.execute(f"SELECT {null_exprs} FROM {src}").df().T.reset_index()
    nulls.columns = ["column", "null_or_empty_pct"]
    out += ["## Null / empty rate (%)\n", nulls.to_markdown(index=False), ""]

    # Timestamp range + cadence
    ts = con.execute(f"""
        WITH t AS (SELECT try_cast(data_as_of AS TIMESTAMP) AS ts FROM {src})
        SELECT min(ts) AS ts_min, max(ts) AS ts_max,
               count(*) FILTER (WHERE ts IS NULL) AS unparseable
        FROM t
    """).df()
    out += ["## `data_as_of` range\n", ts.to_markdown(index=False), ""]

    cadence = con.execute(f"""
        WITH t AS (
            SELECT link_id, try_cast(data_as_of AS TIMESTAMP) AS ts FROM {src}
        ), d AS (
            SELECT date_diff('second', lag(ts) OVER (PARTITION BY link_id ORDER BY ts), ts) AS gap_s
            FROM t
        )
        SELECT
          count(*) FILTER (WHERE gap_s IS NOT NULL) AS intervals,
          round(median(gap_s), 1) AS median_gap_s,
          round(quantile_cont(gap_s, 0.10), 1) AS p10_gap_s,
          round(quantile_cont(gap_s, 0.90), 1) AS p90_gap_s
        FROM d WHERE gap_s > 0
    """).df()
    out += [
        "## Per-link reading cadence (seconds between consecutive readings)\n",
        cadence.to_markdown(index=False),
        "",
    ]

    # DST probe: local wall clock should SKIP 02:00-02:59 on spring-forward and
    # (in a naive local feed) show no impossible times. If timestamps were UTC,
    # the 07:00-07:59 UTC hour would be unremarkable but local rush-hour shifts.
    dst = con.execute(f"""
        WITH t AS (SELECT try_cast(data_as_of AS TIMESTAMP) AS ts FROM {src})
        SELECT
          count(*) FILTER (
            WHERE ts BETWEEN TIMESTAMP '2024-03-10 02:00:00'
                         AND TIMESTAMP '2024-03-10 02:59:59'
          ) AS spring_forward_gap_hour,
          count(*) FILTER (
            WHERE ts BETWEEN TIMESTAMP '2024-03-10 03:00:00'
                         AND TIMESTAMP '2024-03-10 03:59:59'
          ) AS hour_after,
          count(*) FILTER (
            WHERE ts BETWEEN TIMESTAMP '2024-11-03 01:00:00'
                         AND TIMESTAMP '2024-11-03 01:59:59'
          ) AS fall_back_hour
        FROM t
    """).df()
    out += [
        "## DST probe (expect `spring_forward_gap_hour` ≈ 0 if naive local time)\n",
        dst.to_markdown(index=False),
        "\n> If `spring_forward_gap_hour` is ~0 while `hour_after` is populated, "
        "`data_as_of` is naive **local** time. If it is populated, it is likely UTC.\n",
    ]

    # link_id cardinality and id semantics
    ids = con.execute(f"""
        SELECT
          count(DISTINCT link_id) AS distinct_link_id,
          count(DISTINCT id)      AS distinct_id,
          count(DISTINCT transcom_id) AS distinct_transcom_id,
          sum(CASE WHEN link_id = transcom_id THEN 1 ELSE 0 END) = count(*)
            AS link_eq_transcom_always
        FROM {src}
    """).df()
    out += ["## Identifier cardinality\n", ids.to_markdown(index=False), ""]

    dupes = con.execute(f"""
        WITH g AS (
            SELECT link_id, data_as_of, count(*) AS n FROM {src}
            GROUP BY 1, 2
        )
        SELECT count(*) FILTER (WHERE n > 1) AS dup_keys,
               sum(n) FILTER (WHERE n > 1) AS dup_rows,
               max(n) AS max_rows_per_key
        FROM g
    """).df()
    out += ["## Duplicates on (link_id, data_as_of)\n", dupes.to_markdown(index=False), ""]

    speed = con.execute(f"""
        WITH s AS (SELECT try_cast(speed AS DOUBLE) AS mph FROM {src})
        SELECT count(*) AS n, count(*) FILTER (WHERE mph IS NULL) AS unparseable,
               round(min(mph),2) AS min, round(quantile_cont(mph,0.01),2) AS p01,
               round(median(mph),2) AS p50, round(quantile_cont(mph,0.99),2) AS p99,
               round(max(mph),2) AS max,
               count(*) FILTER (WHERE mph = 0) AS zeros,
               count(*) FILTER (WHERE mph < 0) AS negatives,
               count(*) FILTER (WHERE mph > 80) AS gt_80
        FROM s
    """).df()
    out += ["## `speed` distribution (raw, no filtering)\n", speed.to_markdown(index=False), ""]

    status = con.execute(f"SELECT status, count(*) AS n FROM {src} GROUP BY 1 ORDER BY n DESC").df()
    out += ["## `status` value counts\n", status.to_markdown(index=False), ""]

    borough = con.execute(
        f"SELECT borough, count(*) AS n, count(DISTINCT link_id) AS links "
        f"FROM {src} GROUP BY 1 ORDER BY n DESC"
    ).df()
    out += ["## `borough` value counts\n", borough.to_markdown(index=False), ""]

    return "\n".join(str(x) for x in out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect()
    try:
        report = build_report(con)
    finally:
        con.close()

    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    log.info("wrote %s", REPORT_PATH)
    print(textwrap.dedent("""
        Next: confirm the timezone finding, decide the duplicate-handling rule,
        and record both in docs/data_dictionary.md before staging.
    """))


if __name__ == "__main__":
    main()
