"""OpenRouter OAuth onboarding API routes.

Implements the PKCE flow for one-click OpenRouter API key setup:
1. POST /api/openrouter/oauth/start → returns auth URL + stores verifier in session
2. POST /api/openrouter/oauth/callback → exchanges code for key, stores it
3. GET /api/openrouter/credits → checks credit balance
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.services.openrouter_oauth import (
    OpenRouterOAuthError,
    build_auth_url,
    check_credits,
    exchange_code_for_key,
    generate_pkce_pair,
    store_api_key,
)

router = APIRouter(prefix="/api/openrouter", tags=["openrouter-oauth"])


# ---- Request/Response schemas ----


class OAuthStartRequest(BaseModel):
    """Request to start the OAuth PKCE flow."""

    callback_url: str = Field(
        ...,
        description="URL to redirect to after OpenRouter authorization",
    )


class OAuthStartResponse(BaseModel):
    """Response with the authorization URL and code verifier."""

    auth_url: str
    code_verifier: str  # Client must store this for the callback step


class OAuthCallbackRequest(BaseModel):
    """Request to exchange authorization code for API key."""

    code: str = Field(..., description="Authorization code from OpenRouter redirect")
    code_verifier: str = Field(..., description="The code_verifier from the start step")


class OAuthCallbackResponse(BaseModel):
    """Response after successful key exchange."""

    success: bool
    message: str
    has_credits: bool = False
    balance: float = 0.0


class CreditsResponse(BaseModel):
    """OpenRouter credit balance response."""

    total_credits: float
    total_usage: float
    balance: float
    needs_deposit: bool


# ---- Routes ----


@router.post("/oauth/start")
async def oauth_start(payload: OAuthStartRequest) -> OAuthStartResponse:
    """Start the OpenRouter OAuth PKCE flow.

    Returns an authorization URL the client should open in a browser,
    plus a code_verifier the client must store for the callback step.
    """
    code_verifier, code_challenge = generate_pkce_pair()
    auth_url = build_auth_url(payload.callback_url, code_challenge)
    return OAuthStartResponse(
        auth_url=auth_url,
        code_verifier=code_verifier,
    )


@router.post("/oauth/callback")
async def oauth_callback(
    payload: OAuthCallbackRequest,
    db: Annotated[Session, Depends(get_db)],
) -> OAuthCallbackResponse:
    """Exchange the authorization code for an OpenRouter API key.

    Stores the key in integration_configs and checks credit balance.
    """
    try:
        api_key = await exchange_code_for_key(payload.code, payload.code_verifier)
    except OpenRouterOAuthError as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"OpenRouter OAuth failed: {e.message}",
        ) from None

    # Store the key
    store_api_key(db, api_key)

    # Check balance
    try:
        credits = await check_credits(api_key)
        balance = credits["balance"]
        return OAuthCallbackResponse(
            success=True,
            message="OpenRouter connected successfully.",
            has_credits=balance > 0,
            balance=balance,
        )
    except OpenRouterOAuthError:
        # Key stored but balance check failed — still a success
        return OAuthCallbackResponse(
            success=True,
            message="OpenRouter connected. Could not check balance — add credits at openrouter.ai.",
        )


@router.get("/credits")
async def get_credits(
    db: Annotated[Session, Depends(get_db)],
) -> CreditsResponse:
    """Check OpenRouter credit balance using stored API key."""
    import json

    from career_os.models.integrations import IntegrationConfig

    row = db.query(IntegrationConfig).filter(IntegrationConfig.name == "ai_providers").first()
    if row is None or not row.credentials:
        raise HTTPException(
            status_code=404,
            detail="No AI provider configured. Complete OpenRouter setup first.",
        )

    try:
        creds = json.loads(row.credentials)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=404, detail="Invalid credentials format.") from None

    api_key = creds.get("openrouter_api_key", "")
    if not api_key:
        raise HTTPException(
            status_code=404,
            detail="No OpenRouter API key configured.",
        )

    try:
        credits = await check_credits(api_key)
    except OpenRouterOAuthError as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"Credits check failed: {e.message}",
        ) from None

    return CreditsResponse(
        total_credits=credits["total_credits"],
        total_usage=credits["total_usage"],
        balance=credits["balance"],
        needs_deposit=credits["balance"] < 1.0,
    )
