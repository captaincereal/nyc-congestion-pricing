"""Where the backfill has got to, and whether it has unblocked the study yet.

Prints a short markdown report to stdout. The scheduled backfill appends it to
the job summary, so each pass answers the only question that matters between
passes: is there enough pre-period yet to test parallel trends, and if not, how
much further is there to go.

The study is gated on the PRE-period, not on total months. Tolling began
2025-01-05, and the pre-trend test currently runs on a window that is
essentially Thanksgiving through New Year. Post-treatment months, however many
land, do not fix that — so this report leads with pre-period depth.

    python -m src.data.coverage_report
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

from src.config import EZPASS_PARTS_DIR, STUDY_START, TABLES_DIR, TREATMENT_DATE

# Measured over the priority window: 30-40 minutes per month against a feed
# that throttles sustained pulls. Used only to size what is left.
MINUTES_PER_MONTH = 35

_PART_RE = re.compile(r"ezpass_speeds_(\d{4})-(\d{2})\.parquet$")


def months_on_disk() -> list[date]:
    out = []
    for p in sorted(EZPASS_PARTS_DIR.glob("ezpass_speeds_*.parquet")):
        m = _PART_RE.search(p.name)
        if m:
            out.append(date(int(m.group(1)), int(m.group(2)), 1))
    return sorted(out)


def target_months(today: date | None = None) -> list[date]:
    """Every month in the frozen study window, 2023-01 to the latest complete one."""
    end = (today or date.today()).replace(day=1)
    cur = STUDY_START.replace(day=1)
    out = []
    while cur < end:
        out.append(cur)
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return out


def contiguous_runs(months: list[date]) -> list[tuple[date, date]]:
    """Group sorted months into unbroken runs.

    A gap matters more than a count: seven scattered months cannot support an
    event study, and the manifest's `coverage` field reports only first and
    last, which hid a three-month hole for a while.
    """
    if not months:
        return []
    runs = [(months[0], months[0])]
    for m in months[1:]:
        prev = runs[-1][1]
        nxt = date(prev.year + 1, 1, 1) if prev.month == 12 else date(prev.year, prev.month + 1, 1)
        if m == nxt:
            runs[-1] = (runs[-1][0], m)
        else:
            runs.append((m, m))
    return runs


def _fmt(m: date) -> str:
    return f"{m:%Y-%m}"


def _span_months(run: tuple[date, date]) -> int:
    """Inclusive month count of a contiguous run."""
    a, b = run
    return (b.year - a.year) * 12 + b.month - a.month + 1


def _pretrend_section() -> list[str]:
    path = TABLES_DIR / "pretrend_tests.csv"
    if not path.exists():
        return ["_No pre-trend test has run against this data yet._", ""]
    df = pd.read_csv(path)
    lines = [
        "| Sample | chi2 | dof | p | Verdict | Pre-weeks | Panel |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['sample']} | {r['chi2']:.1f} | {int(r['dof'])} | {r['p_value']:.3g} "
            f"| {r['verdict']} | {int(r['pre_weeks'])} "
            f"| {r['panel_start']} .. {r['panel_end']} |"
        )
    failing = (df["verdict"] != "PASS").sum()
    lines.append("")
    if failing:
        lines.append(
            f"{failing} of {len(df)} samples reject the zero-lead restriction or are untestable. "
            "The current control design does not support a causal estimate. "
            "See D2 in `docs/decision_register.md`."
        )
    else:
        lines.append(
            "No sample rejects the zero-lead restriction. This does not establish parallel "
            "trends: power, coverage, verification, D2 (control selection), and placebo "
            "tests still need review before any causal claim."
        )
    return [*lines, ""]


def report(today: date | None = None) -> str:
    have = months_on_disk()
    want = target_months(today)
    missing = [m for m in want if m not in set(have)]

    treat_month = TREATMENT_DATE.replace(day=1)
    pre = [m for m in have if m < treat_month]
    post = [m for m in have if m >= treat_month]
    pre_runs = contiguous_runs(pre)
    longest_pre = max(pre_runs, key=_span_months, default=None)

    lines = [
        "## Backfill coverage",
        "",
        f"**{len(have)} of {len(want)} months** on disk "
        f"({len(missing)} to go, roughly {len(missing) * MINUTES_PER_MONTH / 60:.0f}h "
        "of downloading at measured throughput).",
        "",
        f"- Pre-treatment months (before {_fmt(treat_month)}): **{len(pre)}**",
        f"- Post-treatment months: **{len(post)}**",
    ]

    if longest_pre:
        span = _span_months(longest_pre)
        lines.append(
            f"- Longest unbroken pre-period: **{span} months** "
            f"({_fmt(longest_pre[0])} .. {_fmt(longest_pre[1])})"
        )
        if span < 12:
            lines.append(
                f"- The 12-month diagnostic milestone is {12 - span} contiguous month(s) away. "
                "The frozen design requires 24 pre-treatment months; neither duration "
                "alone establishes parallel trends."
            )
    lines.append("")

    runs = contiguous_runs(have)
    if runs:
        lines += [
            "Contiguous coverage: "
            + ", ".join(_fmt(a) if a == b else f"{_fmt(a)}..{_fmt(b)}" for a, b in runs),
            "",
        ]
    if missing:
        head = ", ".join(_fmt(m) for m in missing[:12])
        more = f" (+{len(missing) - 12} more)" if len(missing) > 12 else ""
        lines += [f"Still missing: {head}{more}", ""]

    lines += ["## Pre-trend test — the gate on every estimate", ""]
    lines += _pretrend_section()
    return "\n".join(lines)


def main() -> None:
    print(report())


if __name__ == "__main__":
    main()
