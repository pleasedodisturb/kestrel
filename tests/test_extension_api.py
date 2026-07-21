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
def _deterministic_secret(monkeypatch, tmp_path):
    """Pin the extension secret + isolate per-test pairing/rate-limit state.

    - Pins ``EXTENSION_TOKEN_SECRET`` so codes/tokens are deterministic.
    - Points ``settings.data_dir`` at a tmp dir so the single-use pairing nonce
      file (``.extension_pairing``) is isolated per test.
    - Resets the shared slowapi limiter before and after each test so the 429
      rate-limit test does not throttle unrelated tests (all requests share the
      TestClient source IP).
    """
    from career_os.api.oauth import limiter as _oauth_limiter

    monkeypatch.setenv("EXTENSION_TOKEN_SECRET", "test-extension-secret-000")
    monkeypatch.setattr(extension_pairing.settings, "data_dir", tmp_path)
    extension_pairing.reset_secret_cache()
    _oauth_limiter.reset()
    yield
    extension_pairing.reset_secret_cache()
    _oauth_limiter.reset()


# ---------------------------------------------------------------------------
# Task 1 — pairing + token service (stateless HMAC)
# ---------------------------------------------------------------------------


class TestExtensionPairing:
    """Unit tests for the pure pairing/token functions."""

    def test_mint_pairing_code_is_six_digits_and_persisted(self):
        code = extension_pairing.mint_pairing_code()
        assert isinstance(code, str)
        assert len(code) == 6
        assert code.isdigit()
        # Only the hash + expiry are stored (never the code itself), 0600.
        path = extension_pairing._pairing_path()
        assert path.is_file()
        assert (path.stat().st_mode & 0o777) == 0o600
        assert code not in path.read_text(encoding="utf-8")

    def test_consume_accepts_minted_code_once(self):
        code = extension_pairing.mint_pairing_code()
        assert extension_pairing.consume_pairing_code(code) is True

    def test_consume_is_single_use(self):
        """The second consume of the same code fails (nonce deleted on success)."""
        code = extension_pairing.mint_pairing_code()
        assert extension_pairing.consume_pairing_code(code) is True
        assert extension_pairing.consume_pairing_code(code) is False
        assert extension_pairing._pairing_path().exists() is False

    def test_consume_rejects_expired_code(self):
        """An expired nonce is rejected (and cleaned up); a wrong code stays valid."""
        import json
        import time

        code = extension_pairing.mint_pairing_code()
        # Rewrite the persisted nonce with an already-past expiry.
        path = extension_pairing._pairing_path()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["expires"] = time.time() - 1
        path.write_text(json.dumps(data), encoding="utf-8")
        assert extension_pairing.consume_pairing_code(code) is False
        assert path.exists() is False

    def test_consume_rejects_wrong_code_but_keeps_file(self):
        code = extension_pairing.mint_pairing_code()
        wrong = "000000" if code != "000000" else "111111"
        assert extension_pairing.consume_pairing_code(wrong) is False
        # File left in place so the legitimate user can still retry until expiry.
        assert extension_pairing._pairing_path().is_file()
        assert extension_pairing.consume_pairing_code(code) is True

    def test_consume_rejects_empty_none_and_missing_file(self):
        assert extension_pairing.consume_pairing_code("") is False
        assert extension_pairing.consume_pairing_code(None) is False
        # No file minted yet → reject.
        extension_pairing.reset_pairing_state()
        assert extension_pairing.consume_pairing_code("123456") is False

    def test_mint_regenerates_and_invalidates_previous_code(self):
        first = extension_pairing.mint_pairing_code()
        second = extension_pairing.mint_pairing_code()
        # A re-mint overwrites the nonce, so the first code no longer works.
        assert extension_pairing.consume_pairing_code(first) is False
        assert extension_pairing.consume_pairing_code(second) is True

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

    @staticmethod
    def _token_issued_at(issued_ts: int) -> str:
        """Forge a validly-signed token whose embedded issued-ts is `issued_ts`.

        Uses the real secret + HMAC path (so the signature verifies) but lets the
        test choose the age — no time monkeypatching needed.
        """
        import hashlib
        import hmac

        issued = str(int(issued_ts)).encode("ascii")
        secret = extension_pairing.get_extension_secret()
        signature = hmac.new(secret, issued, hashlib.sha256).digest()
        return (
            f"{extension_pairing._b64url_encode(issued)}."
            f"{extension_pairing._b64url_encode(signature)}"
        )

    def test_fresh_token_verifies_within_ttl(self, monkeypatch):
        monkeypatch.setattr(extension_pairing.settings, "extension_token_ttl_days", 30)
        token = extension_pairing.mint_extension_token()
        assert extension_pairing.verify_extension_token(token) is True

    def test_token_older_than_ttl_is_rejected(self, monkeypatch):
        """A token whose issued-ts is older than the TTL fails verification (→401)."""
        import time

        monkeypatch.setattr(extension_pairing.settings, "extension_token_ttl_days", 30)
        stale = self._token_issued_at(int(time.time()) - 31 * 86400)
        assert extension_pairing.verify_extension_token(stale) is False

    def test_ttl_zero_disables_age_check(self, monkeypatch):
        """TTL <= 0 = never-expire mode: even an ancient token still verifies."""
        import time

        monkeypatch.setattr(extension_pairing.settings, "extension_token_ttl_days", 0)
        ancient = self._token_issued_at(int(time.time()) - 3650 * 86400)  # ~10 years
        assert extension_pairing.verify_extension_token(ancient) is True

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
        code = extension_pairing.mint_pairing_code()
        resp = client.post("/api/extension/pair", json={"pairing_code": code})
        assert resp.status_code == 200
        body = resp.json()
        assert extension_pairing.verify_extension_token(body["token"]) is True
        assert body["instance"] == {"name": "Kestrel", "version": __version__}

    def test_pair_code_is_single_use_over_the_wire(self, client: TestClient):
        """Re-POSTing a consumed code returns 401 (nonce already spent)."""
        code = extension_pairing.mint_pairing_code()
        first = client.post("/api/extension/pair", json={"pairing_code": code})
        assert first.status_code == 200
        second = client.post("/api/extension/pair", json={"pairing_code": code})
        assert second.status_code == 401
        assert second.json()["detail"] == "Invalid or expired pairing code"

    def test_pair_with_wrong_code_returns_401(self, client: TestClient):
        resp = client.post("/api/extension/pair", json={"pairing_code": "999999"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired pairing code"

    def test_pair_rate_limited_returns_429(self, client: TestClient):
        """The 6th /pair within a minute from the same IP is throttled (T-01A-01)."""
        # Fire 6 requests; the limiter is 5/minute/IP. Use a wrong code so none
        # succeed — the limiter counts attempts regardless of the outcome.
        statuses = [
            client.post("/api/extension/pair", json={"pairing_code": "999999"}).status_code
            for _ in range(6)
        ]
        assert statuses[:5] == [401, 401, 401, 401, 401]
        assert statuses[5] == 429

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


# ---------------------------------------------------------------------------
# Task 3 — `kestrel extension pair` CLI
# ---------------------------------------------------------------------------


class TestExtensionCli:
    """The CLI mints a fresh single-use pairing code."""

    @staticmethod
    def _run_pair() -> str:
        """Invoke `kestrel extension pair` and return the printed 6-digit code."""
        import re

        from typer.testing import CliRunner

        from career_os.cli.main import app as cli_app

        result = CliRunner().invoke(cli_app, ["extension", "pair"])
        assert result.exit_code == 0
        # Strip Rich box formatting/newlines to recover the 6-digit code.
        digits = re.findall(r"\b\d{6}\b", result.stdout.replace("\n", " "))
        assert digits, f"no 6-digit code in output: {result.stdout!r}"
        return digits[0]

    def test_pair_command_prints_consumable_code(self):
        code = self._run_pair()
        # The CLI-minted code is accepted by consume_pairing_code exactly once.
        assert extension_pairing.consume_pairing_code(code) is True
        assert extension_pairing.consume_pairing_code(code) is False

    def test_pair_command_regenerates_code_each_call(self):
        first = self._run_pair()
        second = self._run_pair()
        # A second CLI call mints a fresh code and invalidates the first.
        assert extension_pairing.consume_pairing_code(first) is False
        assert extension_pairing.consume_pairing_code(second) is True
