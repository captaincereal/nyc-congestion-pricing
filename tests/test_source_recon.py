"""Source reconnaissance: it must report what it found, and invent nothing.

The property worth pinning is not the parsing. It is that every dataset the
probe describes came back from a search, because this project has already lost
weeks to a source whose coverage was assumed. `test_never_probes_an_id_that_no
_search_returned` is that check; the rest keep the parsing honest and make sure
a failed probe is recorded as a result rather than aborting the survey.

No network: every response here is a fixture.
"""

from __future__ import annotations

import json
import re

import pytest

from src.data import source_recon as recon

SOCRATA_ID = re.compile(r"/(?:api/views|resource)/([a-z0-9]{4}-[a-z0-9]{4})")


class _Response:
    def __init__(self, payload=None, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Records every URL asked for, so a test can audit the call sequence."""

    def __init__(self, catalog=None, views=None, coverage=None, fail: set[str] | None = None):
        self.catalog = catalog or {}
        self.views = views or {}
        self.coverage = coverage or {}
        self.fail = fail or set()
        self.urls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.urls.append(url)
        if url in self.fail:
            raise RuntimeError("boom")
        if url == recon.CATALOG:
            return _Response({"results": self.catalog.get(params["q"], [])})
        found = SOCRATA_ID.search(url)
        dataset_id = found.group(1) if found else ""
        if "/api/views/" in url:
            return _Response(self.views.get(dataset_id, {"name": "", "columns": []}))
        return _Response(self.coverage.get(dataset_id, []))

    def head(self, url, timeout=None, allow_redirects=None):
        self.urls.append(url)
        if url in self.fail:
            raise RuntimeError("unreachable")
        return _Response(status=200, headers={"Content-Type": "text/html", "Content-Length": "12"})


def _hit(dataset_id: str, name: str = "Some dataset") -> dict:
    return {
        "resource": {
            "id": dataset_id,
            "name": name,
            "description": "A description.",
            "updatedAt": "2026-09-01",
            "rows_size": 10,
        },
        "link": f"https://example.invalid/{dataset_id}",
    }


def _view(date_field: str = "toll_date") -> dict:
    return {
        "name": "Some dataset",
        "columns": [
            {"fieldName": date_field, "name": "Date", "dataTypeName": "calendar_date"},
            {"fieldName": "volume", "name": "Volume", "dataTypeName": "number"},
        ],
    }


def test_search_catalog_flattens_and_sorts_hits():
    session = FakeSession(catalog={"bridges": [_hit("bbbb-2222"), _hit("aaaa-1111")]})

    hits = recon.search_catalog(session, "data.ny.gov", "bridges")

    assert [hit["id"] for hit in hits] == ["aaaa-1111", "bbbb-2222"]
    assert hits[0]["name"] == "Some dataset"


def test_describe_dataset_picks_out_the_date_columns():
    session = FakeSession(views={"aaaa-1111": _view("crossing_date")})

    described = recon.describe_dataset(session, "data.ny.gov", "aaaa-1111")

    assert described["date_columns"] == ["crossing_date"]
    assert [column["field"] for column in described["columns"]] == ["crossing_date", "volume"]


def test_probe_coverage_reports_the_range_and_count():
    session = FakeSession(
        coverage={"aaaa-1111": [{"lo": "2019-01-01", "hi": "2026-08-31", "n": 7}]}
    )

    coverage = recon.probe_coverage(session, "data.ny.gov", "aaaa-1111", "crossing_date")

    assert coverage["earliest"] == "2019-01-01"
    assert coverage["latest"] == "2026-08-31"
    assert coverage["rows"] == 7
    assert coverage["date_column"] == "crossing_date"


def test_probe_url_records_what_came_back():
    session = FakeSession()

    probed = recon.probe_url(session, "https://example.invalid/thing")

    assert probed["status"] == 200
    assert probed["content_type"] == "text/html"


def test_survey_merges_hits_across_queries_without_duplicating():
    candidate = recon.Candidate("k", "A question?", "data.ny.gov", ("one", "two"))
    session = FakeSession(
        catalog={"one": [_hit("aaaa-1111")], "two": [_hit("aaaa-1111"), _hit("bbbb-2222")]},
        views={"aaaa-1111": _view(), "bbbb-2222": _view()},
        coverage={"aaaa-1111": [{"lo": "a", "hi": "b", "n": 1}]},
    )

    finding = recon.survey_candidate(session, candidate)

    assert [dataset["id"] for dataset in finding.detail["datasets"]] == ["aaaa-1111", "bbbb-2222"]
    assert finding.detail["question"] == "A question?"


def test_a_failed_search_is_recorded_rather_than_raised():
    candidate = recon.Candidate("k", "q", "data.ny.gov", ("one",))
    session = FakeSession(fail={recon.CATALOG})

    finding = recon.survey_candidate(session, candidate)

    assert finding.detail["search_errors"]["one"]
    assert finding.detail["datasets"] == []


def test_a_failed_description_does_not_abort_the_survey():
    candidate = recon.Candidate("k", "q", "data.ny.gov", ("one",))
    session = FakeSession(
        catalog={"one": [_hit("aaaa-1111"), _hit("bbbb-2222")]},
        views={"bbbb-2222": _view()},
        fail={"https://data.ny.gov/api/views/aaaa-1111.json"},
    )

    finding = recon.survey_candidate(session, candidate)

    ids = [dataset["id"] for dataset in finding.detail["datasets"]]
    assert ids == ["aaaa-1111", "bbbb-2222"], "the broken one is still reported"
    assert finding.detail["datasets"][0]["error"]


def test_never_probes_an_id_that_no_search_returned():
    """The integrity property. Assumed coverage is what cost this project weeks.

    Every dataset id appearing in a metadata or resource URL must have come back
    from a catalog search first. A hardcoded id would fail this.
    """
    catalog = {
        query: [_hit("aaaa-1111")] for candidate in recon.CANDIDATES for query in candidate.queries
    }
    session = FakeSession(
        catalog=catalog,
        views={"aaaa-1111": _view()},
        coverage={"aaaa-1111": [{"lo": "2019-01-01", "hi": "2026-08-31", "n": 5}]},
    )

    recon.run(session)

    searched = {"aaaa-1111"}
    probed = {match.group(1) for url in session.urls if (match := SOCRATA_ID.search(url))}
    assert probed <= searched, f"probed ids that no search returned: {probed - searched}"


def test_candidates_carry_questions_and_searches_rather_than_ids():
    for candidate in recon.CANDIDATES:
        assert candidate.queries, f"{candidate.key} has no search terms"
        assert candidate.question.endswith("?"), f"{candidate.key} states no question"
        assert not hasattr(candidate, "dataset_id")


def test_bare_urls_are_declared_as_guesses_and_probed():
    keys = {key for key, _ in recon.BARE_URLS}
    session = FakeSession(catalog={}, views={}, coverage={})

    findings = {finding.key: finding for finding in recon.run(session)}

    assert keys <= set(findings)
    for key in keys:
        assert findings[key].detail["status"] == 200


def test_markdown_renders_the_facts_and_claims_nothing():
    findings = [
        recon.Finding(
            "mta",
            {
                "question": "Did volume fall?",
                "domain": "data.ny.gov",
                "datasets": [
                    {
                        "id": "aaaa-1111",
                        "name": "Crossings",
                        "description": "Monthly volumes.",
                        "columns": [{"field": "volume"}],
                        "coverage": {
                            "earliest": "2019-01",
                            "latest": "2026-08",
                            "rows": 90,
                            "date_column": "month",
                        },
                    }
                ],
            },
        )
    ]

    report = recon.to_markdown(findings)

    assert "aaaa-1111" in report
    assert "2019-01" in report
    assert "no source is endorsed" in report


def test_output_is_deterministic():
    candidate = recon.Candidate("k", "q?", "data.ny.gov", ("one",))
    args = {
        "catalog": {"one": [_hit("bbbb-2222"), _hit("aaaa-1111")]},
        "views": {"aaaa-1111": _view(), "bbbb-2222": _view()},
        "coverage": {},
    }

    first = recon.survey_candidate(FakeSession(**args), candidate)
    second = recon.survey_candidate(FakeSession(**args), candidate)

    assert json.dumps(first.detail, sort_keys=True) == json.dumps(second.detail, sort_keys=True)


@pytest.mark.parametrize("candidate", recon.CANDIDATES, ids=lambda c: c.key)
def test_every_candidate_targets_a_question_the_study_could_not_answer(candidate):
    assert candidate.domain in ("data.ny.gov", "data.cityofnewyork.us")
    assert candidate.key.islower()
