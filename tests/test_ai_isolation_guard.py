"""Tests for the AI provider test isolation guard.

Verifies that the autouse `block_real_ai_calls` fixture in conftest.py
intercepts outbound HTTP calls to real AI provider domains and raises a
RuntimeError with a clear diagnostic message, preventing accidental API
charges during test runs.
"""

import os

import httpx
import pytest


@pytest.mark.asyncio
async def test_isolation_guard_blocks_openrouter():
    """Guard must raise RuntimeError on any request to openrouter.ai."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.get("https://openrouter.ai/api/v1/models")


@pytest.mark.asyncio
async def test_isolation_guard_blocks_anthropic():
    """Guard must raise RuntimeError on any request to api.anthropic.com."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.post(
                "https://api.anthropic.com/v1/messages",
                json={"model": "claude-3-haiku-20240307", "messages": []},
            )


@pytest.mark.asyncio
async def test_isolation_guard_blocks_openai():
    """Guard must raise RuntimeError on any request to api.openai.com."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.get("https://api.openai.com/v1/models")


@pytest.mark.asyncio
async def test_isolation_guard_blocks_together():
    """Guard must raise RuntimeError on any request to api.together.xyz."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.get("https://api.together.xyz/v1/models")


@pytest.mark.asyncio
async def test_isolation_guard_blocks_groq():
    """Guard must raise RuntimeError on any request to api.groq.com."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.get("https://api.groq.com/openai/v1/models")


@pytest.mark.asyncio
async def test_isolation_guard_blocks_xai():
    """Guard must raise RuntimeError on any request to api.x.ai."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.get("https://api.x.ai/v1/models")


@pytest.mark.asyncio
async def test_isolation_guard_blocks_gemini():
    """Guard must raise RuntimeError on any request to generativelanguage.googleapis.com."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="TEST ISOLATION VIOLATION"):
            await client.get("https://generativelanguage.googleapis.com/v1beta/models")


@pytest.mark.asyncio
async def test_isolation_guard_error_message_includes_domain():
    """Error message must name the blocked domain for easy diagnosis."""
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError) as exc_info:
            await client.get("https://api.openai.com/v1/models")
    assert "api.openai.com" in str(exc_info.value)


def test_ai_provider_env_is_mock():
    """AI_PROVIDER environment variable must be 'mock' during tests."""
    assert os.environ.get("AI_PROVIDER") == "mock", (
        "AI_PROVIDER must be set to 'mock' in conftest.py to prevent real API calls. "
        f"Got: {os.environ.get('AI_PROVIDER')!r}"
    )


@pytest.mark.asyncio
async def test_isolation_guard_allows_non_ai_domains():
    """Guard must NOT block non-AI domains (e.g. localhost connections)."""
    # We verify this by confirming the guard's RuntimeError is NOT raised.
    # A connection refused error is fine — it means the guard passed through.
    async with httpx.AsyncClient() as client:
        try:
            await client.get("http://localhost:9999/health", timeout=0.1)
        except RuntimeError as exc:
            if "TEST ISOLATION VIOLATION" in str(exc):
                pytest.fail(f"Guard incorrectly blocked a non-AI domain: {exc}")
        except Exception:
            # Any other error (ConnectError, TimeoutError, etc.) is expected
            # for a non-existent local server — that's fine.
            pass
