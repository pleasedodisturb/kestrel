"""Tests for cache break detection (G-427).

Covers:
- record_cache_event() tracks hits and misses
- Hit ratio computed correctly over sliding window
- Warning logged when ratio drops below threshold
- No alert on healthy cache usage
- Events without cache activity are ignored
- get_cache_stats() returns per-feature data
"""

import logging

import pytest

from career_os.ai.cache_monitor import (
    _WINDOW_SIZE,
    _reset,
    get_cache_stats,
    record_cache_event,
)
from career_os.schemas.ai import AIFeature, TokenUsage


@pytest.fixture(autouse=True)
def reset_monitor():
    """Reset cache monitor state between tests."""
    _reset()
    yield
    _reset()


def _hit_usage(read_tokens: int = 500) -> TokenUsage:
    """Create a TokenUsage representing a cache hit."""
    return TokenUsage(
        input_tokens=100,
        output_tokens=200,
        cache_read_input_tokens=read_tokens,
        cache_creation_input_tokens=0,
    )


def _miss_usage(creation_tokens: int = 500) -> TokenUsage:
    """Create a TokenUsage representing a cache miss (new creation)."""
    return TokenUsage(
        input_tokens=600,
        output_tokens=200,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=creation_tokens,
    )


def _no_cache_usage() -> TokenUsage:
    """Create a TokenUsage with no cache activity (non-Anthropic provider)."""
    return TokenUsage(
        input_tokens=500,
        output_tokens=200,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )


class TestRecordCacheEvent:
    """record_cache_event() correctly categorizes hits and misses."""

    def test_hit_increments_counter(self) -> None:
        record_cache_event(AIFeature.score, _hit_usage())
        stats = get_cache_stats()
        assert len(stats) == 1
        assert stats[0].total_hits == 1
        assert stats[0].total_misses == 0

    def test_miss_increments_counter(self) -> None:
        record_cache_event(AIFeature.score, _miss_usage())
        stats = get_cache_stats()
        assert stats[0].total_hits == 0
        assert stats[0].total_misses == 1

    def test_ignores_none_usage(self) -> None:
        record_cache_event(AIFeature.score, None)
        assert get_cache_stats() == []

    def test_ignores_no_cache_activity(self) -> None:
        record_cache_event(AIFeature.score, _no_cache_usage())
        assert get_cache_stats() == []

    def test_tracks_per_feature(self) -> None:
        record_cache_event(AIFeature.score, _hit_usage())
        record_cache_event(AIFeature.gap_analysis, _miss_usage())
        stats = get_cache_stats()
        assert len(stats) == 2
        score_stats = next(s for s in stats if s.feature == "score")
        gap_stats = next(s for s in stats if s.feature == "gap_analysis")
        assert score_stats.total_hits == 1
        assert gap_stats.total_misses == 1


class TestHitRatio:
    """Hit ratio is computed correctly over the sliding window."""

    def test_all_hits_ratio_is_one(self) -> None:
        for _ in range(20):
            record_cache_event(AIFeature.score, _hit_usage())
        stats = get_cache_stats()
        assert stats[0].hit_ratio == pytest.approx(1.0)

    def test_all_misses_ratio_is_zero(self) -> None:
        for _ in range(20):
            record_cache_event(AIFeature.score, _miss_usage())
        stats = get_cache_stats()
        assert stats[0].hit_ratio == pytest.approx(0.0)

    def test_mixed_ratio(self) -> None:
        # 8 hits + 2 misses = 80% hit ratio
        for _ in range(8):
            record_cache_event(AIFeature.score, _hit_usage())
        for _ in range(2):
            record_cache_event(AIFeature.score, _miss_usage())
        stats = get_cache_stats()
        assert stats[0].hit_ratio == pytest.approx(0.8)

    def test_window_size_limit(self) -> None:
        # Fill window with hits, then add misses beyond window size
        for _ in range(_WINDOW_SIZE):
            record_cache_event(AIFeature.score, _hit_usage())
        stats = get_cache_stats()
        assert stats[0].window_size == _WINDOW_SIZE


class TestCacheBreakAlert:
    """Warning logged when cache hit ratio drops below threshold."""

    def test_alert_fires_below_threshold(self, caplog) -> None:
        """Warning logged when hit ratio drops below 80%."""
        # 10 events: 5 hits + 5 misses = 50% (below 80% threshold)
        for _ in range(5):
            record_cache_event(AIFeature.score, _hit_usage())
        with caplog.at_level(logging.WARNING, logger="career_os.ai.cache_monitor"):
            for _ in range(5):
                record_cache_event(AIFeature.score, _miss_usage())

        assert "Cache break detected" in caplog.text
        assert "feature=score" in caplog.text
        stats = get_cache_stats()
        assert stats[0].alert_active is True

    def test_no_alert_above_threshold(self, caplog) -> None:
        """No warning when hit ratio is healthy."""
        # 9 hits + 1 miss = 90% (above 80% threshold)
        for _ in range(9):
            record_cache_event(AIFeature.score, _hit_usage())
        with caplog.at_level(logging.WARNING, logger="career_os.ai.cache_monitor"):
            record_cache_event(AIFeature.score, _miss_usage())

        assert "Cache break detected" not in caplog.text

    def test_no_alert_with_insufficient_data(self, caplog) -> None:
        """No alert when window has < 10 events (not enough data)."""
        # 5 events all misses — but too few for alert
        with caplog.at_level(logging.WARNING, logger="career_os.ai.cache_monitor"):
            for _ in range(5):
                record_cache_event(AIFeature.score, _miss_usage())

        assert "Cache break detected" not in caplog.text

    def test_alert_resets_when_ratio_recovers(self) -> None:
        """Alert clears when ratio goes back above threshold."""
        # Drop below threshold
        for _ in range(5):
            record_cache_event(AIFeature.score, _hit_usage())
        for _ in range(5):
            record_cache_event(AIFeature.score, _miss_usage())

        stats = get_cache_stats()
        assert stats[0].alert_active is True

        # Recover with lots of hits
        for _ in range(20):
            record_cache_event(AIFeature.score, _hit_usage())

        stats = get_cache_stats()
        assert stats[0].alert_active is False
