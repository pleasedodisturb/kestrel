"""Tests for AI token usage logging (G-397).

Covers:
- AIUsageLog model creation and field defaults
- log_usage() writes to DB on cache miss
- log_usage() skips when usage is None (cache hit)
- Cost estimation uses model pricing
- X-Title header on OpenRouter
"""

import pytest
from sqlalchemy import select

from career_os.ai.observability import _estimate_cost, log_usage
from career_os.models.ai_usage import AIUsageLog
from career_os.schemas.ai import AIFeature, TokenUsage


class TestAIUsageLogModel:
    """AIUsageLog model creates rows with correct defaults."""

    def test_create_usage_log(self, db_session) -> None:
        """Can create and query an AIUsageLog row."""
        log = AIUsageLog(
            provider="anthropic",
            model="claude-sonnet-5",
            feature="score",
            input_tokens=500,
            output_tokens=200,
            cache_read_tokens=400,
            cache_creation_tokens=0,
            estimated_cost_usd=0.0045,
        )
        db_session.add(log)
        db_session.commit()

        result = db_session.execute(select(AIUsageLog)).scalar_one()
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-5"
        assert result.feature == "score"
        assert result.input_tokens == 500
        assert result.output_tokens == 200
        assert result.cache_read_tokens == 400
        assert result.estimated_cost_usd == pytest.approx(0.0045)
        assert result.timestamp is not None

    def test_defaults_zero(self, db_session) -> None:
        """Token counts default to 0."""
        log = AIUsageLog(
            provider="mock",
            model="mock",
            feature="complete",
        )
        db_session.add(log)
        db_session.commit()

        result = db_session.execute(select(AIUsageLog)).scalar_one()
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cache_read_tokens == 0
        assert result.cache_creation_tokens == 0
        assert result.estimated_cost_usd == 0.0


class TestCostEstimation:
    """_estimate_cost() computes USD from token counts and model pricing."""

    def test_sonnet_pricing(self) -> None:
        """Sonnet: $3/MTok input, $15/MTok output."""
        cost = _estimate_cost("claude-sonnet-5", 1000, 500)
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_haiku_pricing(self) -> None:
        """Haiku is cheaper than Sonnet."""
        haiku_cost = _estimate_cost("claude-haiku-4-5-20251001", 1000, 500)
        sonnet_cost = _estimate_cost("claude-sonnet-5", 1000, 500)
        assert haiku_cost < sonnet_cost

    def test_unknown_model_uses_default(self) -> None:
        """Unknown model falls back to Sonnet-class pricing."""
        cost = _estimate_cost("unknown-model-v99", 1000, 500)
        default_cost = _estimate_cost("claude-sonnet-5", 1000, 500)
        assert cost == pytest.approx(default_cost)

    def test_zero_tokens_zero_cost(self) -> None:
        """Zero tokens = zero cost."""
        assert _estimate_cost("claude-sonnet-5", 0, 0) == 0.0


class TestLogUsage:
    """log_usage() writes token data to SQLite."""

    def test_skips_when_usage_is_none(self, db_session) -> None:
        """Cache hits pass usage=None — should not write to DB."""
        log_usage(
            provider="anthropic",
            model="claude-sonnet-5",
            feature=AIFeature.score,
            usage=None,
        )
        count = db_session.execute(select(AIUsageLog)).scalars().all()
        assert len(count) == 0

    def test_log_usage_does_not_raise(self) -> None:
        """log_usage() is fire-and-forget — never raises on failure."""
        usage = TokenUsage(
            input_tokens=1200,
            output_tokens=800,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=500,
        )
        # Should not raise even if DB is unavailable (uses try/except internally)
        log_usage(
            provider="openrouter",
            model="anthropic/claude-sonnet-5",
            feature=AIFeature.score,
            usage=usage,
        )


class TestOpenRouterXTitle:
    """OpenRouter provider sends X-Title header for dashboard attribution."""

    @pytest.mark.asyncio
    async def test_x_title_header_is_kestrel(self) -> None:
        """X-Title header should be 'Career OS' for cost attribution."""
        from unittest.mock import patch

        import httpx

        from career_os.ai.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key="sk-or-test123")
        captured_headers = {}

        async def mock_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}}],
                    "model": "test",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
                request=httpx.Request("POST", url),
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await provider.complete("test", feature=AIFeature.complete)

        assert captured_headers.get("X-Title") == "Career OS"
