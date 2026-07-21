"""Tests for the browser-extension backend surface (Phase 0 / G-1390).

Covers the stateless pairing/token service, the pair/capture-stub/status routes,
the auth-middleware bypass, the chrome-extension CORS regex, and the
`kestrel extension pair` CLI. No real network, no scoring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from career_os import __version__
from career_os.services import extension_pairing

# A concrete, valid 32-char (a–p) Chrome extension origin for CORS assertions.
_CHROME_ORIGIN = "chrome-extension://" + "a" * 32

_EXTENSION_SRC = (
    Path(__file__).resolve().parent.parent / "src" / "career_os" / "api" / "extension.py"
)


@pytest.fixture(autouse=True)
def _deterministic_secret(monkeypatch):
    """Pin the extension secret so pairing codes/tokens are deterministic."""
    monkeypatch.setenv("EXTENSION_TOKEN_SECRET", "test-extension-secret-000")
    extension_pairing.reset_secret_cache()
    yield
    extension_pairing.reset_secret_cache()


# ---------------------------------------------------------------------------
# Task 1 — pairing + token service (stateless HMAC)
# ---------------------------------------------------------------------------


class TestExtensionPairing:
    """Unit tests for the pure pairing/token functions."""

    def test_current_pairing_code_is_six_digits(self):
        code = extension_pairing.current_pairing_code()
        assert isinstance(code, str)
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_accepts_current_code(self):
        code = extension_pairing.current_pairing_code()
        assert extension_pairing.verify_pairing_code(code) is True

    def test_verify_accepts_previous_window_code(self, monkeypatch):
        """A code from the previous window is still accepted across a boundary."""
        window = extension_pairing._current_window()
        prev_code = extension_pairing._code_for_window(window - 1)
        assert extension_pairing.verify_pairing_code(prev_code) is True

    def test_verify_rejects_wrong_code(self):
        code = extension_pairing.current_pairing_code()
        wrong = "000000" if code != "000000" else "111111"
        assert extension_pairing.verify_pairing_code(wrong) is False

    def test_verify_rejects_empty_and_none(self):
        assert extension_pairing.verify_pairing_code("") is False
        assert extension_pairing.verify_pairing_code(None) is False

    def test_code_changes_across_windows(self, monkeypatch):
        window = extension_pairing._current_window()
        assert extension_pairing._code_for_window(window) != extension_pairing._code_for_window(
            window + 5
        )

    def test_mint_then_verify_token(self):
        token = extension_pairing.mint_extension_token()
        assert extension_pairing.verify_extension_token(token) is True

    def test_two_mints_both_verify(self):
        t1 = extension_pairing.mint_extension_token()
        t2 = extension_pairing.mint_extension_token()
        assert extension_pairing.verify_extension_token(t1) is True
        assert extension_pairing.verify_extension_token(t2) is True

    def test_verify_rejects_tampered_signature(self):
        token = extension_pairing.mint_extension_token()
        head, sig = token.split(".")
        # Flip a character in the signature segment.
        tampered_char = "b" if sig[0] != "b" else "c"
        tampered = f"{head}.{tampered_char}{sig[1:]}"
        assert extension_pairing.verify_extension_token(tampered) is False

    def test_verify_rejects_malformed_and_empty(self):
        assert extension_pairing.verify_extension_token("") is False
        assert extension_pairing.verify_extension_token(None) is False
        assert extension_pairing.verify_extension_token("no-dot") is False
        assert extension_pairing.verify_extension_token("a.b.c") is False
        assert extension_pairing.verify_extension_token(".") is False

    def test_token_minted_under_different_secret_fails(self, monkeypatch):
        token = extension_pairing.mint_extension_token()
        # Rotate the secret — the old token must no longer verify.
        monkeypatch.setenv("EXTENSION_TOKEN_SECRET", "a-completely-different-secret")
        extension_pairing.reset_secret_cache()
        assert extension_pairing.verify_extension_token(token) is False

    def test_secret_persists_to_file_when_no_env(self, monkeypatch, tmp_path):
        """With no env override, the secret is generated once and persisted 0600."""
        monkeypatch.delenv("EXTENSION_TOKEN_SECRET", raising=False)
        monkeypatch.setattr(extension_pairing.settings, "extension_token_secret", "")
        monkeypatch.setattr(extension_pairing.settings, "data_dir", tmp_path)
        extension_pairing.reset_secret_cache()

        secret1 = extension_pairing.get_extension_secret()
        secret_file = tmp_path / ".extension_secret"
        assert secret_file.is_file()
        # Mode is 0600 (owner read/write only).
        assert (secret_file.stat().st_mode & 0o777) == 0o600

        # A fresh read (cache cleared → reads the file) returns the SAME secret,
        # so tokens survive a restart.
        extension_pairing.reset_secret_cache()
        secret2 = extension_pairing.get_extension_secret()
        assert secret1 == secret2


# ---------------------------------------------------------------------------
# Task 2 — routes (pair / capture-stub / status) + middleware bypass + CORS
# ---------------------------------------------------------------------------


def _auth_enabled_app() -> FastAPI:
    """Minimal app with the global API-key middleware ENABLED, extension router on.

    Used to prove the middleware bypass: the extension's dedicated token governs
    /capture even when a global AUTH_API_KEY is configured.
    """
    from career_os.api.extension import router as extension_router
    from career_os.middleware import APIKeyAuthMiddleware

    test_app = FastAPI()
    test_app.add_middleware(APIKeyAuthMiddleware, auth_enabled=True, auth_api_key="the-global-key")
    test_app.include_router(extension_router)
    return test_app


class TestExtensionRoutes:
    """End-to-end route behavior against the wire contract."""

    def test_pair_with_valid_code_returns_token_and_instance(self, client: TestClient):
        code = extension_pairing.current_pairing_code()
        resp = client.post("/api/extension/pair", json={"pairing_code": code})
        assert resp.status_code == 200
        body = resp.json()
        assert extension_pairing.verify_extension_token(body["token"]) is True
        assert body["instance"] == {"name": "Kestrel", "version": __version__}

    def test_pair_with_wrong_code_returns_401(self, client: TestClient):
        resp = client.post("/api/extension/pair", json={"pairing_code": "999999"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired pairing code"

    def test_capture_without_token_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/extension/capture",
            json={"url": "u", "title": "t", "company": "c", "description": "d"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Extension not paired"

    def test_capture_with_token_returns_job_id_unscored(self, client: TestClient):
        token = extension_pairing.mint_extension_token()
        resp = client.post(
            "/api/extension/capture",
            json={
                "url": "https://example.com/job",
                "title": "Engineer",
                "company": "Acme",
                "description": "Build things",
                "location": "Remote",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scored"] is False
        assert body["status"] == "accepted"
        assert isinstance(body["job_id"], str) and body["job_id"]

    def test_capture_with_bad_token_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/extension/capture",
            json={"url": "u", "title": "t", "company": "c", "description": "d"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_status_with_valid_token(self, client: TestClient):
        token = extension_pairing.mint_extension_token()
        resp = client.get("/api/extension/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["instance"] == {"name": "Kestrel", "version": __version__}

    def test_status_without_token_returns_401(self, client: TestClient):
        resp = client.get("/api/extension/status")
        assert resp.status_code == 401

    def test_middleware_bypass_when_auth_enabled(self):
        """With AUTH_ENABLED, the extension token (NOT the global key) governs."""
        app = _auth_enabled_app()
        client = TestClient(app)
        payload = {"url": "u", "title": "t", "company": "c", "description": "d"}

        # No auth header: global check is bypassed, per-route token check → 401.
        assert client.post("/api/extension/capture", json=payload).status_code == 401

        # The GLOBAL key is NOT a valid extension token → still 401.
        resp_global = client.post(
            "/api/extension/capture",
            json=payload,
            headers={"Authorization": "Bearer the-global-key"},
        )
        assert resp_global.status_code == 401

        # A valid EXTENSION token reaches the route → 200.
        token = extension_pairing.mint_extension_token()
        resp_ok = client.post(
            "/api/extension/capture",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_ok.status_code == 200

    def test_cors_preflight_allows_chrome_extension_origin(self, client: TestClient):
        resp = client.options(
            "/api/extension/capture",
            headers={
                "Origin": _CHROME_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == _CHROME_ORIGIN

    def test_capture_does_not_import_score_job(self):
        """Structural guard: the capture module must not reference score_job."""
        assert "score_job" not in _EXTENSION_SRC.read_text(encoding="utf-8")
