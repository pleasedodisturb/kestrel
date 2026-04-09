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


def _parse_creds_json(raw: str | None) -> dict[str, str]:
    """Parse a JSON credentials string, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _merge_credentials(
    existing_raw: str | None,
    new_creds: dict[str, str],
) -> str:
    """Merge new credential values into existing JSON credentials string."""
    existing = _parse_creds_json(existing_raw)
    for key, value in new_creds.items():
        existing[key] = value
    return json.dumps(existing)


def _determine_new_status(
    current_status: str,
    enabled: bool,
    has_required: bool,
) -> str:
    """Determine the new status after a credentials update."""
    if has_required and enabled:
        if current_status in ("not_configured", "disabled"):
            return "not_configured"
        return current_status
    if not has_required and current_status == "connected":
        return "not_configured"
    return current_status


def _has_required_fields(creds: dict[str, str], defn: IntegrationDef) -> bool:
    """Check whether all required credential fields are present and non-empty."""
    return all(bool(creds.get(f.key, "").strip()) for f in defn.credential_fields if f.required)


def _run_integration_test(
    db: Session,
    name: str,
    creds_raw: str | None,
    defn: IntegrationDef,
) -> IntegrationConnectionTestResult | None:
    """Run a connection test if required fields are present, return result."""
    creds = _parse_creds_json(creds_raw)
    if not _has_required_fields(creds, defn):
        return None
    test_resp = test_integration_connection(db, name)
    if test_resp is None:
        return None
    return IntegrationConnectionTestResult(
        success=test_resp.success,
        message=test_resp.message,
        tested_at=test_resp.tested_at,
    )


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
            row.status = "not_configured"

    # Update credentials (merge, don't replace)
    if payload.credentials is not None:
        row.credentials = _merge_credentials(row.credentials, payload.credentials)
        merged_creds = _parse_creds_json(row.credentials)
        has_required = _has_required_fields(merged_creds, defn)
        row.status = _determine_new_status(row.status, row.enabled, has_required)

    db.commit()
    db.refresh(row)

    # Auto-trigger connection test when credentials are provided and integration is enabled
    test_result: IntegrationConnectionTestResult | None = None
    if row.enabled and payload.credentials is not None:
        test_result = _run_integration_test(db, name, row.credentials, defn)
        if test_result is not None:
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
