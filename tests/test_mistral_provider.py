"""Tests for MistralProvider — Mistral AI OpenAI-compatible API.

Covers:
- Provider contract (AIProvider subclass, name, privacy tier, init validation)
- Factory registration and resolution
- OpenAI-compatible request format (Bearer auth, messages array)
- HTTP 402/429 → ProviderQuotaError
- HTTP 401 → httpx.HTTPStatusError
- Response parsing (choices[0].message.content)
- System prompt inclusion for structured features
- score() delegation to complete()
"""

import json
import os
from unittest.mock import patch

import httpx
import pytest

from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.factory import _PROVIDER_REGISTRY, get_ai_provider
from career_os.ai.mistral_provider import (
    MISTRAL_API_URL,
    MistralProvider,
)
from career_os.schemas.ai import AIFeature, AIResponse

# Fake credentials used across all tests — not real.
_TEST_CREDENTIAL = "test-fake-mistral-key"  # noqa: S105
_TEST_CREDENTIAL_2 = "test-fake-mistral-key-2"  # noqa: S105


# ---------------------------------------------------------------------------
# MistralProvider unit tests
# ---------------------------------------------------------------------------


class TestMistralProviderInit:
    """Test MistralProvider initialization and contract."""

    def test_name(self) -> None:
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        assert provider.name == "mistral"

    def test_is_ai_provider(self) -> None:
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        assert isinstance(provider, AIProvider)

    def test_privacy_tier_is_green(self) -> None:
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        assert provider.privacy_tier == "green"

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
            MistralProvider(api_key="")

    def test_default_model(self) -> None:
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        assert provider._model == "mistral-large-latest"

    def test_custom_model(self) -> None:
        provider = MistralProvider(api_key=_TEST_CREDENTIAL, model="mistral-small-latest")
        assert provider._model == "mistral-small-latest"


# ---------------------------------------------------------------------------
# Factory registration tests
# ---------------------------------------------------------------------------


class TestMistralFactoryRegistration:
    """Test Mistral provider is registered in the factory."""

    def test_mistral_in_registry(self) -> None:
        """'mistral' key exists in _PROVIDER_REGISTRY."""
        assert "mistral" in _PROVIDER_REGISTRY

    def test_registry_entry_callable(self) -> None:
        """Registry entry for mistral is callable."""
        assert callable(_PROVIDER_REGISTRY["mistral"])

    def test_factory_creates_mistral_provider(self) -> None:
        """get_ai_provider('mistral') returns MistralProvider."""
        with patch.dict(os.environ, {"MISTRAL_API_KEY": _TEST_CREDENTIAL}):
            provider = get_ai_provider("mistral")
            assert isinstance(provider, MistralProvider)
            assert provider.name == "mistral"

    def test_factory_without_key_raises(self) -> None:
        """get_ai_provider('mistral') without API key raises ValueError."""
        with patch.dict(os.environ, {"MISTRAL_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
                get_ai_provider("mistral")

    def test_mistral_in_unsupported_error_message(self) -> None:
        """UnsupportedProviderError lists mistral as a supported provider."""
        from career_os.ai.factory import UnsupportedProviderError

        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_ai_provider("nonexistent")
        assert "mistral" in str(exc_info.value)


# ---------------------------------------------------------------------------
# API request format tests
# ---------------------------------------------------------------------------


class TestMistralRequestFormat:
    """Test the Mistral API request format (OpenAI-compatible)."""

    @pytest.mark.asyncio
    async def test_headers_include_bearer_auth(self) -> None:
        """Request headers include Authorization: Bearer."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL_2)
        captured_headers = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_headers["Authorization"] == f"Bearer {_TEST_CREDENTIAL_2}"
        assert captured_headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_sent_to_mistral_url(self) -> None:
        """Request is sent to the Mistral AI API URL."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        captured_url = None

        async def mock_post(url, headers=None, json=None, **kwargs):
            nonlocal captured_url
            captured_url = url
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_url == MISTRAL_API_URL

    @pytest.mark.asyncio
    async def test_payload_uses_openai_chat_format(self) -> None:
        """Payload uses OpenAI chat completions format."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "result"}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello world")

        assert captured_payload["model"] == "mistral-large-latest"
        assert captured_payload["messages"] == [{"role": "user", "content": "hello world"}]

    @pytest.mark.asyncio
    async def test_system_message_for_structured_feature(self) -> None:
        """Structured features include a system message."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test", feature=AIFeature.score)

        messages = captured_payload["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_no_system_message_for_generic_complete(self) -> None:
        """Generic complete (no feature) does not include system message."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello", feature=AIFeature.complete)

        messages = captured_payload["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# Response parsing tests
# ---------------------------------------------------------------------------


class TestMistralResponseParsing:
    """Test response parsing from OpenAI-format responses."""

    @pytest.mark.asyncio
    async def test_parses_content_from_choices(self) -> None:
        """Response correctly parses content from choices[0].message.content."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Hello world"}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("greet me")

        assert isinstance(result, AIResponse)
        assert result.content == "Hello world"
        assert result.provider == "mistral"
        assert result.model == "mistral-large-latest"

    @pytest.mark.asyncio
    async def test_uses_model_from_response(self) -> None:
        """Model field uses the model returned in the API response."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "model": "mistral-large-2407",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.model == "mistral-large-2407"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestMistralErrorHandling:
    """Test HTTP error handling (401, 402, 429, 500)."""

    @pytest.mark.asyncio
    async def test_402_raises_provider_quota_error(self) -> None:
        """HTTP 402 raises ProviderQuotaError."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                402,
                json={"error": {"message": "Insufficient credits"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.complete("test")
            assert exc_info.value.status_code == 402
            assert exc_info.value.provider == "mistral"

    @pytest.mark.asyncio
    async def test_429_raises_provider_quota_error(self) -> None:
        """HTTP 429 raises ProviderQuotaError."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                429,
                json={"error": {"message": "Rate limited"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.complete("test")
            assert exc_info.value.status_code == 429
            assert exc_info.value.provider == "mistral"

    @pytest.mark.asyncio
    async def test_401_raises_http_error(self) -> None:
        """HTTP 401 raises httpx.HTTPStatusError (auth failure)."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                401,
                json={"error": {"message": "Unauthorized"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_500_raises_http_error(self) -> None:
        """HTTP 500 raises httpx.HTTPStatusError (not ProviderQuotaError)."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                500,
                json={"error": {"message": "Internal error"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete("test")


# ---------------------------------------------------------------------------
# Score method tests
# ---------------------------------------------------------------------------


class TestMistralScore:
    """Test the score() method delegates to complete() correctly."""

    @pytest.mark.asyncio
    async def test_score_calls_complete_with_score_feature(self) -> None:
        """score() calls complete() with AIFeature.score."""
        provider = MistralProvider(api_key=_TEST_CREDENTIAL)
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

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": score_json}}],
                    "model": "mistral-large-latest",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.score("Software Engineer at Acme", {"name": "Jane"})

        assert result.feature == AIFeature.score
        assert result.provider == "mistral"
        # System message should be present (score feature has system prompt)
        messages = captured_payload["messages"]
        assert messages[0]["role"] == "system"
