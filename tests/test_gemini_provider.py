"""Tests for GeminiProvider — Google Gemini REST API.

Covers:
- Provider contract (AIProvider subclass, name, privacy tier, init validation)
- Factory registration and resolution
- Gemini-specific request format (API key as query param, contents/systemInstruction)
- HTTP 429 → ProviderQuotaError
- Response parsing (candidates[0].content.parts[0].text)
- Token usage from usageMetadata
- System instruction inclusion for structured features
- score() delegation to complete()
"""

import json
import os
from unittest.mock import patch

import httpx
import pytest

from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.factory import _PROVIDER_REGISTRY, get_ai_provider
from career_os.ai.gemini_provider import (
    GEMINI_API_BASE,
    GeminiProvider,
)
from career_os.schemas.ai import AIFeature, AIResponse

# Fake credentials used across all tests — not real.
_TEST_CREDENTIAL = "test-fake-gemini-key"  # noqa: S105
_TEST_CREDENTIAL_2 = "test-fake-gemini-key-2"  # noqa: S105


def _gemini_response(content: str = "ok", model: str = "gemini-2.0-flash") -> dict:
    """Build a minimal Gemini generateContent response."""
    return {
        "candidates": [{"content": {"parts": [{"text": content}]}}],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
        },
        "modelVersion": model,
    }


# ---------------------------------------------------------------------------
# GeminiProvider unit tests
# ---------------------------------------------------------------------------


