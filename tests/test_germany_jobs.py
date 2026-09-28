"""Tests for tools/germany_jobs.py — Germany API scrapers and scoring."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from germany_jobs import (
    PRESETS,
    fetch_arbeitnow,
    fetch_arbeitsagentur,
    is_likely_german_only,
    score_job,
    stars,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "arbeitsagentur_v6_jobs.json"


def _load_v6_fixture() -> dict:
    """Load the recorded real v6 Arbeitsagentur payload (shared with the adapter tests)."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# ==================== is_likely_german_only ====================


class TestIsLikelyGermanOnly:
    def test_detects_german_language_signals(self):
        job = {"title": "Sachbearbeiter", "description": "", "tags": []}
        assert is_likely_german_only(job) is True

    def test_detects_deutsch_c1_in_description(self):
        job = {"title": "Project Manager", "description": "Deutsch C1 erforderlich", "tags": []}
        assert is_likely_german_only(job) is True

    def test_passes_english_role(self):
        job = {
            "title": "AI Product Manager",
            "description": "English working environment",
            "tags": [],
        }
        assert is_likely_german_only(job) is False

    def test_detects_signal_in_tags(self):
        job = {"title": "Manager", "description": "", "tags": ["deutschsprachig"]}
        assert is_likely_german_only(job) is True

    def test_detects_kaufmann_pattern(self):
        job = {"title": "Kaufmann für Büromanagement", "description": "", "tags": []}
        assert is_likely_german_only(job) is True

    def test_case_insensitive(self):
        job = {"title": "SACHBEARBEITER", "description": "", "tags": []}
        assert is_likely_german_only(job) is True

    def test_empty_job(self):
        job = {"title": "", "description": "", "tags": []}
        assert is_likely_german_only(job) is False


# ==================== score_job ====================


class TestScoreJob:
    def test_high_score_many_signals(self):
        job = {
            "title": "AI Product Innovation Platform Builder",
            "company": "Technical Digital Corp",
            "tags": ["program"],
        }
        assert score_job(job) >= 4

    def test_low_score_no_signals(self):
        job = {"title": "Office Manager", "company": "Generic GmbH", "tags": []}
        assert score_job(job) == 1

    def test_medium_score(self):
        job = {"title": "Product Manager", "company": "Some Corp", "tags": []}
        assert 2 <= score_job(job) <= 4

    def test_score_range(self):
        """All scores should be 1-5."""
        for title in [
            "Nothing",
            "AI",
            "AI Product",
            "AI Product Program Technical",
            "AI Product Program Technical Innovation Digital Platform Builder",
        ]:
            job = {"title": title, "company": "", "tags": []}
            s = score_job(job)
            assert 1 <= s <= 5


# ==================== stars ====================


class TestStars:
    def test_full_stars(self):
        assert stars(5) == "★★★★★"

    def test_no_stars(self):
        assert stars(0) == "☆☆☆☆☆"

    def test_partial(self):
        assert stars(3) == "★★★☆☆"

    def test_length_always_five(self):
        for s in range(6):
            assert len(stars(s)) == 5


# ==================== PRESETS ====================


class TestPresets:
    def test_all_presets_exist(self):
        assert "tpm" in PRESETS
        assert "pm" in PRESETS
        assert "ai" in PRESETS
        assert "builder" in PRESETS

    def test_presets_have_keywords(self):
        for name, keywords in PRESETS.items():
            assert len(keywords) > 0, f"Preset '{name}' has no keywords"
            assert all(isinstance(k, str) for k in keywords)


# ==================== fetch_arbeitsagentur ====================


def _mock_arbeitsagentur_client(mock_client_cls, payload):
    """Wire mock_client_cls (a patched germany_jobs.httpx.Client) to return payload as JSON."""
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client
    return mock_client


