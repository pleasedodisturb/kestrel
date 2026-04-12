"""Tests for SQLite-based AI response caching (CachedProvider)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from career_os.ai.base import AIProvider
from career_os.ai.cache import CachedProvider, _cache_key
from career_os.schemas.ai import AIFeature, AIResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(content: str = "hello", feature: AIFeature = AIFeature.complete) -> AIResponse:
    return AIResponse(content=content, provider="mock", feature=feature)


def _mock_provider() -> AIProvider:
    """Return an AsyncMock that satisfies the AIProvider interface."""
    provider = AsyncMock(spec=AIProvider)
    provider.name = "mock"
    provider.complete.return_value = _make_response("complete-result")
    provider.score.return_value = _make_response("score-result", AIFeature.score)
    return provider


# ---------------------------------------------------------------------------
# Key determinism
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_same_inputs_produce_same_key(self):
        k1 = _cache_key("complete", "hello", {"a": 1, "b": 2})
        k2 = _cache_key("complete", "hello", {"b": 2, "a": 1})
        assert k1 == k2

    def test_different_feature_different_key(self):
        k1 = _cache_key("complete", "hello", None)
        k2 = _cache_key("score", "hello", None)
        assert k1 != k2

    def test_different_prompt_different_key(self):
        k1 = _cache_key("complete", "hello", None)
        k2 = _cache_key("complete", "world", None)
        assert k1 != k2

    def test_none_vs_empty_context_different_key(self):
        k1 = _cache_key("complete", "hello", None)
        k2 = _cache_key("complete", "hello", {})
        assert k1 != k2


# ---------------------------------------------------------------------------
# CachedProvider tests
# ---------------------------------------------------------------------------


class TestCachedProvider:
    @pytest.fixture()
    def provider(self, tmp_path):
        inner = _mock_provider()
        cp = CachedProvider(inner, db_path=tmp_path / "cache.db", ttl=60)
        yield cp
        cp.close()

    @pytest.fixture()
    def inner(self, provider):
        return provider._inner

    # -- cache miss --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cache_miss_delegates_to_inner(self, provider, inner):
        resp = await provider.complete("prompt")
        inner.complete.assert_awaited_once()
        assert resp.content == "complete-result"

    # -- cache hit ---------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(self, provider, inner):
        await provider.complete("prompt")
        resp2 = await provider.complete("prompt")
        assert inner.complete.await_count == 1  # only one real call
        assert resp2.content == "complete-result"

    # -- score method ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_score_caches(self, provider, inner):
        r1 = await provider.score("jd", {"skills": ["python"]})
        r2 = await provider.score("jd", {"skills": ["python"]})
        assert inner.score.await_count == 1
        assert r1.content == r2.content == "score-result"

    # -- TTL expiry --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_expired_entry_triggers_new_call(self, tmp_path):
        inner = _mock_provider()
        cp = CachedProvider(inner, db_path=tmp_path / "cache.db", ttl=0.0)
        try:
            await cp.complete("prompt")
            # Entry is immediately expired (ttl=0).
            await cp.complete("prompt")
            assert inner.complete.await_count == 2
        finally:
            cp.close()

    # -- stats -------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stats(self, provider):
        await provider.complete("a")
        await provider.complete("a")  # hit
        await provider.complete("b")  # miss
        stats = provider.get_stats()
        assert stats == {"total": 2, "hits": 1, "misses": 2}

    # -- clear -------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_clear_removes_all_entries(self, provider):
        await provider.complete("a")
        await provider.complete("b")
        assert provider.get_stats()["total"] == 2
        provider.clear()
        assert provider.get_stats()["total"] == 0

    # -- cleanup_expired ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, tmp_path):
        inner = _mock_provider()
        cp = CachedProvider(inner, db_path=tmp_path / "cache.db", ttl=0.0)
        try:
            await cp.complete("x")
            deleted = cp.cleanup_expired()
            assert deleted == 1
            assert cp.get_stats()["total"] == 0
        finally:
            cp.close()

    # -- AIProvider contract -----------------------------------------------

    def test_name_delegates_to_inner(self, provider):
        assert provider.name == "mock"

    def test_is_aiprovider(self, provider):
        assert isinstance(provider, AIProvider)
