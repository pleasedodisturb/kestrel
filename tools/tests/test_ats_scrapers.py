"""Tests for the SmartRecruiters + Personio ATS scrapers.

Exercises the API/XML parse paths with canned fixtures (monkeypatched fetch); no
live network. Adds tools/ to sys.path (tools-test convention). Fixture company
names are de-personalized (fictional example slugs only).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scrape_new_sources as sns

# --- SmartRecruiters postings API (JSON) ---

_SR_DATA = {
    "content": [
        {
            "id": "111",
            "name": "Senior Product Manager",
            "location": {"city": "Dublin", "country": "Ireland", "fullLocation": "Dublin, Ireland"},
            "department": {"label": "Product"},
            "releasedDate": "2026-06-01",
        },
        {
            "id": "222",
            "name": "Staff Software Engineer",
            "location": {"city": "Remote", "country": "EU", "remote": True},
            "department": {"label": "Engineering"},
            "releasedDate": "2026-06-02",
        },
    ]
}


def _run_sr(keyword_filter=None):
    # _retry_with_backoff is called once per (company, query); return the same canned
    # payload each time, and rely on per-company dedup by posting id.
    with (
        patch.object(sns, "_retry_with_backoff", return_value=_SR_DATA),
        patch.object(sns, "_random_delay"),
    ):
        return sns.scrape_smartrecruiters(companies=["example-co"], keyword_filter=keyword_filter)


def test_smartrecruiters_parses_postings():
    jobs = _run_sr()
    titles = {j.title for j in jobs}
    assert "Senior Product Manager" in titles
    assert "Staff Software Engineer" in titles


def test_smartrecruiters_dedups_by_id():
    # Same payload returned for every query -> each posting appears exactly once.
    jobs = _run_sr()
    ids_in_url = [j.url for j in jobs]
    assert len(ids_in_url) == len(set(ids_in_url))


def test_smartrecruiters_normalizes_fields():
    jobs = _run_sr()
    pm = next(j for j in jobs if j.title == "Senior Product Manager")
    assert pm.source == "smartrecruiters"
    assert pm.location == "Dublin, Ireland"
    assert pm.url == "https://jobs.smartrecruiters.com/example-co/111"
    assert "Product" in pm.tags


def test_smartrecruiters_keyword_gate():
    jobs = _run_sr(keyword_filter=["product"])
    titles = {j.title for j in jobs}
    assert "Senior Product Manager" in titles
    assert "Staff Software Engineer" not in titles


def test_smartrecruiters_remote_flag():
    jobs = _run_sr()
    eng = next(j for j in jobs if j.title == "Staff Software Engineer")
    assert eng.remote is True


# --- Personio XML feed ---

_PERSONIO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
  <position>
    <id>901</id>
    <name>Product Manager</name>
    <office>Dublin</office>
    <department>Product</department>
    <createdAt>2026-06-03</createdAt>
    <additionalOffices>
      <office>Cork</office>
    </additionalOffices>
  </position>
  <position>
    <id>902</id>
    <name>Account Executive</name>
    <office>Remote</office>
    <department>Sales</department>
    <createdAt>2026-06-04</createdAt>
  </position>
</workzag-jobs>
"""


def _run_personio(keyword_filter=None):
    with (
        patch.object(sns, "_retry_with_backoff", return_value=_PERSONIO_XML),
        patch.object(sns, "_random_delay"),
    ):
        return sns.scrape_personio(companies=["example-co"], keyword_filter=keyword_filter)


def test_personio_parses_positions():
    jobs = _run_personio()
    titles = {j.title for j in jobs}
    assert "Product Manager" in titles
    assert "Account Executive" in titles


def test_personio_normalizes_fields():
    jobs = _run_personio()
    pm = next(j for j in jobs if j.title == "Product Manager")
    assert pm.source == "personio"
    assert pm.location == "Dublin"
    assert pm.url == "https://example-co.jobs.personio.de/job/901"
    assert "Product" in pm.tags


def test_personio_keyword_gate():
    jobs = _run_personio(keyword_filter=["product"])
    titles = {j.title for j in jobs}
    assert "Product Manager" in titles
    assert "Account Executive" not in titles


def test_personio_remote_flag():
    jobs = _run_personio()
    ae = next(j for j in jobs if j.title == "Account Executive")
    assert ae.remote is True


def test_personio_handles_bad_xml():
    with (
        patch.object(sns, "_retry_with_backoff", return_value="<not-valid-xml"),
        patch.object(sns, "_random_delay"),
    ):
        jobs = sns.scrape_personio(companies=["example-co"])
    assert jobs == []


def test_scrapers_default_to_example_company_lists():
    # The shipped defaults must be EXAMPLE-only placeholders, not real slugs.
    assert sns.SMARTRECRUITERS_COMPANIES == ["example-company-slug"]
    assert sns.PERSONIO_COMPANIES == ["example-company-slug"]
