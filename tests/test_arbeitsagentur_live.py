"""Env-gated live smoke test against the real Arbeitsagentur v6 jobsuche API.

Hits the real network (rest.arbeitsagentur.de), so it is skipped unless
KESTREL_LIVE_TESTS=1. CI never sets that variable, so the env-var gate — not
the `live` marker — is what keeps this suite out of CI; the marker exists so
the suite is selectable on demand.

Run it with:
    KESTREL_LIVE_TESTS=1 .venv/bin/python -m pytest tests/test_arbeitsagentur_live.py -m live
"""

from __future__ import annotations

import os

import pytest
from germany_jobs import fetch_arbeitsagentur

from career_os.discovery.adapters import ArbeitsagenturAdapter, ScrapeParams

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("KESTREL_LIVE_TESTS") != "1",
        reason="Live network test — set KESTREL_LIVE_TESTS=1 to run",
    ),
]


class TestArbeitsagenturLive:
    """Both surfaces (production adapter + standalone tool) against the real API."""

    @pytest.mark.asyncio
    async def test_adapter_returns_rows_for_manager_frankfurt(self):
        """ArbeitsagenturAdapter.scrape() returns real rows with a valid jobdetail URL."""
        results = await ArbeitsagenturAdapter().scrape(
            ScrapeParams(keywords=["Manager"], locations=["Frankfurt"], limit_per_source=10)
        )

        assert len(results) > 0
        assert all(r.source == "arbeitsagentur" and r.title for r in results)
        assert results[0].url.startswith("https://www.arbeitsagentur.de/jobsuche/jobdetail/")

    def test_germany_jobs_tool_returns_rows_for_manager_frankfurt(self):
        """fetch_arbeitsagentur() swallows errors and returns []; len > 0 is the real signal."""
        jobs = fetch_arbeitsagentur(keywords="Manager", location="Frankfurt", limit=10)

        assert len(jobs) > 0
        assert jobs[0]["url"].startswith("https://www.arbeitsagentur.de/jobsuche/jobdetail/")
        assert jobs[0]["country"] != ""
