"""Tests for `career_os.api.integrations` — integration config HTTP layer.

Complementary to `tests/test_integrations_config.py`. These tests target
less-covered branches: 404s on unknown integration names, the inline
connection test result on PUT, and the test endpoint when required
credentials are missing.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _auto_db(db_session):
    return db_session


# ---------------------------------------------------------------------------
# Unknown-integration 404s
# ---------------------------------------------------------------------------


def test_get_unknown_integration_returns_404(client: TestClient):
    resp = client.get("/api/integrations/__nope__/config")
    assert resp.status_code == 404
    assert "Unknown integration" in resp.json()["detail"]


def test_put_unknown_integration_returns_404(client: TestClient):
    resp = client.put(
        "/api/integrations/__nope__/config",
        json={"enabled": True, "credentials": {"api_key": "x"}},
    )
    assert resp.status_code == 404


def test_post_test_unknown_integration_returns_404(client: TestClient):
    resp = client.post("/api/integrations/__nope__/test")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test endpoint behavior
# ---------------------------------------------------------------------------


def test_test_integration_with_missing_required_credentials_fails(client: TestClient):
    """A test against pushover (which has required user_key + app_token)
    with no credentials set should report failure."""
    resp = client.post("/api/integrations/pushover/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "Missing required" in body["message"] or "required" in body["message"].lower()


def test_test_integration_when_disabled(client: TestClient):
    """When all credentials are set but integration is disabled, the test
    should still return success=False with a 'disabled' message."""
    # Configure pushover with credentials but leave enabled=False
    client.put(
        "/api/integrations/pushover/config",
        json={
            "credentials": {"user_key": "u", "app_token": "t"},
            "enabled": False,
        },
    )

    resp = client.post("/api/integrations/pushover/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "disabled" in body["message"].lower()


# ---------------------------------------------------------------------------
# PUT /config — credentials merge
# ---------------------------------------------------------------------------


def test_put_config_merges_credentials(client: TestClient):
    """PUT only updates the keys you provide; existing keys are preserved."""
    # First write
    r1 = client.put(
        "/api/integrations/pushover/config",
        json={"credentials": {"user_key": "u1", "app_token": "t1"}, "enabled": True},
    )
    assert r1.status_code == 200
    set_map = r1.json()["credentials_set"]
    assert set_map["user_key"] is True
    assert set_map["app_token"] is True

    # Second write only updates user_key
    r2 = client.put(
        "/api/integrations/pushover/config",
        json={"credentials": {"user_key": "u2"}},
    )
    assert r2.status_code == 200
    # Both keys should still be present (merge)
    set_map2 = r2.json()["credentials_set"]
    assert set_map2["user_key"] is True
    assert set_map2["app_token"] is True


def test_put_toggles_enabled_without_touching_credentials(client: TestClient):
    """Updating only the enabled flag preserves existing credentials."""
    client.put(
        "/api/integrations/pushover/config",
        json={"credentials": {"user_key": "u", "app_token": "t"}, "enabled": True},
    )

    r = client.put(
        "/api/integrations/pushover/config",
        json={"enabled": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    set_map = body["credentials_set"]
    assert set_map["user_key"] is True
    assert set_map["app_token"] is True
