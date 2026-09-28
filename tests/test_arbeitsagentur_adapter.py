"""Tests for ArbeitsagenturAdapter against the v6 jobsuche-service payload shape.

Fixture provenance: tests/fixtures/arbeitsagentur_v6_jobs.json was recorded live
from GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs
(was=Manager, wo=Frankfurt, size=100, page=1, veroeffentlichtseit=30, angebotsart=1)
on 2026-09-28, then trimmed to 3 real items (legal-entity employers only) covering
homeofficemoeglich true / false / absent, with facetten and the two
employer-identifying hash fields (arbeitgeberKundennummerHash, chiffrenummer)
removed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from career_os.discovery import adapters as adapters_module
from career_os.discovery.adapters import (
    ArbeitsagenturAdapter,
    ScrapeParams,
    _parse_arbeitsagentur_job,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "arbeitsagentur_v6_jobs.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_items() -> list[dict]:
    return _load_fixture()["ergebnisliste"]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestParseArbeitsagenturJob:
    """Parsing individual v6 job dicts into RawJobResult."""

    def test_parses_true_remote_item(self):
        """The homeofficemoeglich=true fixture item maps to remote=True with exact fields."""
        item = _fixture_items()[0]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.title == "Bid Manager (m/w/d)"
        assert result.company == "SD Worx GmbH"
        assert result.location == "Frankfurt am Main, Deutschland"
        assert result.remote is True
        assert result.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003645841-S"
        assert result.posted_at is not None
        assert result.posted_at.isoformat().startswith("2026-09-03")

    def test_parses_false_remote_item(self):
        """The homeofficemoeglich=false fixture item maps to remote=False with exact fields."""
        item = _fixture_items()[1]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.title == "Release Manager (m/w/d)"
        assert result.company == "BWI GmbH"
        assert result.remote is False
        assert (
            result.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/12336-a26f539j0448996-S"
        )

    def test_null_or_non_object_location_entries_fall_back(self):
        """{"stellenlokationen": [null]} and a null adresse must not crash the page."""
        base = _fixture_items()[0]
        for bad in ([None], [{"adresse": None}], ["Frankfurt"], [{"adresse": "x"}]):
            job = _parse_arbeitsagentur_job({**base, "stellenlokationen": bad}, "arbeitsagentur")
            assert job.location == "Deutschland"

    def test_parses_absent_remote_key_item(self):
        """A fixture item with no homeofficemoeglich key at all maps to remote=False."""
        item = _fixture_items()[2]
        assert "homeofficemoeglich" not in item
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.company == "CANCOM SE"
        assert result.remote is False

    def test_title_falls_back_to_hauptberuf(self):
        """A missing stellenangebotsTitel falls back to hauptberuf."""
        item = copy.deepcopy(_fixture_items()[0])
        del item["stellenangebotsTitel"]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.title == "Tender-Manager/in"
        assert result.company == "SD Worx GmbH"

    def test_title_falls_back_to_referenznummer_stub(self):
        """When both title fields are missing, title becomes 'Stelle {referenznummer}'."""
        item = copy.deepcopy(_fixture_items()[0])
        del item["stellenangebotsTitel"]
        del item["hauptberuf"]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.title == "Stelle 10001-1003645841-S"
        assert result.company == "SD Worx GmbH"

    def test_url_falls_back_to_externe_url(self):
        """A missing referenznummer falls back to externeURL (present on the FALSE item)."""
        item = copy.deepcopy(_fixture_items()[1])
        del item["referenznummer"]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.url == item["externeURL"]
        assert result.url.startswith("https://gute-jobs.de/")

    def test_url_empty_when_both_missing(self):
        """When both referenznummer and externeURL are missing, url is an empty string."""
        item = copy.deepcopy(_fixture_items()[0])
        del item["referenznummer"]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.url == ""
        assert result.company == "SD Worx GmbH"

    def test_url_is_percent_encoded(self):
        """A referenznummer with unsafe characters is percent-encoded into the URL path."""
        item = copy.deepcopy(_fixture_items()[0])
        item["referenznummer"] = "10001-abc def/ghi"
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert "abc%20def%2Fghi" in result.url
        assert " " not in result.url


# ---------------------------------------------------------------------------
# Location / country helper
# ---------------------------------------------------------------------------


class TestArbeitsagenturLocation:
    """City/country resolution and de-capitalisation from stellenlokationen."""

    def test_deutschland_item_title_cases_country(self):
        """A DEUTSCHLAND item resolves to ('Frankfurt am Main', 'Deutschland')."""
        item = _fixture_items()[0]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.location == "Frankfurt am Main, Deutschland"
        assert "DEUTSCHLAND" not in result.location

    def test_falls_back_to_region_when_ort_missing(self):
        """When ort is missing, the city component falls back to the title-cased region."""
        item = copy.deepcopy(_fixture_items()[0])
        del item["stellenlokationen"][0]["adresse"]["ort"]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.location == "Hessen, Deutschland"

    def test_missing_stellenlokationen_defaults_to_deutschland(self):
        """A missing stellenlokationen list yields a bare 'Deutschland' location, no crash."""
        item = copy.deepcopy(_fixture_items()[0])
        del item["stellenlokationen"]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.location == "Deutschland"
        assert result.company == "SD Worx GmbH"

    def test_empty_stellenlokationen_defaults_to_deutschland(self):
        """An empty stellenlokationen list yields a bare 'Deutschland' location, no crash."""
        item = copy.deepcopy(_fixture_items()[0])
        item["stellenlokationen"] = []
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.location == "Deutschland"
        assert result.company == "SD Worx GmbH"

    def test_none_adresse_defaults_to_deutschland(self):
        """A stellenlokationen entry whose adresse is None yields 'Deutschland', no crash."""
        item = copy.deepcopy(_fixture_items()[0])
        item["stellenlokationen"] = [{"adresse": None}]
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.location == "Deutschland"
        assert result.company == "SD Worx GmbH"

    def test_mixed_case_land_passes_through_unchanged(self):
        """A mixed-case land value is not touched by the ALL-CAPS-only title() rule."""
        item = copy.deepcopy(_fixture_items()[0])
        item["stellenlokationen"][0]["adresse"]["land"] = "Deutschland"
        result = _parse_arbeitsagentur_job(item, "arbeitsagentur")
        assert result.location == "Frankfurt am Main, Deutschland"


# ---------------------------------------------------------------------------
# scrape() end-to-end via httpx.MockTransport
# ---------------------------------------------------------------------------


def _install_mock_transport(monkeypatch, handler):
    """Monkeypatch adapters.httpx.AsyncClient to route through httpx.MockTransport.

    Captures the real AsyncClient class first, then returns a factory that
    constructs it with transport=httpx.MockTransport(handler) plus the
    caller's kwargs, so production code (self.ARBEITSAGENTUR_BASE etc.) is
    exercised unchanged.
    """
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(adapters_module.httpx, "AsyncClient", factory)


class TestArbeitsagenturAdapterScrape:
    """End-to-end scrape() behavior through a mocked transport."""

    @pytest.mark.asyncio
    async def test_scrape_hits_v6_endpoint_with_expected_params(self, monkeypatch):
        """scrape() sends exactly one GET to /pc/v6/jobs with the right header and params."""
        payload = _load_fixture()
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=payload)

        _install_mock_transport(monkeypatch, handler)

        adapter = ArbeitsagenturAdapter()
        results = await adapter.scrape(
            ScrapeParams(keywords=["Manager"], locations=["Frankfurt"], limit_per_source=5)
        )

        assert len(requests) == 1
        req = requests[0]
        assert urlparse(str(req.url)).path == "/jobboerse/jobsuche-service/pc/v6/jobs"
        assert req.headers["X-API-Key"] == "jobboerse-jobsuche"
        qs = parse_qs(urlparse(str(req.url)).query)
        assert qs["was"] == ["Manager"]
        assert qs["wo"] == ["Frankfurt"]
        assert qs["page"] == ["1"]
        assert qs["size"] == ["5"]
        assert "arbeitszeit" not in qs

        assert len(results) == 3
        assert all(r.source == "arbeitsagentur" for r in results)

    @pytest.mark.asyncio
    async def test_scrape_remote_only_filters_client_side_and_sends_no_arbeitszeit(
        self, monkeypatch
    ):
        """remote_only=True sends no arbeitszeit param and returns only the true row."""
        payload = _load_fixture()
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=payload)

        _install_mock_transport(monkeypatch, handler)

        adapter = ArbeitsagenturAdapter()
        results = await adapter.scrape(
            ScrapeParams(
                keywords=["Manager"],
                locations=["Frankfurt"],
                limit_per_source=5,
                remote_only=True,
            )
        )

        qs = parse_qs(urlparse(str(requests[0].url)).query)
        assert "arbeitszeit" not in qs
        # Client-side filtering asks for the largest v6 page, not `limit`,
        # so a remote-only search does not shrink to the remote rows among
        # the first five results.
        assert qs["size"] == ["100"]
        assert len(results) == 1
        assert results[0].remote is True
        assert results[0].company == "SD Worx GmbH"

    @pytest.mark.asyncio
    async def test_scrape_remote_only_truncates_to_limit_after_filtering(self, monkeypatch):
        """More remote rows than `limit` on the widened page are cut to `limit`."""
        base = _fixture_items()[0]
        payload = {
            "ergebnisliste": [
                {**base, "referenznummer": f"10000-{i}-S", "homeofficemoeglich": True}
                for i in range(7)
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        _install_mock_transport(monkeypatch, handler)

        results = await ArbeitsagenturAdapter().scrape(
            ScrapeParams(
                keywords=["Manager"],
                locations=["Frankfurt"],
                limit_per_source=3,
                remote_only=True,
            )
        )
        assert len(results) == 3
        assert all(r.remote for r in results)

    @pytest.mark.asyncio
    async def test_scrape_remote_only_walks_pages_until_limit_or_short_page(self, monkeypatch):
        """Remote rows on page 2 are found; a short page stops the walk."""
        base = _fixture_items()[0]

        def page(n: int, remote_flags: list[bool]) -> dict:
            return {
                "ergebnisliste": [
                    {**base, "referenznummer": f"1{n}-{i}-S", "homeofficemoeglich": flag}
                    for i, flag in enumerate(remote_flags)
                ]
            }

        pages = {
            "1": page(1, [False] * 100),  # full page, no remote rows
            "2": page(2, [False] * 98 + [True, True]),  # full page, two remote rows
            "3": page(3, [True] * 3),  # short page: result set exhausted
            "4": page(4, [True] * 100),  # never requested
        }
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            n = parse_qs(urlparse(str(request.url)).query)["page"][0]
            seen.append(n)
            return httpx.Response(200, json=pages[n])

        _install_mock_transport(monkeypatch, handler)
        results = await ArbeitsagenturAdapter().scrape(
            ScrapeParams(
                keywords=["Manager"], locations=["Frankfurt"], limit_per_source=4, remote_only=True
            )
        )
        assert seen == ["1", "2", "3"]
        assert [r.url.rsplit("/", 1)[1] for r in results] == [
            "12-98-S",
            "12-99-S",
            "13-0-S",
            "13-1-S",
        ]

    @pytest.mark.asyncio
    async def test_scrape_remote_only_stops_at_the_page_cap(self, monkeypatch):
        """With no remote rows anywhere, the walk gives up after the page cap."""
        base = _fixture_items()[0]
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(parse_qs(urlparse(str(request.url)).query)["page"][0])
            rows = [
                {**base, "referenznummer": f"x-{i}", "homeofficemoeglich": False}
                for i in range(100)
            ]
            return httpx.Response(200, json={"ergebnisliste": rows})

        _install_mock_transport(monkeypatch, handler)
        results = await ArbeitsagenturAdapter().scrape(
            ScrapeParams(
                keywords=["Manager"], locations=["Frankfurt"], limit_per_source=5, remote_only=True
            )
        )
        assert results == []
        assert seen == ["1", "2", "3", "4", "5"]

    @pytest.mark.asyncio
    async def test_scrape_zero_hit_body_returns_empty_list(self, monkeypatch):
        """A v6 zero-hit body (no ergebnisliste key) returns [] rather than raising."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"maxErgebnisse": 0, "page": 1, "size": 5, "woOutput": {}},
            )

        _install_mock_transport(monkeypatch, handler)

        adapter = ArbeitsagenturAdapter()
        results = await adapter.scrape(
            ScrapeParams(keywords=["Manager"], locations=["Frankfurt"], limit_per_source=5)
        )

        assert results == []
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_scrape_403_raises_http_status_error(self, monkeypatch):
        """A 403 (what the retired v4 endpoint now returns) raises out of scrape()."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": "forbidden"})

        _install_mock_transport(monkeypatch, handler)

        adapter = ArbeitsagenturAdapter()
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.scrape(
                ScrapeParams(keywords=["Manager"], locations=["Frankfurt"], limit_per_source=5)
            )
