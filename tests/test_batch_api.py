"""Tests for Anthropic Batch API support — batch scoring for discovery sweeps.

Covers:
- batch_score() builds correct request payload and sends to Batch API endpoint
- batch_score() returns batch ID from response
- get_batch_results() handles in_progress status
- get_batch_results() parses completed results into AIResponse objects
- Base AIProvider raises NotImplementedError for batch methods
- Discovery service uses batch when threshold is met
- Discovery service falls back to sequential below threshold
- Error handling: batch submission failure falls back to sequential
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from career_os.ai.anthropic_provider import (
    ANTHROPIC_BATCH_API_URL,
    ANTHROPIC_VERSION,
    AnthropicProvider,
)
from career_os.ai.base import AIProvider
from career_os.schemas.ai import AIFeature, AIResponse, ScoreResult
from career_os.services.discovery import BATCH_SCORING_THRESHOLD

# Fake credentials — not real.
_TEST_KEY = "test-fake-anthropic-key"  # noqa: S105

# Reusable test data
_SAMPLE_JOBS = [
    {"id": "job-1", "description": "Software Engineer at Acme Corp"},
    {"id": "job-2", "description": "Product Manager at Widget Inc"},
    {"id": "job-3", "description": "Data Scientist at DataCo"},
]

_SAMPLE_PROFILE = {"name": "Jane Doe", "location": "Berlin"}

_SCORE_JSON = json.dumps(
    {
        "fit_score": 7.5,
        "reasoning": "x" * 100,
        "estimated_salary": "120k EUR",
        "effort_flag": "medium",
        "prep_level": "moderate",
        "prep_notes": "Study distributed systems.",
        "readiness_score": 72.0,
        "career_alignment": 8.0,
        "score_breakdown": [
            {"factor": "Technical", "contribution": 2.0, "description": "Strong match"},
            {"factor": "Culture", "contribution": 1.5, "description": "Good alignment"},
            {"factor": "Location", "contribution": -0.5, "description": "Remote preference"},
        ],
    }
)


# ---------------------------------------------------------------------------
# Helper: mock httpx response
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, json_data: dict, headers: dict | None = None):
    """Create a mock httpx.Response."""
    return httpx.Response(
        status_code,
        json=json_data,
        headers=headers or {},
        request=httpx.Request("POST", ANTHROPIC_BATCH_API_URL),
    )


# ---------------------------------------------------------------------------
# AnthropicProvider.batch_score() tests
# ---------------------------------------------------------------------------


class TestBatchScore:
    """Test batch_score() builds correct payload and submits to Batch API."""

    @pytest.mark.asyncio
    async def test_builds_correct_request_payload(self) -> None:
        """batch_score() builds one request per job with correct structure."""
        provider = AnthropicProvider(api_key=_TEST_KEY)
        captured_payload: dict = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json or {})
            return _mock_response(200, {"id": "batch_abc123"})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.batch_score(_SAMPLE_JOBS, _SAMPLE_PROFILE)

        assert "requests" in captured_payload
        requests = captured_payload["requests"]
        assert len(requests) == 3

        # Check first request structure
        req = requests[0]
        assert req["custom_id"] == "job-1"
        assert req["params"]["model"] == provider._model
        assert req["params"]["max_tokens"] == 4096
        assert len(req["params"]["messages"]) == 1
        assert req["params"]["messages"][0]["role"] == "user"
        assert "Software Engineer at Acme Corp" in req["params"]["messages"][0]["content"]
        # Profile data is in the cached system block, not the user message
        system_text = req["params"]["system"][0]["text"]
        assert "Jane Doe" in system_text

    @pytest.mark.asyncio
    async def test_sends_to_batch_api_endpoint(self) -> None:
        """batch_score() POSTs to the correct Batch API URL."""
        provider = AnthropicProvider(api_key=_TEST_KEY)
        captured_url = ""
        captured_headers: dict = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            nonlocal captured_url
            captured_url = url
            captured_headers.update(headers or {})
            return _mock_response(200, {"id": "batch_xyz"})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.batch_score(_SAMPLE_JOBS, _SAMPLE_PROFILE)

        assert captured_url == ANTHROPIC_BATCH_API_URL
        assert captured_headers["x-api-key"] == _TEST_KEY
        assert captured_headers["anthropic-version"] == ANTHROPIC_VERSION

    @pytest.mark.asyncio
    async def test_returns_batch_id(self) -> None:
        """batch_score() returns the batch ID from the API response."""
        provider = AnthropicProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return _mock_response(200, {"id": "batch_return_test"})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            batch_id = await provider.batch_score(_SAMPLE_JOBS, _SAMPLE_PROFILE)

        assert batch_id == "batch_return_test"

    @pytest.mark.asyncio
    async def test_includes_system_blocks_with_cache_control(self) -> None:
        """batch_score() includes system prompt with cache_control in each request."""
        provider = AnthropicProvider(api_key=_TEST_KEY)
        captured_payload: dict = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json or {})
            return _mock_response(200, {"id": "batch_sys"})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.batch_score(_SAMPLE_JOBS, _SAMPLE_PROFILE)

        # Score feature has a system prompt — verify it's in params
        req = captured_payload["requests"][0]
        assert "system" in req["params"]
        system_blocks = req["params"]["system"]
        assert len(system_blocks) == 1
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_402_raises_provider_quota_error(self) -> None:
        """batch_score() raises ProviderQuotaError on HTTP 402."""
        from career_os.ai.base import ProviderQuotaError

        provider = AnthropicProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return _mock_response(
                402,
                {"error": {"message": "Insufficient credits"}},
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.batch_score(_SAMPLE_JOBS, _SAMPLE_PROFILE)
            assert exc_info.value.status_code == 402

    @pytest.mark.asyncio
    async def test_converts_job_ids_to_strings(self) -> None:
        """batch_score() converts integer job IDs to strings for custom_id."""
        provider = AnthropicProvider(api_key=_TEST_KEY)
        captured_payload: dict = {}

        jobs_with_int_ids = [
            {"id": 42, "description": "Engineer"},
            {"id": 99, "description": "Manager"},
        ]

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json or {})
            return _mock_response(200, {"id": "batch_int"})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.batch_score(jobs_with_int_ids, _SAMPLE_PROFILE)

        custom_ids = [r["custom_id"] for r in captured_payload["requests"]]
        assert custom_ids == ["42", "99"]


# ---------------------------------------------------------------------------
# AnthropicProvider.get_batch_results() tests
# ---------------------------------------------------------------------------


class TestGetBatchResults:
    """Test get_batch_results() polling and result parsing."""

    @pytest.mark.asyncio
    async def test_in_progress_status(self) -> None:
        """get_batch_results() returns status without results when in_progress."""
        provider = AnthropicProvider(api_key=_TEST_KEY)

        async def mock_get(url, headers=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "id": "batch_poll",
                    "processing_status": "in_progress",
                    "request_counts": {"processing": 3, "succeeded": 0, "errored": 0},
                },
                request=httpx.Request("GET", url),
            )

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await provider.get_batch_results("batch_poll")

        assert result["status"] == "in_progress"
        assert result["results"] == {}

    @pytest.mark.asyncio
    async def test_parses_completed_results(self) -> None:
        """get_batch_results() parses JSONL results into AIResponse objects."""
        provider = AnthropicProvider(api_key=_TEST_KEY)

        jsonl_lines = "\n".join(
            [
                json.dumps(
                    {
                        "custom_id": "job-1",
                        "result": {
                            "type": "succeeded",
                            "message": {
                                "content": [{"type": "text", "text": _SCORE_JSON}],
                                "model": "claude-sonnet-4-20250514",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "custom_id": "job-2",
                        "result": {
                            "type": "succeeded",
                            "message": {
                                "content": [{"type": "text", "text": _SCORE_JSON}],
                                "model": "claude-sonnet-4-20250514",
                            },
                        },
                    }
                ),
            ]
        )

        call_count = 0

        async def mock_get(url, headers=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: batch status
                return httpx.Response(
                    200,
                    json={
                        "id": "batch_done",
                        "processing_status": "ended",
                        "results_url": "https://api.anthropic.com/results/batch_done",
                    },
                    request=httpx.Request("GET", url),
                )
            else:
                # Second call: JSONL results
                return httpx.Response(
                    200,
                    text=jsonl_lines,
                    request=httpx.Request("GET", url),
                )

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await provider.get_batch_results("batch_done")

        assert result["status"] == "ended"
        assert len(result["results"]) == 2
        assert "job-1" in result["results"]
        assert "job-2" in result["results"]

        # Check parsed AIResponse
        resp = result["results"]["job-1"]
        assert isinstance(resp, AIResponse)
        assert resp.provider == "anthropic"
        assert resp.feature == AIFeature.score
        assert resp.structured is not None
        assert isinstance(resp.structured, ScoreResult)
        assert resp.structured.fit_score == 7.5

    @pytest.mark.asyncio
    async def test_skips_failed_results(self) -> None:
        """get_batch_results() skips results with type != 'succeeded'."""
        provider = AnthropicProvider(api_key=_TEST_KEY)

        jsonl_lines = "\n".join(
            [
                json.dumps(
                    {
                        "custom_id": "job-ok",
                        "result": {
                            "type": "succeeded",
                            "message": {
                                "content": [{"type": "text", "text": _SCORE_JSON}],
                                "model": "claude-sonnet-4-20250514",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "custom_id": "job-fail",
                        "result": {
                            "type": "errored",
                            "error": {"message": "Internal error"},
                        },
                    }
                ),
            ]
        )

        call_count = 0

        async def mock_get(url, headers=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "id": "batch_partial",
                        "processing_status": "ended",
                        "results_url": "https://api.anthropic.com/results/batch_partial",
                    },
                    request=httpx.Request("GET", url),
                )
            else:
                return httpx.Response(
                    200,
                    text=jsonl_lines,
                    request=httpx.Request("GET", url),
                )

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await provider.get_batch_results("batch_partial")

        assert len(result["results"]) == 1
        assert "job-ok" in result["results"]
        assert "job-fail" not in result["results"]


# ---------------------------------------------------------------------------
# Base AIProvider — NotImplementedError tests
# ---------------------------------------------------------------------------


class TestBaseProviderBatchMethods:
    """Test that base AIProvider raises NotImplementedError for batch methods."""

    @pytest.mark.asyncio
    async def test_batch_score_raises_not_implemented(self) -> None:
        """Base AIProvider.batch_score() raises NotImplementedError."""

        class MinimalProvider(AIProvider):
            @property
            def name(self) -> str:
                return "minimal"

            async def complete(self, prompt, *, feature=AIFeature.complete, **kwargs):
                return AIResponse(content="ok", provider="minimal", feature=feature)

            async def score(self, job_description, profile_data, **kwargs):
                return AIResponse(content="ok", provider="minimal", feature=AIFeature.score)

        provider = MinimalProvider()
        with pytest.raises(NotImplementedError, match="minimal.*batch scoring"):
            await provider.batch_score([], {})

    @pytest.mark.asyncio
    async def test_get_batch_results_raises_not_implemented(self) -> None:
        """Base AIProvider.get_batch_results() raises NotImplementedError."""

        class MinimalProvider(AIProvider):
            @property
            def name(self) -> str:
                return "minimal"

            async def complete(self, prompt, *, feature=AIFeature.complete, **kwargs):
                return AIResponse(content="ok", provider="minimal", feature=feature)

            async def score(self, job_description, profile_data, **kwargs):
                return AIResponse(content="ok", provider="minimal", feature=AIFeature.score)

        provider = MinimalProvider()
        with pytest.raises(NotImplementedError, match="minimal.*batch results"):
            await provider.get_batch_results("batch_123")


# ---------------------------------------------------------------------------
# Discovery service — batch vs sequential routing tests
# ---------------------------------------------------------------------------


class TestDiscoveryBatchRouting:
    """Test that discovery service routes to batch or sequential scoring."""

    @pytest.mark.asyncio
    async def test_batch_used_above_threshold(self) -> None:
        """_try_batch_score() is called when job count exceeds threshold."""
        from career_os.services.discovery import _try_batch_score

        # Create mock discovered jobs above threshold
        mock_jobs = []
        for i in range(BATCH_SCORING_THRESHOLD + 5):
            job = MagicMock()
            job.id = i
            job.title = f"Job {i}"
            job.company = f"Company {i}"
            job.location = "Berlin"
            job.description = f"Description for job {i}"
            mock_jobs.append(job)

        mock_provider = MagicMock()
        mock_provider.name = "anthropic"
        mock_provider.batch_score = AsyncMock(return_value="batch_threshold_test")

        with patch(
            "career_os.ai.factory.get_ai_provider",
            return_value=mock_provider,
        ):
            batch_id = await _try_batch_score(mock_jobs, _SAMPLE_PROFILE)

        assert batch_id == "batch_threshold_test"
        mock_provider.batch_score.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_skipped_for_non_anthropic_provider(self) -> None:
        """_try_batch_score() returns None for non-Anthropic providers."""
        from career_os.services.discovery import _try_batch_score

        mock_jobs = [MagicMock() for _ in range(20)]

        mock_provider = MagicMock()
        mock_provider.name = "openrouter"

        with patch(
            "career_os.ai.factory.get_ai_provider",
            return_value=mock_provider,
        ):
            batch_id = await _try_batch_score(mock_jobs, _SAMPLE_PROFILE)

        assert batch_id is None

    @pytest.mark.asyncio
    async def test_batch_fallback_on_submission_error(self) -> None:
        """_try_batch_score() returns None when batch submission fails."""
        from career_os.services.discovery import _try_batch_score

        mock_jobs = []
        for i in range(15):
            job = MagicMock()
            job.id = i
            job.title = f"Job {i}"
            job.company = f"Company {i}"
            job.location = "Berlin"
            job.description = f"Description {i}"
            mock_jobs.append(job)

        mock_provider = MagicMock()
        mock_provider.name = "anthropic"
        mock_provider.batch_score = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=httpx.Request("POST", ANTHROPIC_BATCH_API_URL),
                response=httpx.Response(500),
            )
        )

        with patch(
            "career_os.ai.factory.get_ai_provider",
            return_value=mock_provider,
        ):
            batch_id = await _try_batch_score(mock_jobs, _SAMPLE_PROFILE)

        assert batch_id is None

    @pytest.mark.asyncio
    async def test_auto_score_uses_batch_above_threshold(self) -> None:
        """_auto_score_and_refresh() uses batch scoring for large sweeps."""
        from career_os.services.discovery import _auto_score_and_refresh

        mock_jobs = []
        for i in range(BATCH_SCORING_THRESHOLD + 5):
            job = MagicMock()
            job.id = i
            job.title = f"Job {i}"
            job.company = f"Company {i}"
            job.location = "Berlin"
            job.description = f"Description {i}"
            mock_jobs.append(job)

        mock_profile = MagicMock()
        mock_profile.name = "Jane"
        mock_profile.location = "Berlin"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile

        warnings: list = []

        with patch(
            "career_os.services.discovery._try_batch_score",
            new_callable=AsyncMock,
            return_value="batch_auto",
        ) as mock_batch:
            await _auto_score_and_refresh(mock_db, 1, mock_jobs, warnings)

        mock_batch.assert_called_once()
        # Should have a batch_scoring warning entry
        batch_warnings = [w for w in warnings if w.get("source") == "batch_scoring"]
        assert len(batch_warnings) == 1
        assert batch_warnings[0]["batch_id"] == "batch_auto"

    @pytest.mark.asyncio
    async def test_auto_score_sequential_below_threshold(self) -> None:
        """_auto_score_and_refresh() uses sequential scoring below threshold."""
        from career_os.services.discovery import _auto_score_and_refresh

        mock_jobs = []
        for i in range(BATCH_SCORING_THRESHOLD - 2):
            job = MagicMock()
            job.id = i
            mock_jobs.append(job)

        warnings: list = []

        with (
            patch(
                "career_os.services.discovery._try_batch_score",
                new_callable=AsyncMock,
            ) as mock_batch,
            patch(
                "career_os.services.scoring.batch_score_discovery",
                new_callable=AsyncMock,
            ) as mock_sequential,
            patch(
                "career_os.services.discovery.propagate_discovery_scores",
                return_value=0,
            ),
            patch(
                "career_os.services.market.refresh_market_data",
            ),
        ):
            await _auto_score_and_refresh(MagicMock(), 1, mock_jobs, warnings)

        # Batch should NOT be called (below threshold)
        mock_batch.assert_not_called()
        # Sequential scoring should be called
        mock_sequential.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_score_falls_back_when_batch_fails(self) -> None:
        """_auto_score_and_refresh() falls back to sequential if batch returns None."""
        from career_os.services.discovery import _auto_score_and_refresh

        mock_jobs = []
        for i in range(BATCH_SCORING_THRESHOLD + 5):
            job = MagicMock()
            job.id = i
            mock_jobs.append(job)

        mock_profile = MagicMock()
        mock_profile.name = "Jane"
        mock_profile.location = "Berlin"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile

        warnings: list = []

        with (
            patch(
                "career_os.services.discovery._try_batch_score",
                new_callable=AsyncMock,
                return_value=None,  # batch failed
            ),
            patch(
                "career_os.services.scoring.batch_score_discovery",
                new_callable=AsyncMock,
            ) as mock_sequential,
            patch(
                "career_os.services.discovery.propagate_discovery_scores",
                return_value=0,
            ),
            patch(
                "career_os.services.market.refresh_market_data",
            ),
        ):
            await _auto_score_and_refresh(mock_db, 1, mock_jobs, warnings)

        # Sequential should be called as fallback
        mock_sequential.assert_called_once()


# ---------------------------------------------------------------------------
# BATCH_SCORING_THRESHOLD constant test
# ---------------------------------------------------------------------------


class TestBatchScoringThreshold:
    """Test the batch scoring threshold constant."""

    def test_threshold_is_positive_integer(self) -> None:
        """BATCH_SCORING_THRESHOLD is a positive integer."""
        assert isinstance(BATCH_SCORING_THRESHOLD, int)
        assert BATCH_SCORING_THRESHOLD > 0

    def test_threshold_default_value(self) -> None:
        """BATCH_SCORING_THRESHOLD defaults to 10."""
        assert BATCH_SCORING_THRESHOLD == 10
