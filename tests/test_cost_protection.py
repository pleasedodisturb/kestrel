"""Tests for cost runaway protection mechanisms (G-463).

Verifies that cost controls work correctly:
- Preset limits enforce provider/model/prefilter constraints
- Batch scoring respects size limits
- Pre-filter reduces AI calls before scoring
- Token usage tracking captures input/output tokens
- Provider fallback preserves cost controls
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from career_os.ai.base import ProviderQuotaError
from career_os.ai.fallback import FallbackProvider
from career_os.ai.mock_provider import MockProvider
from career_os.discovery.prefilter import (
    PrefilterConfig,
    PrefilterStrategy,
    run_prefilter,
)
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage
from career_os.services.batch_scoring import (
    DEFAULT_BATCH_SIZE,
    batch_score_jobs,
    chunk_jobs,
    get_batch_size,
)
from career_os.services.presets import (
    PRESETS,
    apply_preset,
)

# ---------------------------------------------------------------------------
# Preset limits — enforce provider/model/prefilter constraints
# ---------------------------------------------------------------------------


class TestPresetCostLimits:
    """Preset definitions enforce cost-related constraints."""

    def test_free_preset_uses_strict_prefilter(self):
        """Free tier uses strict pre-filter to minimise AI calls."""
        preset = PRESETS["free"]
        assert preset.prefilter_strategy == "strict"

    def test_free_preset_has_smallest_batch_size(self):
        """Free tier has the smallest batch size to limit token spend."""
        free_batch = PRESETS["free"].batch_size
        for name, preset in PRESETS.items():
            if name == "custom":
                continue
            assert free_batch <= preset.batch_size, (
                f"free batch_size ({free_batch}) should be <= {name} ({preset.batch_size})"
            )

    def test_budget_preset_uses_strict_prefilter(self):
        """Budget tier keeps strict prefilter enabled."""
        preset = PRESETS["budget"]
        assert preset.prefilter_strategy == "strict"

    def test_quality_preset_uses_moderate_prefilter(self):
        """Quality tier allows moderate prefilter — more accurate, slightly higher cost."""
        preset = PRESETS["quality"]
        assert preset.prefilter_strategy == "moderate"

    def test_private_preset_uses_strict_prefilter(self):
        """Private tier uses strict prefilter to reduce API calls."""
        preset = PRESETS["private"]
        assert preset.prefilter_strategy == "strict"

    def test_non_custom_presets_have_positive_batch_size(self):
        """All non-custom presets define a positive batch size."""
        for name, preset in PRESETS.items():
            if name == "custom":
                continue
            assert preset.batch_size > 0, f"{name} preset has batch_size <= 0"

    def test_apply_preset_updates_settings_prefilter(self):
        """apply_preset() propagates prefilter_strategy to runtime settings."""
        from career_os.config import settings

        apply_preset("quality")
        assert settings.prefilter_strategy == "moderate"

        # Reset to default
        apply_preset("budget")
        assert settings.prefilter_strategy == "strict"

    def test_custom_preset_has_zero_batch_size(self):
        """Custom preset batch_size is 0 — user configures everything."""
        preset = PRESETS["custom"]
        assert preset.batch_size == 0


# ---------------------------------------------------------------------------
# Batch size limits — BATCH_SCORING_SIZE controls prompt size
# ---------------------------------------------------------------------------


class TestBatchSizeLimits:
    """get_batch_size() reads env var and enforces floor."""

    def test_default_batch_size_when_env_unset(self):
        """Without env var, default batch size is used."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BATCH_SCORING_SIZE", None)
            size = get_batch_size()
        assert size == DEFAULT_BATCH_SIZE

    def test_env_var_overrides_batch_size(self):
        """BATCH_SCORING_SIZE env var sets the batch size."""
        with patch.dict(os.environ, {"BATCH_SCORING_SIZE": "3"}):
            size = get_batch_size()
        assert size == 3

    def test_batch_size_zero_falls_back_to_default(self):
        """BATCH_SCORING_SIZE=0 is invalid; falls back to DEFAULT_BATCH_SIZE."""
        with patch.dict(os.environ, {"BATCH_SCORING_SIZE": "0"}):
            size = get_batch_size()
        assert size == DEFAULT_BATCH_SIZE

    def test_batch_size_negative_falls_back_to_default(self):
        """Negative BATCH_SCORING_SIZE is invalid; falls back to DEFAULT_BATCH_SIZE."""
        with patch.dict(os.environ, {"BATCH_SCORING_SIZE": "-5"}):
            size = get_batch_size()
        assert size == DEFAULT_BATCH_SIZE

    def test_batch_size_non_integer_falls_back_to_default(self):
        """Non-integer BATCH_SCORING_SIZE falls back to DEFAULT_BATCH_SIZE."""
        with patch.dict(os.environ, {"BATCH_SCORING_SIZE": "abc"}):
            size = get_batch_size()
        assert size == DEFAULT_BATCH_SIZE

    def test_chunk_jobs_respects_batch_size(self):
        """chunk_jobs() splits jobs into batches no larger than batch_size."""
        jobs = [{"id": i, "description": f"job {i}"} for i in range(25)]
        batches = chunk_jobs(jobs, batch_size=10)
        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    def test_chunk_jobs_single_batch_when_under_limit(self):
        """If jobs < batch_size, a single batch is returned."""
        jobs = [{"id": i, "description": f"job {i}"} for i in range(5)]
        batches = chunk_jobs(jobs, batch_size=10)
        assert len(batches) == 1
        assert len(batches[0]) == 5

    @pytest.mark.asyncio
    async def test_batch_score_uses_configured_batch_size(self):
        """batch_score_jobs() uses the batch_size parameter to limit prompt size."""
        provider = MockProvider()
        # 12 jobs scored with batch_size=5 → 3 batches (5 + 5 + 2)
        jobs = [{"id": i, "description": f"Software engineer job {i}"} for i in range(12)]
        profile = {"name": "Test User", "skills": ["Python"]}

        # Patch build_batch_prompt to count how many jobs each batch receives
        original_calls: list[int] = []
        from career_os.services import batch_scoring as bs_module

        original_build = bs_module.build_batch_prompt

        def tracking_build(jobs_arg, profile_arg):
            original_calls.append(len(jobs_arg))
            return original_build(jobs_arg, profile_arg)

        with patch.object(bs_module, "build_batch_prompt", side_effect=tracking_build):
            await batch_score_jobs(provider, jobs, profile, batch_size=5)

        assert len(original_calls) == 3
        assert original_calls[0] == 5
        assert original_calls[1] == 5
        assert original_calls[2] == 2


