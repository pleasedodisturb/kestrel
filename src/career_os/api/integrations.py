"""Integration configuration API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from career_os.api.constants import RESP_404
from career_os.database import get_db
from career_os.schemas.integrations import (
    IntegrationConfigResponse,
    IntegrationConfigUpdate,
    IntegrationListResponse,
    IntegrationTestResponse,
)
from career_os.services.integrations import (
    get_integration,
    list_integrations,
    test_integration_connection,
    update_integration,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("")
async def list_all_integrations(
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationListResponse:
    """List all known integrations with their configuration status."""
    integrations = list_integrations(db)
    return IntegrationListResponse(integrations=integrations, count=len(integrations))


@router.get("/{name}/config", responses=RESP_404)
async def get_integration_config(
    name: str,
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationConfigResponse:
    """Get a specific integration's configuration by name."""
    result = get_integration(db, name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {name}")
    return result


@router.put("/{name}/config", responses=RESP_404)
async def update_integration_config(
    name: str,
    payload: IntegrationConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationConfigResponse:
    """Update an integration's configuration (credentials and/or enabled state).

    Credentials are merged: only the keys you provide are updated.
    """
    result = update_integration(db, name, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {name}")
    return result


@router.post("/{name}/test", responses=RESP_404)
async def test_integration(
    name: str,
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationTestResponse:
    """Test an integration's connection using stored credentials."""
    result = test_integration_connection(db, name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {name}")
    return result
