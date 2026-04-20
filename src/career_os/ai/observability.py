"""Langfuse observability integration for AI providers.

Provides conditional instrumentation that activates only when:
1. The ``langfuse`` package is installed (``pip install kestrel-app[observability]``)
2. ``LANGFUSE_PUBLIC_KEY`` is set in the environment

When either condition is not met, all exports are no-ops — zero overhead.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

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
