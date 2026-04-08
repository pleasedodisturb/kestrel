"""Tests for tools/germany_jobs.py — Germany API scrapers and scoring."""

from unittest.mock import MagicMock, patch

import pytest

from germany_jobs import (
    PRESETS,
    fetch_arbeitnow,
    fetch_arbeitsagentur,
    is_likely_german_only,
    score_job,
    stars,
)


# ==================== is_likely_german_only ====================


class TestIsLikelyGermanOnly:
    def test_detects_german_language_signals(self):
        job = {"title": "Sachbearbeiter", "description": "", "tags": []}
        assert is_likely_german_only(job) is True

    def test_detects_deutsch_c1_in_description(self):
        job = {"title": "Project Manager", "description": "Deutsch C1 erforderlich", "tags": []}
        assert is_likely_german_only(job) is True

    def test_passes_english_role(self):
        job = {"title": "AI Product Manager", "description": "English working environment", "tags": []}
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
        for title in ["Nothing", "AI", "AI Product", "AI Product Program Technical", "AI Product Program Technical Innovation Digital Platform Builder"]:
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


class TestFetchArbeitsagentur:
    @patch("germany_jobs.httpx.Client")
    def test_parses_response(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "stellenangebote": [
                {
                    "beruf": "Software Engineer",
                    "arbeitgeber": "Tech GmbH",
                    "arbeitsort": {"ort": "Berlin", "land": "Deutschland"},
                    "refnr": "REF123",
                    "hashId": "abc123",
                    "aktuelleVeroeffentlichungsdatum": "2026-03-10",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitsagentur(keywords="Software", location="Berlin")
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Software Engineer"
        assert jobs[0]["company"] == "Tech GmbH"
        assert jobs[0]["source"] == "arbeitsagentur"
        assert "abc123" in jobs[0]["url"]

    @patch("germany_jobs.httpx.Client")
    def test_handles_api_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("API down")
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitsagentur()
        assert jobs == []

    @patch("germany_jobs.httpx.Client")
    def test_handles_empty_response(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"stellenangebote": []}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = fetch_arbeitsagentur()
        assert jobs == []


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
                {"title": "Dev", "company_name": "Co", "location": "Munich", "url": "u", "created_at": 0},
                {"title": "Dev", "company_name": "Co", "location": "Berlin", "url": "u", "created_at": 0},
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
                {"title": "Dev1", "company_name": "A", "location": "X", "url": "u", "remote": False, "created_at": 0},
                {"title": "Dev2", "company_name": "B", "location": "Y", "url": "u", "remote": True, "created_at": 0},
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
