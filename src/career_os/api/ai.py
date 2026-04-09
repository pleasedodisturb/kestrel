"""AI provider API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from career_os.ai.factory import UnsupportedProviderError, get_ai_provider
from career_os.database import get_db
from career_os.schemas.ai import AICompleteRequest, AIResponse
from career_os.schemas.ai_health import AIHealthResponse, ProviderHealthStatus
from career_os.services.ai_health import check_all_providers, check_single_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/complete")
async def ai_complete(request: AICompleteRequest) -> AIResponse:
    """Generate an AI completion.

    Uses the AI provider configured via AI_PROVIDER env var.
    With mock provider, returns deterministic structured responses.
    """
    try:
        provider = get_ai_provider()
    except (UnsupportedProviderError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AI provider configuration error: {exc}",
        ) from exc

    try:
        response = await provider.complete(
            prompt=request.prompt,
            feature=request.feature,
            context=request.context,
        )
    except ValueError as exc:
        # Missing API keys, invalid config, etc.
        raise HTTPException(
            status_code=422,
            detail=f"AI provider configuration error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("AI provider error")
        raise HTTPException(
            status_code=502,
            detail=f"AI provider error: {exc}",
        ) from exc

    return response


@router.get("/provider")
async def get_current_provider() -> dict[str, str]:
    """Return the currently configured AI provider name."""
    try:
        provider = get_ai_provider()
        return {"provider": provider.name}
    except (UnsupportedProviderError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AI provider configuration error: {exc}",
        ) from exc


@router.get("/health")
async def ai_health(db: Session = Depends(get_db)) -> AIHealthResponse:
    """Check connectivity and health of all configured AI providers.

    Reads provider configuration from stored integration config.
    Only reports runtime-supported providers (mock, openrouter).
    Each provider is checked independently — one failure does not affect others.
    """
    return await check_all_providers(db)


@router.get("/health/check")
async def ai_health_check_single(
    provider: str = "mock",
    db: Session = Depends(get_db),
) -> ProviderHealthStatus:
    """Check health of a single AI provider by name."""
    return await check_single_provider(provider, db)