# ---------------------------------------------------------------------------
# Pre-filter reduces AI calls
# ---------------------------------------------------------------------------


class TestPrefilterReducesAICalls:
    """Pre-filter eliminates irrelevant jobs before AI scoring."""

    def _make_jobs(self, titles_descriptions: list[tuple[str, str]]) -> list[dict]:
        return [
            {"id": i, "title": t, "description": d, "industry": ""}
            for i, (t, d) in enumerate(titles_descriptions)
        ]

    def test_strict_mode_eliminates_unrelated_jobs(self):
        """Strict prefilter removes jobs without title or skill match."""
        config = PrefilterConfig(
            strategy=PrefilterStrategy.STRICT,
            title_keywords=["engineer", "developer"],
            skill_keywords=["python", "fastapi", "sql"],
            min_skill_matches=2,
            blacklist_industries=[],
        )
        jobs = self._make_jobs(
            [
                ("Senior Python Engineer", "Python fastapi development role"),  # passes
                ("Marketing Manager", "Build brand awareness campaigns"),  # filtered
                ("Sales Executive", "Drive revenue and customer acquisition"),  # filtered
                ("Backend Developer", "SQL database design and python"),  # passes
            ]
        )
        passed, metrics = run_prefilter(jobs, config)

        assert len(passed) == 2
        assert metrics.filtered == 2
        assert metrics.filter_rate == 50.0

    def test_off_mode_passes_all_jobs(self):
        """Strategy=off disables filtering — all jobs reach AI scoring."""
        config = PrefilterConfig(
            strategy=PrefilterStrategy.OFF,
            title_keywords=["engineer"],
            skill_keywords=["python"],
        )
        jobs = self._make_jobs(
            [
                ("Marketing Manager", "No tech content whatsoever"),
                ("Sales Director", "Revenue growth"),
                ("Python Engineer", "Python fastapi"),
            ]
        )
        passed, metrics = run_prefilter(jobs, config)

        assert len(passed) == 3
        assert metrics.filtered == 0
        assert metrics.filter_rate == 0.0

    def test_strict_mode_blocks_blacklisted_industry(self):
        """Strict mode rejects jobs in blacklisted industries even if title matches."""
        config = PrefilterConfig(
            strategy=PrefilterStrategy.STRICT,
            title_keywords=["engineer"],
            skill_keywords=["python"],
            min_skill_matches=1,
            blacklist_industries=["gambling"],
        )
        jobs = [
            {
                "id": 0,
                "title": "Senior Python Engineer",
                "description": "Python backend development",
                "industry": "Gambling",
            },
            {
                "id": 1,
                "title": "Python Engineer",
                "description": "Python development",
                "industry": "Fintech",
            },
        ]
        passed, metrics = run_prefilter(jobs, config)

        assert len(passed) == 1
        assert passed[0]["id"] == 1
        assert metrics.industry_rejections == 1

    def test_moderate_mode_ignores_blacklist(self):
        """Moderate mode does not apply industry blacklist."""
        config = PrefilterConfig(
            strategy=PrefilterStrategy.MODERATE,
            title_keywords=["engineer"],
            skill_keywords=["python"],
            min_skill_matches=1,
            blacklist_industries=["gambling"],
        )
        jobs = [
            {
                "id": 0,
                "title": "Python Engineer",
                "description": "Python development",
                "industry": "Gambling",
            },
        ]
        passed, _ = run_prefilter(jobs, config)
        assert len(passed) == 1

    def test_prefilter_metrics_tracks_filter_rate(self):
        """Metrics accurately reflect what was filtered.

        In strict mode: (title match OR skill density) AND NOT blacklisted.
        A title match alone is sufficient to pass — no skill requirement.
        """
        config = PrefilterConfig(
            strategy=PrefilterStrategy.STRICT,
            title_keywords=["engineer"],
            skill_keywords=["python", "sql"],
            min_skill_matches=2,
        )
        jobs = self._make_jobs(
            [
                ("Engineer", "python sql database"),  # passes — title match
                ("Engineer", "python only"),  # passes — title match (title OR skills)
                ("Designer", "photoshop ux"),  # filtered — no title or skill match
            ]
        )
        passed, metrics = run_prefilter(jobs, config)

        assert metrics.total == 3
        assert metrics.passed == 2
        assert metrics.filtered == 1
        assert abs(metrics.filter_rate - 33.3) < 0.1


