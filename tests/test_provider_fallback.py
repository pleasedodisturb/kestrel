"""Tests for provider fallback chain (G-405, G-564).

Covers:
- FallbackProvider tries providers in order
- Falls back on ProviderQuotaError
- Falls back on ProviderUnavailableError (G-564 — 404 model routing failures)
- Falls back on httpx.TimeoutException
- Falls back on httpx.HTTPStatusError (G-564 — generic 4xx/5xx safety net)
- Re-raises when all providers fail
- Logs fallback events
- Factory builds chain from AI_PROVIDER_FALLBACK env var
- Factory skips providers with missing keys
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from career_os.ai.base import AIProvider, ProviderQuotaError, ProviderUnavailableError
from career_os.ai.fallback import FallbackProvider
from career_os.schemas.ai import AIFeature, AIResponse


def _http_status_error(status: int, detail: str = "") -> httpx.HTTPStatusError:
    """Construct an httpx.HTTPStatusError for a given status code.

    Mirrors the path providers take when ``response.raise_for_status()`` is
    invoked — useful for simulating provider-side HTTP failures that weren't
    translated into a domain exception.
    """
    request = httpx.Request("POST", "https://example.invalid/v1/chat")
    response = httpx.Response(status_code=status, request=request, text=detail)
    return httpx.HTTPStatusError(
        f"{status} {detail}".strip(),
        request=request,
        response=response,
    )


def _make_provider(name: str, should_fail: str | None = None) -> AIProvider:
    """Create a mock provider that optionally fails with a specific error.

    Supported failure modes:
      - "quota": ProviderQuotaError (402/429 family)
      - "timeout": httpx.TimeoutException
      - "unavailable": ProviderUnavailableError (404 model-routing)
      - "http_5xx": httpx.HTTPStatusError with status 503
      - "http_4xx": httpx.HTTPStatusError with status 404
      - "value_error": ValueError (NOT a fallback trigger — should bubble)
    """
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
    elif should_fail == "unavailable":
        err = ProviderUnavailableError(name, 404, "no allowed providers available")
        provider.complete.side_effect = err
        provider.score.side_effect = err
    elif should_fail == "http_5xx":
        err = _http_status_error(503, "Service Unavailable")
        provider.complete.side_effect = err
        provider.score.side_effect = err
    elif should_fail == "http_4xx":
        err = _http_status_error(404, "Not Found")
        provider.complete.side_effect = err
        provider.score.side_effect = err
    elif should_fail == "value_error":
        provider.complete.side_effect = ValueError("unexpected programming bug")
        provider.score.side_effect = ValueError("unexpected programming bug")
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
        """Non-fallback-trigger errors bubble up immediately."""
        p1 = _make_provider("openrouter")
        p1.complete.side_effect = ValueError("unexpected error")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        with pytest.raises(ValueError, match="unexpected error"):
            await fb.complete("test", feature=AIFeature.complete)
        # p2 never called — error wasn't a fallback trigger
        p2.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_provider_unavailable(self) -> None:
        """ProviderUnavailableError (404 / no model routing) triggers fallback.

        This is the bug that broke daily-scan in G-564 — OpenRouter returned
        404 'No allowed providers' for the configured model. Without this
        catch, every job got fit_score=2 and the digest showed 0 qualified.
        """
        p1 = _make_provider("openrouter", should_fail="unavailable")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "together"
        p1.complete.assert_called_once()
        p2.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_on_http_5xx(self) -> None:
        """5xx HTTPStatusError triggers fallback (provider-side outage)."""
        p1 = _make_provider("openrouter", should_fail="http_5xx")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.score("job", {"name": "test"})

        assert result.provider == "together"

    @pytest.mark.asyncio
    async def test_falls_back_on_http_4xx(self) -> None:
        """Generic 4xx HTTPStatusError triggers fallback as a safety net.

        Catches the case where a provider didn't translate its 4xx into a
        domain exception (e.g. ProviderUnavailableError) — we still try the
        next vendor rather than losing the request.
        """
        p1 = _make_provider("openrouter", should_fail="http_4xx")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "together"

    @pytest.mark.asyncio
    async def test_raises_provider_unavailable_when_all_fail(self) -> None:
        """When every provider in chain raises ProviderUnavailableError, the
        last one is re-raised so the workflow can fail loudly upstream."""
        p1 = _make_provider("openrouter", should_fail="unavailable")
        p2 = _make_provider("together", should_fail="unavailable")

        fb = FallbackProvider([p1, p2])
        with pytest.raises(ProviderUnavailableError):
            await fb.complete("test", feature=AIFeature.complete)

    @pytest.mark.asyncio
    async def test_mixed_failure_modes_chain(self) -> None:
        """Different failure modes across the chain still funnel to last
        successful provider — fallback is mode-agnostic."""
        p1 = _make_provider("openrouter", should_fail="unavailable")
        p2 = _make_provider("together", should_fail="http_5xx")
        p3 = _make_provider("anthropic", should_fail="quota")
        p4 = _make_provider("mistral")

        fb = FallbackProvider([p1, p2, p3, p4])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "mistral"
        for p in (p1, p2, p3, p4):
            p.complete.assert_called_once()

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


# ==================== G-564 review-fix regression tests ====================
#
# These cover the two security/correctness fixes added during code review of
# the G-564 PR. Without them the silent-degradation pattern would re-emerge
# in disguise.


class TestCreditsExhaustedErrorFallback:
    """OpenRouter's CreditsExhaustedError must trigger fallback.

    The class exists separately for a friendlier 'add credits at openrouter.ai'
    message, but it MUST inherit from ProviderQuotaError so FallbackProvider
    catches it. Without the inheritance, an OpenRouter 402/429 response bubbles
    out of the chain unfiltered and fit_score=2 stubs accumulate silently —
    the exact bug G-564 was meant to fix.
    """

    def test_credits_exhausted_inherits_provider_quota_error(self) -> None:
        from career_os.ai.base import ProviderQuotaError
        from career_os.ai.openrouter_provider import CreditsExhaustedError

        assert issubclass(CreditsExhaustedError, ProviderQuotaError)

    @pytest.mark.asyncio
    async def test_credits_exhausted_triggers_fallback(self) -> None:
        from career_os.ai.openrouter_provider import CreditsExhaustedError

        p1 = _make_provider("openrouter")
        p1.complete.side_effect = CreditsExhaustedError(429, "free tier limit")
        p2 = _make_provider("together")

        fb = FallbackProvider([p1, p2])
        result = await fb.complete("test", feature=AIFeature.complete)

        assert result.provider == "together"
        p1.complete.assert_called_once()
        p2.complete.assert_called_once()


class TestGeminiKeyLeakPrevention:
    """Gemini auth uses ?key=<API_KEY> as a query param. Letting
    response.raise_for_status() propagate would embed that URL — including
    the key — in the resulting httpx.HTTPStatusError, which the daily
    pipeline persists into the public scored_*.json artifact and digest.

    The fix translates non-2xx (other than 429, already handled separately)
    into ProviderUnavailableError with a sanitized detail string, so no URL
    or key reaches an exception's __str__.
    """

    @pytest.mark.asyncio
    async def test_gemini_4xx_translates_to_provider_unavailable_no_url_in_msg(
        self,
    ) -> None:
        """Gemini 400/401/403/404 must raise ProviderUnavailableError, never
        an httpx.HTTPStatusError that could carry the request URL."""
        import httpx as _httpx

        from career_os.ai.gemini_provider import GeminiProvider

        # Key marker — if sanitization works, this string never appears in str(exc).
        provider = GeminiProvider(api_key="FAKE-LEAKY-KEY", model="gemini-2.5-flash")

        # Build a request URL that contains the key (matches what Gemini's
        # ?key= auth would produce in production).
        leaky_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent?key=FAKE-LEAKY-KEY"
        )
        request = _httpx.Request("POST", leaky_url)
        mock_response = _httpx.Response(
            403,
            request=request,
            json={"error": {"message": "PERMISSION_DENIED"}},
        )

        async def _mock_post(self, url, **kwargs):  # noqa: ARG001
            return mock_response

        with patch.object(_httpx.AsyncClient, "post", _mock_post):
            with pytest.raises(ProviderUnavailableError) as exc_info:
                await provider.complete("hello", feature=AIFeature.complete)

        msg = str(exc_info.value)
        assert "FAKE-LEAKY-KEY" not in msg, (
            "Gemini key leaked into exception string — would propagate to "
            "scored_*.json artifact and digest. See G-564 review."
        )
        assert "PERMISSION_DENIED" in msg or "see logs" in msg
        assert exc_info.value.provider == "gemini"
        assert exc_info.value.status_code == 403
