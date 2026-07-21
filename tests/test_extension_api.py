"""Tests for the browser-extension backend surface (Phase 0 / G-1390).

Covers the stateless pairing/token service, the pair/capture-stub/status routes,
the auth-middleware bypass, the chrome-extension CORS regex, and the
`kestrel extension pair` CLI. No real network, no scoring.
"""

from __future__ import annotations

import pytest

from career_os.services import extension_pairing


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
