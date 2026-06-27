"""Tests for the Workable scraper ported from Eyas (G-1217 / Eyas G-1119).

Network is fully mocked via scrape_new_sources._retry_with_backoff. tools/tests/
is not in the CI testpaths (pre-existing); run locally with:
pytest tools/tests/test_scrape_workable.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scrape_new_sources as s  # noqa: E402

_FAKE_PAYLOAD = {
    "total": 2,
    "results": [
        {
            "title": "Senior Product Manager",
            "location": {"city": "Berlin", "country": "Germany"},
            "shortcode": "ABC123",
            "department": ["Product"],
            "published": "2026-06-20",
            "remote": True,
        },
        {
            "title": "Warehouse Associate",
            "location": {"city": "Hamburg", "country": "Germany"},
            "shortcode": "XYZ789",
            "department": "Ops",
            "published": "2026-06-21",
            "remote": False,
        },
    ],
}


def test_empty_company_list_returns_nothing():
    assert s.scrape_workable(companies=[]) == []


def test_ships_empty_default_list():
    # No personal target companies are upstreamed — the default is an extension point.
    assert s.WORKABLE_COMPANIES == []


def test_parses_payload_into_scrapedjobs(monkeypatch):
    monkeypatch.setattr(s, "_retry_with_backoff", lambda fn: _FAKE_PAYLOAD)
    monkeypatch.setattr(s, "_random_delay", lambda: None)

    jobs = s.scrape_workable(companies=["acme-co"])

    assert len(jobs) == 2
    pm = jobs[0]
    assert pm.title == "Senior Product Manager"
    assert pm.company == "Acme Co"  # slug -> Title Case
    assert pm.location == "Berlin, Germany"
    assert pm.source == "workable"
    assert pm.url == "https://apply.workable.com/acme-co/j/ABC123/"
    assert pm.remote is True
    assert pm.tags == ["Product"]


def test_keyword_filter_drops_non_matching(monkeypatch):
    monkeypatch.setattr(s, "_retry_with_backoff", lambda fn: _FAKE_PAYLOAD)
    monkeypatch.setattr(s, "_random_delay", lambda: None)

    jobs = s.scrape_workable(companies=["acme-co"], keyword_filter=["product"])

    assert len(jobs) == 1
    assert jobs[0].title == "Senior Product Manager"


def test_failed_fetch_skips_company(monkeypatch):
    monkeypatch.setattr(s, "_retry_with_backoff", lambda fn: None)
    monkeypatch.setattr(s, "_random_delay", lambda: None)

    assert s.scrape_workable(companies=["acme-co"]) == []


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
