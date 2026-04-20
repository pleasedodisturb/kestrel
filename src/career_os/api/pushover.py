"""Pushover notification API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_FILTER_BY_CATEGORY, DESC_PROFILE_ID
from career_os.database import get_db
from career_os.schemas.pushover import (
    NotificationLogListResponse,
    NotificationLogResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationTriggerResponse,
    SendNotificationRequest,
)
from career_os.services.pushover import (
    deliver_queued_notifications,
    get_preferences,
    list_notification_logs,
    send_test_notification,
    test_pushover_connection,
    trigger_discovery_alert,
    trigger_follow_up_reminders,
    trigger_ghost_alerts,
    trigger_interview_reminders,
    update_preferences,
)
from career_os.schemas.constraints import INT64_MAX

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


@router.get("/preferences")
async def get_notification_preferences(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationPreferenceResponse:
    """Get notification preferences for a profile."""
    pref = get_preferences(db, profile_id)
    return NotificationPreferenceResponse.model_validate(pref)


@router.put("/preferences")
async def update_notification_preferences(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    payload: NotificationPreferenceUpdate = ...,
) -> NotificationPreferenceResponse:
    """Update notification preferences for a profile."""
    pref = update_preferences(db, profile_id, payload)
    return NotificationPreferenceResponse.model_validate(pref)


# ---------------------------------------------------------------------------
# Notification log
# ---------------------------------------------------------------------------


@router.get("/log")
async def get_notification_log(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[str | None, Query(description=DESC_FILTER_BY_CATEGORY)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=INT64_MAX)] = 0,
) -> NotificationLogListResponse:
    """List notification history for a profile."""
    logs, total = list_notification_logs(
        db, profile_id=profile_id, category=category, limit=limit, offset=offset
    )
    return NotificationLogListResponse(
        notifications=[NotificationLogResponse.model_validate(log) for log in logs],
        total=total,
    )


# ---------------------------------------------------------------------------
# Trigger endpoints
# ---------------------------------------------------------------------------


@router.post("/trigger/follow-ups")
async def trigger_follow_ups(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationTriggerResponse:
    """Check for due follow-ups and send Pushover notifications."""
    result = trigger_follow_up_reminders(db, profile_id)
    return NotificationTriggerResponse(**result)


@router.post("/trigger/ghosts")
async def trigger_ghosts(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationTriggerResponse:
    """Check for ghost applications and send Pushover notifications."""
    result = trigger_ghost_alerts(db, profile_id)
    return NotificationTriggerResponse(**result)


@router.post("/trigger/discovery")
async def trigger_discovery(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    company: Annotated[str, Query(description="Company name")],
    role: Annotated[str, Query(description="Role title")],
    score: Annotated[float, Query(ge=0, le=10, description="Fit score")],
    db: Annotated[Session, Depends(get_db)],
    application_id: Annotated[int | None, Query(ge=1, le=INT64_MAX, )] = None,
    url: Annotated[str | None, Query()] = None,
) -> NotificationTriggerResponse:
    """Send notification for a high-scoring discovery."""
    result = trigger_discovery_alert(
        db,
        profile_id,
        company=company,
        role=role,
        score=score,
        application_id=application_id,
        url=url,
    )
    return NotificationTriggerResponse(**result)


@router.post("/trigger/interviews")
async def trigger_interviews(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationTriggerResponse:
    """Check for upcoming interviews and send Pushover reminders."""
    result = trigger_interview_reminders(db, profile_id)
    return NotificationTriggerResponse(**result)


# ---------------------------------------------------------------------------
# Send / Test
# ---------------------------------------------------------------------------


@router.post("/deliver-queued")
async def deliver_queued(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Deliver queued notifications that were deferred during quiet hours."""
    return deliver_queued_notifications(db, profile_id)


@router.post("/send")
async def send_notification(
    payload: SendNotificationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Send a manual notification via Pushover."""
    return send_test_notification(
        db,
        profile_id=payload.profile_id,
        category=payload.category,
        title=payload.title,
        message=payload.message,
        application_id=payload.application_id,
    )


@router.post("/test-connection")
async def test_connection(
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Test Pushover connection by validating credentials."""
    return test_pushover_connection(db)
