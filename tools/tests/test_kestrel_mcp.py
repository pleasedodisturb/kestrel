"""Tests for Kestrel MCP server.

Covers:
- Tool registration (all 4 tools present)
- HTTP request format (URL, headers, auth)
- Response formatting for pipeline, stats, score, discovery
- Error handling (HTTP errors, connection failures)
- Configuration (env var defaults, custom values)
"""

import os
import sys
from unittest.mock import MagicMock, patch

import httpx

# Ensure kestrel-mcp/ is importable (hyphen means it's not a package)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kestrel-mcp"))

import pytest  # noqa: E402

# kestrel-mcp/server.py imports the `mcp` SDK (an optional extra). Skip the whole
# module when it isn't installed so test collection doesn't error in minimal envs.
pytest.importorskip("mcp.server.fastmcp")

from server import (  # noqa: I001, E402
    KESTREL_URL,
    PROFILE_ID,
    _format_discovery,
    _format_pipeline,
    _format_score,
    _format_stats,
    discover_jobs,
    list_pipeline,
    pipeline_stats,
    score_job,
)


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestConfiguration:
    """Test MCP server configuration defaults and env var handling."""

    def test_default_url(self) -> None:
        assert KESTREL_URL == "http://localhost:8100"

    def test_default_profile_id(self) -> None:
        assert PROFILE_ID == 1

    def test_headers_without_auth(self) -> None:
        with patch.dict(os.environ, {"KESTREL_API_KEY": ""}, clear=False):
            # Re-import to pick up empty key
            import server as srv

            original_key = srv.API_KEY
            srv.API_KEY = ""
            h = srv._headers()
            assert "X-API-Key" not in h
            assert h["Content-Type"] == "application/json"
            srv.API_KEY = original_key

    def test_headers_with_auth(self) -> None:
        import server as srv

        original_key = srv.API_KEY
        srv.API_KEY = "test-key"
        h = srv._headers()
        assert h["X-API-Key"] == "test-key"
        srv.API_KEY = original_key


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestFormatPipeline:
    """Test pipeline list formatting."""

    def test_empty_pipeline(self) -> None:
        result = _format_pipeline({"applications": [], "total": 0})
        assert result == "Pipeline is empty."

    def test_formats_applications(self) -> None:
        data = {
            "applications": [
                {
                    "id": 1,
                    "status": "applied",
                    "company": "Acme Corp",
                    "role": "Backend Engineer",
                    "fit_score": 8.5,
                },
                {
                    "id": 2,
                    "status": "interviewing",
                    "company": "Widgets Inc",
                    "role": "SRE",
                    "fit_score": None,
                },
            ],
            "total": 2,
        }
        result = _format_pipeline(data)
        assert "Pipeline: 2 applications" in result
        assert "[applied] Acme Corp — Backend Engineer (fit: 8.5)" in result
        assert "[interviewing] Widgets Inc — SRE" in result
        assert "id: 1" in result
        assert "id: 2" in result


class TestFormatStats:
    """Test pipeline stats formatting."""

    def test_formats_flat_stats(self) -> None:
        data = {"total_applications": 42, "active": 15}
        result = _format_stats(data)
        assert "Pipeline Statistics" in result
        assert "total_applications: 42" in result
        assert "active: 15" in result

    def test_formats_nested_stats(self) -> None:
        data = {"by_status": {"applied": 10, "interviewing": 5}}
        result = _format_stats(data)
        assert "by_status:" in result
        assert "applied: 10" in result
        assert "interviewing: 5" in result


class TestFormatScore:
    """Test score response formatting."""

    def test_formats_full_score(self) -> None:
        data = {
            "fit_score": 8.0,
            "readiness_score": 72.0,
            "career_alignment": 7.5,
            "effort_flag": "medium",
            "prep_level": "moderate",
            "reasoning": "Strong technical match",
            "estimated_salary": "120k EUR",
            "prep_notes": "Study system design",
            "score_breakdown": [
                {"factor": "Technical", "contribution": 2.0, "description": "Good fit"},
                {"factor": "Culture", "contribution": -0.5, "description": "Mismatch"},
            ],
        }
        result = _format_score(data)
        assert "Fit Score: 8.0/10" in result
        assert "Readiness: 72.0%" in result
        assert "Career Alignment: 7.5/10" in result
        assert "Effort: medium" in result
        assert "Strong technical match" in result
        assert "120k EUR" in result
        assert "Study system design" in result
        assert "Technical: +2.0" in result
        assert "Culture: -0.5" in result

    def test_formats_minimal_score(self) -> None:
        data = {
            "fit_score": 5.0,
            "readiness_score": 50.0,
            "career_alignment": 5.0,
            "effort_flag": "low",
            "prep_level": "minimal",
            "reasoning": "Average match",
        }
        result = _format_score(data)
        assert "Fit Score: 5.0/10" in result
        assert "Estimated Salary" not in result


