"""Application service layer — business logic for pipeline CRUD."""

from datetime import UTC, datetime

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, joinedload

from career_os.models.models import Application, Profile
from career_os.schemas.applications import (
    ApplicationCreate,
    ApplicationUpdate,
    is_valid_transition,
)
from career_os.services.activity import log_activity


class ApplicationNotFoundError(Exception):
    """Raised when an application is not found or is archived."""


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed."""

    def __init__(self, from_status: str, to_status: str) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Invalid status transition from '{from_status}' to '{to_status}'")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_active_application(
    db: Session, application_id: int, *, profile_id: int | None = None
) -> Application:
    """Fetch a non-archived application or raise.

    When *profile_id* is given the query also filters by profile ownership,
    ensuring cross-profile isolation (returns 404 for wrong profile).
    """
    filters = [Application.id == application_id, Application.archived_at.is_(None)]
    if profile_id is not None:
        filters.append(Application.profile_id == profile_id)
    app_obj = db.query(Application).filter(*filters).first()
    if app_obj is None:
        raise ApplicationNotFoundError(f"Application {application_id} not found")
    return app_obj


def _log_activity(
    db: Session,
    *,
    profile_id: int,
    application_id: int,
    action: str,
    details: str | None = None,
    source: str = "api",
) -> None:
    """Delegate to shared activity logger with application context."""
    log_activity(
        db,
        profile_id=profile_id,
        application_id=application_id,
        entity_type="application",
        entity_id=application_id,
        action=action,
        details=details,
        source=source,
    )


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def create_application(db: Session, payload: ApplicationCreate) -> Application:
    """Create a new application in 'discovered' status.

    Validates profile existence and creates an activity log entry.
    """
    # Verify profile exists
    profile = db.query(Profile).filter(Profile.id == payload.profile_id).first()
    if profile is None:
        raise ProfileNotFoundError(f"Profile {payload.profile_id} not found")

    app_obj = Application(
        profile_id=payload.profile_id,
        company=payload.company,
        role=payload.role,
        url=payload.url,
        source=payload.source,
        status="discovered",
        salary_range=payload.salary_range,
        contact=payload.contact,
        next_step=payload.next_step,
        notes=payload.notes,
        fit_score=payload.fit_score,
    )
    db.add(app_obj)
    db.flush()  # Get the ID

    _log_activity(
        db,
        profile_id=payload.profile_id,
        application_id=app_obj.id,
        action="created",
        details=f"Created application for {payload.company} — {payload.role}",
    )
    db.commit()
    db.refresh(app_obj)

    # Auto-push to TickTick (no-op if not configured)
    from career_os.services.ticktick_sync import try_auto_push_pipeline_action

    try_auto_push_pipeline_action(db, app_obj, "Application created")

    return app_obj


def get_application(
    db: Session, application_id: int, *, profile_id: int | None = None
) -> Application:
    """Get a single non-archived application with related data.

    When *profile_id* is supplied, 404 is returned if the application
    does not belong to that profile (cross-profile isolation).

    Eagerly loads packages to avoid N+1 queries in the detail view.
    """
    filters = [Application.id == application_id, Application.archived_at.is_(None)]
    if profile_id is not None:
        filters.append(Application.profile_id == profile_id)
    app_obj = (
        db.query(Application).options(joinedload(Application.packages)).filter(*filters).first()
    )
    if app_obj is None:
        raise ApplicationNotFoundError(f"Application {application_id} not found")
    return app_obj


def list_applications(
    db: Session,
    *,
    profile_id: int,
    status: str | None = None,
    search: str | None = None,
    sort: str | None = None,
    order: str = "desc",
) -> tuple[list[Application], int]:
    """List applications with optional filters and sorting.

    Returns (applications, total_count).
    """
    query = db.query(Application).filter(
        Application.profile_id == profile_id,
        Application.archived_at.is_(None),
    )

    # Filter by status (case-insensitive to handle DB variants)
    if status:
        query = query.filter(Application.status.ilike(status))

    # Search by company (case-insensitive)
    if search:
        query = query.filter(Application.company.ilike(f"%{search}%"))

    total = query.count()

    # Sorting
    sort_column = Application.created_at  # default
    if sort == "score":
        sort_column = Application.fit_score
    elif sort == "date":
        sort_column = Application.created_at

    if order == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    applications = query.all()
    return applications, total


def update_application(
    db: Session,
    application_id: int,
    payload: ApplicationUpdate,
    *,
    profile_id: int | None = None,
) -> Application:
    """Update an application, with status workflow validation.

    Creates activity log entries for field changes and status changes.
    When *profile_id* is supplied, 404 is returned if the application
    does not belong to that profile.
    """
    app_obj = _get_active_application(db, application_id, profile_id=profile_id)

    update_data = payload.model_dump(exclude_unset=True)

    # Handle status transition validation
    if "status" in update_data:
        new_status = update_data["status"].strip().lower()
        update_data["status"] = new_status  # ensure stored value is canonical
        old_status = app_obj.status.strip().lower()
        if not is_valid_transition(old_status, new_status):
            raise InvalidStatusTransitionError(old_status, new_status)

        # Log status change separately
        _log_activity(
            db,
            profile_id=app_obj.profile_id,
            application_id=app_obj.id,
            action="status_changed",
            details=f"Status changed from '{old_status}' to '{new_status}'",
        )

        # If transitioning to applied, set date_applied
        if new_status == "applied" and app_obj.date_applied is None:
            app_obj.date_applied = datetime.now(UTC)

    # Track non-status changes
    changed_fields = []
    for field, value in update_data.items():
        if field == "status":
            setattr(app_obj, field, value)
        else:
            old_val = getattr(app_obj, field, None)
            if old_val != value:
                changed_fields.append(field)
                setattr(app_obj, field, value)

    # Log field updates (not status — that's logged above)
    if changed_fields:
        _log_activity(
            db,
            profile_id=app_obj.profile_id,
            application_id=app_obj.id,
            action="updated",
            details=f"Updated fields: {', '.join(changed_fields)}",
        )

    # Capture status change for auto-sync before commit
    status_changed = "status" in update_data

    db.commit()
    db.refresh(app_obj)

    # Auto-push status change to TickTick (no-op if not configured)
    if status_changed:
        from career_os.services.ticktick_sync import try_auto_push_pipeline_action

        try_auto_push_pipeline_action(db, app_obj, f"Status changed to {app_obj.status}")

    return app_obj


def delete_application(
    db: Session, application_id: int, *, profile_id: int | None = None
) -> Application:
    """Soft-delete an application by setting archived_at.

    Does NOT destroy related records (follow_ups, activity_logs).
    When *profile_id* is supplied, 404 is returned if the application
    does not belong to that profile.
    """
    app_obj = _get_active_application(db, application_id, profile_id=profile_id)

    app_obj.archived_at = datetime.now(UTC)

    _log_activity(
        db,
        profile_id=app_obj.profile_id,
        application_id=app_obj.id,
        action="archived",
        details="Application archived (soft delete)",
    )

    db.commit()
    db.refresh(app_obj)
    return app_obj
