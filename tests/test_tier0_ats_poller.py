"""Tests for tools.tier0_ats_poller — public ATS JSON polling MVP.

Covers G-636:
- Per-ATS-type parsing (Greenhouse, Lever, Ashby) from mocked HTTP responses
- State tracking: first run surfaces all, second run surfaces zero new
- Graceful error handling: one company 5xx, others still succeed
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from tier0_ats_poller import (  # noqa: E402
    TIER_0_COMPANIES,
    Tier0Job,
    fetch_ashby,
    fetch_greenhouse,
    fetch_lever,
    load_state,
    poll_once,
    save_state,
)

# --- Fixtures: representative ATS payloads -----------------------------------


GREENHOUSE_SAMPLE: dict = {
    "jobs": [
        {
            "id": 5161980008,
            "title": "Account Executive, Beneficial Deployments",
            "absolute_url": "https://job-boards.greenhouse.io/anthropic/jobs/5161980008",
            "location": {"name": "London, UK"},
            "updated_at": "2026-04-01T10:49:08-04:00",
            "first_published": "2026-03-15T10:49:08-04:00",
        },
        {
            "id": 5161980009,
            "title": "Research Engineer (Remote)",
            "absolute_url": "https://job-boards.greenhouse.io/anthropic/jobs/5161980009",
            "location": {"name": "Remote"},
            "updated_at": "2026-04-02T10:00:00-04:00",
            "first_published": "2026-04-02T10:00:00-04:00",
        },
    ],
    "meta": {"total": 2},
}

LEVER_SAMPLE: list[dict] = [
    {
        "id": "2a357282-9d44-4b41-a249-c75ffe878ce2",
        "text": "Account Executive - Enterprise",
        "hostedUrl": "https://jobs.lever.co/mistral/2a357282-9d44-4b41-a249-c75ffe878ce2",
        "categories": {
            "commitment": "Full-time",
            "location": "Paris",
            "team": "Business",
            "allLocations": ["Paris"],
        },
        "createdAt": 1773224977965,
        "workplaceType": "onsite",
        "descriptionPlain": "About Mistral. We democratize AI.",
    },
    {
        "id": "remote-job-uuid",
        "text": "Staff Engineer",
        "hostedUrl": "https://jobs.lever.co/mistral/remote-job-uuid",
        "categories": {"commitment": "Full-time", "team": "Engineering", "allLocations": []},
        "createdAt": 1773224977965,
        "workplaceType": "remote",
        "descriptionPlain": "",
    },
]

ASHBY_SAMPLE: dict = {
    "jobs": [
        {
            "id": "d3bc1ced-3ce4-4086-a050-555055dbb1ff",
            "title": "Senior / Staff Fullstack Engineer",
            "department": "Product",
            "team": "Engineering",
            "employmentType": "FullTime",
            "location": "Europe",
            "publishedAt": "2021-04-27T20:13:45.158+00:00",
            "isListed": True,
            "isRemote": True,
            "jobUrl": "https://jobs.ashbyhq.com/Linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff",
            "applyUrl": "https://jobs.ashbyhq.com/Linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff/application",
            "descriptionPlain": "Build Linear.",
        },
        {
            "id": "unlisted-job",
            "title": "Hidden Role",
            "location": "Anywhere",
            "isListed": False,
            "isRemote": True,
            "jobUrl": "https://jobs.ashbyhq.com/Linear/unlisted-job",
        },
    ],
}


def _mock_client(routes: dict[str, object]) -> httpx.Client:
    """Build an httpx.Client wired with a MockTransport for the given URL→payload map.

    ``routes`` values may be:
      - dict / list  → serialized as JSON, 200 OK
      - int          → returned as status code with empty JSON body
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for prefix, payload in routes.items():
            if url.startswith(prefix):
                if isinstance(payload, int):
                    return httpx.Response(payload, json={})
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": f"no route for {url}"})

    return httpx.Client(transport=httpx.MockTransport(handler))


# --- Per-ATS parser tests ----------------------------------------------------


def test_fetch_greenhouse_parses_jobs():
    """VAL-TIER0-001 Greenhouse: title/url/location/job_id parsed; remote inferred."""
    client = _mock_client(
        {"https://boards-api.greenhouse.io/v1/boards/anthropic/jobs": GREENHOUSE_SAMPLE}
    )
    jobs = fetch_greenhouse("anthropic", company_key="anthropic", client=client)
    assert len(jobs) == 2
    j0 = jobs[0]
    assert isinstance(j0, Tier0Job)
    assert j0.title == "Account Executive, Beneficial Deployments"
    assert j0.company == "anthropic"
    assert j0.location == "London, UK"
    assert j0.url.endswith("/5161980008")
    assert j0.job_id == "5161980008"
    assert j0.source == "tier0:greenhouse:anthropic"
    assert j0.remote is False
    # Second job has "Remote" in location → remote flag derives true
    assert jobs[1].remote is True


