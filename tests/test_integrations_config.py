"""Tests for the Integration Configuration API.

Covers:
- VAL-PUSH-006: All integrations have settings section with credential fields,
                 on/off toggle, status indicator.
- GET /api/integrations — list all integrations
- GET /api/integrations/{name}/config — get single integration config
- PUT /api/integrations/{name}/config — update credentials and/or toggle
- POST /api/integrations/{name}/test — test connection
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.schemas.integrations import KNOWN_INTEGRATIONS

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


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
        try:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# List integrations
# ---------------------------------------------------------------------------


class TestListIntegrations:
    """Tests for GET /api/integrations."""

    def test_list_returns_all_known_integrations(self):
        """All 6 known integrations are returned."""
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == len(KNOWN_INTEGRATIONS)
        names = [i["name"] for i in data["integrations"]]
        for defn in KNOWN_INTEGRATIONS:
            assert defn.name in names

    def test_list_has_required_fields_per_integration(self):
        """Each integration has credential_fields, enabled, status, display_name."""
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        for item in resp.json()["integrations"]:
            assert "name" in item
            assert "display_name" in item
            assert "description" in item
            assert "enabled" in item
            assert "credential_fields" in item
            assert "credentials_set" in item
            assert "status" in item
            assert isinstance(item["credential_fields"], list)
            assert isinstance(item["credentials_set"], dict)

    def test_list_default_state_is_disabled_not_configured(self):
        """Fresh integrations default to disabled and not_configured."""
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        for item in resp.json()["integrations"]:
            assert item["enabled"] is False
            assert item["status"] == "not_configured"

    def test_credential_fields_have_required_structure(self):
        """Each credential field has key, label, field_type."""
        resp = client.get("/api/integrations")
        for item in resp.json()["integrations"]:
            for field in item["credential_fields"]:
                assert "key" in field
                assert "label" in field
                assert "field_type" in field
                assert field["field_type"] in ("password", "text", "url")


# ---------------------------------------------------------------------------
# Get single integration
# ---------------------------------------------------------------------------


class TestGetIntegration:
    """Tests for GET /api/integrations/{name}/config."""

    def test_get_known_integration(self):
        """Returns config for a known integration."""
        resp = client.get("/api/integrations/pushover/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "pushover"
        assert data["display_name"] == "Pushover"
        assert len(data["credential_fields"]) >= 2

    def test_get_unknown_integration_404(self):
        """Unknown integration name returns 404."""
        resp = client.get("/api/integrations/nonexistent/config")
        assert resp.status_code == 404

    def test_get_all_known_integration_names(self):
        """Each known integration can be fetched individually."""
        for defn in KNOWN_INTEGRATIONS:
            resp = client.get(f"/api/integrations/{defn.name}/config")
            assert resp.status_code == 200
            assert resp.json()["name"] == defn.name

    def test_credentials_set_defaults_false(self):
        """Before any credentials are saved, credentials_set are all false."""
        resp = client.get("/api/integrations/pushover/config")
        data = resp.json()
        for _key, is_set in data["credentials_set"].items():
            assert is_set is False


# ---------------------------------------------------------------------------
# Update integration
# ---------------------------------------------------------------------------


class TestUpdateIntegration:
    """Tests for PUT /api/integrations/{name}/config."""

    def test_update_enable_toggle(self):
        """Enable an integration via PUT."""
        resp = client.put(
            "/api/integrations/pushover/config",
            json={"enabled": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    def test_update_disable_toggle(self):
        """Disable an integration via PUT."""
        # First enable
        client.put("/api/integrations/pushover/config", json={"enabled": True})
        # Then disable
        resp = client.put(
            "/api/integrations/pushover/config",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert resp.json()["status"] == "disabled"

    def test_update_credentials(self):
        """Saving credentials marks them as set (without exposing values)."""
        resp = client.put(
            "/api/integrations/pushover/config",
            json={
                "credentials": {
                    "user_key": "my-user-key",
                    "app_token": "my-app-token",
                }
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["credentials_set"]["user_key"] is True
        assert data["credentials_set"]["app_token"] is True
        # Must NOT expose actual credential values
        assert "my-user-key" not in str(data)
        assert "my-app-token" not in str(data)

    def test_update_partial_credentials_merge(self):
        """Updating one credential key preserves others."""
        # Set user_key first
        client.put(
            "/api/integrations/pushover/config",
            json={"credentials": {"user_key": "key1"}},
        )
        # Now set app_token (user_key should persist)
        resp = client.put(
            "/api/integrations/pushover/config",
            json={"credentials": {"app_token": "token1"}},
        )
        data = resp.json()
        assert data["credentials_set"]["user_key"] is True
        assert data["credentials_set"]["app_token"] is True

    def test_update_unknown_integration_404(self):
        """Unknown integration returns 404."""
        resp = client.put(
            "/api/integrations/nonexistent/config",
            json={"enabled": True},
        )
        assert resp.status_code == 404

    def test_update_persists_across_gets(self):
        """Changes persist and are visible in subsequent GET."""
        client.put(
            "/api/integrations/ticktick/config",
            json={"enabled": True, "credentials": {"api_token": "tok123"}},
        )
        resp = client.get("/api/integrations/ticktick/config")
        data = resp.json()
        assert data["enabled"] is True
        assert data["credentials_set"]["api_token"] is True

    def test_update_enable_and_credentials_simultaneously(self):
        """Can set both enabled and credentials in one request."""
        resp = client.put(
            "/api/integrations/calendar/config",
            json={
                "enabled": True,
                "credentials": {"provider": "google", "api_key": "gkey"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["credentials_set"]["provider"] is True
        assert data["credentials_set"]["api_key"] is True

    def test_credentials_no_secrets_in_response(self):
        """Response never includes raw credential values."""
        client.put(
            "/api/integrations/pushover/config",
            json={"credentials": {"user_key": "SECRET_VALUE_123"}},
        )
        resp = client.get("/api/integrations/pushover/config")
        response_text = resp.text
        assert "SECRET_VALUE_123" not in response_text


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


class TestTestConnection:
    """Tests for POST /api/integrations/{name}/test."""

    def test_test_missing_required_credentials(self):
        """Testing without required credentials reports error."""
        # Enable but don't set credentials
        client.put("/api/integrations/pushover/config", json={"enabled": True})
        resp = client.post("/api/integrations/pushover/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Missing required" in data["message"]

    def test_test_disabled_integration(self):
        """Testing a disabled integration reports disabled."""
        # Set credentials but don't enable
        client.put(
            "/api/integrations/pushover/config",
            json={"credentials": {"user_key": "k", "app_token": "t"}},
        )
        resp = client.post("/api/integrations/pushover/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "disabled" in data["message"].lower()

    def test_test_configured_and_enabled(self):
        """Properly configured and enabled integration tests successfully."""
        client.put(
            "/api/integrations/pushover/config",
            json={
                "enabled": True,
                "credentials": {"user_key": "ukey", "app_token": "atoken"},
            },
        )
        resp = client.post("/api/integrations/pushover/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["name"] == "pushover"
        assert data["tested_at"] is not None

    def test_test_updates_status_to_connected(self):
        """Successful test sets status to 'connected'."""
        client.put(
            "/api/integrations/pushover/config",
            json={
                "enabled": True,
                "credentials": {"user_key": "u", "app_token": "t"},
            },
        )
        client.post("/api/integrations/pushover/test")
        resp = client.get("/api/integrations/pushover/config")
        assert resp.json()["status"] == "connected"
        assert resp.json()["last_tested_at"] is not None

    def test_test_updates_status_to_error_on_missing(self):
        """Failed test sets status to 'error' with message."""
        client.put("/api/integrations/pushover/config", json={"enabled": True})
        client.post("/api/integrations/pushover/test")
        resp = client.get("/api/integrations/pushover/config")
        assert resp.json()["status"] == "error"
        assert resp.json()["status_message"] is not None

    def test_test_unknown_integration_404(self):
        """Testing unknown integration returns 404."""
        resp = client.post("/api/integrations/nonexistent/test")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration-specific panels
# ---------------------------------------------------------------------------


class TestIntegrationPanels:
    """Verify each integration has the expected structure (VAL-PUSH-006)."""

    def test_ticktick_panel(self):
        resp = client.get("/api/integrations/ticktick/config")
        data = resp.json()
        assert data["display_name"] == "TickTick"
        field_keys = [f["key"] for f in data["credential_fields"]]
        assert "api_token" in field_keys

    def test_calendar_panel(self):
        resp = client.get("/api/integrations/calendar/config")
        data = resp.json()
        assert data["display_name"] == "Calendar"
        field_keys = [f["key"] for f in data["credential_fields"]]
        assert "provider" in field_keys

    def test_timingsapp_panel(self):
        resp = client.get("/api/integrations/timingsapp/config")
        data = resp.json()
        assert data["display_name"] == "TimingsApp"

    def test_pushover_panel(self):
        resp = client.get("/api/integrations/pushover/config")
        data = resp.json()
        assert data["display_name"] == "Pushover"
        field_keys = [f["key"] for f in data["credential_fields"]]
        assert "user_key" in field_keys
        assert "app_token" in field_keys

    def test_voice_panel(self):
        resp = client.get("/api/integrations/voice/config")
        data = resp.json()
        assert data["display_name"] == "Voice Mode"

    def test_ai_providers_panel(self):
        resp = client.get("/api/integrations/ai_providers/config")
        data = resp.json()
        assert data["display_name"] == "AI Providers"
        field_keys = [f["key"] for f in data["credential_fields"]]
        assert "default_provider" in field_keys
        assert "openrouter_api_key" in field_keys


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSaveTriggersConnectionTest:
    """Tests for PUT triggering a connection test on save."""

    def test_save_credentials_triggers_connection_test(self):
        """Saving credentials on an enabled integration triggers a connection test."""
        resp = client.put(
            "/api/integrations/pushover/config",
            json={
                "enabled": True,
                "credentials": {"user_key": "ukey", "app_token": "atoken"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # connection_test result should be present
        assert data.get("connection_test") is not None
        assert data["connection_test"]["tested_at"] is not None
        # Status should be updated by the test
        assert data["status"] in ("connected", "error")

    def test_save_without_credentials_no_test(self):
        """Saving only enabled=True (no credentials) does not trigger test."""
        resp = client.put(
            "/api/integrations/pushover/config",
            json={"enabled": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("connection_test") is None

    def test_save_disabled_integration_no_test(self):
        """Saving credentials on a disabled integration does not trigger test."""
        resp = client.put(
            "/api/integrations/pushover/config",
            json={
                "enabled": False,
                "credentials": {"user_key": "ukey", "app_token": "atoken"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("connection_test") is None


# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case scenarios."""

    def test_empty_credentials_dict(self):
        """PUT with empty credentials dict does not crash."""
        resp = client.put(
            "/api/integrations/pushover/config",
            json={"credentials": {}},
        )
        assert resp.status_code == 200

    def test_update_with_empty_body(self):
        """PUT with no fields is a no-op (doesn't crash)."""
        resp = client.put("/api/integrations/pushover/config", json={})
        assert resp.status_code == 200

    def test_re_enable_after_disable(self):
        """Re-enabling restores from disabled to not_configured."""
        client.put("/api/integrations/pushover/config", json={"enabled": True})
        client.put("/api/integrations/pushover/config", json={"enabled": False})
        resp = client.put("/api/integrations/pushover/config", json={"enabled": True})
        data = resp.json()
        assert data["enabled"] is True
        assert data["status"] == "not_configured"

    def test_repeated_list_is_idempotent(self):
        """Listing twice returns same results (no duplicate rows created)."""
        resp1 = client.get("/api/integrations")
        resp2 = client.get("/api/integrations")
        assert resp1.json()["count"] == resp2.json()["count"]

    def test_credential_field_with_whitespace_only_is_not_set(self):
        """A credential value of only whitespace is treated as not set."""
        client.put(
            "/api/integrations/pushover/config",
            json={"credentials": {"user_key": "   "}},
        )
        resp = client.get("/api/integrations/pushover/config")
        assert resp.json()["credentials_set"]["user_key"] is False
