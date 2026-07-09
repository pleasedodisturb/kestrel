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

# Fake credentials used across all tests — not real.
_TEST_CREDENTIAL = "test-fake-anthropic-key"  # noqa: S105
_TEST_CREDENTIAL_2 = "test-fake-anthropic-key-2"  # noqa: S105

# ---------------------------------------------------------------------------
# AnthropicProvider unit tests
# ---------------------------------------------------------------------------


class TestAnthropicProviderInit:
    """Test AnthropicProvider initialization and contract."""

    def test_name(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        assert provider.name == "anthropic"

    def test_is_ai_provider(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        assert isinstance(provider, AIProvider)

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider(api_key="")

    def test_default_model(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        assert provider._model == "claude-sonnet-5"

    def test_custom_model(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL, model="claude-opus-4-8")
        assert provider._model == "claude-opus-4-8"


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
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            mock_resp = httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "test response"}],
                    "model": "claude-sonnet-5",
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
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            mock_resp = httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "hello"}],
                    "model": "claude-sonnet-5",
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
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL_2)
        captured_headers = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 5, "output_tokens": 2},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_headers["x-api-key"] == _TEST_CREDENTIAL_2
        assert captured_headers["anthropic-version"] == ANTHROPIC_VERSION

    @pytest.mark.asyncio
    async def test_payload_uses_messages_api_format(self) -> None:
        """Payload uses Anthropic Messages API format (not OpenAI chat format)."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "result"}],
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello world")

        assert captured_payload["model"] == "claude-sonnet-5"
        assert captured_payload["max_tokens"] == 4096
        assert captured_payload["messages"] == [{"role": "user", "content": "hello world"}]

    @pytest.mark.asyncio
    async def test_response_parses_content_blocks(self) -> None:
        """Response correctly parses Anthropic content blocks format."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "world"},
                    ],
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("greet me")

        assert isinstance(result, AIResponse)
        assert result.content == "Hello world"
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-5"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestAnthropicErrorHandling:
    """Test HTTP error handling (402, 429, etc.)."""

    @pytest.mark.asyncio
    async def test_402_raises_provider_quota_error(self) -> None:
        """HTTP 402 raises ProviderQuotaError."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

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
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

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
        """HTTP 500 raises httpx.HTTPStatusError (not ProviderQuotaError)."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

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
    """Test the score() method sends correct payloads with prompt caching."""

    @pytest.mark.asyncio
    async def test_score_calls_complete_with_score_feature(self) -> None:
        """score() calls complete() with AIFeature.score."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
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
                    "model": "claude-sonnet-5",
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

    @pytest.mark.asyncio
    async def test_score_profile_in_system_prefix(self) -> None:
        """Profile data is in the cached system prefix, not the user message."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}
        profile = {"name": "Jane Doe", "skills": ["Python", "FastAPI"]}

        score_json = json.dumps(
            {
                "fit_score": 6.0,
                "reasoning": "x" * 100,
                "estimated_salary": "100k",
                "effort_flag": "low",
                "prep_level": "light",
                "prep_notes": "Review basics.",
                "readiness_score": 80.0,
                "career_alignment": 7.0,
                "score_breakdown": [
                    {"factor": "Skills", "contribution": 2.0, "description": "Good"},
                    {"factor": "Exp", "contribution": 1.0, "description": "OK"},
                    {"factor": "Loc", "contribution": 0.5, "description": "Fine"},
                ],
            }
        )

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": score_json}],
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.score("Backend Engineer at Corp", profile)

        # Profile data must be in system prefix for caching
        system_blocks = captured_payload["system"]
        system_text = system_blocks[0]["text"]
        assert "Jane Doe" in system_text
        assert "Python" in system_text
        assert "Candidate Profile:" in system_text

        # Profile data must NOT be in user message (only job desc)
        user_msg = captured_payload["messages"][0]["content"]
        assert "Jane Doe" not in user_msg
        assert "Backend Engineer at Corp" in user_msg

    @pytest.mark.asyncio
    async def test_score_system_block_has_cache_control(self) -> None:
        """Scoring system blocks include cache_control for prompt caching."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        score_json = json.dumps(
            {
                "fit_score": 5.0,
                "reasoning": "x" * 100,
                "estimated_salary": "90k",
                "effort_flag": "low",
                "prep_level": "light",
                "prep_notes": "None needed.",
                "readiness_score": 60.0,
                "career_alignment": 5.0,
                "score_breakdown": [
                    {"factor": "A", "contribution": 1.0, "description": "OK"},
                    {"factor": "B", "contribution": 1.0, "description": "OK"},
                    {"factor": "C", "contribution": 1.0, "description": "OK"},
                ],
            }
        )

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": score_json}],
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 50, "output_tokens": 30},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.score("Any job", {"name": "Test"})

        system_blocks = captured_payload["system"]
        assert len(system_blocks) == 1
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}


# ---------------------------------------------------------------------------
# Token usage tracking tests
# ---------------------------------------------------------------------------


class TestTokenUsageTracking:
    """Test that cache token metrics are extracted from responses."""

    @pytest.mark.asyncio
    async def test_cache_tokens_in_usage(self) -> None:
        """Token usage includes cache_creation and cache_read metrics."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "cached response"}],
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 150,
                        "output_tokens": 40,
                        "cache_creation_input_tokens": 1200,
                        "cache_read_input_tokens": 0,
                    },
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test", feature=AIFeature.complete)

        assert result.usage is not None
        assert result.usage.input_tokens == 150
        assert result.usage.output_tokens == 40
        assert result.usage.cache_creation_input_tokens == 1200
        assert result.usage.cache_read_input_tokens == 0

    @pytest.mark.asyncio
    async def test_cache_read_tokens_on_subsequent_call(self) -> None:
        """Cache read tokens are tracked when cache is hit."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "from cache"}],
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 50,
                        "output_tokens": 30,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 1200,
                    },
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test", feature=AIFeature.complete)

        assert result.usage is not None
        assert result.usage.cache_creation_input_tokens == 0
        assert result.usage.cache_read_input_tokens == 1200

    @pytest.mark.asyncio
    async def test_score_method_tracks_cache_tokens(self) -> None:
        """score() method independently tracks cache tokens (not via complete)."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)

        score_json = json.dumps(
            {
                "fit_score": 7.0,
                "reasoning": "x" * 100,
                "estimated_salary": "100k",
                "effort_flag": "medium",
                "prep_level": "moderate",
                "prep_notes": "Prep.",
                "readiness_score": 70.0,
                "career_alignment": 7.0,
                "score_breakdown": [
                    {"factor": "A", "contribution": 1.0, "description": "OK"},
                    {"factor": "B", "contribution": 1.0, "description": "OK"},
                    {"factor": "C", "contribution": 1.0, "description": "OK"},
                ],
            }
        )

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": score_json}],
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 80,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 2500,
                    },
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.score("Job desc", {"name": "Test"})

        assert result.usage is not None
        assert result.usage.cache_read_input_tokens == 2500
        assert result.usage.cache_creation_input_tokens == 0
        assert result.usage.input_tokens == 200