class TestGeminiProviderInit:
    """Test GeminiProvider initialization and contract."""

    def test_name(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        assert provider.name == "gemini"

    def test_is_ai_provider(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        assert isinstance(provider, AIProvider)

    def test_privacy_tier_is_yellow(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        assert provider.privacy_tier == "yellow"

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiProvider(api_key="")

    def test_default_model(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        assert provider._model == "gemini-2.0-flash"

    def test_custom_model(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL, model="gemini-2.5-pro")
        assert provider._model == "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Factory registration tests
# ---------------------------------------------------------------------------


class TestGeminiFactoryRegistration:
    """Test Gemini provider is registered in the factory."""

    def test_gemini_in_registry(self) -> None:
        """'gemini' key exists in _PROVIDER_REGISTRY."""
        assert "gemini" in _PROVIDER_REGISTRY

    def test_registry_entry_callable(self) -> None:
        """Registry entry for gemini is callable."""
        assert callable(_PROVIDER_REGISTRY["gemini"])

    def test_factory_creates_gemini_provider(self) -> None:
        """get_ai_provider('gemini') returns GeminiProvider."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": _TEST_CREDENTIAL}):
            provider = get_ai_provider("gemini")
            assert isinstance(provider, GeminiProvider)
            assert provider.name == "gemini"

    def test_factory_without_key_raises(self) -> None:
        """get_ai_provider('gemini') without API key raises ValueError."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                get_ai_provider("gemini")

    def test_gemini_in_unsupported_error_message(self) -> None:
        """UnsupportedProviderError lists gemini as a supported provider."""
        from career_os.ai.factory import UnsupportedProviderError

        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_ai_provider("nonexistent")
        assert "gemini" in str(exc_info.value)


# ---------------------------------------------------------------------------
# API request format tests
# ---------------------------------------------------------------------------


class TestGeminiRequestFormat:
    """Test the Gemini API request format (Google-native, NOT OpenAI)."""

    @pytest.mark.asyncio
    async def test_api_key_sent_as_query_param(self) -> None:
        """API key is sent as ?key= query parameter, not in headers."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL_2)
        captured_params = {}

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            captured_params.update(params or {})
            return httpx.Response(
                200,
                json=_gemini_response(),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_params["key"] == _TEST_CREDENTIAL_2

    @pytest.mark.asyncio
    async def test_request_sent_to_gemini_url(self) -> None:
        """Request is sent to the Gemini generateContent URL."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        captured_url = None

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            nonlocal captured_url
            captured_url = url
            return httpx.Response(
                200,
                json=_gemini_response(),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        expected_url = f"{GEMINI_API_BASE}/gemini-2.0-flash:generateContent"
        assert captured_url == expected_url

    @pytest.mark.asyncio
    async def test_payload_uses_gemini_contents_format(self) -> None:
        """Payload uses Gemini contents format (not OpenAI messages)."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json=_gemini_response(),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello world")

        assert captured_payload["contents"] == [{"parts": [{"text": "hello world"}]}]
        assert "messages" not in captured_payload  # NOT OpenAI format

    @pytest.mark.asyncio
    async def test_system_instruction_for_structured_feature(self) -> None:
        """Structured features include systemInstruction."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json=_gemini_response("{}"),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test", feature=AIFeature.score)

        assert "systemInstruction" in captured_payload
        assert "parts" in captured_payload["systemInstruction"]
        assert len(captured_payload["systemInstruction"]["parts"]) == 1

    @pytest.mark.asyncio
    async def test_no_system_instruction_for_generic_complete(self) -> None:
        """Generic complete (no feature) does not include systemInstruction."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json=_gemini_response(),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello", feature=AIFeature.complete)

        assert "systemInstruction" not in captured_payload


# ---------------------------------------------------------------------------
# Response parsing tests
# ---------------------------------------------------------------------------


class TestGeminiResponseParsing:
    """Test response parsing from Gemini-format responses."""

    @pytest.mark.asyncio
    async def test_parses_content_from_candidates(self) -> None:
        """Response correctly parses content from candidates[0].content.parts[0].text."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json=_gemini_response("Hello world"),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("greet me")

        assert isinstance(result, AIResponse)
        assert result.content == "Hello world"
        assert result.provider == "gemini"
        assert result.model == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_token_usage_from_usage_metadata(self) -> None:
        """Token usage is extracted from usageMetadata."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json=_gemini_response("ok"),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 20

    @pytest.mark.asyncio
    async def test_missing_usage_metadata_defaults_to_zero(self) -> None:
        """Missing usageMetadata defaults to zero tokens."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)

        response_data = {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        }

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json=response_data,
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestGeminiErrorHandling:
    """Test HTTP error handling (429, 500)."""

    @pytest.mark.asyncio
    async def test_429_raises_provider_quota_error(self) -> None:
        """HTTP 429 raises ProviderQuotaError."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            return httpx.Response(
                429,
                json={"error": {"message": "Rate limited"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.complete("test")
            assert exc_info.value.status_code == 429
            assert exc_info.value.provider == "gemini"

    @pytest.mark.asyncio
    async def test_500_raises_provider_unavailable_error(self) -> None:
        """HTTP 500 (and any other non-2xx, non-429) raises
        ProviderUnavailableError, NOT httpx.HTTPStatusError.

        Intentional (G-564): Gemini auth uses ?key=<API_KEY> as a URL query
        param, so httpx.HTTPStatusError.__str__ would embed the URL — and
        the key — into the exception. Persisting that into the digest,
        scored_*.json artifact, or notification email would leak the key.
        Translation to ProviderUnavailableError happens inside the provider
        before the URL ever reaches an exception's string representation.
        """
        from career_os.ai.base import ProviderUnavailableError

        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            return httpx.Response(
                500,
                json={"error": {"message": "Internal error"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderUnavailableError) as exc_info:
                await provider.complete("test")

        assert exc_info.value.status_code == 500
        assert exc_info.value.provider == "gemini"
        # Key marker MUST NOT appear in the exception string.
        assert _TEST_CREDENTIAL not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_429_includes_error_detail(self) -> None:
        """ProviderQuotaError includes error message from response body."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            return httpx.Response(
                429,
                json={"error": {"message": "Quota exceeded for model"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.complete("test")
            assert "Quota exceeded" in str(exc_info.value)
            assert exc_info.value.provider == "gemini"


# ---------------------------------------------------------------------------
# Score method tests
# ---------------------------------------------------------------------------


class TestGeminiScore:
    """Test the score() method delegates to complete() correctly."""

    @pytest.mark.asyncio
    async def test_score_calls_complete_with_score_feature(self) -> None:
        """score() calls complete() with AIFeature.score."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        score_json = json.dumps(
            {
                "fit_score": 7.5,
                "reasoning": "x" * 100,
                "estimated_salary": "120k EUR",
                "effort_flag": "medium",
                "prep_level": "moderate",
                "prep_notes": "Study X.",
                "readiness_score": 72.0,
                "career_alignment": 8.0,
                "score_breakdown": [
                    {"factor": "Technical", "contribution": 2.0, "description": "Strong match"},
                    {"factor": "Culture", "contribution": 1.5, "description": "Good alignment"},
                    {"factor": "Location", "contribution": -0.5, "description": "Remote pref"},
                ],
            }
        )

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json=_gemini_response(score_json),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.score("Software Engineer at Acme", {"name": "Jane"})

        assert result.feature == AIFeature.score
        assert result.provider == "gemini"
        # System instruction should be present (score feature has system prompt)
        assert "systemInstruction" in captured_payload

    @pytest.mark.asyncio
    async def test_score_prompt_contains_job_and_profile(self) -> None:
        """score() prompt includes both job description and profile data."""
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, params=None, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json=_gemini_response("{}"),
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.score("ML Engineer at DeepMind", {"skills": ["Python", "PyTorch"]})

        user_text = captured_payload["contents"][0]["parts"][0]["text"]
        assert "ML Engineer at DeepMind" in user_text
        assert "Python" in user_text


# ---------------------------------------------------------------------------
# URL construction tests
# ---------------------------------------------------------------------------


class TestGeminiUrlConstruction:
    """Test that the generateContent URL is built correctly."""

    def test_default_model_url(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL)
        url = provider._build_url()
        assert url == f"{GEMINI_API_BASE}/gemini-2.0-flash:generateContent"

    def test_custom_model_url(self) -> None:
        provider = GeminiProvider(api_key=_TEST_CREDENTIAL, model="gemini-2.5-pro")
        url = provider._build_url()
        assert url == f"{GEMINI_API_BASE}/gemini-2.5-pro:generateContent"
