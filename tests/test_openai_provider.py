"""Tests for OpenAIProvider — OpenAI direct API.

Covers:
- Provider contract (AIProvider subclass, name, privacy tier, init validation)
- Factory registration and resolution
- OpenAI-compatible request format (Bearer auth, messages array)
- HTTP 402/429 → ProviderQuotaError
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

# NB: imported directly, NOT behind a try/except ImportError -> pytest.skip.
# That skip (added when openai_provider imported a non-existent
# `_scoring_user_prompt`) silently disabled this entire file, which is why CI
# stayed green while the provider was unusable. A broken import must FAIL here.
# See also tests/test_provider_contract.py (G-1348).
from career_os.ai.openai_provider import (
    OPENAI_API_URL,
    OpenAIProvider,
)
from career_os.schemas.ai import AIFeature, AIResponse

# Fake credentials used across all tests — not real.
_TEST_CREDENTIAL = "test-fake-openai-key"  # noqa: S105
_TEST_CREDENTIAL_2 = "test-fake-openai-key-2"  # noqa: S105


# ---------------------------------------------------------------------------
# OpenAIProvider unit tests
# ---------------------------------------------------------------------------


class TestOpenAIProviderInit:
    """Test OpenAIProvider initialization and contract."""

    def test_name(self) -> None:
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        assert provider.name == "openai"

    def test_is_ai_provider(self) -> None:
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        assert isinstance(provider, AIProvider)

    def test_privacy_tier_is_yellow(self) -> None:
        """OpenAI uses API data per org settings — default yellow tier."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        assert provider.privacy_tier == "yellow"

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIProvider(api_key="")

    def test_default_model(self) -> None:
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        assert provider._model == "gpt-4o-mini"

    def test_custom_model(self) -> None:
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL, model="gpt-4o")
        assert provider._model == "gpt-4o"


# ---------------------------------------------------------------------------
# Factory registration tests
# ---------------------------------------------------------------------------


class TestOpenAIFactoryRegistration:
    """Test OpenAI provider is registered in the factory."""

    def test_openai_in_registry(self) -> None:
        """'openai' key exists in _PROVIDER_REGISTRY."""
        assert "openai" in _PROVIDER_REGISTRY

    def test_registry_entry_callable(self) -> None:
        """Registry entry for openai is callable."""
        assert callable(_PROVIDER_REGISTRY["openai"])

    def test_factory_creates_openai_provider(self) -> None:
        """get_ai_provider('openai') returns OpenAIProvider."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": _TEST_CREDENTIAL}):
            provider = get_ai_provider("openai")
            assert isinstance(provider, OpenAIProvider)
            assert provider.name == "openai"

    def test_factory_without_key_raises(self) -> None:
        """get_ai_provider('openai') without API key raises ValueError."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_ai_provider("openai")

    def test_openai_in_unsupported_error_message(self) -> None:
        """UnsupportedProviderError lists openai as a supported provider."""
        from career_os.ai.factory import UnsupportedProviderError

        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_ai_provider("nonexistent")
        assert "openai" in str(exc_info.value)


# ---------------------------------------------------------------------------
# API request format tests
# ---------------------------------------------------------------------------


class TestOpenAIRequestFormat:
    """Test the OpenAI API request format."""

    @pytest.mark.asyncio
    async def test_headers_include_bearer_auth(self) -> None:
        """Request headers include Authorization: Bearer."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL_2)
        captured_headers = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "model": "gpt-4o-mini",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_headers["Authorization"] == f"Bearer {_TEST_CREDENTIAL_2}"
        assert captured_headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_sent_to_openai_url(self) -> None:
        """Request is sent to the OpenAI API URL."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        captured_url = None

        async def mock_post(url, headers=None, json=None, **kwargs):
            nonlocal captured_url
            captured_url = url
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "gpt-4o-mini",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test")

        assert captured_url == OPENAI_API_URL

    @pytest.mark.asyncio
    async def test_payload_uses_openai_chat_format(self) -> None:
        """Payload uses OpenAI chat completions format."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "result"}}],
                    "model": "gpt-4o-mini",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("hello world")

        assert captured_payload["model"] == "gpt-4o-mini"
        assert captured_payload["messages"] == [{"role": "user", "content": "hello world"}]

    @pytest.mark.asyncio
    async def test_system_message_for_structured_feature(self) -> None:
        """Structured features include a system message."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}}],
                    "model": "gpt-4o-mini",
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
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        captured_payload = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_payload.update(json)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "gpt-4o-mini",
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


