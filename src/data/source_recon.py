"""Find out what alternative data actually exists, before anyone designs around it.

This project spent a long stretch estimating the effect of congestion pricing on
roads exempt from congestion pricing, because the primary feed's coverage was
assumed rather than checked. The speed question is closed, and the open ones —
did traffic volume entering the zone fall, did it shift to other crossings, did
people switch to transit — need a source with a genuine pre-period. Several
plausible ones have never been looked at.

So this reports facts and nothing else: which datasets exist, what columns they
carry, what date range they cover, how many rows. It computes no estimate, takes
no position on whether a source is suitable, and needs no hypothesis record —
`docs/hypotheses/README.md` exempts feasibility scoping, and H007 and H008 both
disclose having done it.

**Datasets are discovered by searching, not by asserting ids.** Nothing here
hardcodes a Socrata id, because a confidently wrong id is exactly the failure
this is meant to prevent. The few bare URLs below are marked as guesses and are
probed so the guess becomes a measurement.

    python -m src.data.source_recon
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import requests

from src.config import DOCS_DIR, TABLES_DIR
from src.data.download import _session

log = logging.getLogger(__name__)

CATALOG = "https://api.us.socrata.com/api/catalog/v1"
TIMEOUT = 60
SEARCH_LIMIT = 6

DATE_TYPES = ("calendar_date", "floating_timestamp", "date")


@dataclass(frozen=True)
class Candidate:
    """One question, and the searches that might find data able to answer it."""

    key: str
    question: str
    domain: str
    queries: tuple[str, ...]


# Ordered by how directly each bears on a question the study could not answer.
CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "mta_bridges_tunnels",
        "Did vehicle volume fall on crossings that feed the zone, against "
        "crossings run by the same operator that do not?",
        "data.ny.gov",
        ("bridges and tunnels traffic", "MTA bridge tunnel crossing volume"),
    ),
    Candidate(
        "subway_ridership",
        "Did people switch to transit inside the zone relative to outside?",
        "data.ny.gov",
        ("subway hourly ridership", "MTA daily ridership"),
    ),
    Candidate(
        "traffic_volume_counts",
        "Are there street-level vehicle counts with a pre-period near the cordon?",
        "data.cityofnewyork.us",
        ("traffic volume counts", "automated traffic volume"),
    ),
    Candidate(
        "tlc_trips",
        "Is there a door-to-door travel-time outcome with a long pre-period?",
        "data.cityofnewyork.us",
        ("taxi trip records", "for hire vehicle trip records"),
    ),
    Candidate(
        "crz_entries",
        "What else does the zone-entry feed carry beyond what H008-H010 use?",
        "data.ny.gov",
        ("congestion relief zone vehicle entries",),
    ),
)

# Guesses, deliberately labelled as such. The probe turns each into a fact.
BARE_URLS: tuple[tuple[str, str], ...] = (
    (
        "tlc_cloudfront_parquet",
        "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet",
    ),
    ("tlc_landing_page", "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"),
    ("port_authority_traffic", "https://www.panynj.gov/bridges-tunnels/en/traffic-volumes.html"),
)


@dataclass
class Finding:
    """What a probe actually returned. `error` is a result, not a failure."""

    key: str
    detail: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def search_catalog(session: requests.Session, domain: str, query: str) -> list[dict]:
    """Socrata's discovery API: find datasets by words rather than by id."""
    response = session.get(
        CATALOG,
        params={"q": query, "domains": domain, "only": "dataset", "limit": SEARCH_LIMIT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    hits = []
    for item in response.json().get("results", []):
        resource = item.get("resource", {})
        hits.append(
            {
                "id": resource.get("id", ""),
                "name": resource.get("name", ""),
                "description": (resource.get("description") or "")[:400],
                "updated_at": resource.get("updatedAt", ""),
                "rows": resource.get("rows_size"),
                "link": item.get("link", ""),
            }
        )
    return sorted(hits, key=lambda hit: hit["id"])


def describe_dataset(session: requests.Session, domain: str, dataset_id: str) -> dict:
    """Column names and types, so a later design can be written against reality."""
    response = session.get(f"https://{domain}/api/views/{dataset_id}.json", timeout=TIMEOUT)
    response.raise_for_status()
    view = response.json()
    columns = [
        {
            "field": column.get("fieldName", ""),
            "name": column.get("name", ""),
            "type": column.get("dataTypeName", ""),
        }
        for column in view.get("columns", [])
    ]
    return {
        "name": view.get("name", ""),
        "row_count": view.get("columns", [{}])[0].get("cachedContents", {}).get("non_null"),
        "columns": sorted(columns, key=lambda column: column["field"]),
        "date_columns": [c["field"] for c in columns if c["type"] in DATE_TYPES],
    }


def probe_coverage(
    session: requests.Session, domain: str, dataset_id: str, date_column: str
) -> dict:
    """Earliest and latest observation, and how many rows.

    An aggregate `$select`, which is safe. The paging collapse AGENTS.md warns
    about comes from putting a function on a timestamp inside `$where`.
    """
    response = session.get(
        f"https://{domain}/resource/{dataset_id}.json",
        params={"$select": f"min({date_column}) as lo, max({date_column}) as hi, count(*) as n"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    rows = response.json()
    row = rows[0] if rows else {}
    return {
        "date_column": date_column,
        "earliest": row.get("lo", ""),
        "latest": row.get("hi", ""),
        "rows": row.get("n", ""),
    }


def probe_url(session: requests.Session, url: str) -> dict:
    """Reachability of a guessed URL, recorded so the guess stops being one."""
    response = session.head(url, timeout=TIMEOUT, allow_redirects=True)
    return {
        "url": url,
        "status": response.status_code,
        "content_type": response.headers.get("Content-Type", ""),
        "content_length": response.headers.get("Content-Length", ""),
    }


def survey_candidate(session: requests.Session, candidate: Candidate) -> Finding:
    """Search, then describe and date-bound the best-matching datasets."""
    finding = Finding(key=candidate.key)
    finding.detail["question"] = candidate.question
    finding.detail["domain"] = candidate.domain
    datasets: dict[str, dict] = {}
    for query in candidate.queries:
        try:
            hits = search_catalog(session, candidate.domain, query)
        except Exception as problem:  # a failed search is a reportable outcome
            finding.detail.setdefault("search_errors", {})[query] = repr(problem)
            continue
        for hit in hits:
            datasets.setdefault(hit["id"], hit)

    for dataset_id, hit in sorted(datasets.items()):
        try:
            hit.update(describe_dataset(session, candidate.domain, dataset_id))
            for date_column in hit.get("date_columns", [])[:1]:
                hit["coverage"] = probe_coverage(session, candidate.domain, dataset_id, date_column)
        except Exception as problem:
            hit["error"] = repr(problem)
    finding.detail["datasets"] = [datasets[key] for key in sorted(datasets)]
    return finding


def run(session: requests.Session) -> list[Finding]:
    findings = [survey_candidate(session, candidate) for candidate in CANDIDATES]
    for key, url in BARE_URLS:
        try:
            findings.append(Finding(key=key, detail=probe_url(session, url)))
        except Exception as problem:
            findings.append(Finding(key=key, detail={"url": url}, error=repr(problem)))
    return findings


def to_markdown(findings: list[Finding]) -> str:
    """A report a person reads, beside the JSON a later session parses."""
    lines = [
        "# Source reconnaissance",
        "",
        "Generated by `python -m src.data.source_recon`. **Facts only.** No estimate",
        "is computed here and no source is endorsed; suitability is a judgement for",
        "a registered hypothesis, not for a probe.",
        "",
        "Datasets were found by searching Socrata's discovery API rather than by",
        "asserting ids. The `tlc_*` and `port_authority_*` sections below started",
        "as guessed URLs and carry whatever the probe actually returned, so the",
        "guess is now a measurement either way.",
        "",
    ]
    for finding in findings:
        lines.append(f"## {finding.key}")
        lines.append("")
        if finding.error:
            lines += [f"Probe failed: `{finding.error}`", ""]
            continue
        question = finding.detail.get("question")
        if question:
            lines += [f"*{question}*", ""]
        if "url" in finding.detail:
            detail = finding.detail
            lines += [
                f"- `{detail['url']}`",
                f"  - status **{detail.get('status')}**, type `{detail.get('content_type')}`,"
                f" length `{detail.get('content_length')}`",
                "",
            ]
            continue
        datasets = finding.detail.get("datasets", [])
        if not datasets:
            lines += ["No datasets matched.", ""]
        for dataset in datasets:
            lines.append(f"### `{dataset['id']}` — {dataset.get('name', '')}")
            coverage = dataset.get("coverage")
            if coverage:
                lines.append(
                    f"- Coverage: **{coverage.get('earliest', '?')}** to "
                    f"**{coverage.get('latest', '?')}**, {coverage.get('rows', '?')} rows "
                    f"(on `{coverage.get('date_column')}`)"
                )
            if dataset.get("error"):
                lines.append(f"- Probe error: `{dataset['error']}`")
            fields = ", ".join(f"`{column['field']}`" for column in dataset.get("columns", []))
            if fields:
                lines.append(f"- Columns: {fields}")
            if dataset.get("description"):
                lines.append(f"- {dataset['description']}")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-prefix", default="source_recon")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    findings = run(_session())
    payload = [
        {"key": finding.key, "detail": finding.detail, "error": finding.error}
        for finding in findings
    ]
    json_path = TABLES_DIR / f"{args.out_prefix}.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    markdown_path = DOCS_DIR / f"{args.out_prefix}.md"
    markdown_path.write_text(to_markdown(findings))
    log.info("wrote %s and %s", json_path, markdown_path)


if __name__ == "__main__":
    main()
