"""Calendar integration service.

Provides:
- Calendar event CRUD (interviews, follow-ups, prep reminders)
- iCal (.ics) export (provider 1)
- Google Calendar URL generation (provider 2)
- Fantastical URL scheme generation (provider 3)
- Auto-creation of prep reminders at configurable lead time

Covers: VAL-CAL-001 through VAL-CAL-004, VAL-CROSS-017
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from icalendar import Alarm, Calendar, Event
from sqlalchemy import or_ as db_or
from sqlalchemy.orm import Session

from career_os.models.calendar import CalendarEvent
from career_os.models.models import Application, FollowUp, Profile
from career_os.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
)

logger = logging.getLogger(__name__)


class CalendarEventNotFoundError(Exception):
    """Raised when a calendar event is not found."""


class ProfileNotFoundError(Exception):
    """Raised when the specified profile does not exist."""


class ApplicationNotFoundError(Exception):
    """Raised when the specified application does not exist."""


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def create_calendar_event(db: Session, payload: CalendarEventCreate) -> CalendarEvent:
    """Create a new calendar event and optionally a prep reminder.

    Returns the created CalendarEvent.
    """
    # Validate profile exists
    profile = db.query(Profile).filter(Profile.id == payload.profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {payload.profile_id} not found")

    # Validate application if specified
    if payload.application_id is not None:
        app_obj = (
            db.query(Application)
            .filter(
                Application.id == payload.application_id,
                Application.profile_id == payload.profile_id,
            )
            .first()
        )
        if not app_obj:
            raise ApplicationNotFoundError(
                f"Application {payload.application_id} not found for profile {payload.profile_id}"
            )

    # Generate a unique iCal UID
    event_uid = f"career-os-{uuid.uuid4()}@career-os.local"

    event = CalendarEvent(
        profile_id=payload.profile_id,
        application_id=payload.application_id,
        follow_up_id=payload.follow_up_id,
        event_type=payload.event_type,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        start_time=payload.start_time,
        end_time=payload.end_time,
        company=payload.company,
        role=payload.role,
        interview_type=payload.interview_type,
        meeting_link=payload.meeting_link,
        prep_notes=payload.prep_notes,
        reminder_minutes_before=payload.reminder_minutes_before,
        uid=event_uid,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Auto-create prep reminder for interviews
    if payload.event_type == "interview" and payload.reminder_minutes_before > 0:
        _create_prep_reminder(db, event)

    return event


def _create_prep_reminder(db: Session, interview_event: CalendarEvent) -> CalendarEvent | None:
    """Create a prep reminder event before an interview.

    Returns the created prep reminder event, or None if creation fails.
    """
    reminder_minutes = interview_event.reminder_minutes_before or 1440
    reminder_time = interview_event.start_time - timedelta(minutes=reminder_minutes)

    # Don't create reminders in the past
    now = datetime.now(UTC)
    # Ensure timezone-aware comparison
    rt = reminder_time if reminder_time.tzinfo else reminder_time.replace(tzinfo=UTC)
    if rt < now:
        logger.info(
            "Skipping prep reminder for event %d: reminder time is in the past",
            interview_event.id,
        )
        return None

    # Build prep materials link
    prep_link = ""
    if interview_event.application_id:
        prep_link = f"/applications/{interview_event.application_id}/prep"

    description_parts = [
        f"🎯 Prep reminder for: {interview_event.title}",
    ]
    if interview_event.prep_notes:
        description_parts.append(f"\n📝 Prep Notes:\n{interview_event.prep_notes}")
    if prep_link:
        description_parts.append(f"\n🔗 Prep materials: {prep_link}")
    if interview_event.meeting_link:
        description_parts.append(f"\n📞 Meeting link: {interview_event.meeting_link}")

    reminder_uid = f"career-os-reminder-{uuid.uuid4()}@career-os.local"

    reminder_event = CalendarEvent(
        profile_id=interview_event.profile_id,
        application_id=interview_event.application_id,
        parent_event_id=interview_event.id,
        event_type="prep_reminder",
        title=f"📚 Prep: {interview_event.title}",
        description="\n".join(description_parts),
        start_time=reminder_time,
        end_time=reminder_time + timedelta(minutes=30),
        company=interview_event.company,
        role=interview_event.role,
        interview_type=interview_event.interview_type,
        meeting_link=interview_event.meeting_link,
        prep_notes=interview_event.prep_notes,
        uid=reminder_uid,
    )
    db.add(reminder_event)
    db.commit()
    db.refresh(reminder_event)
    return reminder_event


def get_calendar_event(db: Session, event_id: int, *, profile_id: int) -> CalendarEvent:
    """Get a calendar event by ID, scoped to profile.

    Raises CalendarEventNotFoundError if not found.
    """
    event = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.id == event_id,
            CalendarEvent.profile_id == profile_id,
        )
        .first()
    )
    if not event:
        raise CalendarEventNotFoundError(
            f"Calendar event {event_id} not found for profile {profile_id}"
        )
    return event


def list_calendar_events(
    db: Session,
    *,
    profile_id: int,
    event_type: str | None = None,
    application_id: int | None = None,
) -> tuple[list[CalendarEvent], int]:
    """List calendar events for a profile with optional filters.

    Excludes events linked to archived applications (VAL-CROSS-019).
    Returns (events, total_count).
    """
    query = (
        db.query(CalendarEvent)
        .outerjoin(
            Application,
            CalendarEvent.application_id == Application.id,
        )
        .filter(
            CalendarEvent.profile_id == profile_id,
            # Keep events with no application link, or where app is not archived
            db_or(
                CalendarEvent.application_id.is_(None),
                Application.archived_at.is_(None),
            ),
        )
    )

    if event_type:
        query = query.filter(CalendarEvent.event_type == event_type)
    if application_id is not None:
        query = query.filter(CalendarEvent.application_id == application_id)

    total = query.count()
    events = query.order_by(CalendarEvent.start_time.asc()).all()
    return events, total


def update_calendar_event(
    db: Session,
    event_id: int,
    payload: CalendarEventUpdate,
    *,
    profile_id: int,
) -> CalendarEvent:
    """Update a calendar event.

    Raises CalendarEventNotFoundError if not found.
    """
    event = get_calendar_event(db, event_id, profile_id=profile_id)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)

    db.commit()
    db.refresh(event)

    # If start_time changed on an interview, update associated prep reminders
    if "start_time" in update_data and event.event_type == "interview":
        _update_prep_reminders(db, event)

    return event


def _update_prep_reminders(db: Session, interview_event: CalendarEvent) -> None:
    """Update prep reminder times when interview is rescheduled.

    Keyed by parent_event_id so rescheduling one interview doesn't affect
    prep reminders for other interviews on the same application.
    """
    reminders = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.parent_event_id == interview_event.id,
            CalendarEvent.event_type == "prep_reminder",
        )
        .all()
    )

    reminder_minutes = interview_event.reminder_minutes_before or 1440
    new_reminder_time = interview_event.start_time - timedelta(minutes=reminder_minutes)

    for reminder in reminders:
        reminder.start_time = new_reminder_time
        reminder.end_time = new_reminder_time + timedelta(minutes=30)

    if reminders:
        db.commit()


def delete_calendar_event(db: Session, event_id: int, *, profile_id: int) -> None:
    """Delete a calendar event and its associated prep reminders.

    Raises CalendarEventNotFoundError if not found.
    """
    event = get_calendar_event(db, event_id, profile_id=profile_id)

    # Delete child prep reminders first (if this is an interview event)
    if event.event_type == "interview":
        db.query(CalendarEvent).filter(CalendarEvent.parent_event_id == event.id).delete()

    db.delete(event)
    db.commit()


# ---------------------------------------------------------------------------
# Follow-up → Calendar event creation
# ---------------------------------------------------------------------------


def create_follow_up_calendar_event(
    db: Session,
    follow_up: FollowUp,
) -> CalendarEvent:
    """Create a calendar event from a follow-up.

    Returns the created CalendarEvent.
    """
    app_obj = db.query(Application).filter(Application.id == follow_up.application_id).first()
    app_context = f"{app_obj.company} — {app_obj.role}" if app_obj else "Unknown"

    payload = CalendarEventCreate(
        profile_id=follow_up.profile_id,
        application_id=follow_up.application_id,
        follow_up_id=follow_up.id,
        event_type="follow_up",
        title=f"Follow-up: {app_context} ({follow_up.follow_up_type})",
        description=follow_up.notes or f"Follow-up for {app_context}",
        start_time=follow_up.due_date,
        end_time=follow_up.due_date + timedelta(minutes=30),
        company=app_obj.company if app_obj else None,
        role=app_obj.role if app_obj else None,
        reminder_minutes_before=0,  # No auto prep reminder for follow-ups
    )
    return create_calendar_event(db, payload)


# ---------------------------------------------------------------------------
# Provider: iCal (.ics) export
# ---------------------------------------------------------------------------


def export_event_ical(db: Session, event_id: int, *, profile_id: int) -> str:
    """Export a calendar event as iCal (.ics) string.

    Provider 1: Standard iCal format, importable by any calendar app.
    """
    event = get_calendar_event(db, event_id, profile_id=profile_id)
    return _build_ical(event)


def export_events_ical(
    db: Session,
    *,
    profile_id: int,
    event_type: str | None = None,
    application_id: int | None = None,
) -> str:
    """Export multiple calendar events as a single iCal (.ics) string."""
    events, _ = list_calendar_events(
        db, profile_id=profile_id, event_type=event_type, application_id=application_id
    )
    return _build_ical_multi(events)


def _build_ical(event: CalendarEvent) -> str:
    """Build iCal string for a single event."""
    cal = Calendar()
    cal.add("prodid", "-//Career OS//Calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    vevent = _event_to_vevent(event)
    cal.add_component(vevent)

    return cal.to_ical().decode("utf-8")


def _build_ical_multi(events: list[CalendarEvent]) -> str:
    """Build iCal string for multiple events."""
    cal = Calendar()
    cal.add("prodid", "-//Career OS//Calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    for event in events:
        vevent = _event_to_vevent(event)
        cal.add_component(vevent)

    return cal.to_ical().decode("utf-8")


def _event_to_vevent(event: CalendarEvent) -> Event:
    """Convert a CalendarEvent to an iCal VEVENT component."""
    vevent = Event()
    vevent.add("uid", event.uid or f"career-os-{event.id}@career-os.local")
    vevent.add("dtstart", event.start_time)
    vevent.add("dtend", event.end_time)
    vevent.add("summary", event.title)

    # Build rich description
    desc_parts = []
    if event.company:
        desc_parts.append(f"Company: {event.company}")
    if event.role:
        desc_parts.append(f"Role: {event.role}")
    if event.interview_type:
        desc_parts.append(f"Type: {event.interview_type}")
    if event.meeting_link:
        desc_parts.append(f"Link: {event.meeting_link}")
    if event.prep_notes:
        desc_parts.append(f"\nPrep Notes:\n{event.prep_notes}")
    if event.description:
        desc_parts.append(f"\n{event.description}")

    if desc_parts:
        vevent.add("description", "\n".join(desc_parts))

    if event.location:
        vevent.add("location", event.location)
    elif event.meeting_link:
        vevent.add("location", event.meeting_link)

    vevent.add("dtstamp", datetime.now(UTC))

    # Add alarm for prep reminder
    if event.reminder_minutes_before and event.reminder_minutes_before > 0:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("trigger", timedelta(minutes=-event.reminder_minutes_before))
        alarm.add("description", f"Prep reminder: {event.title}")
        vevent.add_component(alarm)

    return vevent


# ---------------------------------------------------------------------------
# Provider: Google Calendar URL
# ---------------------------------------------------------------------------


def generate_google_calendar_url(db: Session, event_id: int, *, profile_id: int) -> str:
    """Generate a Google Calendar 'Add Event' URL.

    Provider 2: Opens Google Calendar with pre-filled event details.
    """
    event = get_calendar_event(db, event_id, profile_id=profile_id)
    return _build_google_calendar_url(event)


def _build_google_calendar_url(event: CalendarEvent) -> str:
    """Build a Google Calendar URL for adding an event."""
    base_url = "https://calendar.google.com/calendar/render"

    # Format dates as required by Google Calendar (YYYYMMDDTHHmmssZ)
    start_str = event.start_time.strftime("%Y%m%dT%H%M%SZ")
    end_str = event.end_time.strftime("%Y%m%dT%H%M%SZ")

    # Build description
    desc_parts = []
    if event.company:
        desc_parts.append(f"Company: {event.company}")
    if event.role:
        desc_parts.append(f"Role: {event.role}")
    if event.interview_type:
        desc_parts.append(f"Type: {event.interview_type}")
    if event.meeting_link:
        desc_parts.append(f"Link: {event.meeting_link}")
    if event.prep_notes:
        desc_parts.append(f"\nPrep Notes:\n{event.prep_notes}")
    if event.description:
        desc_parts.append(f"\n{event.description}")

    description = "\n".join(desc_parts) if desc_parts else ""
    location = event.location or event.meeting_link or ""

    params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{start_str}/{end_str}",
        "details": description,
        "location": location,
    }

    return f"{base_url}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Provider: Fantastical URL scheme
# ---------------------------------------------------------------------------


def generate_fantastical_url(db: Session, event_id: int, *, profile_id: int) -> str:
    """Generate a Fantastical URL scheme for adding an event.

    Provider 3: Opens Fantastical with pre-filled event details.
    """
    event = get_calendar_event(db, event_id, profile_id=profile_id)
    return _build_fantastical_url(event)


def _build_fantastical_url(event: CalendarEvent) -> str:
    """Build a Fantastical x-fantastical3://add URL for an event."""
    # Fantastical uses x-fantastical3://add with query params
    base_url = "x-fantastical3://add"

    # Build notes
    notes_parts = []
    if event.company:
        notes_parts.append(f"Company: {event.company}")
    if event.role:
        notes_parts.append(f"Role: {event.role}")
    if event.interview_type:
        notes_parts.append(f"Type: {event.interview_type}")
    if event.meeting_link:
        notes_parts.append(f"Link: {event.meeting_link}")
    if event.prep_notes:
        notes_parts.append(f"\nPrep Notes:\n{event.prep_notes}")
    if event.description:
        notes_parts.append(f"\n{event.description}")

    notes = "\n".join(notes_parts) if notes_parts else ""
    location = event.location or event.meeting_link or ""

    params: dict[str, str] = {
        "title": event.title,
        "start": event.start_time.isoformat(),
        "end": event.end_time.isoformat(),
        "notes": notes,
    }
    if location:
        params["location"] = location

    return f"{base_url}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Multi-provider export
# ---------------------------------------------------------------------------


def get_event_provider_urls(db: Session, event_id: int, *, profile_id: int) -> dict[str, str]:
    """Get export URLs/data for all supported providers.

    Returns dict: provider_name -> url_or_ical_data
    """
    event = get_calendar_event(db, event_id, profile_id=profile_id)
    return {
        "ical": _build_ical(event),
        "google": _build_google_calendar_url(event),
        "fantastical": _build_fantastical_url(event),
    }
