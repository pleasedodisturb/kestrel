"""OpenRouter OAuth PKCE authentication endpoints."""

import hashlib
import logging
import os
import secrets
import time
from base64 import urlsafe_b64encode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from career_os.config import settings
from career_os.database import get_db
from career_os.schemas.integrations import IntegrationConfigUpdate
from career_os.services.integrations import get_integration, update_integration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

limiter = Limiter(key_func=get_remote_address)

# In-memory store for PKCE verifiers keyed by state token.
# Each entry is (code_verifier, created_at_timestamp).
# Entries are consumed on callback; expired entries are purged on each /start call.
_pending_verifiers: dict[str, tuple[str, float]] = {}

# Limits to prevent memory exhaustion from abandoned OAuth flows.
_MAX_PENDING = 1000
_VERIFIER_TTL_SECONDS = 600  # 10 minutes

OPENROUTER_AUTH_URL = "https://openrouter.ai/auth"
OPENROUTER_KEYS_URL = "https://openrouter.ai/api/v1/auth/keys"


def _cleanup_expired_verifiers() -> None:
    """Remove expired PKCE verifiers from the in-memory store."""
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
@limiter.limit("10/minute")
async def openrouter_auth_start(request: Request) -> dict:
    """Generate PKCE challenge and return the OpenRouter authorization URL.

    The frontend should redirect or open this URL so the user can authorize
    Kestrel to use their OpenRouter account.
    """
    # Purge expired entries and enforce size limit to prevent memory exhaustion.
    _cleanup_expired_verifiers()
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

    auth_url = (
        f"{OPENROUTER_AUTH_URL}"
        f"?callback_url={callback_url}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
    )

    return {"auth_url": auth_url, "state": state}


@router.get("/openrouter/callback")
@limiter.limit("20/minute")
async def openrouter_auth_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from OpenRouter"),
    state: str = Query(..., description="State token for PKCE verification"),
    db: Session = Depends(get_db),
) -> dict:
    """Exchange the authorization code for an OpenRouter API key.

    OpenRouter redirects here after the user authorizes.  We POST the code
    together with the original code_verifier to obtain a permanent API key.
    """
    entry = _pending_verifiers.pop(state, None)
    if entry is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter. Please restart the OAuth flow.",
        )

    code_verifier, created_at = entry
    if time.time() - created_at > _VERIFIER_TTL_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="OAuth flow expired. Please restart the authorization.",
        )

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

    # Persist to database via integrations service and also set env var for
    # backward compatibility with the current process.
    update_integration(
        db,
        "ai_providers",
        IntegrationConfigUpdate(
            enabled=True,
            credentials={"openrouter_api_key": api_key},
        ),
    )
    os.environ["OPENROUTER_API_KEY"] = api_key
    logger.info("OpenRouter API key persisted to database and process environment.")

    return {"success": True, "provider": "openrouter"}


def _get_stored_api_key(db: Session) -> str:
    """Read the OpenRouter API key from the DB, then fall back to env/settings."""
    integration = get_integration(db, "ai_providers")
    if integration is not None and integration.credentials_set.get("openrouter_api_key"):
        # Key exists in DB — we can't read the raw value from the response
        # schema (it only reports booleans), but if it's been set via OAuth,
        # the env var should still be populated in this process.
        pass
    return os.environ.get("OPENROUTER_API_KEY", "") or settings.openrouter_api_key


@router.get("/openrouter/status")
async def openrouter_auth_status(db: Session = Depends(get_db)) -> dict:
    """Check whether an OpenRouter API key is currently configured."""
    key = _get_stored_api_key(db)
    connected = bool(key)
    # Show only the last 4 characters to avoid leaking the key prefix.
    key_preview = f"...{key[-4:]}" if connected and len(key) > 4 else ""

    return {"connected": connected, "provider": "openrouter", "key_preview": key_preview}
