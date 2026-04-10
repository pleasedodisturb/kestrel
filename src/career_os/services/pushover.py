"""Pushover notification service — business logic for sending notifications.

Handles: follow-up reminders, ghost alerts, high-scoring discovery alerts,
interview reminders. Respects user preferences (per-category enable/disable,
quiet hours). Auth failures are logged and surfaced, never crash.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from career_os.models.integrations import IntegrationConfig
from career_os.models.models import Application, FollowUp

if TYPE_CHECKING:
    from career_os.models.calendar import CalendarEvent
from career_os.models.pushover import NotificationLog, NotificationPreference
from career_os.schemas.pushover import NotificationPreferenceUpdate
from career_os.services.follow_ups import (
    get_ghost_applications,
)
from career_os.services.pushover_client import (
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PushoverAPIError,
    PushoverAuthError,
    PushoverClient,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class PushoverNotConfiguredError(Exception):
    """Raised when Pushover integration is not configured or disabled."""


def _get_pushover_client(db: Session) -> PushoverClient:
    """Get a PushoverClient from the integration config.

    Raises PushoverNotConfiguredError if not configured or disabled.
    """
    row = db.query(IntegrationConfig).filter(IntegrationConfig.name == "pushover").first()
    if row is None or not row.enabled:
        raise PushoverNotConfiguredError("Pushover integration is not enabled")

    creds: dict[str, str] = {}
    if row.credentials:
        import contextlib

        with contextlib.suppress(json.JSONDecodeError, TypeError):
            creds = json.loads(row.credentials)

    user_key = creds.get("user_key", "").strip()
    app_token = creds.get("app_token", "").strip()

    if not user_key or not app_token:
        raise PushoverNotConfiguredError(
            "Pushover credentials incomplete (user_key and app_token required)"
        )

    return PushoverClient(user_key=user_key, app_token=app_token)


def _get_or_create_preferences(db: Session, profile_id: int) -> NotificationPreference:
    """Get or create notification preferences for a profile."""
    pref = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.profile_id == profile_id)
        .first()
    )
    if pref is None:
        pref = NotificationPreference(profile_id=profile_id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def _is_category_enabled(pref: NotificationPreference, category: str) -> bool:
    """Check if a notification category is enabled in preferences."""
    mapping = {
        "follow_up": pref.follow_up_reminders,
        "ghost": pref.ghost_alerts,
        "discovery": pref.discovery_alerts,
        "interview": pref.interview_reminders,
    }
    return mapping.get(category, True)


def _is_quiet_hours(pref: NotificationPreference) -> bool:
    """Check if current time is within quiet hours."""
    if pref.quiet_hours_start is None or pref.quiet_hours_end is None:
        return False

    now = datetime.now(UTC)
    current_hour = now.hour

    start = pref.quiet_hours_start
    end = pref.quiet_hours_end

    if start <= end:
        # Simple range, e.g., 8-17
        return start <= current_hour < end
    else:
        # Wraps midnight, e.g., 22-8 means quiet from 22:00 to 08:00
        return current_hour >= start or current_hour < end


def _log_notification(
    db: Session,
    *,
    profile_id: int,
    category: str,
    title: str,
    message: str,
    application_id: int | None = None,
    status: str = "sent",
    error_message: str | None = None,
) -> NotificationLog:
    """Create a notification log entry."""
    log = NotificationLog(
        profile_id=profile_id,
        category=category,
        title=title,
        message=message,
        application_id=application_id,
        status=status,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _queue_notification(
    db: Session,
    *,
    profile_id: int,
    category: str,
    title: str,
    message: str,
    application_id: int | None = None,
    url: str | None = None,
    url_title: str | None = None,
    priority: int = PRIORITY_NORMAL,
) -> dict:
    """Queue a notification for later delivery (during quiet hours).

    Persists a log entry with status='queued' so it can be delivered
    when quiet hours end.
    """
    log = NotificationLog(
        profile_id=profile_id,
        category=category,
        title=title,
        message=message,
        application_id=application_id,
        status="queued",
        error_message=json.dumps(
            {
                "url": url,
                "url_title": url_title,
                "priority": priority,
            }
        ),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"status": "queued", "title": title}


def _send_and_log(
    db: Session,
    client: PushoverClient,
    *,
    profile_id: int,
    category: str,
    title: str,
    message: str,
    application_id: int | None = None,
    url: str | None = None,
    url_title: str | None = None,
    priority: int = PRIORITY_NORMAL,
) -> dict:
    """Send notification via Pushover and log the result.

    Returns a result dict with 'status' and optional 'error'.
    Auth failures are caught and logged — never raised.
    """
    try:
        client.send_notification(
            message=message,
            title=title,
            url=url,
            url_title=url_title,
            priority=priority,
        )
        _log_notification(
            db,
            profile_id=profile_id,
            category=category,
            title=title,
            message=message,
            application_id=application_id,
            status="sent",
        )
        return {"status": "sent", "title": title}
    except PushoverAuthError as exc:
        logger.error("Pushover auth error: %s", exc)
        _log_notification(
            db,
            profile_id=profile_id,
            category=category,
            title=title,
            message=message,
            application_id=application_id,
            status="failed",
            error_message=f"Auth error: {exc}",
        )
        # Update integration status to error
        _update_integration_status(db, status="error", message=f"Authentication failed: {exc}")
        return {"status": "failed", "error": str(exc), "title": title}
    except PushoverAPIError as exc:
        logger.error("Pushover API error: %s", exc)
        _log_notification(
            db,
            profile_id=profile_id,
            category=category,
            title=title,
            message=message,
            application_id=application_id,
            status="failed",
            error_message=str(exc),
        )
        return {"status": "failed", "error": str(exc), "title": title}


def _update_integration_status(db: Session, *, status: str, message: str) -> None:
    """Update the pushover integration config status."""
    row = db.query(IntegrationConfig).filter(IntegrationConfig.name == "pushover").first()
    if row:
        row.status = status
        row.status_message = message
        db.commit()


# ---------------------------------------------------------------------------
# Notification Preferences
# ---------------------------------------------------------------------------


def get_preferences(db: Session, profile_id: int) -> NotificationPreference:
    """Get notification preferences for a profile."""
    return _get_or_create_preferences(db, profile_id)


def update_preferences(
    db: Session, profile_id: int, payload: NotificationPreferenceUpdate
) -> NotificationPreference:
    """Update notification preferences for a profile."""
    pref = _get_or_create_preferences(db, profile_id)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pref, key, value)

    db.commit()
    db.refresh(pref)
    return pref


# ---------------------------------------------------------------------------
# Notification Log
# ---------------------------------------------------------------------------


def list_notification_logs(
    db: Session,
    *,
    profile_id: int,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[NotificationLog], int]:
    """List notification logs for a profile.

    Excludes notifications whose parent application is archived (VAL-CROSS-019).
    Notifications without an application_id are always included.
    """
    query = (
        db.query(NotificationLog)
        .outerjoin(
            Application,
            NotificationLog.application_id == Application.id,
        )
        .filter(
            NotificationLog.profile_id == profile_id,
            # Include if no application_id OR application is not archived
            (NotificationLog.application_id.is_(None)) | (Application.archived_at.is_(None)),
        )
    )
    if category:
        query = query.filter(NotificationLog.category == category)

    total = query.count()
    logs = query.order_by(NotificationLog.sent_at.desc()).offset(offset).limit(limit).all()
    return logs, total


# ---------------------------------------------------------------------------
# Trigger: Follow-up reminders
# ---------------------------------------------------------------------------


def _validate_followup_config(
    db: Session, profile_id: int, category: str
) -> tuple[NotificationPreference, bool, PushoverClient | None, dict | None]:
    """Validate preferences and config for follow-up reminders.

    Returns (pref, quiet, client, error_result).
    If error_result is not None, the caller should return it immediately.
    """
    pref = _get_or_create_preferences(db, profile_id)

    if not _is_category_enabled(pref, category):
        return (
            pref,
            False,
            None,
            {
                "triggered": 0,
                "skipped": 1,
                "failed": 0,
                "details": [{"reason": f"{category}_reminders disabled"}],
            },
        )

    quiet = _is_quiet_hours(pref)

    if quiet:
        return pref, True, None, None

    try:
        client = _get_pushover_client(db)
    except PushoverNotConfiguredError as exc:
        return (
            pref,
            False,
            None,
            {
                "triggered": 0,
                "skipped": 0,
                "failed": 1,
                "details": [{"reason": str(exc)}],
            },
        )

    return pref, False, client, None


def _build_followup_message(fu: FollowUp, app_obj: Application) -> str:
    """Build notification message for a follow-up reminder."""
    message = (
        f"{app_obj.company} — {app_obj.role}\n"
        f"Type: {fu.follow_up_type}\n"
        f"Due: {fu.due_date.strftime('%Y-%m-%d')}"
    )
    if fu.notes:
        message += f"\n{fu.notes}"
    return message


def trigger_follow_up_reminders(db: Session, profile_id: int) -> dict:
    """Check for due follow-ups and send Pushover notifications.

    VAL-PUSH-001: Due follow-up triggers Pushover notification with company,
    role, suggested action.
    """
    pref, quiet, client, error_result = _validate_followup_config(db, profile_id, "follow_up")
    if error_result is not None:
        return error_result

    result: dict = {"triggered": 0, "skipped": 0, "failed": 0, "details": []}

    # Find due, incomplete follow-ups
    now = datetime.now(UTC)
    follow_ups = (
        db.query(FollowUp)
        .join(Application, FollowUp.application_id == Application.id)
        .filter(
            FollowUp.profile_id == profile_id,
            FollowUp.due_date <= now,
            FollowUp.completed_at.is_(None),
            Application.archived_at.is_(None),
        )
        .all()
    )

    for fu in follow_ups:
        app_obj = db.query(Application).filter(Application.id == fu.application_id).first()
        if not app_obj:
            continue

        title = "📋 Follow-up Reminder"
        message = _build_followup_message(fu, app_obj)

        send_result = _send_or_queue_notification(
            db,
            client,
            quiet,
            profile_id=profile_id,
            category="follow_up",
            title=title,
            message=message,
            application_id=fu.application_id,
            url=f"http://localhost:8101/applications/{fu.application_id}",
            url_title="View Application",
        )

        if send_result["status"] in ("sent", "queued"):
            result["triggered"] += 1
        else:
            result["failed"] += 1
        result["details"].append(send_result)

    return result


# ---------------------------------------------------------------------------
# Trigger: Ghost alerts
# ---------------------------------------------------------------------------


def _build_ghost_notification(app_obj: Application, days_since: int) -> tuple[str, str, str]:
    """Build notification title, message, and url for a ghost alert."""
    title = "👻 Ghost Alert"
    message = (
        f"{app_obj.company} — {app_obj.role}\n"
        f"Status: {app_obj.status}\n"
        f"No response for {days_since} days\n"
        f"Consider following up or marking as ghosted."
    )
    url = f"http://localhost:8101/applications/{app_obj.id}"
    return title, message, url


def _send_or_queue_notification(
    db: Session,
    client: PushoverClient | None,
    quiet: bool,
    *,
    profile_id: int,
    category: str,
    title: str,
    message: str,
    application_id: int | None = None,
    url: str | None = None,
    url_title: str | None = None,
    priority: int = PRIORITY_NORMAL,
) -> dict:
    """Send a notification immediately or queue it during quiet hours."""
    if quiet:
        return _queue_notification(
            db,
            profile_id=profile_id,
            category=category,
            title=title,
            message=message,
            application_id=application_id,
            url=url,
            url_title=url_title,
            priority=priority,
        )
    return _send_and_log(
        db,
        client,
        profile_id=profile_id,
        category=category,
        title=title,
        message=message,
        application_id=application_id,
        url=url,
        url_title=url_title,
        priority=priority,
    )


def _send_ghost_notification(
    db: Session,
    client: PushoverClient | None,
    quiet: bool,
    pushover_configured: bool,
    *,
    profile_id: int,
    app_obj: Application,
    days_since: int,
    result: dict,
) -> None:
    """Send or queue a ghost notification and update the result dict."""
    title, message, url = _build_ghost_notification(app_obj, days_since)

    if not pushover_configured and not quiet:
        result["details"].append(
            {"status": "skipped", "reason": "Pushover not configured", "title": title}
        )
        return

    send_result = _send_or_queue_notification(
        db,
        client,
        quiet,
        profile_id=profile_id,
        category="ghost",
        title=title,
        message=message,
        application_id=app_obj.id,
        url=url,
        url_title="View Application",
        priority=PRIORITY_HIGH,
    )

    if send_result["status"] in ("sent", "queued"):
        result["triggered"] += 1
    else:
        result["failed"] += 1
    result["details"].append(send_result)


def _auto_create_ghost_follow_up(
    db: Session,
    profile_id: int,
    app_obj: Application,
    days_since: int,
) -> None:
    """Auto-create a follow-up for a ghost application (VAL-CROSS-008).

    Skips if an open ghost-type follow-up already exists.
    """
    from datetime import timedelta

    from career_os.schemas.follow_ups import FollowUpCreate

    existing_fu = (
        db.query(FollowUp)
        .filter(
            FollowUp.application_id == app_obj.id,
            FollowUp.profile_id == profile_id,
            FollowUp.follow_up_type == "ghost_follow_up",
            FollowUp.completed_at.is_(None),
        )
        .first()
    )
    if existing_fu:
        return

    try:
        from career_os.services.follow_ups import create_follow_up

        now = datetime.now(UTC)
        fu_payload = FollowUpCreate(
            profile_id=profile_id,
            application_id=app_obj.id,
            due_date=now + timedelta(days=2),
            follow_up_type="ghost_follow_up",
            notes=(
                f"Auto-created by ghost alert: {app_obj.company} — "
                f"{app_obj.role} has had no response for {days_since} days. "
                f"Consider sending a follow-up email or marking as ghosted."
            ),
        )
        create_follow_up(db, fu_payload)
    except Exception:
        logger.debug(
            "Failed to auto-create follow-up for ghost app %d",
            app_obj.id,
            exc_info=True,
        )


def trigger_ghost_alerts(db: Session, profile_id: int) -> dict:
    """Check for ghost applications and send Pushover notifications.

    VAL-PUSH-002: Application past ghost threshold triggers notification
    with company, role, days since contact.

    VAL-CROSS-008: Ghost alert also auto-creates a follow-up for the
    application and triggers TickTick push (via create_follow_up which
    already hooks into TickTick sync).
    """
    pref = _get_or_create_preferences(db, profile_id)
    result: dict = {"triggered": 0, "skipped": 0, "failed": 0, "details": []}

    if not _is_category_enabled(pref, "ghost"):
        result["skipped"] = 1
        result["details"].append({"reason": "ghost_alerts disabled"})
        return result

    quiet = _is_quiet_hours(pref)

    # Try to get Pushover client; if not configured, we still proceed
    # with ghost detection and follow-up creation (VAL-CROSS-008).
    client = None
    pushover_configured = True
    if not quiet:
        try:
            client = _get_pushover_client(db)
        except PushoverNotConfiguredError:
            pushover_configured = False

    ghosts = get_ghost_applications(db, profile_id=profile_id)

    for app_obj in ghosts:
        now = datetime.now(UTC)
        updated = app_obj.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        days_since = (now - updated).days

        _send_ghost_notification(
            db,
            client,
            quiet,
            pushover_configured,
            profile_id=profile_id,
            app_obj=app_obj,
            days_since=days_since,
            result=result,
        )

        _auto_create_ghost_follow_up(db, profile_id, app_obj, days_since)

    return result


# ---------------------------------------------------------------------------
# Trigger: Discovery alerts
# ---------------------------------------------------------------------------


def trigger_discovery_alert(
    db: Session,
    profile_id: int,
    *,
    company: str,
    role: str,
    score: float,
    application_id: int | None = None,
    url: str | None = None,
) -> dict:
    """Send notification for a high-scoring job discovery.

    VAL-PUSH-003: High-scoring discovery triggers notification with company,
    role, score, review link.
    """
    pref = _get_or_create_preferences(db, profile_id)
    result = {"triggered": 0, "skipped": 0, "failed": 0, "details": []}

    if not _is_category_enabled(pref, "discovery"):
        result["skipped"] = 1
        result["details"].append({"reason": "discovery_alerts disabled"})
        return result

    # Check score threshold
    if score < pref.discovery_score_threshold:
        result["skipped"] = 1
        result["details"].append(
            {"reason": f"Score {score} below threshold {pref.discovery_score_threshold}"}
        )
        return result

    quiet = _is_quiet_hours(pref)

    title = "🎯 New High-Scoring Job"
    message = f"{company} — {role}\nFit Score: {score}/10"

    notification_url = url or (
        f"http://localhost:8101/applications/{application_id}" if application_id else None
    )
    notification_priority = PRIORITY_HIGH if score >= 9 else PRIORITY_NORMAL

    if quiet:
        send_result = _queue_notification(
            db,
            profile_id=profile_id,
            category="discovery",
            title=title,
            message=message,
            application_id=application_id,
            url=notification_url,
            url_title="Review Job",
            priority=notification_priority,
        )
    else:
        try:
            client = _get_pushover_client(db)
        except PushoverNotConfiguredError as exc:
            result["failed"] = 1
            result["details"].append({"reason": str(exc)})
            return result

        send_result = _send_and_log(
            db,
            client,
            profile_id=profile_id,
            category="discovery",
            title=title,
            message=message,
            application_id=application_id,
            url=notification_url,
            url_title="Review Job",
            priority=notification_priority,
        )

    if send_result["status"] in ("sent", "queued"):
        result["triggered"] += 1
    else:
        result["failed"] += 1
    result["details"].append(send_result)

    return result


# ---------------------------------------------------------------------------
# Trigger: Interview reminders
# ---------------------------------------------------------------------------


def _build_interview_message(event: CalendarEvent) -> str:
    """Build the notification message string for an interview event."""
    message = (
        f"{event.company or 'Unknown'} — {event.role or 'Unknown'}\n"
        f"Time: {event.start_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Type: {event.interview_type or 'Interview'}"
    )
    if event.meeting_link:
        message += f"\nLink: {event.meeting_link}"
    if event.prep_notes:
        message += f"\nPrep: {event.prep_notes[:100]}"
    return message


def _process_interview_event(
    db: Session,
    event: CalendarEvent,
    profile_id: int,
    client: PushoverClient | None,
    quiet: bool,
) -> dict | None:
    """Process a single interview event: check duplicates, build message, send.

    Returns a dict with 'status' key if the event was processed,
    or None if already notified (caller should record as skipped).
    """
    event_time_str = event.start_time.strftime("%Y-%m-%d %H:%M")
    existing = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.profile_id == profile_id,
            NotificationLog.category == "interview",
            NotificationLog.application_id == event.application_id,
            NotificationLog.status.in_(["sent", "queued"]),
            NotificationLog.message.contains(event_time_str),
        )
        .first()
    )
    if existing:
        return None

    title = "🗓️ Interview Reminder"
    message = _build_interview_message(event)

    url = event.meeting_link or (
        f"http://localhost:8101/applications/{event.application_id}"
        if event.application_id
        else None
    )
    url_title = "Join Interview" if event.meeting_link else "View Application"

    return _send_or_queue_notification(
        db,
        client,
        quiet,
        profile_id=profile_id,
        category="interview",
        title=title,
        message=message,
        application_id=event.application_id,
        url=url,
        url_title=url_title,
        priority=PRIORITY_HIGH,
    )


def trigger_interview_reminders(db: Session, profile_id: int) -> dict:
    """Check for upcoming interviews and send Pushover reminders.

    VAL-PUSH-004: Notification sent at configured interval before interview
    with company, role, time, link.

    Uses CalendarEvent table for interview events.
    """
    from datetime import timedelta

    from career_os.models.calendar import CalendarEvent

    pref, quiet, client, error_result = _validate_followup_config(db, profile_id, "interview")
    if error_result is not None:
        return error_result

    result: dict = {"triggered": 0, "skipped": 0, "failed": 0, "details": []}

    # Find interviews happening within the lead time window
    now = datetime.now(UTC)
    lead_minutes = pref.interview_lead_time_minutes
    window_end = now + timedelta(minutes=lead_minutes)

    interviews = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.profile_id == profile_id,
            CalendarEvent.event_type == "interview",
            CalendarEvent.start_time > now,
            CalendarEvent.start_time <= window_end,
        )
        .all()
    )

    for event in interviews:
        send_result = _process_interview_event(db, event, profile_id, client, quiet)

        if send_result is None:
            result["skipped"] += 1
            result["details"].append({"reason": "already notified", "event": event.title})
            continue

        if send_result["status"] in ("sent", "queued"):
            result["triggered"] += 1
        else:
            result["failed"] += 1
        result["details"].append(send_result)

    return result


# ---------------------------------------------------------------------------
# Send manual/test notification
# ---------------------------------------------------------------------------


def send_test_notification(
    db: Session,
    *,
    profile_id: int,
    category: str,
    title: str,
    message: str,
    application_id: int | None = None,
) -> dict:
    """Send a manual notification (for testing or ad-hoc alerts).

    VAL-PUSH-005: Auth failure logged and surfaced in UI, no crash.
    """
    try:
        client = _get_pushover_client(db)
    except PushoverNotConfiguredError as exc:
        _log_notification(
            db,
            profile_id=profile_id,
            category=category,
            title=title,
            message=message,
            application_id=application_id,
            status="failed",
            error_message=str(exc),
        )
        return {"status": "failed", "error": str(exc)}

    return _send_and_log(
        db,
        client,
        profile_id=profile_id,
        category=category,
        title=title,
        message=message,
        application_id=application_id,
    )


# ---------------------------------------------------------------------------
# Alert: AI credits exhausted
# ---------------------------------------------------------------------------


def send_credits_exhausted_alert(
    db: Session,
    *,
    profile_id: int,
    scored_count: int,
    total_count: int,
) -> dict:
    """Send a high-priority notification when AI credits are exhausted mid-scoring.

    Gracefully no-ops when Pushover is not configured.
    """
    try:
        client = _get_pushover_client(db)
    except PushoverNotConfiguredError:
        return {"status": "skipped", "reason": "pushover not configured"}

    title = "AI Scoring Stopped"
    message = (
        f"OpenRouter credits exhausted during batch scoring. "
        f"{scored_count} of {total_count} jobs were scored before credits ran out.\n\n"
        f"Add credits at https://openrouter.ai"
    )

    return _send_and_log(
        db,
        client,
        profile_id=profile_id,
        category="scoring",
        title=title,
        message=message,
        priority=PRIORITY_HIGH,
    )


# ---------------------------------------------------------------------------
# Test Pushover connection (with actual API call)
# ---------------------------------------------------------------------------


def test_pushover_connection(db: Session) -> dict:
    """Test Pushover connection by validating credentials.

    Updates integration status based on result.
    """
    try:
        client = _get_pushover_client(db)
    except PushoverNotConfiguredError as exc:
        return {"success": False, "message": str(exc)}

    try:
        client.validate_credentials()
        _update_integration_status(
            db, status="connected", message="Credentials validated successfully"
        )
        return {"success": True, "message": "Pushover connection successful"}
    except PushoverAuthError as exc:
        _update_integration_status(db, status="error", message=f"Authentication failed: {exc}")
        return {"success": False, "message": f"Auth error: {exc}"}
    except PushoverAPIError as exc:
        _update_integration_status(db, status="error", message=f"API error: {exc}")
        return {"success": False, "message": f"API error: {exc}"}


# ---------------------------------------------------------------------------
# Deliver queued notifications
# ---------------------------------------------------------------------------


def _deliver_single_notification(client: PushoverClient, log_entry: NotificationLog) -> bool:
    """Attempt to send one queued notification. Returns True on success."""
    metadata: dict = {}
    if log_entry.error_message:
        try:
            metadata = json.loads(log_entry.error_message)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    try:
        client.send_notification(
            message=log_entry.message,
            title=log_entry.title,
            url=metadata.get("url"),
            url_title=metadata.get("url_title"),
            priority=metadata.get("priority", PRIORITY_NORMAL),
        )
        log_entry.status = "sent"
        log_entry.error_message = None
        log_entry.sent_at = datetime.now(UTC)
        return True
    except (PushoverAuthError, PushoverAPIError) as exc:
        log_entry.status = "failed"
        log_entry.error_message = str(exc)
        return False


def deliver_queued_notifications(db: Session, profile_id: int) -> dict:
    """Deliver all queued notifications for a profile.

    Called when quiet hours end. Sends all queued notifications
    and updates their status to 'sent' or 'failed'.

    Returns {"delivered": N, "failed": M}.
    """
    pref = _get_or_create_preferences(db, profile_id)

    # Don't deliver if still in quiet hours
    if _is_quiet_hours(pref):
        return {"delivered": 0, "failed": 0, "reason": "still in quiet hours"}

    try:
        client = _get_pushover_client(db)
    except PushoverNotConfiguredError as exc:
        return {"delivered": 0, "failed": 0, "reason": str(exc)}

    queued = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.profile_id == profile_id,
            NotificationLog.status == "queued",
        )
        .order_by(NotificationLog.sent_at.asc())
        .all()
    )

    delivered = 0
    failed = 0

    for log_entry in queued:
        if _deliver_single_notification(client, log_entry):
            delivered += 1
        else:
            failed += 1

    db.commit()
    return {"delivered": delivered, "failed": failed}
