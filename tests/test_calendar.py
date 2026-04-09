"""Tests for Calendar Integration.

Covers:
- VAL-CAL-001: Interview creates calendar event with all details
- VAL-CAL-002: Follow-up dates as calendar events
- VAL-CAL-003: Prep reminders before interviews (configurable lead time)
- VAL-CAL-004: Multi-provider support (iCal, Google Calendar, Fantastical)
- VAL-CROSS-017: Calendar reflects pipeline and prep deadlines
- Profile isolation tests
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.calendar import CalendarEvent
from career_os.models.models import Application, FollowUp, Profile
from career_os.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
)
from career_os.services.calendar import (
    create_calendar_event,
    create_follow_up_calendar_event,
    export_event_ical,
    generate_fantastical_url,
    generate_google_calendar_url,
    get_event_provider_urls,
    list_calendar_events,
    update_calendar_event,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def profile(db_session) -> Profile:
    """Create a test profile."""
    p = Profile(name="Test User", email="test@example.com", location="Frankfurt")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def profile_b(db_session) -> Profile:
    """Second profile for isolation tests."""
    p = Profile(name="Other User", email="other@example.com", location="Berlin")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def application(db_session, profile) -> Application:
    """Create a test application."""
    app_obj = Application(
        profile_id=profile.id,
        company="Acme Corp",
        role="Senior TPM",
        status="interviewing",
        fit_score=8.5,
        url="https://acme.com/jobs/1",
    )
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


@pytest.fixture()
def follow_up(db_session, profile, application) -> FollowUp:
    """Create a test follow-up."""
    fu = FollowUp(
        profile_id=profile.id,
        application_id=application.id,
        due_date=datetime.now(UTC) + timedelta(days=3),
        follow_up_type="email",
        notes="Send follow-up email about status",
    )
    db_session.add(fu)
    db_session.commit()
    db_session.refresh(fu)
    return fu


def _interview_payload(profile_id: int, application_id: int | None = None) -> dict:
    """Build a standard interview event payload."""
    start = datetime.now(UTC) + timedelta(days=3)
    end = start + timedelta(hours=1)
    return {
        "profile_id": profile_id,
        "application_id": application_id,
        "event_type": "interview",
        "title": "Technical Interview — Acme Corp (Senior TPM)",
        "description": "System design interview focusing on distributed systems",
        "location": "https://zoom.us/j/123456789",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "company": "Acme Corp",
        "role": "Senior TPM",
        "interview_type": "technical",
        "meeting_link": "https://zoom.us/j/123456789",
        "prep_notes": "Review system design patterns, prepare STAR stories for leadership",
        "reminder_minutes_before": 1440,
    }


# ---------------------------------------------------------------------------
# VAL-CAL-001: Interview creates calendar event with all details
# ---------------------------------------------------------------------------


class TestInterviewCalendarEvent:
    """Interview scheduling creates calendar event with all details."""

    def test_create_interview_event_with_all_details(self, db_session, profile, application):
        """Interview creates event with company, role, type, link, prep notes."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        assert event.id is not None
        assert event.event_type == "interview"
        assert event.company == "Acme Corp"
        assert event.role == "Senior TPM"
        assert event.interview_type == "technical"
        assert event.meeting_link == "https://zoom.us/j/123456789"
        assert event.prep_notes is not None
        assert "STAR stories" in event.prep_notes
        assert event.uid is not None
        assert event.uid.endswith("@career-os.local")

    def test_create_interview_via_api(self, db_session, profile, application):
        """POST /api/calendar/events creates interview event."""
        payload = _interview_payload(profile.id, application.id)
        resp = client.post("/api/calendar/events", json=payload)
        assert resp.status_code == 201

        data = resp.json()
        assert data["event_type"] == "interview"
        assert data["company"] == "Acme Corp"
        assert data["role"] == "Senior TPM"
        assert data["interview_type"] == "technical"
        assert data["meeting_link"] == "https://zoom.us/j/123456789"
        assert data["prep_notes"] is not None
        assert data["uid"] is not None

    def test_interview_event_includes_description(self, db_session, profile, application):
        """Description captures interview context."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        assert event.description == "System design interview focusing on distributed systems"

    def test_interview_event_includes_location(self, db_session, profile, application):
        """Location set to meeting link or physical address."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        assert event.location == "https://zoom.us/j/123456789"

    def test_create_interview_without_application(self, db_session, profile):
        """Interview event can be created without application link."""
        payload = _interview_payload(profile.id, None)
        resp = client.post("/api/calendar/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["application_id"] is None
        assert data["event_type"] == "interview"

    def test_create_event_invalid_profile_returns_404(self, db_session):
        """Creating event with nonexistent profile returns 404."""
        payload = _interview_payload(9999)
        resp = client.post("/api/calendar/events", json=payload)
        assert resp.status_code == 404

    def test_create_event_invalid_application_returns_404(self, db_session, profile):
        """Creating event with nonexistent application returns 404."""
        payload = _interview_payload(profile.id, 9999)
        resp = client.post("/api/calendar/events", json=payload)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# VAL-CAL-002: Follow-up dates as calendar events
# ---------------------------------------------------------------------------


class TestFollowUpCalendarEvent:
    """Follow-up dates create calendar events."""

    def test_create_follow_up_event(self, db_session, profile, application, follow_up):
        """Follow-up creates calendar event with correct details."""
        event = create_follow_up_calendar_event(db_session, follow_up)

        assert event.event_type == "follow_up"
        assert event.follow_up_id == follow_up.id
        assert event.application_id == application.id
        assert "Follow-up" in event.title
        assert "Acme Corp" in event.title
        assert "email" in event.title.lower()
        assert event.start_time == follow_up.due_date
        assert event.uid is not None

    def test_create_follow_up_event_via_api(self, db_session, profile, application, follow_up):
        """POST /api/calendar/events/from-follow-up creates event from follow-up."""
        resp = client.post(
            f"/api/calendar/events/from-follow-up/{follow_up.id}?profile_id={profile.id}"
        )
        assert resp.status_code == 201

        data = resp.json()
        assert data["event_type"] == "follow_up"
        assert data["follow_up_id"] == follow_up.id
        assert "Acme Corp" in data["title"]

    def test_follow_up_event_includes_notes(self, db_session, profile, application, follow_up):
        """Follow-up event description includes follow-up notes."""
        event = create_follow_up_calendar_event(db_session, follow_up)
        assert "follow-up email" in event.description.lower()

    def test_follow_up_event_nonexistent_returns_404(self, db_session, profile):
        """Creating event from nonexistent follow-up returns 404."""
        resp = client.post(f"/api/calendar/events/from-follow-up/9999?profile_id={profile.id}")
        assert resp.status_code == 404

    def test_follow_up_event_wrong_profile_returns_404(
        self, db_session, profile, profile_b, application, follow_up
    ):
        """Creating event from another profile's follow-up returns 404."""
        resp = client.post(
            f"/api/calendar/events/from-follow-up/{follow_up.id}?profile_id={profile_b.id}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# VAL-CAL-003: Prep reminders before interviews (configurable)
# ---------------------------------------------------------------------------


class TestPrepReminders:
    """Prep reminder at configurable lead time before interview."""

    def test_interview_creates_prep_reminder(self, db_session, profile, application):
        """Creating interview auto-creates prep reminder at T-24h."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        # Should have created a prep reminder event
        reminders = (
            db_session.query(CalendarEvent)
            .filter(
                CalendarEvent.profile_id == profile.id,
                CalendarEvent.event_type == "prep_reminder",
            )
            .all()
        )
        assert len(reminders) == 1

        reminder = reminders[0]
        expected_reminder_time = event.start_time - timedelta(minutes=1440)
        assert reminder.start_time == expected_reminder_time
        assert "Prep" in reminder.title
        assert event.title in reminder.title

    def test_prep_reminder_includes_prep_materials_link(self, db_session, profile, application):
        """Prep reminder includes link to prep materials."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        create_calendar_event(db_session, payload)

        reminder = (
            db_session.query(CalendarEvent)
            .filter(CalendarEvent.event_type == "prep_reminder")
            .first()
        )
        assert reminder is not None
        assert f"/applications/{application.id}/prep" in reminder.description

    def test_custom_reminder_lead_time(self, db_session, profile, application):
        """Configurable lead time: 2 hours instead of 24h."""
        payload_dict = _interview_payload(profile.id, application.id)
        payload_dict["reminder_minutes_before"] = 120  # 2 hours
        payload = CalendarEventCreate(**payload_dict)
        event = create_calendar_event(db_session, payload)

        reminder = (
            db_session.query(CalendarEvent)
            .filter(CalendarEvent.event_type == "prep_reminder")
            .first()
        )
        assert reminder is not None
        expected_time = event.start_time - timedelta(minutes=120)
        assert reminder.start_time == expected_time

    def test_zero_reminder_skips_creation(self, db_session, profile, application):
        """Setting reminder_minutes_before=0 skips prep reminder creation."""
        payload_dict = _interview_payload(profile.id, application.id)
        payload_dict["reminder_minutes_before"] = 0
        payload = CalendarEventCreate(**payload_dict)
        create_calendar_event(db_session, payload)

        reminder_count = (
            db_session.query(CalendarEvent)
            .filter(CalendarEvent.event_type == "prep_reminder")
            .count()
        )
        assert reminder_count == 0

    def test_prep_reminder_includes_meeting_link(self, db_session, profile, application):
        """Prep reminder description includes meeting link."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        create_calendar_event(db_session, payload)

        reminder = (
            db_session.query(CalendarEvent)
            .filter(CalendarEvent.event_type == "prep_reminder")
            .first()
        )
        assert reminder is not None
        assert "zoom.us" in reminder.description


# ---------------------------------------------------------------------------
# VAL-CAL-004: Multi-provider support
# ---------------------------------------------------------------------------


class TestICalExport:
    """iCal (.ics) export — Provider 1."""

    def test_ical_export_contains_vevent(self, db_session, profile, application):
        """Exported .ics contains VEVENT with correct fields."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        ical_data = export_event_ical(db_session, event.id, profile_id=profile.id)

        assert "BEGIN:VCALENDAR" in ical_data
        assert "BEGIN:VEVENT" in ical_data
        assert "END:VEVENT" in ical_data
        assert "END:VCALENDAR" in ical_data
        assert "Acme Corp" in ical_data
        assert event.uid in ical_data

    def test_ical_export_includes_alarm(self, db_session, profile, application):
        """iCal export includes VALARM for prep reminder."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        ical_data = export_event_ical(db_session, event.id, profile_id=profile.id)
        assert "BEGIN:VALARM" in ical_data
        assert "TRIGGER" in ical_data

    def test_ical_export_includes_description_with_details(self, db_session, profile, application):
        """iCal DESCRIPTION includes company, role, type, link, prep notes."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        ical_data = export_event_ical(db_session, event.id, profile_id=profile.id)
        # The description should contain key details
        assert "Company: Acme Corp" in ical_data
        assert "Role: Senior TPM" in ical_data
        assert "zoom.us" in ical_data

    def test_ical_export_via_api(self, db_session, profile, application):
        """GET /api/calendar/events/{id}/ical returns .ics file."""
        # Create event first
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.get(f"/api/calendar/events/{event_id}/ical?profile_id={profile.id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/calendar; charset=utf-8"
        assert "BEGIN:VCALENDAR" in resp.text

    def test_ical_multi_event_export(self, db_session, profile, application):
        """Export multiple events as a single .ics."""
        # Create 2 events
        for i in range(2):
            p = _interview_payload(profile.id, application.id)
            p["title"] = f"Interview {i}"
            client.post("/api/calendar/events", json=p)

        resp = client.get(f"/api/calendar/export/ical?profile_id={profile.id}")
        assert resp.status_code == 200
        # At least 2 VEVENTs (2 interviews + 2 prep reminders)
        vevent_count = resp.text.count("BEGIN:VEVENT")
        assert vevent_count >= 2


class TestGoogleCalendar:
    """Google Calendar URL generation — Provider 2."""

    def test_google_url_has_required_params(self, db_session, profile, application):
        """Google Calendar URL contains action, text, dates, details."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        url = generate_google_calendar_url(db_session, event.id, profile_id=profile.id)

        assert "calendar.google.com/calendar/render" in url
        assert "action=TEMPLATE" in url
        assert "text=" in url
        assert "dates=" in url
        assert "details=" in url

    def test_google_url_includes_event_details(self, db_session, profile, application):
        """Google Calendar URL encodes company, role, link in details."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        url = generate_google_calendar_url(db_session, event.id, profile_id=profile.id)

        # URL-encoded details should contain key info
        assert "Acme" in url
        assert "zoom" in url.lower()

    def test_google_url_via_api(self, db_session, profile, application):
        """GET /api/calendar/events/{id}/google returns URL."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.get(f"/api/calendar/events/{event_id}/google?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        from urllib.parse import urlparse

        assert urlparse(data["url"]).hostname == "calendar.google.com"
        assert data["event_id"] == event_id


class TestFantastical:
    """Fantastical URL scheme — Provider 3."""

    def test_fantastical_url_scheme(self, db_session, profile, application):
        """Fantastical URL uses x-fantastical3:// scheme."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        url = generate_fantastical_url(db_session, event.id, profile_id=profile.id)

        assert url.startswith("x-fantastical3://add")
        assert "title=" in url
        assert "start=" in url
        assert "end=" in url

    def test_fantastical_url_includes_notes(self, db_session, profile, application):
        """Fantastical URL includes event details in notes."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        url = generate_fantastical_url(db_session, event.id, profile_id=profile.id)
        assert "notes=" in url
        assert "Acme" in url

    def test_fantastical_url_via_api(self, db_session, profile, application):
        """GET /api/calendar/events/{id}/fantastical returns URL."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.get(f"/api/calendar/events/{event_id}/fantastical?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert "x-fantastical3" in data["url"]


class TestMultiProvider:
    """All providers work for the same event — VAL-CAL-004."""

    def test_providers_endpoint_returns_all_three(self, db_session, profile, application):
        """GET /api/calendar/events/{id}/providers returns iCal, Google, Fantastical."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.get(f"/api/calendar/events/{event_id}/providers?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_id"] == event_id
        assert "ical" in data["providers"]
        assert "google" in data["providers"]
        assert "fantastical" in data["providers"]

        # Verify each provider has content
        assert "BEGIN:VCALENDAR" in data["providers"]["ical"]
        from urllib.parse import urlparse

        assert urlparse(data["providers"]["google"]).hostname == "calendar.google.com"
        assert "x-fantastical3" in data["providers"]["fantastical"]

    def test_service_get_event_provider_urls(self, db_session, profile, application):
        """Service returns provider URLs for all three providers."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        urls = get_event_provider_urls(db_session, event.id, profile_id=profile.id)

        assert "ical" in urls
        assert "google" in urls
        assert "fantastical" in urls


# ---------------------------------------------------------------------------
# VAL-CROSS-017: Calendar reflects pipeline and prep deadlines
# ---------------------------------------------------------------------------


class TestRescheduling:
    """Rescheduling updates both interview and prep reminder."""

    def test_reschedule_updates_prep_reminder(self, db_session, profile, application):
        """Changing start_time on interview updates prep reminder time."""
        payload = CalendarEventCreate(**_interview_payload(profile.id, application.id))
        event = create_calendar_event(db_session, payload)

        new_start = event.start_time + timedelta(days=2)
        new_end = new_start + timedelta(hours=1)

        update_payload = CalendarEventUpdate(
            start_time=new_start,
            end_time=new_end,
        )
        updated = update_calendar_event(db_session, event.id, update_payload, profile_id=profile.id)

        assert updated.start_time == new_start

        # Prep reminder should be updated too
        reminder = (
            db_session.query(CalendarEvent)
            .filter(
                CalendarEvent.event_type == "prep_reminder",
                CalendarEvent.application_id == application.id,
            )
            .first()
        )
        assert reminder is not None
        expected_reminder_time = new_start - timedelta(minutes=1440)
        assert reminder.start_time == expected_reminder_time

    def test_reschedule_via_api(self, db_session, profile, application):
        """PATCH /api/calendar/events/{id} updates event and prep reminder."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]
        original_start = create_resp.json()["start_time"]

        new_start = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        new_end = (datetime.now(UTC) + timedelta(days=5, hours=1)).isoformat()
        resp = client.patch(
            f"/api/calendar/events/{event_id}?profile_id={profile.id}",
            json={"start_time": new_start, "end_time": new_end},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["start_time"] != original_start


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


class TestCalendarCRUD:
    """Calendar event CRUD operations."""

    def test_list_events(self, db_session, profile, application):
        """GET /api/calendar/events lists events for profile."""
        # Create events
        for i in range(3):
            p = _interview_payload(profile.id, application.id)
            p["title"] = f"Interview {i}"
            client.post("/api/calendar/events", json=p)

        resp = client.get(f"/api/calendar/events?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        # 3 interviews + 3 prep reminders = 6 events
        assert data["total"] == 6

    def test_list_filter_by_event_type(self, db_session, profile, application):
        """Filtering by event_type works."""
        p = _interview_payload(profile.id, application.id)
        client.post("/api/calendar/events", json=p)

        resp = client.get(f"/api/calendar/events?profile_id={profile.id}&event_type=interview")
        assert resp.status_code == 200
        data = resp.json()
        for ev in data["events"]:
            assert ev["event_type"] == "interview"

    def test_list_filter_by_application_id(self, db_session, profile, application):
        """Filtering by application_id works."""
        p = _interview_payload(profile.id, application.id)
        client.post("/api/calendar/events", json=p)

        resp = client.get(
            f"/api/calendar/events?profile_id={profile.id}&application_id={application.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for ev in data["events"]:
            assert ev["application_id"] == application.id

    def test_get_single_event(self, db_session, profile, application):
        """GET /api/calendar/events/{id} returns event."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.get(f"/api/calendar/events/{event_id}?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == event_id

    def test_get_nonexistent_event_returns_404(self, db_session, profile):
        """Getting nonexistent event returns 404."""
        resp = client.get(f"/api/calendar/events/9999?profile_id={profile.id}")
        assert resp.status_code == 404

    def test_update_event(self, db_session, profile, application):
        """PATCH /api/calendar/events/{id} updates fields."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/calendar/events/{event_id}?profile_id={profile.id}",
            json={"title": "Updated Interview Title", "prep_notes": "New prep notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Interview Title"
        assert data["prep_notes"] == "New prep notes"

    def test_delete_event(self, db_session, profile, application):
        """DELETE /api/calendar/events/{id} removes event."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.delete(f"/api/calendar/events/{event_id}?profile_id={profile.id}")
        assert resp.status_code == 204

        # Verify deleted
        get_resp = client.get(f"/api/calendar/events/{event_id}?profile_id={profile.id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, db_session, profile):
        """Deleting nonexistent event returns 404."""
        resp = client.delete(f"/api/calendar/events/9999?profile_id={profile.id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Profile isolation tests
# ---------------------------------------------------------------------------


class TestProfileIsolation:
    """Calendar events are profile-scoped — no cross-profile leaks."""

    def test_profile_b_cannot_see_profile_a_events(
        self, db_session, profile, profile_b, application
    ):
        """Events created by profile A are invisible to profile B."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        # Profile B can't see it
        resp = client.get(f"/api/calendar/events/{event_id}?profile_id={profile_b.id}")
        assert resp.status_code == 404

    def test_profile_b_cannot_update_profile_a_events(
        self, db_session, profile, profile_b, application
    ):
        """Profile B cannot update profile A's events."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/calendar/events/{event_id}?profile_id={profile_b.id}",
            json={"title": "Hacked!"},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_delete_profile_a_events(
        self, db_session, profile, profile_b, application
    ):
        """Profile B cannot delete profile A's events."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.delete(f"/api/calendar/events/{event_id}?profile_id={profile_b.id}")
        assert resp.status_code == 404

    def test_list_only_own_events(self, db_session, profile, profile_b, application):
        """Listing events returns only own profile's events."""
        payload = _interview_payload(profile.id, application.id)
        client.post("/api/calendar/events", json=payload)

        resp_a = client.get(f"/api/calendar/events?profile_id={profile.id}")
        resp_b = client.get(f"/api/calendar/events?profile_id={profile_b.id}")

        assert resp_a.json()["total"] >= 1
        assert resp_b.json()["total"] == 0

    def test_profile_b_cannot_export_ical_for_profile_a(
        self, db_session, profile, profile_b, application
    ):
        """Profile B cannot export iCal for profile A's events."""
        payload = _interview_payload(profile.id, application.id)
        create_resp = client.post("/api/calendar/events", json=payload)
        event_id = create_resp.json()["id"]

        resp = client.get(f"/api/calendar/events/{event_id}/ical?profile_id={profile_b.id}")
        assert resp.status_code == 404

    def test_follow_up_event_wrong_profile_isolated(
        self, db_session, profile, profile_b, application, follow_up
    ):
        """Cannot create calendar event from another profile's follow-up."""
        resp = client.post(
            f"/api/calendar/events/from-follow-up/{follow_up.id}?profile_id={profile_b.id}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case scenarios for calendar integration."""

    def test_event_without_meeting_link(self, db_session, profile, application):
        """Event without meeting link still exports correctly."""
        payload_dict = _interview_payload(profile.id, application.id)
        payload_dict["meeting_link"] = None
        payload_dict["location"] = "Acme Corp HQ, Frankfurt"
        payload = CalendarEventCreate(**payload_dict)
        event = create_calendar_event(db_session, payload)

        ical_data = export_event_ical(db_session, event.id, profile_id=profile.id)
        assert "Frankfurt" in ical_data

    def test_event_without_prep_notes(self, db_session, profile, application):
        """Event without prep notes still works."""
        payload_dict = _interview_payload(profile.id, application.id)
        payload_dict["prep_notes"] = None
        payload = CalendarEventCreate(**payload_dict)
        event = create_calendar_event(db_session, payload)

        assert event.id is not None
        ical_data = export_event_ical(db_session, event.id, profile_id=profile.id)
        assert "BEGIN:VEVENT" in ical_data

    def test_multiple_events_for_same_application(self, db_session, profile, application):
        """Multiple interviews for the same application."""
        for i in range(3):
            p = _interview_payload(profile.id, application.id)
            p["title"] = f"Round {i + 1} Interview"
            client.post("/api/calendar/events", json=p)

        _events, total = list_calendar_events(
            db_session, profile_id=profile.id, application_id=application.id
        )
        # 3 interviews + 3 prep reminders
        assert total == 6

    def test_empty_event_list(self, db_session, profile):
        """Empty event list returns properly."""
        resp = client.get(f"/api/calendar/events?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["events"] == []

    def test_ical_export_empty_events(self, db_session, profile):
        """Exporting with no events returns valid empty calendar."""
        resp = client.get(f"/api/calendar/export/ical?profile_id={profile.id}")
        assert resp.status_code == 200
        assert "BEGIN:VCALENDAR" in resp.text
        assert "END:VCALENDAR" in resp.text

    def test_unique_uid_per_event(self, db_session, profile, application):
        """Each event gets a unique UID."""
        uids = set()
        for _ in range(5):
            p = _interview_payload(profile.id, application.id)
            resp = client.post("/api/calendar/events", json=p)
            data = resp.json()
            uids.add(data["uid"])
        assert len(uids) == 5
