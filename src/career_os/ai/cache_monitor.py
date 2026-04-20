"""Cache break detection for Anthropic prompt caching.

Tracks cache hit/miss ratios per AIFeature over a sliding window.
Logs warnings when the cache hit ratio drops below a configurable
threshold, indicating that the cached system prompt prefix is being
invalidated between calls (a "cache break").

Usage:
    from career_os.ai.cache_monitor import record_cache_event, get_cache_stats

    # After each Anthropic response:
    record_cache_event(feature, usage)

    # Query stats:
    stats = get_cache_stats()
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from career_os.schemas.ai import AIFeature, TokenUsage

logger = logging.getLogger(__name__)

# Sliding window size and alert threshold
_WINDOW_SIZE = 100
_ALERT_THRESHOLD = 0.80  # Warn if hit ratio drops below 80%


@dataclass
class _FeatureWindow:
    """Sliding window of cache hit/miss events for a single feature."""

    events: deque[bool] = field(default_factory=lambda: deque(maxlen=_WINDOW_SIZE))
    total_hits: int = 0
    total_misses: int = 0
    alert_fired: bool = False

    @property
    def hit_ratio(self) -> float:
        """Cache hit ratio over the current window (0.0 to 1.0)."""
        if not self.events:
            return 1.0  # No data yet — assume healthy
        return sum(self.events) / len(self.events)

    @property
    def window_size(self) -> int:
        return len(self.events)


# Per-feature sliding windows (module-level state, reset via _reset())
_windows: dict[str, _FeatureWindow] = {}


def record_cache_event(feature: AIFeature, usage: TokenUsage | None) -> None:
    """Record a cache hit or miss from an Anthropic API response.

    A cache **hit** means cache_read_input_tokens > 0.
    A cache **miss** means cache_creation_input_tokens > 0 and
    cache_read_input_tokens == 0.
    Calls with no cache tokens (non-Anthropic providers) are ignored.

    Logs a warning when the hit ratio drops below the alert threshold.
    """
    if usage is None:
        return

    # Only track calls that interacted with the cache system
    has_cache_activity = usage.cache_read_input_tokens > 0 or usage.cache_creation_input_tokens > 0
    if not has_cache_activity:
        return

    is_hit = usage.cache_read_input_tokens > 0
    key = feature.value

    if key not in _windows:
        _windows[key] = _FeatureWindow()

    w = _windows[key]
    w.events.append(is_hit)
    if is_hit:
        w.total_hits += 1
    else:
        w.total_misses += 1

    # Check alert threshold once we have enough data
    if w.window_size >= 10 and w.hit_ratio < _ALERT_THRESHOLD:
        if not w.alert_fired:
            logger.warning(
                "Cache break detected for feature=%s: hit ratio %.0f%% "
                "(threshold %.0f%%, window=%d events, %d hits, %d misses)",
                key,
                w.hit_ratio * 100,
                _ALERT_THRESHOLD * 100,
                w.window_size,
                sum(w.events),
                w.window_size - sum(w.events),
            )
            w.alert_fired = True
    else:
        w.alert_fired = False  # Reset alert when ratio recovers


@dataclass
class CacheStats:
    """Cache statistics for a single feature."""

    feature: str
    hit_ratio: float
    window_size: int
    total_hits: int
    total_misses: int
    alert_active: bool


def get_cache_stats() -> list[CacheStats]:
    """Return cache statistics for all tracked features."""
    return [
        CacheStats(
            feature=key,
            hit_ratio=w.hit_ratio,
            window_size=w.window_size,
            total_hits=w.total_hits,
            total_misses=w.total_misses,
            alert_active=w.alert_fired,
        )
        for key, w in sorted(_windows.items())
    ]


def _reset() -> None:
    """Reset all tracking state (for testing)."""
    _windows.clear()
