"""Integration configuration API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
) -> IntegrationListResponse:
    """List all known integrations with their configuration status."""
    integrations = list_integrations(db)
    return IntegrationListResponse(integrations=integrations, count=len(integrations))


@router.get("/{name}/config", responses={404: {"description": "Not found"}})
async def get_integration_config(
    name: str,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    """Get a specific integration's configuration by name."""
    result = get_integration(db, name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {name}")
    return result


@router.put("/{name}/config", responses={404: {"description": "Not found"}})
async def update_integration_config(
    name: str,
    payload: IntegrationConfigUpdate,
    db: Session = Depends(get_db),
) -> IntegrationConfigResponse:
    """Update an integration's configuration (credentials and/or enabled state).

    Credentials are merged: only the keys you provide are updated.
    """
    result = update_integration(db, name, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {name}")
    return result


@router.post("/{name}/test", responses={404: {"description": "Not found"}})
async def test_integration(
    name: str,
    db: Session = Depends(get_db),
) -> IntegrationTestResponse:
    """Test an integration's connection using stored credentials."""
    result = test_integration_connection(db, name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {name}")
    return result
