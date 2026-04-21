"""OpenRouter OAuth PKCE service.

Handles the OAuth PKCE flow for OpenRouter API key generation:
1. Generate code challenge/verifier pair and auth URL
2. Exchange authorization code for API key
3. Check credit balance

See: https://openrouter.ai/docs/guides/overview/auth/oauth
"""

import hashlib
import json
import logging
import secrets

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_AUTH_URL = "https://openrouter.ai/auth"
OPENROUTER_KEY_EXCHANGE_URL = "https://openrouter.ai/api/v1/auth/keys"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"


class OpenRouterOAuthError(Exception):
    """Raised when an OpenRouter OAuth operation fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256).

    Returns:
        (code_verifier, code_challenge) tuple.
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    # base64url encode without padding
    code_challenge = (
        secrets.base64.b64encode(digest).rstrip(b"=").replace(b"+", b"-").replace(b"/", b"_")
    ).decode("ascii")
    return code_verifier, code_challenge


def build_auth_url(callback_url: str, code_challenge: str) -> str:
    """Build the OpenRouter authorization URL for the PKCE flow.

    Args:
        callback_url: URL to redirect to after authorization.
        code_challenge: S256 code challenge from generate_pkce_pair().

    Returns:
        Full authorization URL the user should visit.
    """
    params = (
        f"callback_url={callback_url}&code_challenge={code_challenge}&code_challenge_method=S256"
    )
    return f"{OPENROUTER_AUTH_URL}?{params}"


async def exchange_code_for_key(
    code: str,
    code_verifier: str,
) -> str:
    """Exchange an authorization code for an OpenRouter API key.

    Args:
        code: Authorization code from the callback redirect.
        code_verifier: The original code_verifier from generate_pkce_pair().

    Returns:
        The API key string (sk-or-...).

    Raises:
        OpenRouterOAuthError: If the exchange fails.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENROUTER_KEY_EXCHANGE_URL,
            json={
                "code": code,
                "code_verifier": code_verifier,
                "code_challenge_method": "S256",
            },
        )

    if response.status_code != 200:
        detail = ""
        try:
            body = response.json()
            detail = body.get("error", {}).get("message", str(body))
        except Exception:
            detail = response.text[:200]
        raise OpenRouterOAuthError(
            f"Key exchange failed: {detail}",
            status_code=response.status_code,
        )

    data = response.json()
    key = data.get("key", "")
    if not key:
        raise OpenRouterOAuthError("Key exchange returned empty key")
    return key


async def check_credits(api_key: str) -> dict:
    """Check OpenRouter credit balance.

    Args:
        api_key: OpenRouter API key.

    Returns:
        Dict with total_credits, total_usage, and balance fields.

    Raises:
        OpenRouterOAuthError: If the request fails.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            OPENROUTER_CREDITS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    if response.status_code != 200:
        raise OpenRouterOAuthError(
            f"Credits check failed (HTTP {response.status_code})",
            status_code=response.status_code,
        )

    data = response.json().get("data", {})
    total_credits = data.get("total_credits", 0.0)
    total_usage = data.get("total_usage", 0.0)
    return {
        "total_credits": total_credits,
        "total_usage": total_usage,
        "balance": round(total_credits - total_usage, 4),
    }


def store_api_key(db_session, api_key: str) -> None:
    """Store an OpenRouter API key in integration_configs.

    Args:
        db_session: SQLAlchemy session.
        api_key: The OpenRouter API key to store.
    """
    from career_os.models.integrations import IntegrationConfig

    row = (
        db_session.query(IntegrationConfig).filter(IntegrationConfig.name == "ai_providers").first()
    )

    if row is None:
        row = IntegrationConfig(
            name="ai_providers",
            display_name="AI Providers",
            enabled=True,
            credentials=json.dumps({"openrouter_api_key": api_key}),
            status="connected",
        )
        db_session.add(row)
    else:
        creds = {}
        if row.credentials:
            try:
                creds = json.loads(row.credentials)
            except (json.JSONDecodeError, TypeError):
                creds = {}
        creds["openrouter_api_key"] = api_key
        row.credentials = json.dumps(creds)
        row.enabled = True
        row.status = "connected"

    db_session.commit()
