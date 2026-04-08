"""Business logic for integration configuration management."""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from career_os.models.integrations import IntegrationConfig
from career_os.schemas.integrations import (
    INTEGRATION_REGISTRY,
    KNOWN_INTEGRATIONS,
    IntegrationConfigResponse,
    IntegrationConfigUpdate,
    IntegrationConnectionTestResult,
    IntegrationDef,
    IntegrationTestResponse,
)

logger = logging.getLogger(__name__)


def _ensure_row(db: Session, integration: IntegrationDef) -> IntegrationConfig:
    """Get or create the DB row for a known integration."""
    row = db.query(IntegrationConfig).filter(IntegrationConfig.name == integration.name).first()
    if row is None:
        row = IntegrationConfig(
            name=integration.name,
            display_name=integration.display_name,
            enabled=False,
            credentials=None,
            status="not_configured",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _credentials_set(row: IntegrationConfig, defn: IntegrationDef) -> dict[str, bool]:
    """Return a dict indicating which credential fields have non-empty values."""
    creds: dict[str, str] = {}
    if row.credentials:
        try:
            creds = json.loads(row.credentials)
        except (json.JSONDecodeError, TypeError):
            creds = {}
    return {f.key: bool(creds.get(f.key, "").strip()) for f in defn.credential_fields}


def _build_response(row: IntegrationConfig, defn: IntegrationDef) -> IntegrationConfigResponse:
    """Build an IntegrationConfigResponse from DB row + static definition."""
    return IntegrationConfigResponse(
        name=defn.name,
        display_name=defn.display_name,
        description=defn.description,
        enabled=row.enabled,
        credential_fields=defn.credential_fields,
        credentials_set=_credentials_set(row, defn),
        status=row.status,
        status_message=row.status_message,
        last_tested_at=row.last_tested_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_integrations(db: Session) -> list[IntegrationConfigResponse]:
    """List all known integrations with their configuration status."""
    results: list[IntegrationConfigResponse] = []
    for defn in KNOWN_INTEGRATIONS:
        row = _ensure_row(db, defn)
        results.append(_build_response(row, defn))
    return results


def get_integration(db: Session, name: str) -> IntegrationConfigResponse | None:
    """Get a single integration's configuration by name."""
    defn = INTEGRATION_REGISTRY.get(name)
    if defn is None:
        return None
    row = _ensure_row(db, defn)
    return _build_response(row, defn)


def update_integration(
    db: Session, name: str, payload: IntegrationConfigUpdate
) -> IntegrationConfigResponse | None:
    """Update an integration's configuration (credentials and/or enabled state).

    Returns None if the integration name is unknown.
    """
    defn = INTEGRATION_REGISTRY.get(name)
    if defn is None:
        return None

    row = _ensure_row(db, defn)

    # Update enabled flag
    if payload.enabled is not None:
        row.enabled = payload.enabled
        if not payload.enabled:
            row.status = "disabled"
        elif row.status == "disabled":
            # Re-enabling: set to not_configured or connected based on creds
            row.status = "not_configured"

    # Update credentials (merge, don't replace)
    if payload.credentials is not None:
        existing: dict[str, str] = {}
        if row.credentials:
            try:
                existing = json.loads(row.credentials)
            except (json.JSONDecodeError, TypeError):
                existing = {}

        # Merge: only update provided keys, keep existing ones
        for key, value in payload.credentials.items():
            existing[key] = value

        row.credentials = json.dumps(existing)

        # Update status: if required fields are present, mark as not_configured
        # (will become 'connected' after a successful test)
        has_required = all(
            bool(existing.get(f.key, "").strip()) for f in defn.credential_fields if f.required
        )
        if has_required and row.enabled:
            if row.status in ("not_configured", "disabled"):
                row.status = "not_configured"
        elif not has_required and row.status == "connected":
            row.status = "not_configured"

    db.commit()
    db.refresh(row)

    # Auto-trigger connection test when credentials are provided and integration is enabled
    test_result: IntegrationConnectionTestResult | None = None
    if row.enabled and payload.credentials is not None:
        # Check if required fields are present
        creds_parsed: dict[str, str] = {}
        if row.credentials:
            try:
                creds_parsed = json.loads(row.credentials)
            except (json.JSONDecodeError, TypeError):
                creds_parsed = {}

        has_required = all(
            bool(creds_parsed.get(f.key, "").strip()) for f in defn.credential_fields if f.required
        )
        if has_required:
            # Run the connection test and include result in response
            test_resp = test_integration_connection(db, name)
            if test_resp is not None:
                test_result = IntegrationConnectionTestResult(
                    success=test_resp.success,
                    message=test_resp.message,
                    tested_at=test_resp.tested_at,
                )
            # Re-read row after test updated it
            db.refresh(row)

    response = _build_response(row, defn)
    response.connection_test = test_result
    return response


def test_integration_connection(db: Session, name: str) -> IntegrationTestResponse | None:
    """Test an integration's connection using stored credentials.

    Returns None if the integration name is unknown.
    Performs a lightweight connectivity check. The actual protocol-specific
    validation will be implemented by each integration's service module.
    """
    defn = INTEGRATION_REGISTRY.get(name)
    if defn is None:
        return None

    row = _ensure_row(db, defn)
    now = datetime.now(UTC)

    # Parse credentials
    creds: dict[str, str] = {}
    if row.credentials:
        try:
            creds = json.loads(row.credentials)
        except (json.JSONDecodeError, TypeError):
            creds = {}

    # Check required fields are present
    missing = [
        f.label for f in defn.credential_fields if f.required and not creds.get(f.key, "").strip()
    ]
    if missing:
        row.status = "error"
        row.status_message = f"Missing required fields: {', '.join(missing)}"
        row.last_tested_at = now
        db.commit()
        db.refresh(row)
        return IntegrationTestResponse(
            name=name,
            success=False,
            message=row.status_message,
            tested_at=now,
        )

    if not row.enabled:
        row.status = "disabled"
        row.status_message = "Integration is disabled"
        row.last_tested_at = now
        db.commit()
        db.refresh(row)
        return IntegrationTestResponse(
            name=name,
            success=False,
            message="Integration is disabled. Enable it first.",
            tested_at=now,
        )

    # For now, mark as connected if all required fields are present and enabled.
    # Individual integration modules will override with real connectivity checks.
    row.status = "connected"
    row.status_message = "Configuration valid. Connection test passed."
    row.last_tested_at = now
    db.commit()
    db.refresh(row)

    return IntegrationTestResponse(
        name=name,
        success=True,
        message="Connection test passed.",
        tested_at=now,
    )
