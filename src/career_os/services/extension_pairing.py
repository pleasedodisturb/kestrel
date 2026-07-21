"""Browser-extension pairing + token service (stateless HMAC).

Phase 0 / G-1390. The browser extension authenticates with a DEDICATED token that
is entirely separate from the global ``AUTH_API_KEY`` (locked decision D-1) and is
required even when ``AUTH_ENABLED`` is off (D-2). The flow:

1. The user reads a short-lived, 6-digit pairing code from their own running
   instance (``kestrel extension pair`` / a future web-UI surface). The code is an
   HMAC of a server-side secret over a time window, so possession of the code
   proves local access to the instance.
2. The extension submits the code to ``POST /api/extension/pair``; the backend
   validates it and mints a distinct, stateless HMAC token the extension stores and
   sends as ``Authorization: Bearer <token>`` on every subsequent call.

**Stateless by design (no DB table, no Alembic migration).** These are pure
functions over a persisted secret — trivially unit-testable and avoiding a
migration on the just-reconciled in-package Alembic history (G-1350). Consequences,
accepted for the foundation phase:

* **No expiry.** A minted token is valid as long as the secret is unchanged.
* **Revocation = rotate the secret.** Setting a new ``EXTENSION_TOKEN_SECRET`` (or
  deleting ``{data_dir}/.extension_secret``) invalidates every issued token.

A persisted, per-device revocable token store is a clean later-phase upgrade if
multi-browser management is ever needed.

**Secret persistence is load-bearing:** the secret is auto-generated once and
written to ``{data_dir}/.extension_secret`` (mode 0600), mirroring the
``cache_encryption_key`` precedent. It must NOT live only in a per-process global,
or every backend restart would silently un-pair every extension.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from career_os.config import settings

# Module-level cache for the auto-generated file secret only. An explicit
# EXTENSION_TOKEN_SECRET in the environment always takes precedence and is read
# fresh each call, so tests can monkeypatch it for determinism without a stale
# cache getting in the way.
_cached_file_secret: bytes | None = None

_SECRET_FILENAME = ".extension_secret"


class InvalidPairingCodeError(Exception):
    """Raised when a submitted pairing code is invalid or expired."""


class InvalidExtensionTokenError(Exception):
    """Raised when an extension token is missing, malformed, or tampered."""


def _env_secret() -> str:
    """Return an explicitly configured secret from env/settings, or ''."""
    # Read os.environ directly (not just the settings singleton) so a test that
    # monkeypatches the env var after import is honored deterministically.
    return os.environ.get("EXTENSION_TOKEN_SECRET") or settings.extension_token_secret


def get_extension_secret() -> bytes:
    """Return the HMAC secret, auto-generating + persisting one if needed.

    Resolution order:
    1. ``EXTENSION_TOKEN_SECRET`` env var / settings field (explicit override).
    2. A urlsafe secret read from ``{data_dir}/.extension_secret``.
    3. A freshly generated secret written there (mode 0600) on first run.
    """
    explicit = _env_secret()
    if explicit:
        return explicit.encode()

    global _cached_file_secret
    if _cached_file_secret is not None:
        return _cached_file_secret

    secret_path = Path(settings.data_dir) / _SECRET_FILENAME
    if secret_path.is_file():
        value = secret_path.read_text(encoding="utf-8").strip()
        if value:
            _cached_file_secret = value.encode()
            return _cached_file_secret

    # First run (or empty file): generate and persist ATOMICALLY with tight perms.
    # O_CREAT|O_EXCL means the file is created 0600 from the first byte (never a
    # world-readable window) and only one process wins the create — a concurrent
    # worker that loses the race reads the winner's secret so every worker agrees.
    value = secrets.token_urlsafe(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        value = secret_path.read_text(encoding="utf-8").strip()
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(value)
    _cached_file_secret = value.encode()
    return _cached_file_secret


def reset_secret_cache() -> None:
    """Clear the cached file secret (test helper)."""
    global _cached_file_secret
    _cached_file_secret = None


# ---------------------------------------------------------------------------
# base64url helpers (no padding, so tokens stay URL/header safe)
# ---------------------------------------------------------------------------


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


# ---------------------------------------------------------------------------
# Pairing code — HMAC(secret, window), truncated to 6 digits
# ---------------------------------------------------------------------------


def _current_window() -> int:
    """Return the current pairing time window index."""
    window_seconds = settings.extension_pairing_window_seconds or 300
    return int(time.time()) // window_seconds


def _code_for_window(window: int) -> str:
    """Derive the 6-digit zero-padded code for a given window."""
    digest = hmac.new(get_extension_secret(), str(window).encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:4], 'big') % 1_000_000:06d}"


def current_pairing_code() -> str:
    """Return the current 6-digit pairing code."""
    return _code_for_window(_current_window())


def verify_pairing_code(code: str | None) -> bool:
    """Accept the code for the current AND previous window; reject everything else.

    Checking the previous window keeps a code valid across a window boundary so a
    user who reads a code near the end of a window can still submit it. Comparison
    is timing-safe.
    """
    if not code:
        return False
    candidate = str(code)
    window = _current_window()
    valid = False
    # Evaluate both windows unconditionally (no short-circuit) to keep timing flat.
    for w in (window, window - 1):
        if hmac.compare_digest(candidate, _code_for_window(w)):
            valid = True
    return valid


# ---------------------------------------------------------------------------
# Token — b64url(issued_ts) "." b64url(HMAC(secret, issued_ts))
# ---------------------------------------------------------------------------


def mint_extension_token() -> str:
    """Mint a stateless HMAC token the extension stores and sends as a Bearer."""
    issued = str(int(time.time())).encode("ascii")
    signature = hmac.new(get_extension_secret(), issued, hashlib.sha256).digest()
    return f"{_b64url_encode(issued)}.{_b64url_encode(signature)}"


def verify_extension_token(token: str | None) -> bool:
    """Return True iff the token verifies under the current secret AND is not stale.

    Rejects empty input, malformed/truncated strings, and tampered signatures.
    The signature is checked FIRST (timing-safe); only then is the embedded
    issued-ts compared against ``settings.extension_token_ttl_days`` — so an
    attacker learns nothing new from an expired-vs-forged distinction. A token
    strictly older than the TTL is rejected (→ 401 re-pair). A TTL of 0 or less
    disables the age check (signature-only), for tests and a "never expire" mode.
    """
    if not token or not isinstance(token, str):
        return False
    parts = token.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False
    try:
        issued = _b64url_decode(parts[0])
        signature = _b64url_decode(parts[1])
    except (ValueError, TypeError, binascii.Error):
        return False
    expected = hmac.new(get_extension_secret(), issued, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        return False

    # Max-age check (G-1391). The signed payload IS the issued epoch, so a valid
    # signature guarantees the timestamp is authentic (not attacker-chosen).
    ttl_days = settings.extension_token_ttl_days
    if ttl_days > 0:
        try:
            issued_ts = int(issued.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return False
        if time.time() - issued_ts > ttl_days * 86400:
            return False
    return True
