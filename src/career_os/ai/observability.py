"""Langfuse observability integration and local token usage logging.

Provides conditional instrumentation that activates only when:
1. The ``langfuse`` package is installed (``pip install kestrel-app[observability]``)
2. ``LANGFUSE_PUBLIC_KEY`` is set in the environment

When either condition is not met, all exports are no-ops — zero overhead.

Also provides ``log_usage()`` for local SQLite token usage logging (always active).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from career_os.schemas.ai import AIFeature, TokenUsage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detect availability
# ---------------------------------------------------------------------------

_langfuse_available = False
_langfuse_configured = False

try:
    import langfuse as _langfuse_mod  # noqa: F401

    _langfuse_available = True
except ImportError:
    pass

if _langfuse_available and os.getenv("LANGFUSE_PUBLIC_KEY"):
    _langfuse_configured = True
    logger.info("Langfuse observability enabled (LANGFUSE_PUBLIC_KEY set)")
else:
    if _langfuse_available:
        logger.debug("Langfuse installed but LANGFUSE_PUBLIC_KEY not set — observability disabled")
    else:
        logger.debug("Langfuse not installed — observability disabled")


def is_enabled() -> bool:
    """Return True if Langfuse instrumentation is active."""
    return _langfuse_configured


# ---------------------------------------------------------------------------
# observe() decorator — wraps provider methods
# ---------------------------------------------------------------------------


def observe(*, name: str | None = None, as_type: str | None = None) -> Callable:
    """Decorator that wraps a function with Langfuse ``@observe``.

    Falls back to a no-op passthrough when Langfuse is not available or
    not configured.

    Args:
        name: Observation name (defaults to function name).
        as_type: Observation type — ``"generation"`` for LLM calls,
                 ``None`` for spans.
    """
    if not _langfuse_configured:

        def _noop_decorator(fn: Callable) -> Callable:
            return fn

        return _noop_decorator

    from langfuse import observe as _lf_observe

    def _decorator(fn: Callable) -> Callable:
        kwargs: dict[str, Any] = {}
        if name is not None:
            kwargs["name"] = name
        if as_type is not None:
            kwargs["as_type"] = as_type
        return _lf_observe(**kwargs)(fn)

    return _decorator


# ---------------------------------------------------------------------------
# update_current_generation() — report model/usage/IO to Langfuse
# ---------------------------------------------------------------------------


def update_current_generation(**kwargs: Any) -> None:
    """Update the current Langfuse generation with model, usage, and IO data.

    No-op when Langfuse is not configured. Safe to call unconditionally.

    Common kwargs:
        model: str — model identifier
        input: Any — prompt/messages sent to the LLM
        output: Any — response content
        usage_details: dict — token counts (input, output, cache_read_input_tokens, etc.)
        metadata: dict — arbitrary key-value pairs
    """
    if not _langfuse_configured:
        return
    from langfuse import get_client

    try:
        get_client().update_current_generation(**kwargs)
    except Exception:
        logger.debug("Failed to update Langfuse generation", exc_info=True)


# ---------------------------------------------------------------------------
# update_current_span() — report metadata on non-generation spans
# ---------------------------------------------------------------------------


def update_current_span(**kwargs: Any) -> None:
    """Update the current Langfuse span with metadata.

    No-op when Langfuse is not configured. Used by cache/PII layers.
    """
    if not _langfuse_configured:
        return
    from langfuse import get_client

    try:
        get_client().update_current_span(**kwargs)
    except Exception:
        logger.debug("Failed to update Langfuse span", exc_info=True)


# ---------------------------------------------------------------------------
# propagate_attributes() — inject user/session/metadata context
# ---------------------------------------------------------------------------


@contextmanager
def propagate_attributes(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> Generator[None, None, None]:
    """Context manager to propagate trace attributes to all child observations.

    No-op when Langfuse is not configured.

    Args:
        user_id: Profile ID for user-scoped traces.
        session_id: Session identifier for grouping traces.
        tags: List of string tags for filtering.
        metadata: Arbitrary key-value metadata dict.
    """
    if not _langfuse_configured:
        yield
        return

    from langfuse import propagate_attributes as _lf_propagate

    kwargs: dict[str, Any] = {}
    if user_id is not None:
        kwargs["user_id"] = user_id
    if session_id is not None:
        kwargs["session_id"] = session_id
    if tags is not None:
        kwargs["tags"] = tags
    if metadata is not None:
        kwargs["metadata"] = metadata

    with _lf_propagate(**kwargs):
        yield


# ---------------------------------------------------------------------------
# flush() — drain pending events on shutdown
# ---------------------------------------------------------------------------


def flush() -> None:
    """Flush any pending Langfuse events. Call during application shutdown."""
    if not _langfuse_configured:
        return
    from langfuse import get_client

    try:
        get_client().flush()
        logger.info("Langfuse client flushed")
    except Exception:
        logger.warning("Failed to flush Langfuse client", exc_info=True)


# ---------------------------------------------------------------------------
# log_usage() — local SQLite token usage logging (always active)
# ---------------------------------------------------------------------------

# Approximate pricing per million tokens (input/output) as of 2026-04.
# Used for cost estimation only — not billing.
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input $/MTok, output $/MTok)
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
    "anthropic/claude-opus-4": (15.0, 75.0),
    "anthropic/claude-sonnet-4": (3.0, 15.0),
    "anthropic/claude-haiku-4-5": (0.80, 4.0),
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": (0.88, 0.88),
}
_DEFAULT_PRICING = (3.0, 15.0)  # Sonnet-class fallback


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate USD cost from token counts and model pricing."""
    input_rate, output_rate = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def log_usage(
    *,
    provider: str,
    model: str | None,
    feature: AIFeature,
    usage: TokenUsage | None,
) -> None:
    """Log AI call token usage to SQLite (fire-and-forget).

    Runs the DB write in a background task so it never blocks the AI call.
    Safe to call from any async context.
    """
    if usage is None:
        return

    def _write_sync() -> None:
        try:
            from career_os.database import SessionLocal
            from career_os.models.ai_usage import AIUsageLog

            cost = _estimate_cost(
                model or "unknown",
                usage.input_tokens,
                usage.output_tokens,
            )
            db = SessionLocal()
            try:
                db.add(
                    AIUsageLog(
                        provider=provider,
                        model=model or "unknown",
                        feature=feature.value,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cache_read_tokens=usage.cache_read_input_tokens,
                        cache_creation_tokens=usage.cache_creation_input_tokens,
                        estimated_cost_usd=cost,
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            logger.debug("Failed to log AI usage", exc_info=True)

    # Fire-and-forget in thread pool to avoid blocking the async call
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _write_sync)
    except RuntimeError:
        # No running loop (CLI or test context) — run synchronously
        _write_sync()
