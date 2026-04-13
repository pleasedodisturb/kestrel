"""Tests for the Ollama AI provider.

Covers:
- OllamaProvider initialization and properties
- Factory registration (AI_PROVIDER=ollama)
- complete() with mocked httpx responses
- JSON retry logic when first response is not valid JSON
- score() delegation to complete()
- Connection error handling (Ollama not running)
"""

import json
import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from career_os.ai.base import AIProvider
from career_os.ai.factory import _PROVIDER_REGISTRY, get_ai_provider
from career_os.ai.ollama_provider import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OllamaConnectionError,
    OllamaProvider,
)
from career_os.schemas.ai import AIFeature, AIResponse

# ---------------------------------------------------------------------------
# OllamaProvider unit tests
# ---------------------------------------------------------------------------


class TestOllamaProviderInit:
    """Test OllamaProvider initialization and properties."""

    def test_name(self) -> None:
        provider = OllamaProvider()
        assert provider.name == "ollama"

    def test_is_ai_provider(self) -> None:
        provider = OllamaProvider()
        assert isinstance(provider, AIProvider)

    def test_default_base_url(self) -> None:
        provider = OllamaProvider()
        assert provider._base_url == DEFAULT_BASE_URL

    def test_default_model(self) -> None:
        provider = OllamaProvider()
        assert provider._model == DEFAULT_MODEL

    def test_custom_base_url(self) -> None:
        provider = OllamaProvider(base_url="http://myhost:9999")
        assert provider._base_url == "http://myhost:9999"

    def test_custom_model(self) -> None:
        provider = OllamaProvider(model="mistral")
        assert provider._model == "mistral"

    def test_trailing_slash_stripped(self) -> None:
        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert provider._base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# Factory registration tests
# ---------------------------------------------------------------------------


class TestOllamaFactoryRegistration:
    """Test that Ollama is registered in the provider factory."""

    def test_ollama_in_registry(self) -> None:
        """'ollama' key exists in _PROVIDER_REGISTRY."""
        assert "ollama" in _PROVIDER_REGISTRY

    def test_ollama_registry_entry_returns_provider(self) -> None:
        """Registry entry produces a valid OllamaProvider."""
        provider = _PROVIDER_REGISTRY["ollama"]()
        assert isinstance(provider, OllamaProvider)
        assert isinstance(provider, AIProvider)
        assert provider.name == "ollama"

    def test_get_ai_provider_ollama(self) -> None:
        """get_ai_provider('ollama') returns OllamaProvider."""
        provider = get_ai_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_env_var_selection(self) -> None:
        """AI_PROVIDER=ollama env var selects OllamaProvider."""
        with patch.dict(os.environ, {"AI_PROVIDER": "ollama"}):
            provider = get_ai_provider()
            assert isinstance(provider, OllamaProvider)

    def test_custom_env_vars(self) -> None:
        """OLLAMA_BASE_URL and OLLAMA_MODEL env vars are respected."""
        with patch.dict(
            os.environ,
            {
                "OLLAMA_BASE_URL": "http://custom:8080",
                "OLLAMA_MODEL": "phi3",
            },
        ):
            provider = _PROVIDER_REGISTRY["ollama"]()
            assert provider._base_url == "http://custom:8080"
            assert provider._model == "phi3"


# ---------------------------------------------------------------------------
# complete() with mocked httpx
# ---------------------------------------------------------------------------


def _mock_ollama_response(content: str, model: str = "llama3.3") -> dict:
    """Build a mock Ollama OpenAI-compatible response payload."""
    return {
        "choices": [{"message": {"content": content}}],
        "model": model,
    }


