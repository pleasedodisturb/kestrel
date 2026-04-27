"""Provider fallback chain — automatic retry with next provider on failure.

Wraps an ordered list of AI providers. On ProviderQuotaError or timeout,
transparently retries with the next provider in the chain. If all providers
fail, raises the last error.

Composition example:
    CachedProvider(MaskedProvider(FallbackProvider([openrouter, together, ollama])))
"""

from __future__ import annotations

import logging

import httpx

from career_os.ai.base import (
    AIProvider,
    ComplexityTier,
    ProviderQuotaError,
    ProviderUnavailableError,
)
from career_os.schemas.ai import AIFeature, AIResponse

logger = logging.getLogger(__name__)


class FallbackProvider(AIProvider):
    """AI provider that tries a chain of providers in order.

    Falls back to the next provider when the current one raises:
      - ProviderQuotaError (402/429 — quota/credit exhaustion)
      - ProviderUnavailableError (404 — model-routing failure)
      - httpx.TimeoutException (transient network)
      - httpx.HTTPStatusError (any other non-2xx — provider returned an HTTP
        error that wasn't translated to a domain exception, e.g., 5xx)
    Re-raises the last exception when all providers in the chain fail.
    """

    def __init__(self, chain: list[AIProvider]) -> None:
        if not chain:
            raise ValueError("FallbackProvider requires at least one provider in the chain")
        self._chain = chain

    @property
    def name(self) -> str:
        return f"fallback({','.join(p.name for p in self._chain)})"

    @property
    def privacy_tier(self) -> str:
        return self._chain[0].privacy_tier

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Try each provider in order until one succeeds."""
        return await self._try_chain(
            "complete",
            lambda p: p.complete(prompt, feature=feature, context=context, tier=tier, **kwargs),
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Try each provider in order until one succeeds."""
        return await self._try_chain(
            "score",
            lambda p: p.score(job_description, profile_data, tier=tier, **kwargs),
        )

    async def _try_chain(self, method: str, call):
        """Execute call against each provider in the chain.

        Catches ProviderQuotaError, ProviderUnavailableError, TimeoutException,
        and any HTTPStatusError, logs the fallback, and tries the next provider.
        Re-raises the last error if all providers fail.
        """
        last_error: Exception | None = None

        for i, provider in enumerate(self._chain):
            try:
                return await call(provider)
            except (
                ProviderQuotaError,
                ProviderUnavailableError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
            ) as exc:
                last_error = exc
                remaining = len(self._chain) - i - 1
                if remaining > 0:
                    next_provider = self._chain[i + 1]
                    logger.warning(
                        "Fallback: %s.%s() failed (%s: %s), trying %s (%d remaining)",
                        provider.name,
                        method,
                        type(exc).__name__,
                        str(exc)[:100],
                        next_provider.name,
                        remaining,
                    )
                else:
                    logger.error(
                        "Fallback: all %d providers exhausted for %s(). Last error from %s: %s",
                        len(self._chain),
                        method,
                        provider.name,
                        str(exc)[:200],
                    )

        # All providers failed — re-raise the last error
        raise last_error  # type: ignore[misc]