def test_fetch_lever_parses_postings():
    """VAL-TIER0-002 Lever: list payload, ms-epoch createdAt, workplaceType=remote."""
    client = _mock_client({"https://api.lever.co/v0/postings/mistral": LEVER_SAMPLE})
    jobs = fetch_lever("mistral", company_key="mistral", client=client)
    assert len(jobs) == 2
    j0 = jobs[0]
    assert j0.title == "Account Executive - Enterprise"
    assert j0.location == "Paris"
    assert j0.url.startswith("https://jobs.lever.co/mistral/")
    assert j0.job_id == "2a357282-9d44-4b41-a249-c75ffe878ce2"
    assert j0.source == "tier0:lever:mistral"
    assert j0.posted.startswith("20")  # ISO from ms epoch
    assert "Business" in j0.tags
    assert j0.remote is False
    # Second posting: workplaceType=remote → remote true
    assert jobs[1].remote is True


def test_fetch_ashby_skips_unlisted_jobs():
    """VAL-TIER0-003 Ashby: parses listed jobs, skips isListed=False."""
    client = _mock_client({"https://api.ashbyhq.com/posting-api/job-board/Linear": ASHBY_SAMPLE})
    jobs = fetch_ashby("Linear", company_key="linear", client=client)
    assert len(jobs) == 1, "Unlisted job must be filtered out"
    j = jobs[0]
    assert j.title == "Senior / Staff Fullstack Engineer"
    assert j.company == "linear"
    assert j.location == "Europe"
    assert j.url.startswith("https://jobs.ashbyhq.com/Linear/")
    assert j.job_id == "d3bc1ced-3ce4-4086-a050-555055dbb1ff"
    assert j.source == "tier0:ashby:Linear"
    assert j.remote is True
    assert "Product" in j.tags
    assert "FullTime" in j.tags


# --- State tracking tests ----------------------------------------------------


def test_state_roundtrip(tmp_path: Path):
    """VAL-TIER0-010 save_state then load_state returns the same dict."""
    state_path = tmp_path / "state.json"
    state = {"anthropic": ["1", "2", "3"], "mistral": ["abc"]}
    save_state(state_path, state)
    assert state_path.exists()
    assert load_state(state_path) == state


def test_state_missing_file_returns_empty(tmp_path: Path):
    """VAL-TIER0-011 Missing state file is treated as empty dict."""
    assert load_state(tmp_path / "does-not-exist.json") == {}


def test_state_corrupt_file_returns_empty(tmp_path: Path):
    """VAL-TIER0-012 Corrupt JSON is treated as empty dict (with a warning)."""
    state_path = tmp_path / "bad.json"
    state_path.write_text("{not json")
    assert load_state(state_path) == {}


def test_poll_once_first_run_surfaces_all_second_run_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """VAL-TIER0-020 Two consecutive runs against same response: 2 new then 0 new."""
    state_path = tmp_path / "state.json"
    companies = {"anthropic": ("greenhouse", "anthropic")}
    client = _mock_client(
        {"https://boards-api.greenhouse.io/v1/boards/anthropic/jobs": GREENHOUSE_SAMPLE}
    )

    run1 = poll_once(
        companies=companies,
        state_path=state_path,
        inter_company_delay=0,
        client=client,
    )
    assert len(run1) == 1
    assert run1[0].fetched == 2
    assert run1[0].new == 2
    assert {j.job_id for j in run1[0].new_jobs} == {"5161980008", "5161980009"}

    # State persisted
    saved = load_state(state_path)
    assert "anthropic" in saved
    assert set(saved["anthropic"]) == {"5161980008", "5161980009"}

    # Second run against same payload → 0 new
    client2 = _mock_client(
        {"https://boards-api.greenhouse.io/v1/boards/anthropic/jobs": GREENHOUSE_SAMPLE}
    )
    run2 = poll_once(
        companies=companies,
        state_path=state_path,
        inter_company_delay=0,
        client=client2,
    )
    assert run2[0].fetched == 2
    assert run2[0].new == 0
    assert run2[0].new_jobs == []


