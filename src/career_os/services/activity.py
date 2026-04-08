"""Shared activity logging helper — universal audit trail for all entities."""

from sqlalchemy.orm import Session

from career_os.models.models import ActivityLog


def log_activity(
    db: Session,
    *,
    profile_id: int,
    action: str,
    application_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: str | None = None,
    source: str = "api",
    duration_ms: int | None = None,
    error: str | None = None,
    extra_data: str | None = None,
) -> ActivityLog:
    """Create an activity log entry.

    Supports both legacy application-scoped logging (via *application_id*)
    and Phase 2 entity-generic logging (via *entity_type*/*entity_id*).

    Does NOT commit — caller handles the transaction boundary.
    """
    log = ActivityLog(
        profile_id=profile_id,
        application_id=application_id,
        action=action,
        details=details,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
        duration_ms=duration_ms,
        error=error,
        extra_data=extra_data,
    )
    db.add(log)
    return log
