"""Tests for JSON parse robustness and retry logic in AI providers."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from career_os.ai.openrouter_provider import (
    CreditsExhaustedError,
    OpenRouterProvider,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature

VALID_SCORE_JSON = {
    "fit_score": 5.0,
    "reasoning": (
        "Test reasoning that is at least one hundred characters long to pass"
        " validation requirements for the scoring system."
    ),
    "estimated_salary": "$100k",
    "effort_flag": "medium",
    "prep_level": "moderate",
    "prep_notes": "Study up",
    "readiness_score": 65.0,
    "career_alignment": 6.0,
    "score_breakdown": [
        {"factor": "skills", "contribution": 2.0, "description": "Good match"},
        {"factor": "experience", "contribution": 1.5, "description": "Partial"},
        {"factor": "location", "contribution": -0.5, "description": "Remote only"},
    ],
}


# ---------------------------------------------------------------------------
# _try_parse_structured tests
# ---------------------------------------------------------------------------


class TestTryParseStructured:
    """Tests for the _try_parse_structured function."""

    def test_clean_json_parses_correctly(self):
        """Test 1: Clean JSON parses correctly."""
        content = json.dumps(VALID_SCORE_JSON)
        result = _try_parse_structured(content, AIFeature.score)
        assert result is not None
        assert result.fit_score == 5.0

    def test_json_in_markdown_fence(self):
        """Test 2: JSON wrapped in markdown code fences parses correctly."""
        content = "```json\n" + json.dumps(VALID_SCORE_JSON) + "\n```"
        result = _try_parse_structured(content, AIFeature.score)
        assert result is not None
        assert result.fit_score == 5.0

    def test_json_with_trailing_comma(self):
        """Test 3: JSON with trailing commas parses correctly."""
        raw = json.dumps(VALID_SCORE_JSON)
        # Insert a trailing comma before the last }
        raw = raw[:-1] + ",}"
        result = _try_parse_structured(raw, AIFeature.score)
        assert result is not None
        assert result.fit_score == 5.0

    def test_json_embedded_in_text(self):
        """Test 4: JSON embedded in explanatory text is extracted and parsed."""
        content = (
            "Here is the result: "
            + json.dumps(VALID_SCORE_JSON)
            + " Let me know if you need anything else."
        )
        result = _try_parse_structured(content, AIFeature.score)
        assert result is not None
        assert result.fit_score == 5.0

    def test_completely_invalid_content_returns_none(self):
        """Test 5: Completely invalid content returns None."""
        result = _try_parse_structured("I cannot score this", AIFeature.score)
        assert result is None

    def test_truncated_json_returns_none(self):
        """Test 6: Truncated JSON returns None without crashing."""
        content = '{"fit_score": 5.0, "reasoning": "tes'
        result = _try_parse_structured(content, AIFeature.score)
        assert result is None

    def test_complete_feature_returns_none(self):
        """complete feature always returns None (unstructured)."""
        content = json.dumps(VALID_SCORE_JSON)
        result = _try_parse_structured(content, AIFeature.complete)
        assert result is None


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------


def _make_openrouter_response(content: str, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response for OpenRouter."""
    body = {
        "choices": [{"message": {"content": content}}],
        "model": "test-model",
    }
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def _make_error_response(status_code: int) -> httpx.Response:
    """Build a fake error httpx.Response."""
    body = {"error": {"message": "quota exceeded"}}
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


class TestRetryLogic:
    """Tests for retry logic in OpenRouterProvider.complete()."""

    @pytest.mark.asyncio
    async def test_retry_returns_valid_on_second_attempt(self):
        """Test 7: Bad JSON first, good JSON second -> valid AIResponse."""
        bad_response = _make_openrouter_response("Not valid JSON at all")
        good_response = _make_openrouter_response(json.dumps(VALID_SCORE_JSON))

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[bad_response, good_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        provider = OpenRouterProvider(api_key="test-key")

        with patch("career_os.ai.openrouter_provider.httpx.AsyncClient", return_value=mock_client):
            result = await provider.complete("Score this", feature=AIFeature.score)

        assert result.structured is not None
        assert result.structured.fit_score == 5.0
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_returns_none_structured(self):
        """Test 8: Bad JSON on all attempts -> structured is None, no crash."""
        bad_response = _make_openrouter_response("I cannot produce JSON")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=bad_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        provider = OpenRouterProvider(api_key="test-key")

        with patch("career_os.ai.openrouter_provider.httpx.AsyncClient", return_value=mock_client):
            result = await provider.complete("Score this", feature=AIFeature.score)

        assert result.structured is None
        assert result.content == "I cannot produce JSON"
        assert mock_client.post.call_count == 2  # initial + 1 retry

    @pytest.mark.asyncio
    async def test_credits_exhausted_raises_immediately(self):
        """Test 9: 402 raises CreditsExhaustedError immediately, no retry."""
        error_response = _make_error_response(402)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        provider = OpenRouterProvider(api_key="test-key")

        with patch("career_os.ai.openrouter_provider.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(CreditsExhaustedError):
                await provider.complete("Score this", feature=AIFeature.score)

        assert mock_client.post.call_count == 1  # no retry
