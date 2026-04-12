"""Tests for AnthropicProvider — Anthropic Messages API with prompt caching.

Covers:
- Provider contract (AIProvider subclass, name, init validation)
- Factory registration and resolution
- Prompt caching: cache_control in system message blocks
- HTTP 402 → CreditsExhaustedError
- HTTP 429 → CreditsExhaustedError with retry-after
- Anthropic Messages API response format parsing (content blocks)
- System prompt inclusion for structured features
"""

import json
import os
from unittest.mock import patch

import httpx
import pytest

from career_os.ai.anthropic_provider import (
    ANTHROPIC_VERSION,
    AnthropicProvider,
)
from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.factory import _PROVIDER_REGISTRY, get_ai_provider
from career_os.schemas.ai import AIFeature, AIResponse

# ---------------------------------------------------------------------------
# AnthropicProvider unit tests
# ---------------------------------------------------------------------------


class TestAnthropicProviderInit:
    """Test AnthropicProvider initialization and contract."""

    def test_name(self) -> None:
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
        assert provider.name == "anthropic"

    def test_is_ai_provider(self) -> None:
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
        assert isinstance(provider, AIProvider)

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider(api_key="")

    def test_default_model(self) -> None:
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
        assert provider._model == "claude-sonnet-4-20250514"

    def test_custom_model(self) -> None:
        provider = AnthropicProvider(
            api_key="test-fake-anthropic-key", model="claude-opus-4-20250514"
        )
        assert provider._model == "claude-opus-4-20250514"


# ---------------------------------------------------------------------------
# Factory registration tests
# ---------------------------------------------------------------------------


class TestAnthropicFactoryRegistration:
    """Test Anthropic provider is registered in the factory."""

    def test_anthropic_in_registry(self) -> None:
        """'anthropic' key exists in _PROVIDER_REGISTRY."""
        assert "anthropic" in _PROVIDER_REGISTRY

    def test_registry_entry_callable(self) -> None:
        """Registry entry for anthropic is callable."""
        assert callable(_PROVIDER_REGISTRY["anthropic"])

    def test_factory_creates_anthropic_provider(self) -> None:
        """get_ai_provider('anthropic') returns AnthropicProvider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-fake-anthropic-key-3"}):
            provider = get_ai_provider("anthropic")
            assert isinstance(provider, AnthropicProvider)
            assert provider.name == "anthropic"

    def test_factory_without_key_raises(self) -> None:
        """get_ai_provider('anthropic') without API key raises ValueError."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                get_ai_provider("anthropic")

    def test_anthropic_in_unsupported_error_message(self) -> None:
        """UnsupportedProviderError lists anthropic as a supported provider."""
        from career_os.ai.factory import UnsupportedProviderError

        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_ai_provider("nonexistent")
        assert "anthropic" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Prompt caching tests
# ---------------------------------------------------------------------------


class TestPromptCaching:
    """Test that cache_control is applied to system message blocks."""

    @pytest.mark.asyncio
    async def test_cache_control_in_system_block(self) -> None:
        """System message blocks include cache_control for prompt caching."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            mock_resp = httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "test response"}],
                    "model": "claude-sonnet-4-20250514",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
                request=httpx.Request("POST", url),
            )
            return mock_resp

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test prompt", feature=AIFeature.score)

        # Verify system blocks have cache_control
        assert "system" in captured_payload
        system_blocks = captured_payload["system"]
        assert len(system_blocks) == 1
        assert system_blocks[0]["type"] == "text"
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_no_system_block_for_generic_complete(self) -> None:
        """Generic complete (no feature) does not include system blocks."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            mock_resp = httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "hello"}],
                    "model": "claude-sonnet-4-20250514",
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                },
                request=httpx.Request("POST", url),
            )
            return mock_resp

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello", feature=AIFeature.complete)

        # No system key when feature is 'complete' (unstructured)
        assert "system" not in captured_payload


# ---------------------------------------------------------------------------
# API request format tests
# ---------------------------------------------------------------------------


class TestAnthropicRequestFormat:
    """Test the Anthropic Messages API request format."""

    @pytest.mark.asyncio
    async def test_headers_include_api_key_and_version(self) -> None:
        """Request headers include x-api-key and anthropic-version."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key-2")
        captured_headers = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "model": "claude-sonnet-4-20250514",
                    "usage": {"input_tokens": 5, "output_tokens": 2},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_headers["x-api-key"] == "test-fake-anthropic-key-2"
        assert captured_headers["anthropic-version"] == ANTHROPIC_VERSION

    @pytest.mark.asyncio
    async def test_payload_uses_messages_api_format(self) -> None:
        """Payload uses Anthropic Messages API format (not OpenAI chat format)."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "result"}],
                    "model": "claude-sonnet-4-20250514",
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello world")

        assert captured_payload["model"] == "claude-sonnet-4-20250514"
        assert captured_payload["max_tokens"] == 4096
        assert captured_payload["messages"] == [{"role": "user", "content": "hello world"}]

    @pytest.mark.asyncio
    async def test_response_parses_content_blocks(self) -> None:
        """Response correctly parses Anthropic content blocks format."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "world"},
                    ],
                    "model": "claude-sonnet-4-20250514",
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("greet me")

        assert isinstance(result, AIResponse)
        assert result.content == "Hello world"
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestAnthropicErrorHandling:
    """Test HTTP error handling (402, 429, etc.)."""

    @pytest.mark.asyncio
    async def test_402_raises_provider_quota_error(self) -> None:
        """HTTP 402 raises ProviderQuotaError."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                402,
                json={
                    "error": {"type": "invalid_request_error", "message": "Insufficient credits"}
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.complete("test")
            assert exc_info.value.status_code == 402
            assert exc_info.value.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_429_raises_provider_quota_error(self) -> None:
        """HTTP 429 raises ProviderQuotaError with rate limit info."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                429,
                json={"error": {"type": "rate_limit_error", "message": "Rate limited"}},
                headers={"retry-after": "30"},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError) as exc_info:
                await provider.complete("test")
            assert exc_info.value.status_code == 429
            assert "retry-after" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_500_raises_http_error(self) -> None:
        """HTTP 500 raises httpx.HTTPStatusError (not CreditsExhaustedError)."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                500,
                json={"error": {"type": "api_error", "message": "Internal error"}},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete("test")


# ---------------------------------------------------------------------------
# Score method tests
# ---------------------------------------------------------------------------


class TestAnthropicScore:
    """Test the score() method delegates to complete() correctly."""

    @pytest.mark.asyncio
    async def test_score_calls_complete_with_score_feature(self) -> None:
        """score() calls complete() with AIFeature.score."""
        provider = AnthropicProvider(api_key="test-fake-anthropic-key")
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
                    "content": [{"type": "text", "text": score_json}],
                    "model": "claude-sonnet-4-20250514",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.score("Software Engineer at Acme", {"name": "Jane"})

        assert result.feature == AIFeature.score
        assert result.provider == "anthropic"
        # System blocks should be present (score feature has system prompt)
        assert "system" in captured_payload
