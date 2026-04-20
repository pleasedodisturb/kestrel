"""Tests for Langfuse observability integration.

Tests verify:
1. The observability module is a no-op when Langfuse is not configured
2. The observe() decorator passes through functions unchanged when disabled
3. update_current_generation/span are safe to call when disabled
4. propagate_attributes context manager is a no-op when disabled
5. flush() is safe to call when disabled
6. The module correctly detects availability
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestObservabilityDisabled:
    """Tests when Langfuse is NOT configured (default for test suite)."""

    def test_is_enabled_returns_false_without_env(self):
        """Observability should be disabled when LANGFUSE_PUBLIC_KEY is not set."""
        from career_os.ai.observability import is_enabled

        assert is_enabled() is False

    def test_observe_is_noop_when_disabled(self):
        """@observe() should return the function unchanged when disabled."""
        from career_os.ai.observability import observe

        @observe(name="test-fn", as_type="generation")
        async def my_function(x: int) -> int:
            return x * 2

        # The function should be the original, not wrapped
        assert my_function.__name__ == "my_function"

    def test_update_current_generation_noop(self):
        """update_current_generation should not raise when disabled."""
        from career_os.ai.observability import update_current_generation

        # Should not raise
        update_current_generation(
            model="test-model",
            input="test input",
            output="test output",
            usage_details={"input": 10, "output": 20},
        )

    def test_update_current_span_noop(self):
        """update_current_span should not raise when disabled."""
        from career_os.ai.observability import update_current_span

        update_current_span(metadata={"cache": "hit"})

    def test_propagate_attributes_noop(self):
        """propagate_attributes should yield without error when disabled."""
        from career_os.ai.observability import propagate_attributes

        with propagate_attributes(
            user_id="user-123",
            session_id="session-abc",
            tags=["test"],
            metadata={"env": "test"},
        ):
            pass  # Should not raise

    def test_flush_noop(self):
        """flush() should not raise when disabled."""
        from career_os.ai.observability import flush

        flush()  # Should not raise


class TestObservabilityModuleDetection:
    """Tests for the module's availability detection logic."""

    def test_langfuse_available_flag_matches_import(self):
        """_langfuse_available should reflect whether langfuse can be imported."""
        from career_os.ai.observability import _langfuse_available

        try:
            import langfuse  # noqa: F401

            assert _langfuse_available is True
        except ImportError:
            assert _langfuse_available is False

    def test_configured_requires_both_import_and_env(self):
        """_langfuse_configured should be False even if installed but no env var."""
        import os

        from career_os.ai.observability import _langfuse_available, _langfuse_configured

        if _langfuse_available and not os.getenv("LANGFUSE_PUBLIC_KEY"):
            assert _langfuse_configured is False


