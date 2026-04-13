"""Privacy metadata API routes."""

import logging

from fastapi import APIRouter, HTTPException

from career_os.ai.privacy import PROVIDER_PRIVACY_REGISTRY, get_privacy_info
from career_os.schemas.privacy import ProviderPrivacyInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/privacy", tags=["privacy"])


@router.get("", response_model=list[ProviderPrivacyInfo])
async def list_provider_privacy() -> list[ProviderPrivacyInfo]:
    """Return privacy info for all known AI providers."""
    return list(PROVIDER_PRIVACY_REGISTRY.values())


@router.get("/{provider}", response_model=ProviderPrivacyInfo)
async def get_provider_privacy(provider: str) -> ProviderPrivacyInfo:
    """Return privacy info for a single AI provider.

    Raises 404 if the provider is not in the registry.
    """
    info = get_privacy_info(provider)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    return info