def test_poll_once_no_persist_does_not_write_state(tmp_path: Path):
    """VAL-TIER0-021 ``persist=False`` does not create the state file."""
    state_path = tmp_path / "state.json"
    companies = {"anthropic": ("greenhouse", "anthropic")}
    client = _mock_client(
        {"https://boards-api.greenhouse.io/v1/boards/anthropic/jobs": GREENHOUSE_SAMPLE}
    )
    poll_once(
        companies=companies,
        state_path=state_path,
        inter_company_delay=0,
        client=client,
        persist=False,
    )
    assert not state_path.exists()


# --- Error isolation tests ---------------------------------------------------


def test_poll_once_isolates_company_failure(tmp_path: Path):
    """VAL-TIER0-030 One company 5xx → others still succeed; error recorded."""
    state_path = tmp_path / "state.json"
    companies = {
        "anthropic": ("greenhouse", "anthropic"),
        "mistral": ("lever", "mistral"),
        "linear": ("ashby", "Linear"),
    }
    # Anthropic returns 503; mistral + linear succeed
    client = _mock_client(
        {
            "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs": 503,
            "https://api.lever.co/v0/postings/mistral": LEVER_SAMPLE,
            "https://api.ashbyhq.com/posting-api/job-board/Linear": ASHBY_SAMPLE,
        }
    )
    results = poll_once(
        companies=companies,
        state_path=state_path,
        inter_company_delay=0,
        client=client,
    )
    by_company = {r.company: r for r in results}
    assert by_company["anthropic"].error is not None
    assert by_company["anthropic"].fetched == 0
    assert by_company["mistral"].error is None
    assert by_company["mistral"].fetched == 2
    assert by_company["linear"].error is None
    assert by_company["linear"].fetched == 1


def test_poll_once_unsupported_ats_does_not_crash(tmp_path: Path):
    """VAL-TIER0-031 Unknown ATS type yields error result, never raises."""
    state_path = tmp_path / "state.json"
    companies = {"oxide": ("custom", "https://oxide.computer/careers")}
    client = _mock_client({})  # no routes needed; never called
    results = poll_once(
        companies=companies,
        state_path=state_path,
        inter_company_delay=0,
        client=client,
    )
    assert len(results) == 1
    assert results[0].error is not None
    assert "unsupported" in results[0].error.lower()


# --- Config sanity -----------------------------------------------------------


def test_tier_0_companies_config_shape():
    """VAL-TIER0-040 Every configured company has a known ATS type and non-empty slug."""
    known = {"greenhouse", "lever", "ashby"}
    for key, (ats, slug) in TIER_0_COMPANIES.items():
        assert isinstance(key, str) and key
        assert ats in known, f"{key} has unsupported ATS {ats}"
        assert isinstance(slug, str) and slug, f"{key} has empty slug"


def test_state_file_is_under_data_directory():
    """VAL-TIER0-041 Default state path is under data/ (gitignored)."""
    from tier0_ats_poller import DEFAULT_STATE_PATH

    parts = DEFAULT_STATE_PATH.parts
    assert "data" in parts
    assert DEFAULT_STATE_PATH.name == "tier0_state.json"


# --- Output schema -----------------------------------------------------------


def test_tier0_job_matches_pipeline_shape():
    """VAL-TIER0-050 Tier0Job exposes the same fields downstream consumers rely on.

    Mirrors ``tools.scrape_resilient.ScrapedJob`` so dedup, scoring, and digest
    code can consume both interchangeably.
    """
    j = Tier0Job(
        title="t",
        company="c",
        location="l",
        url="u",
        source="s",
    )
    expected = {
        "title",
        "company",
        "location",
        "url",
        "source",
        "description",
        "posted",
        "remote",
        "salary",
        "tags",
        "search_keyword",
        "scraped_at",
        "job_id",
    }
    assert expected.issubset(j.__dict__.keys())
    # dedup_key produces lowercase tuple
    assert j.dedup_key() == ("t", "c")


def test_poll_once_json_serializable(tmp_path: Path):
    """VAL-TIER0-051 New jobs serialize cleanly via dataclasses.asdict + json.dumps."""
    from dataclasses import asdict

    state_path = tmp_path / "state.json"
    companies = {"mistral": ("lever", "mistral")}
    client = _mock_client({"https://api.lever.co/v0/postings/mistral": LEVER_SAMPLE})
    results = poll_once(
        companies=companies,
        state_path=state_path,
        inter_company_delay=0,
        client=client,
    )
    serialized = json.dumps([asdict(j) for j in results[0].new_jobs])
    assert "Mistral" not in serialized or "Account Executive" in serialized
    # Round-trip check
    decoded = json.loads(serialized)
    assert isinstance(decoded, list)
    assert decoded[0]["company"] == "mistral"