# ---------------------------------------------------------------------------
# Token usage tracking
# ---------------------------------------------------------------------------


class TestTokenUsageTracking:
    """AIResponse.usage captures token counts from provider responses."""

    def test_token_usage_model_has_correct_fields(self):
        """TokenUsage tracks input, output, and cache tokens."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=150,
        )
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_creation_input_tokens == 200
        assert usage.cache_read_input_tokens == 150

    def test_token_usage_defaults_to_zero(self):
        """TokenUsage fields default to 0 (not None)."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_creation_input_tokens == 0
        assert usage.cache_read_input_tokens == 0

    def test_ai_response_accepts_token_usage(self):
        """AIResponse.usage field accepts a TokenUsage instance."""
        usage = TokenUsage(input_tokens=500, output_tokens=200)
        response = AIResponse(
            content="test",
            provider="mock",
            feature=AIFeature.score,
            model="mock-v1",
            usage=usage,
        )
        assert response.usage is not None
        assert response.usage.input_tokens == 500
        assert response.usage.output_tokens == 200

    def test_ai_response_usage_is_none_by_default(self):
        """AIResponse.usage is None by default (cache hit path)."""
        response = AIResponse(
            content="test",
            provider="mock",
            feature=AIFeature.complete,
            model="mock-v1",
        )
        assert response.usage is None

    @pytest.mark.asyncio
    async def test_mock_provider_returns_response_without_usage(self):
        """MockProvider returns valid AIResponse (usage=None — no real token cost)."""
        provider = MockProvider()
        response = await provider.complete("test prompt", feature=AIFeature.complete)
        # Mock provider doesn't simulate token billing — usage is None or absent
        assert isinstance(response, AIResponse)
        assert response.provider == "mock"


