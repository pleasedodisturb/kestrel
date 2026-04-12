"""OpenRouter OAuth PKCE authentication endpoints."""

import hashlib
import logging
import secrets
import time
from base64 import urlsafe_b64encode
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query

from career_os.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory store for PKCE verifiers keyed by state token.
# Entries are capped and expire after 10 minutes to prevent DoS.
_MAX_PENDING = 100
_VERIFIER_TTL_SECONDS = 600  # 10 minutes

_pending_verifiers: dict[str, tuple[str, float]] = {}  # state → (verifier, created_at)

# In-memory store for the OAuth-obtained API key.
# Using a module-level variable instead of os.environ avoids leaking the key
# to child processes and /proc/<pid>/environ.  DB persistence is future work.
_runtime_api_key: str = ""

OPENROUTER_AUTH_URL = "https://openrouter.ai/auth"
OPENROUTER_KEYS_URL = "https://openrouter.ai/api/v1/auth/keys"


def _cleanup_expired() -> None:
    """Remove expired verifier entries."""
    now = time.time()
    expired = [k for k, (_, ts) in _pending_verifiers.items() if now - ts > _VERIFIER_TTL_SECONDS]
    for k in expired:
        del _pending_verifiers[k]


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256).

    Returns:
        (code_verifier, code_challenge) where challenge is the SHA-256
        hash of the verifier, base64url-encoded without padding.
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


@router.get("/openrouter/start")
async def openrouter_auth_start() -> dict:
    """Generate PKCE challenge and return the OpenRouter authorization URL.

    The frontend should redirect or open this URL so the user can authorize
    Kestrel to use their OpenRouter account.
    """
    _cleanup_expired()

    if len(_pending_verifiers) >= _MAX_PENDING:
        raise HTTPException(
            status_code=429,
            detail="Too many pending OAuth flows. Please try again later.",
        )

    code_verifier, code_challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(32)

    _pending_verifiers[state] = (code_verifier, time.time())

    # Build callback URL from the backend's own address.
    callback_url = f"{settings.frontend_url}/api/auth/openrouter/callback"

    params = urlencode(
        {
            "callback_url": callback_url,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    auth_url = f"{OPENROUTER_AUTH_URL}?{params}"

    return {"auth_url": auth_url, "state": state}


@router.get("/openrouter/callback")
async def openrouter_auth_callback(
    code: str = Query(..., description="Authorization code from OpenRouter"),
    state: str = Query(..., min_length=1, description="State token for PKCE verification"),
) -> dict:
    """Exchange the authorization code for an OpenRouter API key.

    OpenRouter redirects here after the user authorizes.  We POST the code
    together with the original code_verifier to obtain a permanent API key.
    """
    _cleanup_expired()

    entry = _pending_verifiers.pop(state, None)
    if entry is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter. Please restart the OAuth flow.",
        )
    code_verifier, _ = entry

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENROUTER_KEYS_URL,
                json={"code": code, "code_verifier": code_verifier},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("OpenRouter key exchange failed: %s %s", exc.response.status_code, exc)
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter key exchange failed ({exc.response.status_code}).",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("OpenRouter key exchange request error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach OpenRouter to exchange the authorization code.",
        ) from exc

    api_key = data.get("key", "")
    if not api_key:
        raise HTTPException(status_code=502, detail="OpenRouter returned an empty API key.")

    # Store in application memory (runtime only — DB persistence is future work).
    global _runtime_api_key  # noqa: PLW0603
    _runtime_api_key = api_key

    return {"success": True, "provider": "openrouter"}


@router.get("/openrouter/status")
async def openrouter_auth_status() -> dict:
    """Check whether an OpenRouter API key is currently configured."""
    key = _runtime_api_key or settings.openrouter_api_key
    connected = bool(key)
    return {"connected": connected, "provider": "openrouter"}
