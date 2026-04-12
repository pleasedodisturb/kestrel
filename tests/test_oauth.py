"""Tests for OpenRouter OAuth PKCE endpoints."""

import hashlib
import time
from base64 import urlsafe_b64encode
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from career_os.api.oauth import (
    OPENROUTER_KEYS_URL,
    _generate_pkce_pair,
    _pending_verifiers,
)
from career_os.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_pending_verifiers():
    """Ensure the pending verifiers dict is clean between tests."""
    _pending_verifiers.clear()
    yield
    _pending_verifiers.clear()


# ---------------------------------------------------------------------------
# PKCE crypto
# ---------------------------------------------------------------------------


class TestPKCECrypto:
    """Verify the PKCE code_verifier / code_challenge generation."""

    def test_verifier_is_url_safe_string(self):
        verifier, _ = _generate_pkce_pair()
        assert isinstance(verifier, str)
        assert len(verifier) > 40  # 64 random bytes → ~86 chars in base64url

    def test_challenge_is_sha256_base64url_of_verifier(self):
        verifier, challenge = _generate_pkce_pair()
        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        assert challenge == expected_challenge

    def test_each_call_produces_unique_pair(self):
        pairs = [_generate_pkce_pair() for _ in range(5)]
        verifiers = [p[0] for p in pairs]
        assert len(set(verifiers)) == 5, "Verifiers should be unique"


# ---------------------------------------------------------------------------
# GET /api/auth/openrouter/start
# ---------------------------------------------------------------------------


class TestStartEndpoint:
    """Tests for the OAuth start endpoint."""

    def test_returns_auth_url_with_pkce_params(self, client):
        resp = client.get("/api/auth/openrouter/start")
        assert resp.status_code == 200
        data = resp.json()

        assert "auth_url" in data
        assert "state" in data

        auth_url = data["auth_url"]
        assert "https://openrouter.ai/auth" in auth_url
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "callback_url=" in auth_url

    def test_stores_verifier_in_pending(self, client):
        resp = client.get("/api/auth/openrouter/start")
        state = resp.json()["state"]
        assert state in _pending_verifiers
        verifier, created_at = _pending_verifiers[state]
        assert len(verifier) > 40
        assert created_at <= time.time()

    def test_max_pending_returns_429(self, client):
        """Exceeding the max pending verifiers returns 429."""
        from career_os.api.oauth import _MAX_PENDING

        for i in range(_MAX_PENDING):
            _pending_verifiers[f"state-{i}"] = ("verifier", time.time())
        resp = client.get("/api/auth/openrouter/start")
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET /api/auth/openrouter/callback
# ---------------------------------------------------------------------------


class TestCallbackEndpoint:
    """Tests for the OAuth callback endpoint."""

    def test_invalid_state_returns_400(self, client):
        resp = client.get("/api/auth/openrouter/callback", params={"code": "test", "state": "bad"})
        assert resp.status_code == 400
        assert "Invalid or expired state" in resp.json()["detail"]

    def test_missing_state_returns_422(self, client):
        """State is a required query parameter."""
        resp = client.get("/api/auth/openrouter/callback", params={"code": "test"})
        assert resp.status_code == 422

    def test_successful_exchange(self, client):
        """Mock a successful code-for-key exchange with OpenRouter."""
        # Pre-populate a pending verifier (now stores tuple with timestamp).
        _pending_verifiers["test-state"] = ("test-verifier", time.time())

        mock_response = httpx.Response(
            200,
            json={"key": "test-fake-openrouter-key"},
            request=httpx.Request("POST", OPENROUTER_KEYS_URL),
        )

        with patch("career_os.api.oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            resp = client.get(
                "/api/auth/openrouter/callback",
                params={"code": "auth-code-xyz", "state": "test-state"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["provider"] == "openrouter"

        # Verifier should be consumed.
        assert "test-state" not in _pending_verifiers

        # Key should be stored in module-level variable (not os.environ).
        from career_os.api.oauth import _runtime_api_key

        assert _runtime_api_key == "test-fake-openrouter-key"

    def test_exchange_http_error_returns_502(self, client):
        """OpenRouter returning a non-2xx should yield a 502."""
        _pending_verifiers["err-state"] = ("verifier", time.time())

        mock_response = httpx.Response(
            401,
            json={"error": "invalid_code"},
            request=httpx.Request("POST", OPENROUTER_KEYS_URL),
        )

        with patch("career_os.api.oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            resp = client.get(
                "/api/auth/openrouter/callback",
                params={"code": "bad-code", "state": "err-state"},
            )

        assert resp.status_code == 502

    def test_exchange_network_error_returns_502(self, client):
        """Network failure contacting OpenRouter should yield a 502."""
        _pending_verifiers["net-state"] = ("verifier", time.time())

        with patch("career_os.api.oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            resp = client.get(
                "/api/auth/openrouter/callback",
                params={"code": "code", "state": "net-state"},
            )

        assert resp.status_code == 502

    def test_empty_key_returns_502(self, client):
        """OpenRouter returning an empty key should be treated as an error."""
        _pending_verifiers["empty-state"] = ("verifier", time.time())

        mock_response = httpx.Response(
            200,
            json={"key": ""},
            request=httpx.Request("POST", OPENROUTER_KEYS_URL),
        )

        with patch("career_os.api.oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            resp = client.get(
                "/api/auth/openrouter/callback",
                params={"code": "code", "state": "empty-state"},
            )

        assert resp.status_code == 502
        assert "empty API key" in resp.json()["detail"]

    def test_expired_verifier_returns_400(self, client):
        """A verifier older than the TTL is treated as expired."""
        from career_os.api.oauth import _VERIFIER_TTL_SECONDS

        _pending_verifiers["old-state"] = ("verifier", time.time() - _VERIFIER_TTL_SECONDS - 1)

        resp = client.get(
            "/api/auth/openrouter/callback",
            params={"code": "code", "state": "old-state"},
        )
        assert resp.status_code == 400
        assert "Invalid or expired state" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/auth/openrouter/status
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    """Tests for the OAuth status endpoint."""

    def test_disconnected_when_no_key(self, client):
        import career_os.api.oauth as oauth_mod

        original = oauth_mod._runtime_api_key
        try:
            oauth_mod._runtime_api_key = ""
            with patch("career_os.api.oauth.settings") as mock_settings:
                mock_settings.openrouter_api_key = ""
                resp = client.get("/api/auth/openrouter/status")
        finally:
            oauth_mod._runtime_api_key = original

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["provider"] == "openrouter"
        assert "key_preview" not in data  # removed for security

    def test_connected_when_key_present(self, client):
        import career_os.api.oauth as oauth_mod

        original = oauth_mod._runtime_api_key
        try:
            oauth_mod._runtime_api_key = "test-fake-openrouter-key-2"
            resp = client.get("/api/auth/openrouter/status")
        finally:
            oauth_mod._runtime_api_key = original

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
