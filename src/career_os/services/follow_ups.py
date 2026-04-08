"""Follow-up service layer — business logic for follow-up engine."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from career_os.models.models import Application, FollowUp, Profile
from career_os.schemas.follow_ups import FollowUpCreate
from career_os.services.activity import log_activity

# Default ghost detection thresholds (in days)
DEFAULT_GHOST_APPLIED_DAYS = 14
DEFAULT_GHOST_INTERVIEWING_DAYS = 7


class FollowUpNotFoundError(Exception):
    """Raised when a follow-up is not found."""


class ApplicationNotFoundError(Exception):
    """Raised when the referenced application does not exist."""


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Follow-Up CRUD
# ---------------------------------------------------------------------------


def create_follow_up(db: Session, payload: FollowUpCreate) -> FollowUp:
    """Create a new follow-up for an application.

    Validates that the profile and application exist.
    Creates an activity log entry.
    """
    # Verify profile
    profile = db.query(Profile).filter(Profile.id == payload.profile_id).first()
    if profile is None:
        raise ProfileNotFoundError(f"Profile {payload.profile_id} not found")

    # Verify application exists, is not archived, AND belongs to this profile
    app_obj = (
        db.query(Application)
        .filter(
            Application.id == payload.application_id,
            Application.profile_id == payload.profile_id,
            Application.archived_at.is_(None),
        )
        .first()
    )
    if app_obj is None:
        raise ApplicationNotFoundError(
            f"Application {payload.application_id} not found"
        )

    follow_up = FollowUp(
        profile_id=payload.profile_id,
        application_id=payload.application_id,
        due_date=payload.due_date,
        follow_up_type=payload.follow_up_type,
        notes=payload.notes,
    )
    db.add(follow_up)
    db.flush()

    _log_activity(
        db,
        profile_id=payload.profile_id,
        application_id=payload.application_id,
        action="follow_up_created",
        details=(
            f"Follow-up ({payload.follow_up_type}) "
            f"scheduled for {payload.due_date.strftime('%Y-%m-%d')}"
        ),
    )

    db.commit()
    db.refresh(follow_up)

    # Auto-push to TickTick (no-op if not configured)
    from career_os.services.ticktick_sync import try_auto_push_follow_up

    try_auto_push_follow_up(db, follow_up)

    # Auto-create calendar event for follow-up (no-op if calendar not configured)
    from career_os.services.calendar import create_follow_up_calendar_event

    try:
        create_follow_up_calendar_event(db, follow_up)
    except Exception:
        logger.warning(
            "Failed to create calendar event for follow-up %d",
            follow_up.id,
            exc_info=True,
        )

    return follow_up


def list_follow_ups(
    db: Session,
    *,
    profile_id: int,
    overdue: bool = False,
) -> tuple[list[FollowUp], int]:
    """List follow-ups, optionally filtering to overdue only.

    Excludes follow-ups whose parent application is archived (VAL-CROSS-019).
    Returns (follow_ups, total_count).
    """
    query = (
        db.query(FollowUp)
        .join(Application, FollowUp.application_id == Application.id)
        .filter(
            FollowUp.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
    )

    if overdue:
        now = datetime.now(UTC)
        query = query.filter(
            and_(
                FollowUp.due_date < now,
                FollowUp.completed_at.is_(None),
            )
        )

    # Order by due date ascending (soonest first)
    query = query.order_by(FollowUp.due_date.asc())
    follow_ups = query.all()
    return follow_ups, len(follow_ups)


def complete_follow_up(
    db: Session, follow_up_id: int, *, profile_id: int | None = None
) -> FollowUp:
    """Mark a follow-up as completed.

    Sets completed_at to current UTC time.
    Creates activity log entry.
    When *profile_id* is supplied, authorization is checked by joining
    through the owning application (follow_up → application →
    application.profile_id) rather than relying on follow_ups.profile_id.
    This handles legacy/migrated rows whose profile_id may be mismatched.
    """
    if profile_id is not None:
        # Authorize via the owning application's profile_id
        follow_up = (
            db.query(FollowUp)
            .join(Application, FollowUp.application_id == Application.id)
            .filter(
                FollowUp.id == follow_up_id,
                Application.profile_id == profile_id,
            )
            .first()
        )
    else:
        follow_up = db.query(FollowUp).filter(FollowUp.id == follow_up_id).first()
    if follow_up is None:
        raise FollowUpNotFoundError(f"Follow-up {follow_up_id} not found")

    follow_up.completed_at = datetime.now(UTC)

    _log_activity(
        db,
        profile_id=follow_up.profile_id,
        application_id=follow_up.application_id,
        action="follow_up_completed",
        details=f"Follow-up ({follow_up.follow_up_type}) marked as completed",
    )

    db.commit()
    db.refresh(follow_up)
    return follow_up


def get_overdue_count(db: Session, *, profile_id: int) -> int:
    """Count overdue, incomplete follow-ups.

    Excludes follow-ups for archived applications (VAL-CROSS-019).
    """
    now = datetime.now(UTC)
    count = (
        db.query(FollowUp)
        .join(Application, FollowUp.application_id == Application.id)
        .filter(
            FollowUp.profile_id == profile_id,
            FollowUp.due_date < now,
            FollowUp.completed_at.is_(None),
            Application.archived_at.is_(None),
        )
        .count()
    )
    return count


# ---------------------------------------------------------------------------
# Ghost Detection
# ---------------------------------------------------------------------------


def get_ghost_applications(
    db: Session,
    *,
    profile_id: int,
    applied_threshold_days: int = DEFAULT_GHOST_APPLIED_DAYS,
    interviewing_threshold_days: int = DEFAULT_GHOST_INTERVIEWING_DAYS,
) -> list[Application]:
    """Find applications that may be ghosted.

    An application is a ghost candidate if:
    - Status is 'applied' and last update was > applied_threshold_days ago
    - Status is 'interviewing' and last update was > interviewing_threshold_days ago
    """
    now = datetime.now(UTC)
    applied_cutoff = now - timedelta(days=applied_threshold_days)
    interviewing_cutoff = now - timedelta(days=interviewing_threshold_days)

    ghosts = (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .filter(
            # Applied ghosts OR interviewing ghosts
            (
                and_(
                    Application.status.ilike("applied"),
                    Application.updated_at < applied_cutoff,
                )
            )
            | (
                and_(
                    Application.status.ilike("interviewing"),
                    Application.updated_at < interviewing_cutoff,
                )
            )
        )
        .all()
    )
    return ghosts


def is_ghost_application(
    app_obj: Application,
    *,
    applied_threshold_days: int = DEFAULT_GHOST_APPLIED_DAYS,
    interviewing_threshold_days: int = DEFAULT_GHOST_INTERVIEWING_DAYS,
) -> bool:
    """Check if a single application is a ghost candidate."""
    now = datetime.now(UTC)
    status_lower = app_obj.status.lower()

    # Ensure updated_at is timezone-aware
    updated = app_obj.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)

    if status_lower == "applied":
        return (now - updated).days >= applied_threshold_days
    if status_lower == "interviewing":
        return (now - updated).days >= interviewing_threshold_days
    return False
