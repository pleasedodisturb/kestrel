"""SQLite-based response caching for AI providers.

Wraps any AIProvider to transparently cache complete() and score() results,
keyed by a SHA-256 digest of the request parameters.  Storage is a single
SQLite table using stdlib sqlite3 (no async driver needed — cache I/O is
fast local disk).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from career_os.ai.base import AIProvider
from career_os.schemas.ai import AIFeature, AIResponse

# Default cache lifetime: 7 days in seconds.
_DEFAULT_TTL_SECONDS: float = 7 * 24 * 60 * 60

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_cache (
    key         TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    feature     TEXT NOT NULL,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL
)
"""


def _cache_key(feature: str, prompt: str, context: dict | None) -> str:
    """Deterministic SHA-256 cache key from request parameters."""
    ctx_str = json.dumps(context, sort_keys=True) if context is not None else ""
    raw = f"{feature}\x00{prompt}\x00{ctx_str}"
    return hashlib.sha256(raw.encode()).hexdigest()


class CachedProvider(AIProvider):
    """Transparent caching wrapper around any :class:`AIProvider`.

    Parameters
    ----------
    inner:
        The real provider to delegate to on cache misses.
    db_path:
        Path to the SQLite database file.  Created automatically if absent.
    ttl:
        Cache entry lifetime in seconds (default 7 days).
    """

    def __init__(
        self,
        inner: AIProvider,
        db_path: str | Path = "data/ai_cache.db",
        ttl: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._inner = inner
        self._db_path = str(db_path)
        self._ttl = ttl

        # Ensure parent directory exists so sqlite3.connect doesn't fail.
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()

        # Internal counters for stats.
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:  # pragma: no cover – trivial delegation
        return self._inner.name

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        **kwargs: object,
    ) -> AIResponse:
        key = _cache_key(feature.value, prompt, context)
        cached = self._get(key)
        if cached is not None:
            self._hits += 1
            return cached

        self._misses += 1
        response = await self._inner.complete(prompt, feature=feature, context=context, **kwargs)
        self._put(key, response, feature.value)
        return response

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        feature = AIFeature.score
        key = _cache_key(feature.value, job_description, profile_data)
        cached = self._get(key)
        if cached is not None:
            self._hits += 1
            return cached

        self._misses += 1
        response = await self._inner.score(job_description, profile_data, **kwargs)
        self._put(key, response, feature.value)
        return response

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get(self, key: str) -> AIResponse | None:
        """Return cached response if present and not expired."""
        row = self._conn.execute(
            "SELECT response_json FROM ai_cache WHERE key = ? AND expires_at > ?",
            (key, time.time()),
        ).fetchone()
        if row is None:
            return None
        return AIResponse.model_validate_json(row[0])

    def _put(self, key: str, response: AIResponse, feature: str) -> None:
        """Insert or replace a cache entry."""
        now = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, response_json, feature, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (key, response.model_dump_json(), feature, now, now + self._ttl),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public cache management
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        """Return cache statistics."""
        total = self._conn.execute("SELECT COUNT(*) FROM ai_cache").fetchone()[0]
        return {"total": total, "hits": self._hits, "misses": self._misses}

    def clear(self) -> None:
        """Delete all cache entries."""
        self._conn.execute("DELETE FROM ai_cache")
        self._conn.commit()

    def cleanup_expired(self) -> int:
        """Remove expired entries and return the number deleted."""
        cur = self._conn.execute(
            "DELETE FROM ai_cache WHERE expires_at <= ?", (time.time(),)
        )
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
