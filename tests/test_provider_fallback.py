"""Tests for provider fallback chain (G-405).

Covers:
- FallbackProvider tries providers in order
- Falls back on ProviderQuotaError
- Falls back on httpx.TimeoutException
- Re-raises when all providers fail
- Logs fallback events
- Factory builds chain from AI_PROVIDER_FALLBACK env var
- Factory skips providers with missing keys
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from career_os.ai.base import AIProvider, ProviderQuotaError
from career_os.ai.fallback import FallbackProvider
from career_os.schemas.ai import AIFeature, AIResponse


def _make_provider(name: str, should_fail: str | None = None) -> AIProvider:
    """Create a mock provider that optionally fails with a specific error."""
    provider = AsyncMock(spec=AIProvider)
    provider.name = name
    provider.privacy_tier = "green"

    success_response = AIResponse(
        content='{"fit_score": 7}',
        provider=name,
        feature=AIFeature.score,
        structured=None,
        model="test-model",
    )

    if should_fail == "quota":
        provider.complete.side_effect = ProviderQuotaError(name, 429, "rate limited")
        provider.score.side_effect = ProviderQuotaError(name, 429, "rate limited")
    elif should_fail == "timeout":
        provider.complete.side_effect = httpx.TimeoutException("timed out")
        provider.score.side_effect = httpx.TimeoutException("timed out")
    else:
        provider.complete.return_value = success_response
        provider.score.return_value = success_response

    return provider


class TestFallbackProvider:
    """FallbackProvider tries providers in order."""

    @pytest.mark.asyncio
    async def test_uses_first_provider_on_success(self) -> None:
        """First provider succeeds — no fallback needed."""
        p1 = _make_provider("openrouter")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "openrouter"
        p1.complete.assert_called_once()
        p2.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_quota_error(self) -> None:
        """Quota error triggers fallback to next provider."""
        p1 = _make_provider("openrouter", should_fail="quota")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "together"
        p1.complete.assert_called_once()
        p2.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout(self) -> None:
        """Timeout triggers fallback to next provider."""
        p1 = _make_provider("openrouter", should_fail="timeout")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.score("job desc", {"name": "test"})

        assert result.provider == "together"

    @pytest.mark.asyncio
    async def test_tries_all_providers_in_order(self) -> None:
        """Falls through multiple providers until one succeeds."""
        p1 = _make_provider("openrouter", should_fail="quota")
        p2 = _make_provider("together", should_fail="timeout")
        p3 = _make_provider("ollama")

        fb = FallbackProvider([p1, p2, p3])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "ollama"
        p1.complete.assert_called_once()
        p2.complete.assert_called_once()
        p3.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_when_all_fail(self) -> None:
        """Re-raises last error when all providers exhaust."""
        p1 = _make_provider("openrouter", should_fail="quota")
        p2 = _make_provider("together", should_fail="timeout")

        fb = FallbackProvider([p1, p2])
        with pytest.raises(httpx.TimeoutException):
            await fb.complete("test", feature=AIFeature.complete)

    @pytest.mark.asyncio
    async def test_does_not_catch_other_errors(self) -> None:
        """Non-quota/timeout errors are not caught (bubble up immediately)."""
        p1 = _make_provider("openrouter")
        p1.complete.side_effect = ValueError("unexpected error")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        with pytest.raises(ValueError, match="unexpected error"):
            await fb.complete("test", feature=AIFeature.complete)
        # p2 never called — error wasn't a fallback trigger
        p2.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_logs_fallback_events(self, caplog) -> None:
        """Logs a warning on each fallback attempt."""
        import logging

        p1 = _make_provider("openrouter", should_fail="quota")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        with caplog.at_level(logging.WARNING, logger="career_os.ai.fallback"):
            await fb.complete("test", feature=AIFeature.complete)

        assert "Fallback: openrouter.complete() failed" in caplog.text
        assert "trying together" in caplog.text

    def test_requires_at_least_one_provider(self) -> None:
        """Empty chain raises ValueError."""
        with pytest.raises(ValueError, match="at least one provider"):
            FallbackProvider([])

    def test_name_includes_chain(self) -> None:
        """Name property shows the full chain."""
        p1 = _make_provider("openrouter")
        p2 = _make_provider("together")
        fb = FallbackProvider([p1, p2])
        assert fb.name == "fallback(openrouter,together)"


class TestFactoryFallbackChain:
    """Factory builds fallback chain from AI_PROVIDER_FALLBACK env var."""

    def test_no_fallback_env_returns_single_provider(self) -> None:
        """Without AI_PROVIDER_FALLBACK, factory returns single provider."""
        from career_os.ai.factory import get_ai_provider

        provider = get_ai_provider("mock")
        assert provider.name == "mock"

    def test_fallback_env_builds_chain(self) -> None:
        """With AI_PROVIDER_FALLBACK, factory returns FallbackProvider."""
        from career_os.ai.factory import get_ai_provider

        with patch.dict(
            "os.environ",
            {"AI_PROVIDER_FALLBACK": "mock,demo", "AI_PROVIDER": "mock"},
        ):
            provider = get_ai_provider()

        assert "fallback" in provider.name

    def test_fallback_skips_unknown_providers(self) -> None:
        """Unknown providers in chain are silently skipped."""
        from career_os.ai.factory import _build_fallback_chain

        with patch.dict("os.environ", {"AI_PROVIDER_FALLBACK": "mock,nonexistent,demo"}):
            chain = _build_fallback_chain()

        # mock + demo = 2 providers (nonexistent skipped)
        assert chain is not None
        assert len(chain) == 2

    def test_single_provider_fallback_returns_none(self) -> None:
        """Single provider in fallback env doesn't create a chain."""
        from career_os.ai.factory import _build_fallback_chain

        with patch.dict("os.environ", {"AI_PROVIDER_FALLBACK": "mock"}):
            assert _build_fallback_chain() is None