class TestFormatDiscovery:
    """Test discovery response formatting."""

    def test_empty_discovery(self) -> None:
        data = {
            "total_found": 0,
            "new_jobs": 0,
            "duplicates": 0,
            "sources_queried": ["indeed"],
            "jobs": [],
        }
        result = _format_discovery(data)
        assert "0 found" in result
        assert "No new jobs found." in result

    def test_formats_jobs(self) -> None:
        data = {
            "total_found": 2,
            "new_jobs": 2,
            "duplicates": 0,
            "sources_queried": ["indeed", "linkedin"],
            "jobs": [
                {
                    "title": "Python Developer",
                    "company": "Acme",
                    "location": "Berlin",
                    "remote": True,
                    "fit_score": 7.5,
                },
                {
                    "title": "SRE",
                    "company": "Widgets",
                    "location": "Munich",
                    "remote": False,
                    "fit_score": None,
                },
            ],
        }
        result = _format_discovery(data)
        assert "2 found, 2 new" in result
        assert "indeed, linkedin" in result
        assert "Acme — Python Developer @ Berlin [remote] (fit: 7.5)" in result
        assert "Widgets — SRE @ Munich" in result


# ---------------------------------------------------------------------------
# Tool function tests (with mocked HTTP)
# ---------------------------------------------------------------------------


class TestListPipeline:
    """Test list_pipeline tool with mocked HTTP."""

    def test_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "applications": [
                {"id": 1, "status": "applied", "company": "X", "role": "Y", "fit_score": 7.0},
            ],
            "total": 1,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = list_pipeline()
            assert "Pipeline: 1 applications" in result
            assert "[applied] X — Y" in result

    def test_connection_error(self) -> None:
        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client_cls.return_value = mock_client

            result = list_pipeline()
            assert "Cannot connect to Kestrel" in result


class TestScoreJob:
    """Test score_job tool with mocked HTTP."""

    def test_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "fit_score": 8.0,
            "readiness_score": 75.0,
            "career_alignment": 7.0,
            "effort_flag": "medium",
            "prep_level": "moderate",
            "reasoning": "Good match",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = score_job("We are looking for a Python developer...")
            assert "Fit Score: 8.0/10" in result
            assert "Good match" in result

    def test_sends_correct_payload(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "fit_score": 5.0,
            "readiness_score": 50.0,
            "career_alignment": 5.0,
            "effort_flag": "low",
            "prep_level": "minimal",
            "reasoning": "ok",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            score_job("desc", job_title="SWE", job_company="Acme", job_url="https://x.com/j/1")

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["job_description"] == "desc"
            assert payload["job_title"] == "SWE"
            assert payload["job_company"] == "Acme"
            assert payload["job_url"] == "https://x.com/j/1"
            assert payload["profile_id"] == PROFILE_ID


class TestDiscoverJobs:
    """Test discover_jobs tool with mocked HTTP."""

    def test_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "total_found": 5,
            "new_jobs": 3,
            "duplicates": 2,
            "sources_queried": ["indeed"],
            "jobs": [
                {
                    "title": "Dev",
                    "company": "Co",
                    "location": "Berlin",
                    "remote": False,
                    "fit_score": 6.0,
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = discover_jobs(keywords="python,backend", locations="Berlin")
            assert "5 found, 3 new" in result
            assert "Co — Dev @ Berlin" in result

    def test_parses_comma_separated_keywords(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "total_found": 0,
            "new_jobs": 0,
            "duplicates": 0,
            "sources_queried": [],
            "jobs": [],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            discover_jobs(keywords="python, backend, senior")

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["keywords"] == ["python", "backend", "senior"]


class TestPipelineStats:
    """Test pipeline_stats tool with mocked HTTP."""

    def test_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total": 42, "by_status": {"applied": 10}}
        mock_resp.raise_for_status = MagicMock()

        with patch("server.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = pipeline_stats()
            assert "Pipeline Statistics" in result
            assert "total: 42" in result
