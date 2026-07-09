"""Tests for TokenUsage tracking across all AI providers.

Covers:
- TokenUsage schema defaults and construction
- AIResponse with usage field (optional, backwards compatible)
- Anthropic provider extracts usage including cache tokens
- OpenRouter provider maps prompt_tokens/completion_tokens
- Ollama provider maps prompt_eval_count/eval_count
- CachedProvider sets usage=None on cache hits, passes through on misses
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from career_os.ai.anthropic_provider import AnthropicProvider
from career_os.ai.base import AIProvider
from career_os.ai.cache import CachedProvider
from career_os.ai.ollama_provider import OllamaProvider
from career_os.ai.openrouter_provider import OpenRouterProvider
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage

# Fake credentials — not real.
_TEST_KEY = "test-fake-key"  # noqa: S105


# ---------------------------------------------------------------------------
# TokenUsage schema tests
# ---------------------------------------------------------------------------


class TestTokenUsageSchema:
    """Test TokenUsage Pydantic model."""

    def test_defaults_are_zero(self) -> None:
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_creation_input_tokens == 0
        assert usage.cache_read_input_tokens == 0

    def test_custom_values(self) -> None:
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=80,
        )
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_creation_input_tokens == 200
        assert usage.cache_read_input_tokens == 80

    def test_partial_values(self) -> None:
        usage = TokenUsage(input_tokens=42, output_tokens=10)
        assert usage.input_tokens == 42
        assert usage.output_tokens == 10
        assert usage.cache_creation_input_tokens == 0
        assert usage.cache_read_input_tokens == 0

    def test_serialization_roundtrip(self) -> None:
        usage = TokenUsage(input_tokens=10, output_tokens=20)
        data = usage.model_dump()
        restored = TokenUsage.model_validate(data)
        assert restored == usage


# ---------------------------------------------------------------------------
# AIResponse backwards compatibility
# ---------------------------------------------------------------------------


class TestAIResponseUsageField:
    """Test AIResponse.usage is optional and backwards compatible."""

    def test_usage_defaults_to_none(self) -> None:
        resp = AIResponse(content="hi", provider="mock", feature=AIFeature.complete)
        assert resp.usage is None

    def test_usage_can_be_set(self) -> None:
        usage = TokenUsage(input_tokens=10, output_tokens=5)
        resp = AIResponse(content="hi", provider="mock", feature=AIFeature.complete, usage=usage)
        assert resp.usage is not None
        assert resp.usage.input_tokens == 10

    def test_serialization_with_usage(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        resp = AIResponse(content="test", provider="test", feature=AIFeature.complete, usage=usage)
        data = json.loads(resp.model_dump_json())
        assert data["usage"]["input_tokens"] == 100
        assert data["usage"]["output_tokens"] == 50

    def test_serialization_without_usage(self) -> None:
        resp = AIResponse(content="test", provider="test", feature=AIFeature.complete)
        data = json.loads(resp.model_dump_json())
        assert data["usage"] is None

    def test_deserialization_without_usage_key(self) -> None:
        """Old serialized responses without 'usage' key still deserialize."""
        raw = {
            "content": "hello",
            "provider": "mock",
            "feature": "complete",
            "structured": None,
            "model": None,
        }
        resp = AIResponse.model_validate(raw)
        assert resp.usage is None


# ---------------------------------------------------------------------------
# Anthropic provider usage extraction
# ---------------------------------------------------------------------------


class TestAnthropicUsageExtraction:
    """Test AnthropicProvider extracts usage from API response."""

    @pytest.mark.asyncio
    async def test_extracts_full_usage(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "hello"}],
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": 200,
                        "cache_read_input_tokens": 80,
                    },
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 50
        assert result.usage.cache_creation_input_tokens == 200
        assert result.usage.cache_read_input_tokens == 80

    @pytest.mark.asyncio
    async def test_handles_missing_cache_fields(self) -> None:
        """When cache fields are absent, they default to 0."""
        provider = AnthropicProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "hello"}],
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5
        assert result.usage.cache_creation_input_tokens == 0
        assert result.usage.cache_read_input_tokens == 0

    @pytest.mark.asyncio
    async def test_handles_missing_usage_block(self) -> None:
        """When usage block is entirely absent, all fields default to 0."""
        provider = AnthropicProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "hello"}],
                    "model": "claude-sonnet-5",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0


# ---------------------------------------------------------------------------
# OpenRouter provider usage extraction
# ---------------------------------------------------------------------------


class TestOpenRouterUsageExtraction:
    """Test OpenRouterProvider maps OpenAI-format usage fields."""

    @pytest.mark.asyncio
    async def test_extracts_openai_format_usage(self) -> None:
        provider = OpenRouterProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "anthropic/claude-sonnet-5",
                    "usage": {
                        "prompt_tokens": 75,
                        "completion_tokens": 30,
                        "total_tokens": 105,
                    },
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 75
        assert result.usage.output_tokens == 30
        assert result.usage.cache_creation_input_tokens == 0
        assert result.usage.cache_read_input_tokens == 0

    @pytest.mark.asyncio
    async def test_handles_missing_usage(self) -> None:
        provider = OpenRouterProvider(api_key=_TEST_KEY)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "anthropic/claude-sonnet-5",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0


# ---------------------------------------------------------------------------
# Ollama provider usage extraction
# ---------------------------------------------------------------------------


class TestOllamaUsageExtraction:
    """Test OllamaProvider maps Ollama-format usage fields."""

    @pytest.mark.asyncio
    async def test_extracts_openai_compat_usage(self) -> None:
        """Ollama v1 chat endpoint returns OpenAI-format usage."""
        provider = OllamaProvider()
        mock_resp = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "model": "llama3.3",
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 20,
                },
            },
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 40
        assert result.usage.output_tokens == 20

    @pytest.mark.asyncio
    async def test_extracts_native_ollama_usage(self) -> None:
        """Ollama native format uses prompt_eval_count/eval_count."""
        provider = OllamaProvider()
        mock_resp = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "model": "llama3.3",
                "usage": {
                    "prompt_eval_count": 35,
                    "eval_count": 15,
                },
            },
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 35
        assert result.usage.output_tokens == 15

    @pytest.mark.asyncio
    async def test_handles_missing_usage(self) -> None:
        provider = OllamaProvider()
        mock_resp = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "model": "llama3.3",
            },
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await provider.complete("test")

        assert result.usage is not None
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0


# ---------------------------------------------------------------------------
# CachedProvider usage passthrough
# ---------------------------------------------------------------------------


def _make_response_with_usage(
    content: str = "hello",
    feature: AIFeature = AIFeature.complete,
    usage: TokenUsage | None = None,
) -> AIResponse:
    return AIResponse(content=content, provider="mock", feature=feature, usage=usage)


def _mock_provider_with_usage() -> AsyncMock:
    provider = AsyncMock(spec=AIProvider)
    provider.name = "mock"
    usage = TokenUsage(input_tokens=50, output_tokens=25)
    provider.complete.return_value = _make_response_with_usage("result", usage=usage)
    provider.score.return_value = _make_response_with_usage(
        "score-result", AIFeature.score, usage=usage
    )
    return provider


class TestCachedProviderUsage:
    """Test CachedProvider handles usage on hits vs misses."""

    @pytest.fixture()
    def provider(self, tmp_path):
        inner = _mock_provider_with_usage()
        cp = CachedProvider(inner, db_path=tmp_path / "cache.db", ttl=60)
        yield cp
        cp.close()

    @pytest.mark.asyncio
    async def test_cache_miss_preserves_usage(self, provider):
        """Cache miss passes through the provider's usage."""
        resp = await provider.complete("prompt")
        assert resp.usage is not None
        assert resp.usage.input_tokens == 50
        assert resp.usage.output_tokens == 25

    @pytest.mark.asyncio
    async def test_cache_hit_clears_usage(self, provider):
        """Cache hit sets usage to None (no tokens consumed)."""
        await provider.complete("prompt")  # miss — populates cache
        resp = await provider.complete("prompt")  # hit
        assert resp.usage is None

    @pytest.mark.asyncio
    async def test_score_cache_miss_preserves_usage(self, provider):
        resp = await provider.score("jd", {"skills": ["python"]})
        assert resp.usage is not None
        assert resp.usage.input_tokens == 50

    @pytest.mark.asyncio
    async def test_score_cache_hit_clears_usage(self, provider):
        await provider.score("jd", {"skills": ["python"]})  # miss
        resp = await provider.score("jd", {"skills": ["python"]})  # hit
        assert resp.usage is None