class TestOpenAIResponseParsing:
    """Test response parsing from OpenAI-format responses."""

    @pytest.mark.asyncio
    async def test_parses_content_from_choices(self) -> None:
        """Response correctly parses content from choices[0].message.content."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Hello world"}}],
                    "model": "gpt-4o-mini",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("greet me")

        assert isinstance(result, AIResponse)
        assert result.content == "Hello world"
        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_uses_model_from_response(self) -> None:
        """Model field uses the model returned in the API response."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, headers=None, json=None, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "model": "gpt-4o-mini-2024-07-18",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.complete("test")

        assert result.model == "gpt-4o-mini-2024-07-18"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestOpenAIErrorHandling:
    """Test HTTP error handling (402, 429, 500)."""

    @pytest.mark.asyncio
    async def test_402_raises_provider_quota_error(self) -> None:
        """HTTP 402 raises ProviderQuotaError."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)

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
            assert exc_info.value.provider == "openai"

    @pytest.mark.asyncio
    async def test_429_raises_provider_quota_error(self) -> None:
        """HTTP 429 raises ProviderQuotaError."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)

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
            assert exc_info.value.provider == "openai"

    @pytest.mark.asyncio
    async def test_500_raises_http_error(self) -> None:
        """HTTP 500 raises httpx.HTTPStatusError (not ProviderQuotaError)."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)

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


class TestOpenAIScore:
    """Test the score() method delegates to complete() correctly."""

    @pytest.mark.asyncio
    async def test_score_calls_complete_with_score_feature(self) -> None:
        """score() calls complete() with AIFeature.score."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
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
                    "model": "gpt-4o-mini",
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await provider.score("Software Engineer at Acme", {"name": "Jane"})

        assert result.feature == AIFeature.score
        assert result.provider == "openai"
        # System message should be present (score feature has system prompt)
        messages = captured_payload["messages"]
        assert messages[0]["role"] == "system"


# ---------------------------------------------------------------------------
# Batch API tests (G-1348: this path was untested while the file was skipped)
# ---------------------------------------------------------------------------


class TestOpenAIBatchScore:
    """Test the Batch API JSONL assembly."""

    @pytest.mark.asyncio
    async def test_batch_score_builds_one_request_per_job_with_gate(self) -> None:
        """Each job becomes one JSONL request carrying the anti-halo role-fit gate."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
        uploaded: dict[str, str] = {}

        async def mock_post(url, headers=None, json=None, files=None, data=None, **kwargs):
            if files is not None:  # 1) file upload
                uploaded["jsonl"] = files["file"][1].read().decode()
                return httpx.Response(
                    200, json={"id": "file-abc"}, request=httpx.Request("POST", url)
                )
            return httpx.Response(  # 2) batch create
                200, json={"id": "batch-xyz"}, request=httpx.Request("POST", url)
            )

        jobs = [
            {"id": 1, "description": "Senior Backend Engineer at Acme"},
            {"id": 2, "description": "Staff Platform Engineer at Globex"},
        ]
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            batch_id = await provider.batch_score(jobs, {"name": "Jane"})

        assert batch_id == "batch-xyz"
        lines = [json.loads(x) for x in uploaded["jsonl"].splitlines()]
        assert len(lines) == 2, "one JSONL request per job"
        assert [x["custom_id"] for x in lines] == ["1", "2"]
        for line, job in zip(lines, jobs, strict=True):
            assert line["method"] == "POST"
            assert line["url"] == "/v1/chat/completions"
            assert line["body"]["model"] == "gpt-4o-mini"
            user_msg = line["body"]["messages"][-1]["content"]
            # the batch path must carry the same gate as real-time score()
            assert "role-fit gate (anti-halo)" in user_msg
            assert job["description"] in user_msg
            assert user_msg.index("role-fit gate (anti-halo)") < user_msg.index(job["description"])

    @pytest.mark.asyncio
    async def test_batch_score_raises_quota_error_on_upload_402(self) -> None:
        """A 402 on the file upload surfaces as ProviderQuotaError, not a raw HTTP error."""
        provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)

        async def mock_post(url, **kwargs):
            return httpx.Response(
                402, json={"error": {"message": "no credits"}}, request=httpx.Request("POST", url)
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(ProviderQuotaError):
                await provider.batch_score([{"id": 1, "description": "x"}], {"name": "Jane"})