# ---------------------------------------------------------------------------
# Provider fallback preserves cost controls
# ---------------------------------------------------------------------------


class TestFallbackPreservesCostControls:
    """FallbackProvider retries next provider without bypassing cost controls."""

    @pytest.mark.asyncio
    async def test_fallback_uses_next_provider_on_quota_error(self):
        """On ProviderQuotaError, FallbackProvider moves to next provider."""
        primary = AsyncMock(spec=MockProvider)
        primary.name = "primary"
        primary.complete.side_effect = ProviderQuotaError("primary", 402)

        secondary = MockProvider()
        fallback = FallbackProvider([primary, secondary])

        response = await fallback.complete("test prompt", feature=AIFeature.complete)
        assert response.provider == "mock"
        primary.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_raises_when_all_providers_fail(self):
        """If all providers fail with quota errors, re-raises the last error."""
        primary = AsyncMock(spec=MockProvider)
        primary.name = "primary"
        primary.complete.side_effect = ProviderQuotaError("primary", 402)

        secondary = AsyncMock(spec=MockProvider)
        secondary.name = "secondary"
        secondary.complete.side_effect = ProviderQuotaError("secondary", 429)

        fallback = FallbackProvider([primary, secondary])

        with pytest.raises(ProviderQuotaError):
            await fallback.complete("test prompt", feature=AIFeature.complete)

    @pytest.mark.asyncio
    async def test_fallback_does_not_bypass_prefilter_settings(self):
        """Switching providers in a fallback chain does not change prefilter_strategy."""
        from career_os.config import settings

        apply_preset("budget")  # sets strict prefilter
        strategy_before = settings.prefilter_strategy

        primary = AsyncMock(spec=MockProvider)
        primary.name = "primary"
        primary.complete.side_effect = ProviderQuotaError("primary", 429)

        secondary = MockProvider()
        fallback = FallbackProvider([primary, secondary])

        await fallback.complete("test prompt", feature=AIFeature.complete)

        # Prefilter strategy must not have changed after provider fallback
        assert settings.prefilter_strategy == strategy_before

    @pytest.mark.asyncio
    async def test_fallback_score_uses_secondary_on_timeout(self):
        """FallbackProvider.score() also falls back on TimeoutException."""
        import httpx

        primary = AsyncMock(spec=MockProvider)
        primary.name = "primary"
        primary.score.side_effect = httpx.TimeoutException("timed out")

        secondary = MockProvider()
        fallback = FallbackProvider([primary, secondary])

        response = await fallback.score("job description text", {"name": "User"})
        assert response.provider == "mock"
        primary.score.assert_called_once()

    def test_fallback_provider_name_lists_chain(self):
        """FallbackProvider.name describes the chain it holds."""
        p1 = MockProvider()
        p2 = MockProvider()
        fallback = FallbackProvider([p1, p2])
        assert "mock" in fallback.name

    def test_fallback_requires_at_least_one_provider(self):
        """FallbackProvider raises ValueError on empty chain."""
        with pytest.raises(ValueError, match="at least one provider"):
            FallbackProvider([])
