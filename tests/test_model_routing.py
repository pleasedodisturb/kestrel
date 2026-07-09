"""Tests for task-based model routing with ComplexityTier.

Covers:
- ComplexityTier enum values and membership
- Provider model selection per tier (Anthropic, OpenRouter)
- Default tier behaviour (None -> STANDARD)
- Env-var model override takes precedence over tier
- FEATURE_TIER_MAP completeness (all AIFeature members covered)
- CachedProvider and MaskedProvider pass tier through
- MockProvider and OllamaProvider accept tier without error
"""

import pytest

from career_os.ai.base import ComplexityTier
from career_os.ai.mock_provider import MockProvider
from career_os.schemas.ai import AIFeature, get_feature_tier_map

# ---------------------------------------------------------------------------
# ComplexityTier enum
# ---------------------------------------------------------------------------


class TestComplexityTier:
    """ComplexityTier enum basics."""

    def test_values(self):
        assert ComplexityTier.SIMPLE == "simple"
        assert ComplexityTier.STANDARD == "standard"
        assert ComplexityTier.COMPLEX == "complex"

    def test_member_count(self):
        assert len(ComplexityTier) == 3

    def test_str_enum(self):
        """ComplexityTier members are strings (StrEnum)."""
        assert isinstance(ComplexityTier.SIMPLE, str)

    def test_from_value(self):
        assert ComplexityTier("simple") is ComplexityTier.SIMPLE
        assert ComplexityTier("standard") is ComplexityTier.STANDARD
        assert ComplexityTier("complex") is ComplexityTier.COMPLEX


# ---------------------------------------------------------------------------
# Anthropic provider model routing
# ---------------------------------------------------------------------------


class TestAnthropicProviderRouting:
    """AnthropicProvider._resolve_model selects the right model per tier."""

    def _make_provider(self, model: str | None = None):
        from career_os.ai.anthropic_provider import DEFAULT_MODEL, AnthropicProvider

        return AnthropicProvider(
            api_key="sk-ant-test-key",
            model=model or DEFAULT_MODEL,
        )

    def test_simple_tier(self):
        provider = self._make_provider()
        assert provider._resolve_model(ComplexityTier.SIMPLE) == "claude-haiku-4-5-20251001"

    def test_standard_tier(self):
        provider = self._make_provider()
        assert provider._resolve_model(ComplexityTier.STANDARD) == "claude-sonnet-5"

    def test_complex_tier(self):
        provider = self._make_provider()
        assert provider._resolve_model(ComplexityTier.COMPLEX) == "claude-opus-4-8"

    def test_none_defaults_to_standard(self):
        provider = self._make_provider()
        assert provider._resolve_model(None) == "claude-sonnet-5"

    def test_env_var_override_wins(self):
        """When an explicit model is set (not the default), tier is ignored."""
        provider = self._make_provider(model="claude-custom-model")
        # Even with SIMPLE tier, the custom model should be returned
        assert provider._resolve_model(ComplexityTier.SIMPLE) == "claude-custom-model"
        assert provider._resolve_model(ComplexityTier.COMPLEX) == "claude-custom-model"
        assert provider._resolve_model(None) == "claude-custom-model"


# ---------------------------------------------------------------------------
# OpenRouter provider model routing
# ---------------------------------------------------------------------------


class TestOpenRouterProviderRouting:
    """OpenRouterProvider._resolve_model selects the right model per tier."""

    def _make_provider(self, model: str | None = None):
        from career_os.ai.openrouter_provider import DEFAULT_MODEL, OpenRouterProvider

        return OpenRouterProvider(
            api_key="or-test-key",
            model=model or DEFAULT_MODEL,
        )

    def test_simple_tier(self):
        provider = self._make_provider()
        assert provider._resolve_model(ComplexityTier.SIMPLE) == "anthropic/claude-haiku-4-5"

    def test_standard_tier(self):
        provider = self._make_provider()
        assert provider._resolve_model(ComplexityTier.STANDARD) == "anthropic/claude-sonnet-5"

    def test_complex_tier(self):
        provider = self._make_provider()
        assert provider._resolve_model(ComplexityTier.COMPLEX) == "anthropic/claude-opus-4.8"

    def test_none_defaults_to_standard(self):
        provider = self._make_provider()
        assert provider._resolve_model(None) == "anthropic/claude-sonnet-5"

    def test_env_var_override_wins(self):
        """When an explicit model is set (not the default), tier is ignored."""
        provider = self._make_provider(model="openai/gpt-4o")
        assert provider._resolve_model(ComplexityTier.SIMPLE) == "openai/gpt-4o"
        assert provider._resolve_model(ComplexityTier.COMPLEX) == "openai/gpt-4o"


# ---------------------------------------------------------------------------
# MockProvider accepts tier without error
# ---------------------------------------------------------------------------


class TestMockProviderTier:
    """MockProvider accepts the tier parameter gracefully."""

    @pytest.mark.asyncio
    async def test_complete_with_tier(self):
        provider = MockProvider()
        response = await provider.complete(
            "Hello", feature=AIFeature.complete, tier=ComplexityTier.SIMPLE
        )
        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_complete_without_tier(self):
        provider = MockProvider()
        response = await provider.complete("Hello", feature=AIFeature.complete)
        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_score_with_tier(self):
        provider = MockProvider()
        response = await provider.score(
            "Job description", {"skills": []}, tier=ComplexityTier.COMPLEX
        )
        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_score_without_tier(self):
        provider = MockProvider()
        response = await provider.score("Job description", {"skills": []})
        assert response.provider == "mock"