# ---------------------------------------------------------------------------
# Batch score caching tests
# ---------------------------------------------------------------------------


class TestBatchScoreCaching:
    """Test that batch_score includes profile in cached system prefix."""

    @pytest.mark.asyncio
    async def test_batch_score_profile_in_system_blocks(self) -> None:
        """batch_score() puts profile data in system blocks, not user messages."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}
        profile = {"name": "Alice", "skills": ["Go", "Kubernetes"]}
        jobs = [
            {"id": "job-1", "description": "SRE at CloudCo"},
            {"id": "job-2", "description": "Backend at StartupX"},
        ]

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={"id": "batch-abc123"},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            batch_id = await provider.batch_score(jobs, profile)

        assert batch_id == "batch-abc123"

        requests = captured_payload["requests"]
        assert len(requests) == 2

        # Both requests should share the same system blocks with profile
        for req in requests:
            params = req["params"]
            system_blocks = params["system"]
            assert len(system_blocks) == 1
            assert "Alice" in system_blocks[0]["text"]
            assert "Kubernetes" in system_blocks[0]["text"]
            assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

            # User message should NOT contain profile data
            user_msg = params["messages"][0]["content"]
            assert "Alice" not in user_msg

    @pytest.mark.asyncio
    async def test_batch_score_user_messages_differ_per_job(self) -> None:
        """Each batch request has a different user message (job description)."""
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}
        jobs = [
            {"id": "j1", "description": "Frontend role"},
            {"id": "j2", "description": "Backend role"},
        ]

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={"id": "batch-xyz"},
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.batch_score(jobs, {"name": "Bob"})

        requests = captured_payload["requests"]
        user_msg_1 = requests[0]["params"]["messages"][0]["content"]
        user_msg_2 = requests[1]["params"]["messages"][0]["content"]
        assert "Frontend role" in user_msg_1
        assert "Backend role" in user_msg_2
        # System blocks are identical (same object reference)
        assert requests[0]["params"]["system"] is requests[1]["params"]["system"]


class TestBatchResultsUrlValidation:
    """results_url host validation prevents API-key exfiltration (SSRF guard).

    get_batch_results() fetches the batch results_url with the x-api-key header
    attached. A tampered or unexpected results_url must never be requested, or
    the API key would leak to an arbitrary host.
    """

    @pytest.mark.asyncio
    async def test_rejects_non_anthropic_results_url(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        requested_urls: list[str] = []

        async def mock_get(url, headers=None, **kwargs):
            requested_urls.append(url)
            # Status poll returns a malicious results_url on a foreign host.
            return httpx.Response(
                200,
                json={
                    "processing_status": "ended",
                    "results_url": "https://evil.example.com/leak",
                },
                request=httpx.Request("GET", url),
            )

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await provider.get_batch_results("batch_123")

        assert result["status"] == "ended"
        assert result["results"] == {}
        # The malicious results_url must never be fetched (no key leak).
        assert not any("evil.example.com" in u for u in requested_urls)

    @pytest.mark.asyncio
    async def test_accepts_anthropic_results_url(self) -> None:
        provider = AnthropicProvider(api_key=_TEST_CREDENTIAL)
        jsonl = json.dumps(
            {
                "custom_id": "req_0",
                "result": {
                    "type": "succeeded",
                    "message": {
                        "content": [{"type": "text", "text": "ok"}],
                        "model": "claude-sonnet-5",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    },
                },
            }
        )

        async def mock_get(url, headers=None, **kwargs):
            if "/results" in url:
                return httpx.Response(200, text=jsonl, request=httpx.Request("GET", url))
            return httpx.Response(
                200,
                json={
                    "processing_status": "ended",
                    "results_url": "https://api.anthropic.com/v1/messages/batches/batch_123/results",
                },
                request=httpx.Request("GET", url),
            )

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await provider.get_batch_results("batch_123")

        assert result["status"] == "ended"
        assert "req_0" in result["results"]
        assert result["results"]["req_0"].content == "ok"