class TestFetchArbeitsagentur:
    """fetch_arbeitsagentur against the recorded real v6 fixture (shared drift guard)."""

    @patch("germany_jobs.httpx.Client")
    def test_parses_response_with_exact_literal_values(self, mock_client_cls):
        """All 3 fixture rows parse to the exact literal fields asserted for the adapter."""
        _mock_arbeitsagentur_client(mock_client_cls, _load_v6_fixture())

        jobs = fetch_arbeitsagentur(keywords="Manager", location="Frankfurt")

        assert len(jobs) == 3
        assert jobs[0]["title"] == "Bid Manager (m/w/d)"
        assert jobs[0]["company"] == "SD Worx GmbH"
        assert jobs[0]["location"] == "Frankfurt am Main, Deutschland"
        assert jobs[0]["country"] == "Deutschland"
        assert jobs[0]["remote"] is True
        assert jobs[0]["url"] == (
            "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003645841-S"
        )
        assert jobs[0]["refnr"] == "10001-1003645841-S"
        assert jobs[0]["posted"] == "2026-09-03"
        assert jobs[0]["source"] == "arbeitsagentur"
        assert jobs[0]["tags"] == []

        assert jobs[1]["company"] == "BWI GmbH"
        assert jobs[1]["remote"] is False
        assert jobs[1]["url"] == (
            "https://www.arbeitsagentur.de/jobsuche/jobdetail/12336-a26f539j0448996-S"
        )

        assert jobs[2]["company"] == "CANCOM SE"
        assert jobs[2]["remote"] is False

    @patch("germany_jobs.httpx.Client")
    def test_request_targets_v6_endpoint_with_no_arbeitszeit_param(self, mock_client_cls):
        """The single client.get call hits /pc/v6/jobs, sends the API key, no arbeitszeit."""
        mock_client = _mock_arbeitsagentur_client(mock_client_cls, _load_v6_fixture())

        fetch_arbeitsagentur(keywords="Manager", location="Frankfurt")

        assert mock_client.get.call_count == 1
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        headers = call_args[1]["headers"]
        assert "/pc/v6/jobs" in url
        assert "was=Manager" in url
        assert "wo=Frankfurt" in url
        assert "arbeitszeit" not in url
        assert headers["X-API-Key"] == "jobboerse-jobsuche"

    @patch("germany_jobs.httpx.Client")
    def test_remote_true_filters_client_side_and_sends_no_arbeitszeit(self, mock_client_cls):
        """remote=True returns only the homeofficemoeglich-true row, no arbeitszeit param."""
        mock_client = _mock_arbeitsagentur_client(mock_client_cls, _load_v6_fixture())

        jobs = fetch_arbeitsagentur(keywords="Manager", location="Frankfurt", remote=True)

        assert len(jobs) == 1
        assert jobs[0]["company"] == "SD Worx GmbH"
        assert jobs[0]["remote"] is True
        url = mock_client.get.call_args[0][0]
        assert "arbeitszeit" not in url
        assert "size=100" in url, "client-side filtering asks for the largest page"

    @patch("germany_jobs.httpx.Client")
    def test_remote_true_truncates_to_limit_after_filtering(self, mock_client_cls):
        """Qualifying rows beyond `limit` on the widened page are kept up to `limit`."""
        base = _load_v6_fixture()["ergebnisliste"][0]
        items = [
            {**base, "referenznummer": f"10000-{i}-S", "homeofficemoeglich": i >= 4}
            for i in range(9)
        ]
        _mock_arbeitsagentur_client(mock_client_cls, {"ergebnisliste": items})

        jobs = fetch_arbeitsagentur(keywords="Manager", limit=3, remote=True)

        assert len(jobs) == 3
        assert all(j["remote"] for j in jobs)
        assert jobs[0]["url"].endswith("10000-4-S")

    @patch("germany_jobs.httpx.Client")
    def test_remote_true_walks_pages_until_limit_or_short_page(self, mock_client_cls):
        """Remote rows on page 2 are found; a short page stops the walk."""
        base = _load_v6_fixture()["ergebnisliste"][0]

        def page(n, flags):
            return {
                "ergebnisliste": [
                    {**base, "referenznummer": f"1{n}-{i}-S", "homeofficemoeglich": f}
                    for i, f in enumerate(flags)
                ]
            }

        payloads = [
            page(1, [False] * 100),
            page(2, [False] * 98 + [True, True]),
            page(3, [True] * 3),
        ]
        mock_client = _mock_arbeitsagentur_client(mock_client_cls, payloads[0])
        responses = []
        for p in payloads:
            r = MagicMock()
            r.json.return_value = p
            r.raise_for_status = MagicMock()
            responses.append(r)
        mock_client.get.side_effect = responses

        jobs = fetch_arbeitsagentur(keywords="Manager", limit=4, remote=True)

        assert [c[0][0] for c in mock_client.get.call_args_list].__len__() == 3
        assert ["page=1" in c[0][0] for c in mock_client.get.call_args_list][0]
        assert "page=3" in mock_client.get.call_args_list[2][0][0]
        assert [j["url"].rsplit("/", 1)[1] for j in jobs] == [
            "12-98-S",
            "12-99-S",
            "13-0-S",
            "13-1-S",
        ]

    @patch("germany_jobs.httpx.Client")
    def test_null_location_entry_does_not_abort_the_fetch(self, mock_client_cls):
        base = _load_v6_fixture()["ergebnisliste"][0]
        rows = [
            {**base, "stellenlokationen": [None]},
            {**base, "stellenlokationen": [{"adresse": None}]},
            {**base, "stellenlokationen": {"adresse": None}},
            {**base, "stellenlokationen": 1},
            {**base, "stellenlokationen": [{"adresse": {"region": 123, "land": ["DE"]}}]},
            None,  # a null row is skipped, not fatal
            "x",
        ]
        _mock_arbeitsagentur_client(mock_client_cls, {"ergebnisliste": rows})

        jobs = fetch_arbeitsagentur(keywords="Manager")

        assert [j["location"] for j in jobs] == ["Deutschland"] * 5

    @patch("germany_jobs.httpx.Client")
    def test_non_list_ergebnisliste_is_empty(self, mock_client_cls):
        _mock_arbeitsagentur_client(mock_client_cls, {"ergebnisliste": {"oops": 1}})
        assert fetch_arbeitsagentur(keywords="Manager") == []

    @patch("germany_jobs.httpx.Client")
    def test_non_object_json_body_is_empty(self, mock_client_cls):
        for body in (None, [], 3, "x"):
            _mock_arbeitsagentur_client(mock_client_cls, body)
            assert fetch_arbeitsagentur(keywords="Manager") == []
            assert fetch_arbeitsagentur(keywords="Manager", remote=True) == []

    @patch("germany_jobs.httpx.Client")
    def test_remote_true_keeps_rows_when_a_later_page_fails(self, mock_client_cls):
        base = _load_v6_fixture()["ergebnisliste"][0]
        page1 = {
            "ergebnisliste": [
                {**base, "referenznummer": f"11-{i}-S", "homeofficemoeglich": i == 7}
                for i in range(100)
            ]
        }
        mock_client = _mock_arbeitsagentur_client(mock_client_cls, page1)
        ok = MagicMock()
        ok.json.return_value = page1
        ok.raise_for_status = MagicMock()
        mock_client.get.side_effect = [ok, httpx.ReadTimeout("page 2 timed out")]

        jobs = fetch_arbeitsagentur(keywords="Manager", limit=2, remote=True)

        assert [j["url"].rsplit("/", 1)[1] for j in jobs] == ["11-7-S"]

    @patch("germany_jobs.httpx.Client")
    def test_remote_true_null_row_on_a_full_page_is_not_exhaustion(self, mock_client_cls):
        base = _load_v6_fixture()["ergebnisliste"][0]
        page1 = {
            "ergebnisliste": [
                {**base, "referenznummer": f"a-{i}", "homeofficemoeglich": False} for i in range(99)
            ]
            + [None]
        }
        page2 = {"ergebnisliste": [{**base, "referenznummer": "b-0", "homeofficemoeglich": True}]}
        mock_client = _mock_arbeitsagentur_client(mock_client_cls, page1)
        responses = []
        for p in (page1, page2):
            r = MagicMock()
            r.json.return_value = p
            r.raise_for_status = MagicMock()
            responses.append(r)
        mock_client.get.side_effect = responses

        jobs = fetch_arbeitsagentur(keywords="Manager", limit=1, remote=True)

        assert mock_client.get.call_count == 2
        assert [j["url"].rsplit("/", 1)[1] for j in jobs] == ["b-0"]

    @patch("germany_jobs.httpx.Client")
    def test_non_object_publication_period_is_absent(self, mock_client_cls):
        base = _load_v6_fixture()["ergebnisliste"][0]
        rows = [
            {**base, "veroeffentlichungszeitraum": "unknown"},
            {**base, "veroeffentlichungszeitraum": [1]},
        ]
        _mock_arbeitsagentur_client(mock_client_cls, {"ergebnisliste": rows})

        jobs = fetch_arbeitsagentur(keywords="Manager")

        assert len(jobs) == 2

    @patch("germany_jobs.httpx.Client")
    def test_handles_api_error(self, mock_client_cls):
        """A raised exception from client.get is swallowed and returns []."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("API down")
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitsagentur()
        assert jobs == []
        assert isinstance(jobs, list)

    @patch("germany_jobs.httpx.Client")
    def test_zero_hit_v6_body_returns_empty_list(self, mock_client_cls):
        """A v6 zero-hit body (no ergebnisliste key at all) returns []."""
        _mock_arbeitsagentur_client(
            mock_client_cls, {"maxErgebnisse": 0, "page": 1, "size": 25, "woOutput": {}}
        )

        jobs = fetch_arbeitsagentur()
        assert jobs == []
        assert isinstance(jobs, list)


# ==================== fetch_arbeitnow ====================


class TestFetchArbeitnow:
    @patch("germany_jobs.httpx.Client")
    def test_parses_response(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "Frontend Developer",
                    "company_name": "Startup Berlin",
                    "location": "Berlin",
                    "url": "https://arbeitnow.com/job/1",
                    "remote": True,
                    "tags": ["react", "javascript"],
                    "created_at": 1710000000,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitnow(keywords="frontend", location="Berlin")
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Frontend Developer"
        assert jobs[0]["source"] == "arbeitnow"
        assert jobs[0]["remote"] is True

    @patch("germany_jobs.httpx.Client")
    def test_filters_by_location(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "Dev",
                    "company_name": "Co",
                    "location": "Munich",
                    "url": "u",
                    "created_at": 0,
                },
                {
                    "title": "Dev",
                    "company_name": "Co",
                    "location": "Berlin",
                    "url": "u",
                    "created_at": 0,
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitnow(location="Berlin")
        assert len(jobs) == 1
        assert jobs[0]["location"] == "Berlin"

    @patch("germany_jobs.httpx.Client")
    def test_remote_only_filter(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "Dev1",
                    "company_name": "A",
                    "location": "X",
                    "url": "u",
                    "remote": False,
                    "created_at": 0,
                },
                {
                    "title": "Dev2",
                    "company_name": "B",
                    "location": "Y",
                    "url": "u",
                    "remote": True,
                    "created_at": 0,
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitnow(remote_only=True)
        assert len(jobs) == 1
        assert jobs[0]["remote"] is True