class TestOllamaComplete:
    """Test OllamaProvider.complete() with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_complete_generic(self) -> None:
        """Generic complete returns text response with no structured data."""
        provider = OllamaProvider()
        mock_resp = httpx.Response(
            200,
            json=_mock_ollama_response("Hello from Ollama!"),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = await provider.complete("Hello")

        assert isinstance(resp, AIResponse)
        assert resp.provider == "ollama"
        assert resp.feature == AIFeature.complete
        assert resp.content == "Hello from Ollama!"
        assert resp.structured is None

    @pytest.mark.asyncio
    async def test_complete_sends_json_format_for_structured(self) -> None:
        """Structured features include format='json' in the payload."""
        provider = OllamaProvider()
        score_json = json.dumps(
            {
                "fit_score": 7.0,
                "reasoning": "x" * 100,
                "estimated_salary": "100k",
                "effort_flag": "medium",
                "prep_level": "moderate",
                "prep_notes": "Study.",
                "readiness_score": 70.0,
                "career_alignment": 7.0,
                "score_breakdown": [
                    {"factor": "A", "contribution": 1.0, "description": "Good"},
                    {"factor": "B", "contribution": 1.5, "description": "Great"},
                    {"factor": "C", "contribution": -0.5, "description": "Meh"},
                ],
            }
        )
        mock_resp = httpx.Response(
            200,
            json=_mock_ollama_response(score_json),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.complete("Score this", feature=AIFeature.score)

            # Verify payload included format: "json"
            call_kwargs = mock_client.post.call_args
            sent_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert sent_payload["format"] == "json"

    @pytest.mark.asyncio
    async def test_complete_no_json_format_for_plain(self) -> None:
        """Plain complete does NOT include format='json'."""
        provider = OllamaProvider()
        mock_resp = httpx.Response(
            200,
            json=_mock_ollama_response("Just text"),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.complete("Hello", feature=AIFeature.complete)

            call_kwargs = mock_client.post.call_args
            sent_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert "format" not in sent_payload


# ---------------------------------------------------------------------------
# JSON retry logic
# ---------------------------------------------------------------------------


class TestOllamaJsonRetry:
    """Test JSON retry when first response is not valid JSON."""

    @pytest.mark.asyncio
    async def test_retry_on_invalid_json(self) -> None:
        """When structured feature returns non-JSON, retries once with JSON instruction."""
        provider = OllamaProvider()

        # First call returns invalid text, second returns valid JSON
        bad_resp = httpx.Response(
            200,
            json=_mock_ollama_response("Sorry, here is my analysis in plain text..."),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )
        good_json = json.dumps(
            {
                "suggestions": [
                    {"action": "Do X", "hours": 5, "weeks": 1, "difficulty": "low", "priority": 1}
                ],
                "focus_area": "Skills",
            }
        )
        good_resp = httpx.Response(
            200,
            json=_mock_ollama_response(good_json),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [bad_resp, good_resp]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = await provider.complete("Coach me", feature=AIFeature.coaching)

        # Should have been called twice (original + retry)
        assert mock_client.post.call_count == 2
        # The retry message should contain "Return valid JSON only"
        retry_payload = mock_client.post.call_args_list[1].kwargs.get(
            "json"
        ) or mock_client.post.call_args_list[1][1].get("json")
        last_msg = retry_payload["messages"][-1]
        assert last_msg["content"] == "Return valid JSON only."
        # Should have structured data from the retry
        assert resp.structured is not None

    @pytest.mark.asyncio
    async def test_no_retry_for_valid_json(self) -> None:
        """When structured feature returns valid JSON on first try, no retry."""
        provider = OllamaProvider()
        coaching_json = json.dumps(
            {
                "suggestions": [
                    {"action": "Do X", "hours": 5, "weeks": 1, "difficulty": "low", "priority": 1}
                ],
                "focus_area": "Skills",
            }
        )
        mock_resp = httpx.Response(
            200,
            json=_mock_ollama_response(coaching_json),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.complete("Coach me", feature=AIFeature.coaching)

        # Only one call, no retry
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_for_complete_feature(self) -> None:
        """Plain complete never triggers retry, even if content looks non-JSON."""
        provider = OllamaProvider()
        mock_resp = httpx.Response(
            200,
            json=_mock_ollama_response("Just plain text"),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.complete("Hello", feature=AIFeature.complete)

        assert mock_client.post.call_count == 1


# ---------------------------------------------------------------------------
# score() delegation
# ---------------------------------------------------------------------------


class TestOllamaScore:
    """Test that score() delegates to complete() with AIFeature.score."""

    @pytest.mark.asyncio
    async def test_score_delegates_to_complete(self) -> None:
        """score() calls complete() with feature=AIFeature.score."""
        provider = OllamaProvider()
        score_json = json.dumps(
            {
                "fit_score": 8.0,
                "reasoning": "x" * 100,
                "estimated_salary": "130k",
                "effort_flag": "low",
                "prep_level": "light",
                "prep_notes": "Review.",
                "readiness_score": 80.0,
                "career_alignment": 8.5,
                "score_breakdown": [
                    {"factor": "A", "contribution": 2.0, "description": "Strong"},
                    {"factor": "B", "contribution": 1.0, "description": "Good"},
                    {"factor": "C", "contribution": 0.5, "description": "Ok"},
                ],
            }
        )
        mock_resp = httpx.Response(
            200,
            json=_mock_ollama_response(score_json),
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
        )

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = await provider.score("Engineer at Acme", {"name": "Test"})

        assert isinstance(resp, AIResponse)
        assert resp.feature == AIFeature.score
        assert resp.provider == "ollama"


# ---------------------------------------------------------------------------
# Connection error handling
# ---------------------------------------------------------------------------


class TestOllamaConnectionErrors:
    """Test graceful handling when Ollama is not running."""

    @pytest.mark.asyncio
    async def test_connect_error_raises_ollama_connection_error(self) -> None:
        """httpx.ConnectError is caught and re-raised as OllamaConnectionError."""
        provider = OllamaProvider()

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OllamaConnectionError) as exc_info:
                await provider.complete("Hello")

        assert "localhost:11434" in str(exc_info.value)
        assert "ollama serve" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_raises_ollama_connection_error(self) -> None:
        """httpx.TimeoutException is caught and re-raised as OllamaConnectionError."""
        provider = OllamaProvider()

        with patch("career_os.ai.ollama_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OllamaConnectionError) as exc_info:
                await provider.complete("Hello")

        assert "timed out" in str(exc_info.value)

    def test_connection_error_message_includes_url(self) -> None:
        """OllamaConnectionError message includes the base URL."""
        err = OllamaConnectionError("http://myhost:9999")
        assert "http://myhost:9999" in str(err)
        assert "ollama serve" in str(err)

    def test_connection_error_message_with_detail(self) -> None:
        """OllamaConnectionError message includes optional detail."""
        err = OllamaConnectionError("http://localhost:11434", detail="refused")
        assert "refused" in str(err)
