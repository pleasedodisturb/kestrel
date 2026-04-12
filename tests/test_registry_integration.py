"""Integration tests: registry refactor preserves end-to-end behavior.

Verifies that the factory → service → API chain works identically
after the if-elif → dict registry migration.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from career_os.ai.factory import UnsupportedProviderError, get_ai_provider
from career_os.ai.mock_provider import MockProvider


@pytest.fixture(autouse=True)
def _auto_db(db_session):
    return db_session


# ---------------------------------------------------------------------------
# Factory → API chain
# ---------------------------------------------------------------------------


class TestRegistryEndToEnd:
    """Full-stack tests that the registry refactor is transparent."""

    def test_complete_via_mock(self, client: TestClient) -> None:
        """POST /api/ai/complete works for mock provider."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "test", "feature": "complete"},
            )
        assert resp.status_code == 200
        assert resp.json()["provider"] == "mock"

    def test_complete_via_demo_alias(self, client: TestClient) -> None:
        """POST /api/ai/complete with demo alias resolves to mock."""
        with patch.dict(os.environ, {"AI_PROVIDER": "demo"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "test", "feature": "complete"},
            )
        assert resp.status_code == 200
        assert resp.json()["provider"] == "mock"

    def test_provider_endpoint_mock(self, client: TestClient) -> None:
        """GET /api/ai/provider works for mock."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 200
        assert resp.json()["provider"] == "mock"

    def test_provider_endpoint_demo_alias(self, client: TestClient) -> None:
        """GET /api/ai/provider with demo resolves to mock."""
        with patch.dict(os.environ, {"AI_PROVIDER": "demo"}):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 200
        assert resp.json()["provider"] == "mock"

    def test_health_endpoint_lists_providers(self, client: TestClient) -> None:
        """GET /api/ai/health returns 200 and lists all providers."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        assert len(providers) >= 2
        names = {p["name"] for p in providers}
        assert "mock" in names
        assert "openrouter" in names

    def test_unsupported_provider_returns_422(self, client: TestClient) -> None:
        """Unsupported provider name returns 422 from API, not 500."""
        with patch.dict(os.environ, {"AI_PROVIDER": "nonexistent"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "test", "feature": "complete"},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Factory → service chain
# ---------------------------------------------------------------------------


class TestRegistryServiceIntegration:
    """Services that use get_ai_provider still work through the registry."""

    def test_factory_default_is_mock(self) -> None:
        """Default provider (no env var) is mock."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_PROVIDER", None)
            provider = get_ai_provider()
        assert isinstance(provider, MockProvider)

    def test_factory_explicit_mock(self) -> None:
        """get_ai_provider('mock') returns MockProvider."""
        provider = get_ai_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_factory_explicit_demo(self) -> None:
        """get_ai_provider('demo') returns MockProvider."""
        provider = get_ai_provider("demo")
        assert isinstance(provider, MockProvider)

    def test_factory_unsupported_raises(self) -> None:
        """Unsupported provider raises UnsupportedProviderError."""
        with pytest.raises(UnsupportedProviderError):
            get_ai_provider("nonexistent")

    def test_factory_case_insensitive(self) -> None:
        """Provider names are case-insensitive."""
        assert isinstance(get_ai_provider("Mock"), MockProvider)
        assert isinstance(get_ai_provider("DEMO"), MockProvider)

    def test_factory_whitespace_trimmed(self) -> None:
        """Leading/trailing whitespace is trimmed."""
        assert isinstance(get_ai_provider("  mock  "), MockProvider)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestRegistryConfigValidation:
    """Config validation uses the data-driven pattern."""

    def test_config_rejects_openrouter_without_key(self) -> None:
        """Settings validator rejects openrouter without API key."""
        from career_os.config import Settings

        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            Settings(ai_provider="openrouter", openrouter_api_key="")

    def test_config_accepts_mock_without_keys(self) -> None:
        """Settings validator accepts mock without any API keys."""
        from career_os.config import Settings

        s = Settings(ai_provider="mock")
        assert s.ai_provider == "mock"

    def test_config_accepts_demo_without_keys(self) -> None:
        """Settings validator accepts demo without any API keys."""
        from career_os.config import Settings

        s = Settings(ai_provider="demo")
        assert s.ai_provider == "demo"

    def test_config_accepts_openrouter_with_key(self) -> None:
        """Settings validator accepts openrouter with valid key."""
        from career_os.config import Settings

        s = Settings(ai_provider="openrouter", openrouter_api_key="sk-or-test123")
        assert s.ai_provider == "openrouter"
