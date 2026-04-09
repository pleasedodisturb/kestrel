"""Tests for AI provider health dashboard.

Covers:
- VAL-AI-HEALTH-001: Provider connectivity check (reads stored integration config)
- VAL-AI-HEALTH-002: Credit and rate limit display
- VAL-AI-HEALTH-003: Auth failure isolation
- VAL-CROSS-012: AI provider switching preserves functionality

The dashboard now only reports runtime-supported providers (mock, openrouter)
and reads credentials from stored integration config, falling back to env vars.
"""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.integrations import IntegrationConfig


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# VAL-AI-HEALTH-001: Provider connectivity check
# ---------------------------------------------------------------------------


class TestProviderHealthEndpoint:
    """GET /api/ai/health returns health status for all configured providers."""

    def test_health_returns_all_providers(self, client: TestClient) -> None:
        """Health endpoint returns status for runtime-supported providers only."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        providers = data["providers"]
        assert isinstance(providers, list)
        # Should list only runtime-supported providers (mock, openrouter)
        names = {p["name"] for p in providers}
        expected = {"mock", "openrouter"}
        assert expected == names

    def test_health_provider_fields(self, client: TestClient) -> None:
        """Each provider entry has required fields."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        data = resp.json()
        for provider in data["providers"]:
            assert "name" in provider
            assert "display_name" in provider
            assert "status" in provider  # reachable | unreachable | not_configured | error
            assert "is_default" in provider
            assert "error_message" in provider  # null if no error
            assert "credits" in provider  # null if not available
            assert "rate_limit" in provider  # null if not available

    def test_mock_provider_always_reachable(self, client: TestClient) -> None:
        """Mock provider is always reachable."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        data = resp.json()
        mock_p = next(p for p in data["providers"] if p["name"] == "mock")
        assert mock_p["status"] == "reachable"
        assert mock_p["is_default"] is True
        assert mock_p["error_message"] is None

    def test_unconfigured_providers_show_not_configured(self, client: TestClient) -> None:
        """Providers without API keys show not_configured."""
        env = {
            "AI_PROVIDER": "mock",
            "OPENROUTER_API_KEY": "",
        }
        with patch.dict(os.environ, env, clear=False):
            resp = client.get("/api/ai/health")
        data = resp.json()
        or_p = next(p for p in data["providers"] if p["name"] == "openrouter")
        assert or_p["status"] == "not_configured"

    def test_default_provider_flag(self, client: TestClient) -> None:
        """Only the active provider has is_default=True."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        data = resp.json()
        defaults = [p for p in data["providers"] if p["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "mock"


# ---------------------------------------------------------------------------
# VAL-AI-HEALTH-002: Credit and rate limit display
# ---------------------------------------------------------------------------


class TestCreditsAndRateLimits:
    """Credits and rate limits shown for providers that expose them."""

    def test_mock_no_credits(self, client: TestClient) -> None:
        """Mock provider has no credits or rate limits."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        data = resp.json()
        mock_p = next(p for p in data["providers"] if p["name"] == "mock")
        assert mock_p["credits"] is None
        assert mock_p["rate_limit"] is None

    def test_credits_structure_when_available(self, client: TestClient) -> None:
        """Credits field has expected structure when provided."""
        # We test the schema structure — when credits are present,
        # they should have remaining/total/unit fields
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        data = resp.json()
        # Just validate structure exists (mock will have null)
        for p in data["providers"]:
            credits = p["credits"]
            if credits is not None:
                assert "remaining" in credits
                assert "unit" in credits

    def test_rate_limit_structure_when_available(self, client: TestClient) -> None:
        """Rate limit field has expected structure when provided."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health")
        data = resp.json()
        for p in data["providers"]:
            rate_limit = p["rate_limit"]
            if rate_limit is not None:
                assert "requests_per_minute" in rate_limit


# ---------------------------------------------------------------------------
# VAL-AI-HEALTH-003: Auth failure isolation
# ---------------------------------------------------------------------------


class TestAuthFailureIsolation:
    """One misconfigured provider doesn't affect others."""

    def test_bad_openrouter_key_doesnt_affect_mock(self, client: TestClient) -> None:
        """Bad OpenRouter key shows error only for OpenRouter, mock still reachable."""
        env = {
            "AI_PROVIDER": "mock",
            "OPENROUTER_API_KEY": "sk-or-INVALID",
        }
        with patch.dict(os.environ, env, clear=False):
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        data = resp.json()

        mock_p = next(p for p in data["providers"] if p["name"] == "mock")
        assert mock_p["status"] == "reachable"

        or_p = next(p for p in data["providers"] if p["name"] == "openrouter")
        # OpenRouter with an invalid key should be error or unreachable
        # (depending on whether we can reach the API)
        assert or_p["status"] in ("error", "unreachable")

    def test_bad_openrouter_key_shows_own_error(self, client: TestClient) -> None:
        """Bad OpenRouter key shows error, mock unaffected."""
        env = {
            "AI_PROVIDER": "mock",
            "OPENROUTER_API_KEY": "bad-key",
        }
        with patch.dict(os.environ, env, clear=False):
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        data = resp.json()

        mock_p = next(p for p in data["providers"] if p["name"] == "mock")
        assert mock_p["status"] == "reachable"

        or_p = next(p for p in data["providers"] if p["name"] == "openrouter")
        assert or_p["status"] in ("error", "unreachable")

    def test_health_endpoint_never_crashes(self, client: TestClient) -> None:
        """Health endpoint always returns 200 even with all providers misconfigured."""
        env = {
            "AI_PROVIDER": "nonexistent_provider",
            "OPENROUTER_API_KEY": "bad",
            "ANTHROPIC_API_KEY": "bad",
        }
        with patch.dict(os.environ, env, clear=False):
            resp = client.get("/api/ai/health")
        # Should still return 200 with status info, not crash
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# VAL-CROSS-012: AI provider switching preserves functionality
# ---------------------------------------------------------------------------


class TestProviderSwitching:
    """Switching providers doesn't break functionality."""

    def test_health_check_per_provider(self, client: TestClient) -> None:
        """GET /api/ai/health/check?provider=mock tests specific provider."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health/check", params={"provider": "mock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "mock"
        assert data["status"] == "reachable"

    def test_health_check_unsupported_provider(self, client: TestClient) -> None:
        """GET /api/ai/health/check with unsupported provider returns error."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/health/check", params={"provider": "anthropic"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "not supported" in data["error_message"].lower()


# ---------------------------------------------------------------------------
# Stored config integration
# ---------------------------------------------------------------------------


class TestStoredConfigIntegration:
    """AI health reads from stored integration config."""

    def test_reads_default_provider_from_stored_config(
        self, client: TestClient, db_session
    ) -> None:
        """Health endpoint reads default_provider from stored ai_providers config."""
        # Store config with openrouter as default
        row = IntegrationConfig(
            name="ai_providers",
            display_name="AI Providers",
            enabled=True,
            credentials=json.dumps({"default_provider": "openrouter"}),
            status="connected",
        )
        db_session.add(row)
        db_session.commit()

        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}, clear=False):
            resp = client.get("/api/ai/health")
        data = resp.json()
        # Stored config should override env var
        assert data["default_provider"] == "openrouter"

    def test_only_runtime_supported_providers_shown(self, client: TestClient, db_session) -> None:
        """Dashboard only shows mock and openrouter, not unsupported providers."""
        resp = client.get("/api/ai/health")
        data = resp.json()
        names = {p["name"] for p in data["providers"]}
        assert names == {"mock", "openrouter"}
        # Verify anthropic, openai, gemini, together, droid_exec are NOT present
        assert "anthropic" not in names
        assert "openai" not in names
        assert "droid_exec" not in names