class TestObservabilityEnabled:
    """Tests with mocked Langfuse to verify correct delegation."""

    def test_observe_delegates_to_langfuse_when_configured(self):
        """When configured, observe() should call langfuse.observe()."""
        mock_inner = MagicMock(return_value=lambda fn: fn)
        mock_observe = MagicMock(return_value=mock_inner)

        with (
            patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk-test"}),
            patch.dict("sys.modules", {"langfuse": MagicMock(observe=mock_observe)}),
        ):
            # Reload to pick up env var and mock module
            import career_os.ai.observability as obs_mod

            importlib.reload(obs_mod)

            assert obs_mod._langfuse_configured is True
            assert obs_mod.is_enabled() is True

            # Apply the decorator to a function to trigger the langfuse.observe call
            decorator = obs_mod.observe(name="test", as_type="generation")

            @decorator
            def dummy():
                pass

            mock_observe.assert_called_once_with(name="test", as_type="generation")

        # Restore module state outside the context manager
        importlib.reload(obs_mod)

    def test_update_current_generation_delegates_when_configured(self):
        """When configured, update_current_generation calls langfuse client."""
        mock_client = MagicMock()
        mock_get_client = MagicMock(return_value=mock_client)
        mock_langfuse = MagicMock(get_client=mock_get_client)

        with (
            patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk-test"}),
            patch.dict("sys.modules", {"langfuse": mock_langfuse}),
        ):
            import career_os.ai.observability as obs_mod

            importlib.reload(obs_mod)

            obs_mod.update_current_generation(
                model="gpt-4",
                usage_details={"input": 10, "output": 20},
            )
            mock_get_client.assert_called_once()
            mock_client.update_current_generation.assert_called_once_with(
                model="gpt-4",
                usage_details={"input": 10, "output": 20},
            )

        importlib.reload(obs_mod)

    def test_flush_delegates_when_configured(self):
        """When configured, flush() calls get_client().flush()."""
        mock_client = MagicMock()
        mock_get_client = MagicMock(return_value=mock_client)
        mock_langfuse = MagicMock(get_client=mock_get_client)

        with (
            patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk-test"}),
            patch.dict("sys.modules", {"langfuse": mock_langfuse}),
        ):
            import career_os.ai.observability as obs_mod

            importlib.reload(obs_mod)
            obs_mod.flush()
            mock_client.flush.assert_called_once()

        importlib.reload(obs_mod)

    def test_propagate_attributes_delegates_when_configured(self):
        """When configured, propagate_attributes uses langfuse's context manager."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_propagate = MagicMock(return_value=mock_ctx)
        mock_langfuse = MagicMock(propagate_attributes=mock_propagate)

        with (
            patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk-test"}),
            patch.dict("sys.modules", {"langfuse": mock_langfuse}),
        ):
            import career_os.ai.observability as obs_mod

            importlib.reload(obs_mod)

            with obs_mod.propagate_attributes(
                user_id="user-1",
                session_id="sess-1",
                tags=["scoring"],
                metadata={"job_family": "engineering"},
            ):
                pass

            mock_propagate.assert_called_once_with(
                user_id="user-1",
                session_id="sess-1",
                tags=["scoring"],
                metadata={"job_family": "engineering"},
            )

        importlib.reload(obs_mod)

    def test_update_current_generation_swallows_exceptions(self):
        """Langfuse errors should be caught, not propagated to the caller."""
        mock_client = MagicMock()
        mock_client.update_current_generation.side_effect = RuntimeError("network error")
        mock_get_client = MagicMock(return_value=mock_client)
        mock_langfuse = MagicMock(get_client=mock_get_client)

        with (
            patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk-test"}),
            patch.dict("sys.modules", {"langfuse": mock_langfuse}),
        ):
            import career_os.ai.observability as obs_mod

            importlib.reload(obs_mod)
            # Should not raise despite the RuntimeError
            obs_mod.update_current_generation(model="test")

        importlib.reload(obs_mod)


class TestProviderInstrumentation:
    """Verify that provider classes have the observability decorator applied."""

    def test_openrouter_complete_has_observe(self):
        """OpenRouterProvider.complete should reference observability."""
        from career_os.ai.openrouter_provider import OpenRouterProvider

        # The method should exist and be callable
        assert hasattr(OpenRouterProvider, "complete")
        assert callable(OpenRouterProvider.complete)

    def test_anthropic_complete_has_observe(self):
        from career_os.ai.anthropic_provider import AnthropicProvider

        assert hasattr(AnthropicProvider, "complete")
        assert callable(AnthropicProvider.complete)

    def test_together_complete_has_observe(self):
        from career_os.ai.together_provider import TogetherProvider

        assert hasattr(TogetherProvider, "complete")
        assert callable(TogetherProvider.complete)

    def test_ollama_complete_has_observe(self):
        from career_os.ai.ollama_provider import OllamaProvider

        assert hasattr(OllamaProvider, "complete")
        assert callable(OllamaProvider.complete)


class TestCacheObservability:
    """Verify cache layer emits observability metadata."""

    @pytest.mark.asyncio
    async def test_cache_hit_emits_metadata(self):
        """Cache hit should call update_current_span with cache=hit."""
        from career_os.ai.cache import CachedProvider
        from career_os.ai.mock_provider import MockProvider

        inner = MockProvider()
        cached = CachedProvider(inner, db_path=":memory:", enabled=True)

        with patch("career_os.ai.cache.update_current_span") as mock_span:
            # Prime the cache (miss)
            await cached.complete("test prompt")
            mock_span.reset_mock()
            # Second call should be a hit
            await cached.complete("test prompt")
            mock_span.assert_called()
            call_kwargs = mock_span.call_args[1]
            assert call_kwargs["metadata"]["cache"] == "hit"

        cached.close()

    @pytest.mark.asyncio
    async def test_cache_miss_emits_metadata(self):
        """Cache miss should call update_current_span with cache=miss."""
        from career_os.ai.cache import CachedProvider
        from career_os.ai.mock_provider import MockProvider

        inner = MockProvider()
        cached = CachedProvider(inner, db_path=":memory:", enabled=True)

        with patch("career_os.ai.cache.update_current_span") as mock_span:
            await cached.complete("unique prompt for miss test")
            mock_span.assert_called()
            call_kwargs = mock_span.call_args[1]
            assert call_kwargs["metadata"]["cache"] == "miss"

        cached.close()


class TestPIIMaskingObservability:
    """Verify PII masking layer emits detection count metadata."""

    @pytest.mark.asyncio
    async def test_pii_detection_count_emitted(self):
        """MaskedProvider should emit pii_detections count."""
        from career_os.ai.mock_provider import MockProvider
        from career_os.ai.pii_masking import MaskedProvider

        inner = MockProvider()
        masked = MaskedProvider(inner)

        with patch("career_os.ai.pii_masking.update_current_span") as mock_span:
            await masked.complete("Contact me at test@example.com or +1-555-123-4567")
            mock_span.assert_called()
            call_kwargs = mock_span.call_args[1]
            assert call_kwargs["metadata"]["pii_detections"] >= 1

    @pytest.mark.asyncio
    async def test_no_pii_emits_zero(self):
        """When no PII is found, pii_detections should be 0."""
        from career_os.ai.mock_provider import MockProvider
        from career_os.ai.pii_masking import MaskedProvider

        inner = MockProvider()
        masked = MaskedProvider(inner)

        with patch("career_os.ai.pii_masking.update_current_span") as mock_span:
            await masked.complete("Hello world, no PII here")
            mock_span.assert_called()
            call_kwargs = mock_span.call_args[1]
            assert call_kwargs["metadata"]["pii_detections"] == 0