# ---------------------------------------------------------------------------
# OllamaProvider accepts tier without error
# ---------------------------------------------------------------------------


class TestOllamaProviderTierSignature:
    """OllamaProvider accepts the tier parameter in its signature."""

    def test_complete_signature_accepts_tier(self):
        """Verify OllamaProvider.complete accepts tier kwarg (no network call)."""
        import inspect

        from career_os.ai.ollama_provider import OllamaProvider

        sig = inspect.signature(OllamaProvider.complete)
        assert "tier" in sig.parameters

    def test_score_signature_accepts_tier(self):
        """Verify OllamaProvider.score accepts tier kwarg (no network call)."""
        import inspect

        from career_os.ai.ollama_provider import OllamaProvider

        sig = inspect.signature(OllamaProvider.score)
        assert "tier" in sig.parameters


# ---------------------------------------------------------------------------
# FEATURE_TIER_MAP completeness
# ---------------------------------------------------------------------------


class TestFeatureTierMap:
    """FEATURE_TIER_MAP covers all AIFeature members."""

    def test_all_features_covered(self):
        tier_map = get_feature_tier_map()
        for feature in AIFeature:
            assert feature in tier_map, f"AIFeature.{feature.name} missing from FEATURE_TIER_MAP"

    def test_values_are_complexity_tiers(self):
        tier_map = get_feature_tier_map()
        for feature, tier in tier_map.items():
            assert isinstance(tier, ComplexityTier), (
                f"FEATURE_TIER_MAP[{feature}] = {tier!r} is not a ComplexityTier"
            )

    def test_simple_features(self):
        """Certain features should be SIMPLE (cheap classification tasks)."""
        tier_map = get_feature_tier_map()
        simple_features = [
            AIFeature.learning_recommendations,
            AIFeature.interview_format,
            AIFeature.interview_patterns,
        ]
        for feature in simple_features:
            assert tier_map[feature] == ComplexityTier.SIMPLE, (
                f"Expected AIFeature.{feature.name} to be SIMPLE"
            )

    def test_standard_features(self):
        """Core features should default to STANDARD."""
        tier_map = get_feature_tier_map()
        standard_features = [
            AIFeature.score,
            AIFeature.gap_analysis,
            AIFeature.coaching,
            AIFeature.complete,
        ]
        for feature in standard_features:
            assert tier_map[feature] == ComplexityTier.STANDARD, (
                f"Expected AIFeature.{feature.name} to be STANDARD"
            )


# ---------------------------------------------------------------------------
# CachedProvider passes tier through
# ---------------------------------------------------------------------------


class TestCachedProviderTier:
    """CachedProvider delegates tier to the inner provider."""

    @pytest.mark.asyncio
    async def test_complete_passes_tier(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from career_os.ai.cache import CachedProvider

        inner = MockProvider()
        cached = CachedProvider(inner, db_path=tmp_path / "test_cache.db")

        with patch.object(inner, "complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = await MockProvider().complete("test")
            await cached.complete("test", tier=ComplexityTier.SIMPLE)
            mock_complete.assert_called_once()
            _, kwargs = mock_complete.call_args
            assert kwargs["tier"] is ComplexityTier.SIMPLE

    @pytest.mark.asyncio
    async def test_score_passes_tier(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from career_os.ai.cache import CachedProvider

        inner = MockProvider()
        cached = CachedProvider(inner, db_path=tmp_path / "test_cache.db")

        with patch.object(inner, "score", new_callable=AsyncMock) as mock_score:
            mock_score.return_value = await MockProvider().score("jd", {})
            await cached.score("jd", {}, tier=ComplexityTier.COMPLEX)
            mock_score.assert_called_once()
            _, kwargs = mock_score.call_args
            assert kwargs["tier"] is ComplexityTier.COMPLEX


# ---------------------------------------------------------------------------
# MaskedProvider passes tier through
# ---------------------------------------------------------------------------


class TestMaskedProviderTier:
    """MaskedProvider delegates tier to the inner provider."""

    @pytest.mark.asyncio
    async def test_complete_passes_tier(self):
        from unittest.mock import AsyncMock, patch

        from career_os.ai.pii_masking import MaskedProvider

        inner = MockProvider()
        masked = MaskedProvider(inner)

        with patch.object(inner, "complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = await MockProvider().complete("test")
            await masked.complete("test", tier=ComplexityTier.COMPLEX)
            mock_complete.assert_called_once()
            _, kwargs = mock_complete.call_args
            assert kwargs["tier"] is ComplexityTier.COMPLEX

    @pytest.mark.asyncio
    async def test_score_passes_tier(self):
        from unittest.mock import AsyncMock, patch

        from career_os.ai.pii_masking import MaskedProvider

        inner = MockProvider()
        masked = MaskedProvider(inner)

        with patch.object(inner, "score", new_callable=AsyncMock) as mock_score:
            mock_score.return_value = await MockProvider().score("jd", {})
            await masked.score("jd", {}, tier=ComplexityTier.SIMPLE)
            mock_score.assert_called_once()
            _, kwargs = mock_score.call_args
            assert kwargs["tier"] is ComplexityTier.SIMPLE


# ---------------------------------------------------------------------------
# Export from package __init__
# ---------------------------------------------------------------------------


class TestPackageExport:
    """ComplexityTier is exported from the ai package."""

    def test_import_from_package(self):
        from career_os.ai import ComplexityTier as CT

        assert CT is ComplexityTier
