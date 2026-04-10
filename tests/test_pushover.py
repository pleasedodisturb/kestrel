"""Tests for Pushover notification integration.

Covers:
- VAL-PUSH-001: Follow-up due triggers Pushover notification with company, role, suggested action
- VAL-PUSH-002: Ghost detection triggers notification with days count
- VAL-PUSH-003: High-scoring discovery triggers notification with company, role, score
- VAL-PUSH-004: Interview reminder at configured lead time
- VAL-PUSH-005: Auth failure logged and surfaced in UI, no crash
- VAL-CROSS-008: Ghost detection → follow-up + Pushover + TickTick chain (same app ID)
- VAL-CROSS-018: Notifications respect user preferences (categories, quiet hours)
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.calendar import CalendarEvent
from career_os.models.integrations import IntegrationConfig
from career_os.models.models import Application, FollowUp, Profile
from career_os.models.pushover import NotificationLog
from career_os.schemas.pushover import NotificationPreferenceUpdate
from career_os.services.pushover import (
    _is_quiet_hours,
    get_preferences,
    send_test_notification,
    trigger_discovery_alert,
    trigger_follow_up_reminders,
    trigger_ghost_alerts,
    trigger_interview_reminders,
    update_preferences,
)
from career_os.services.pushover_client import (
    PushoverAPIError,
    PushoverAuthError,
    PushoverClient,
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


@pytest.fixture()
def profile(db_session):
    """Create a test profile."""
    p = Profile(name="Test User", email="test@example.com", location="Frankfurt")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def profile_b(db_session):
    """Create a second test profile for isolation tests."""
    p = Profile(name="Other User", email="other@example.com", location="Berlin")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def pushover_config(db_session):
    """Create a configured and enabled Pushover integration."""
    config = IntegrationConfig(
        name="pushover",
        display_name="Pushover",
        enabled=True,
        credentials=json.dumps({"user_key": "test_user_key", "app_token": "test_app_token"}),
        status="connected",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture()
def application(db_session, profile):
    """Create a test application."""
    app_obj = Application(
        profile_id=profile.id,
        company="TestCorp",
        role="Senior Engineer",
        status="applied",
        url="https://testcorp.com/jobs/123",
        fit_score=8.5,
    )
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


@pytest.fixture()
def due_follow_up(db_session, profile, application):
    """Create a follow-up that is due (past due date)."""
    fu = FollowUp(
        profile_id=profile.id,
        application_id=application.id,
        due_date=datetime.now(UTC) - timedelta(hours=2),
        follow_up_type="email",
        notes="Follow up on application status",
    )
    db_session.add(fu)
    db_session.commit()
    db_session.refresh(fu)
    return fu


@pytest.fixture()
def ghost_application(db_session, profile):
    """Create an application that has been in 'applied' for 15+ days (ghost)."""
    old_date = datetime.now(UTC) - timedelta(days=16)
    app_obj = Application(
        profile_id=profile.id,
        company="GhostCo",
        role="Product Manager",
        status="applied",
        url="https://ghostco.com/jobs/1",
    )
    db_session.add(app_obj)
    db_session.commit()
    # Manually set updated_at to the past
    app_obj.updated_at = old_date
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


@pytest.fixture()
def interview_event(db_session, profile, application):
    """Create an upcoming interview calendar event."""
    now = datetime.now(UTC)
    event = CalendarEvent(
        profile_id=profile.id,
        application_id=application.id,
        event_type="interview",
        title="Technical Interview - TestCorp",
        company="TestCorp",
        role="Senior Engineer",
        interview_type="technical",
        start_time=now + timedelta(hours=12),
        end_time=now + timedelta(hours=13),
        meeting_link="https://meet.google.com/abc-def",
        prep_notes="Review system design patterns",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Pushover Client Tests
# ---------------------------------------------------------------------------


class TestPushoverClient:
    """Tests for the Pushover API client."""

    @patch("career_os.services.pushover_client.httpx.post")
    def test_send_notification_success(self, mock_post):
        """Successful notification returns response with status 1."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": 1, "request": "abc123"}),
        )
        client_obj = PushoverClient("user_key", "app_token")
        result = client_obj.send_notification(message="Test", title="Title")
        assert result["status"] == 1
        assert result["request"] == "abc123"

    @patch("career_os.services.pushover_client.httpx.post")
    def test_send_notification_auth_error(self, mock_post):
        """401 response raises PushoverAuthError."""
        mock_post.return_value = MagicMock(status_code=401)
        client_obj = PushoverClient("bad_key", "bad_token")
        with pytest.raises(PushoverAuthError):
            client_obj.send_notification(message="Test")

    @patch("career_os.services.pushover_client.httpx.post")
    def test_send_notification_rate_limit(self, mock_post):
        """429 response raises PushoverAPIError with rate limit message."""
        mock_post.return_value = MagicMock(status_code=429, text="Rate limited")
        client_obj = PushoverClient("key", "token")
        with pytest.raises(PushoverAPIError, match="Rate limited"):
            client_obj.send_notification(message="Test")

    @patch("career_os.services.pushover_client.httpx.post")
    def test_send_notification_with_all_options(self, mock_post):
        """All optional parameters are sent correctly."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": 1, "request": "req1"}),
        )
        client_obj = PushoverClient("key", "token")
        client_obj.send_notification(
            message="Test",
            title="Title",
            url="https://example.com",
            url_title="Click here",
            priority=1,
            sound="pushover",
            html=True,
        )
        call_kwargs = mock_post.call_args
        data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert data["html"] == 1
        assert data["priority"] == 1
        assert data["url"] == "https://example.com"

    @patch("career_os.services.pushover_client.httpx.post")
    def test_validate_credentials_success(self, mock_post):
        """Valid credentials return True."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": 1, "devices": ["iphone"]}),
        )
        client_obj = PushoverClient("key", "token")
        assert client_obj.validate_credentials() is True

    @patch("career_os.services.pushover_client.httpx.post")
    def test_validate_credentials_failure(self, mock_post):
        """Invalid credentials raise PushoverAuthError."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": 0, "errors": ["user key is invalid"]}),
        )
        client_obj = PushoverClient("bad_key", "token")
        with pytest.raises(PushoverAuthError, match="user key is invalid"):
            client_obj.validate_credentials()


# ---------------------------------------------------------------------------
# Notification Preferences Tests
# ---------------------------------------------------------------------------


class TestNotificationPreferences:
    """Tests for notification preferences CRUD."""

    def test_get_preferences_creates_defaults(self, db_session, profile):
        """Getting preferences for a new profile creates default preferences."""
        pref = get_preferences(db_session, profile.id)
        assert pref.profile_id == profile.id
        assert pref.follow_up_reminders is True
        assert pref.ghost_alerts is True
        assert pref.discovery_alerts is True
        assert pref.interview_reminders is True
        assert pref.quiet_hours_start is None
        assert pref.quiet_hours_end is None
        assert pref.interview_lead_time_minutes == 1440
        assert pref.discovery_score_threshold == 7

    def test_update_preferences(self, db_session, profile):
        """Update specific preferences."""
        payload = NotificationPreferenceUpdate(
            follow_up_reminders=False,
            quiet_hours_start=22,
            quiet_hours_end=8,
            discovery_score_threshold=8.0,
        )
        pref = update_preferences(db_session, profile.id, payload)
        assert pref.follow_up_reminders is False
        assert pref.ghost_alerts is True  # Unchanged
        assert pref.quiet_hours_start == 22
        assert pref.quiet_hours_end == 8
        assert pref.discovery_score_threshold == 8

    def test_preferences_api_get(self, db_session, profile):
        """GET /api/notifications/preferences returns defaults."""
        resp = client.get(f"/api/notifications/preferences?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["follow_up_reminders"] is True
        assert data["ghost_alerts"] is True

    def test_preferences_api_update(self, db_session, profile):
        """PUT /api/notifications/preferences updates values."""
        resp = client.put(
            f"/api/notifications/preferences?profile_id={profile.id}",
            json={"ghost_alerts": False, "interview_lead_time_minutes": 60},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ghost_alerts"] is False
        assert data["interview_lead_time_minutes"] == 60

    def test_preferences_profile_isolation(self, db_session, profile, profile_b):
        """Each profile has its own preferences."""
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(follow_up_reminders=False),
        )
        pref_b = get_preferences(db_session, profile_b.id)
        assert pref_b.follow_up_reminders is True  # Profile B unchanged


# ---------------------------------------------------------------------------
# Quiet Hours Tests (VAL-CROSS-018)
# ---------------------------------------------------------------------------


class TestQuietHours:
    """Tests for quiet hours logic."""

    def test_no_quiet_hours_set(self, db_session, profile):
        """No quiet hours configured means never quiet."""
        pref = get_preferences(db_session, profile.id)
        assert _is_quiet_hours(pref) is False

    def test_quiet_hours_simple_range(self, db_session, profile):
        """Quiet hours 22:00-08:00 (wraps midnight)."""
        pref = update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(quiet_hours_start=22, quiet_hours_end=8),
        )
        # Mock current hour
        with patch("career_os.services.pushover.datetime") as mock_dt:
            mock_now = datetime(2026, 3, 14, 23, 0, tzinfo=UTC)  # 23:00 UTC
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert _is_quiet_hours(pref) is True

    def test_outside_quiet_hours(self, db_session, profile):
        """Outside quiet hours means not quiet."""
        pref = update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(quiet_hours_start=22, quiet_hours_end=8),
        )
        with patch("career_os.services.pushover.datetime") as mock_dt:
            mock_now = datetime(2026, 3, 14, 14, 0, tzinfo=UTC)  # 14:00 UTC
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert _is_quiet_hours(pref) is False


# ---------------------------------------------------------------------------
# Follow-up Reminders Tests (VAL-PUSH-001)
# ---------------------------------------------------------------------------


class TestFollowUpReminders:
    """Tests for follow-up reminder notifications."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_due_follow_up_triggers_notification(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up, application
    ):
        """Due follow-up triggers Pushover notification with company, role."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        result = trigger_follow_up_reminders(db_session, profile.id)
        assert result["triggered"] == 1
        assert result["failed"] == 0

        # Verify notification was called with correct content
        call_args = mock_instance.send_notification.call_args
        assert "TestCorp" in call_args.kwargs["message"]
        assert "Senior Engineer" in call_args.kwargs["message"]
        assert "email" in call_args.kwargs["message"]  # follow_up_type
        assert "Follow-up Reminder" in call_args.kwargs["title"]

    @patch("career_os.services.pushover.PushoverClient")
    def test_follow_up_logged(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up
    ):
        """Follow-up notification creates a log entry."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        trigger_follow_up_reminders(db_session, profile.id)

        logs = (
            db_session.query(NotificationLog)
            .filter(
                NotificationLog.profile_id == profile.id,
                NotificationLog.category == "follow_up",
            )
            .all()
        )
        assert len(logs) == 1
        assert logs[0].status == "sent"

    def test_follow_up_disabled_skipped(self, db_session, profile, pushover_config, due_follow_up):
        """When follow_up_reminders is disabled, no notification sent."""
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(follow_up_reminders=False),
        )
        result = trigger_follow_up_reminders(db_session, profile.id)
        assert result["triggered"] == 0
        assert result["skipped"] == 1

    def test_no_due_follow_ups(self, db_session, profile, pushover_config):
        """No due follow-ups triggers nothing."""
        result = trigger_follow_up_reminders(db_session, profile.id)
        assert result["triggered"] == 0

    def test_follow_up_api_trigger(self, db_session, profile, pushover_config, due_follow_up):
        """POST /api/notifications/trigger/follow-ups works via API."""
        with patch("career_os.services.pushover.PushoverClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
            mock_client_cls.return_value = mock_instance

            resp = client.post(f"/api/notifications/trigger/follow-ups?profile_id={profile.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["triggered"] >= 1


# ---------------------------------------------------------------------------
# Ghost Alert Tests (VAL-PUSH-002)
# ---------------------------------------------------------------------------


class TestGhostAlerts:
    """Tests for ghost detection notifications."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_ghost_triggers_notification_with_days(
        self, mock_client_cls, db_session, profile, pushover_config, ghost_application
    ):
        """Ghost application triggers notification with company, role, days count."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        result = trigger_ghost_alerts(db_session, profile.id)
        assert result["triggered"] >= 1

        call_args = mock_instance.send_notification.call_args
        assert "GhostCo" in call_args.kwargs["message"]
        assert "Product Manager" in call_args.kwargs["message"]
        # Should mention days count
        assert "days" in call_args.kwargs["message"].lower()
        assert "Ghost Alert" in call_args.kwargs["title"]

    @patch("career_os.services.pushover.PushoverClient")
    def test_ghost_notification_logged(
        self, mock_client_cls, db_session, profile, pushover_config, ghost_application
    ):
        """Ghost notification creates a log entry with application_id."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        trigger_ghost_alerts(db_session, profile.id)

        logs = (
            db_session.query(NotificationLog)
            .filter(
                NotificationLog.category == "ghost",
            )
            .all()
        )
        assert len(logs) >= 1
        assert logs[0].application_id == ghost_application.id
        assert logs[0].status == "sent"

    def test_ghost_disabled_skipped(self, db_session, profile, pushover_config, ghost_application):
        """When ghost_alerts is disabled, no notification sent."""
        update_preferences(db_session, profile.id, NotificationPreferenceUpdate(ghost_alerts=False))
        result = trigger_ghost_alerts(db_session, profile.id)
        assert result["triggered"] == 0
        assert result["skipped"] == 1

    def test_no_ghost_applications(self, db_session, profile, pushover_config, application):
        """No ghost applications means no notifications."""
        result = trigger_ghost_alerts(db_session, profile.id)
        assert result["triggered"] == 0


# ---------------------------------------------------------------------------
# Discovery Alert Tests (VAL-PUSH-003)
# ---------------------------------------------------------------------------


class TestDiscoveryAlerts:
    """Tests for high-scoring discovery notifications."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_high_score_triggers_notification(
        self, mock_client_cls, db_session, profile, pushover_config
    ):
        """High-scoring discovery sends notification with company, role, score."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        result = trigger_discovery_alert(
            db_session,
            profile.id,
            company="DreamCo",
            role="AI Lead",
            score=9.0,
        )
        assert result["triggered"] == 1

        call_args = mock_instance.send_notification.call_args
        assert "DreamCo" in call_args.kwargs["message"]
        assert "AI Lead" in call_args.kwargs["message"]
        assert "9.0" in call_args.kwargs["message"]
        assert "High-Scoring" in call_args.kwargs["title"]

    @patch("career_os.services.pushover.PushoverClient")
    def test_below_threshold_skipped(self, mock_client_cls, db_session, profile, pushover_config):
        """Score below threshold is skipped."""
        result = trigger_discovery_alert(
            db_session,
            profile.id,
            company="LowCo",
            role="Intern",
            score=3.0,
        )
        assert result["triggered"] == 0
        assert result["skipped"] == 1

    @patch("career_os.services.pushover.PushoverClient")
    def test_custom_threshold(self, mock_client_cls, db_session, profile, pushover_config):
        """Custom threshold is respected."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        # Set threshold to 9
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(discovery_score_threshold=9.0),
        )

        # Score of 8 should be skipped
        result = trigger_discovery_alert(
            db_session,
            profile.id,
            company="MedCo",
            role="Lead",
            score=8.0,
        )
        assert result["skipped"] == 1

        # Score of 9 should trigger
        result = trigger_discovery_alert(
            db_session,
            profile.id,
            company="HighCo",
            role="Lead",
            score=9.0,
        )
        assert result["triggered"] == 1

    def test_discovery_disabled_skipped(self, db_session, profile, pushover_config):
        """When discovery_alerts is disabled, no notification sent."""
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(discovery_alerts=False),
        )
        result = trigger_discovery_alert(
            db_session,
            profile.id,
            company="Co",
            role="Role",
            score=10.0,
        )
        assert result["skipped"] == 1

    def test_discovery_api_trigger(self, db_session, profile, pushover_config):
        """POST /api/notifications/trigger/discovery works via API."""
        with patch("career_os.services.pushover.PushoverClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
            mock_client_cls.return_value = mock_instance

            resp = client.post(
                "/api/notifications/trigger/discovery"
                f"?profile_id={profile.id}&company=DreamCo&role=AI+Lead&score=9.0"
            )
            assert resp.status_code == 200
            assert resp.json()["triggered"] == 1


# ---------------------------------------------------------------------------
# Interview Reminder Tests (VAL-PUSH-004)
# ---------------------------------------------------------------------------


class TestInterviewReminders:
    """Tests for interview reminder notifications."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_upcoming_interview_triggers_reminder(
        self, mock_client_cls, db_session, profile, pushover_config, interview_event
    ):
        """Upcoming interview within lead time triggers notification."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        result = trigger_interview_reminders(db_session, profile.id)
        assert result["triggered"] == 1

        call_args = mock_instance.send_notification.call_args
        assert "TestCorp" in call_args.kwargs["message"]
        assert "Senior Engineer" in call_args.kwargs["message"]
        assert "technical" in call_args.kwargs["message"].lower()

    @patch("career_os.services.pushover.PushoverClient")
    def test_interview_includes_meeting_link(
        self, mock_client_cls, db_session, profile, pushover_config, interview_event
    ):
        """Interview reminder includes meeting link."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        trigger_interview_reminders(db_session, profile.id)

        call_args = mock_instance.send_notification.call_args
        assert "meet.google.com" in call_args.kwargs["message"]  # content check, not URL validation

    @patch("career_os.services.pushover.PushoverClient")
    def test_no_duplicate_interview_reminders(
        self, mock_client_cls, db_session, profile, pushover_config, interview_event, application
    ):
        """Already-notified interview is skipped on second trigger."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        # First trigger sends
        result1 = trigger_interview_reminders(db_session, profile.id)
        assert result1["triggered"] == 1

        # Second trigger skips (already notified)
        result2 = trigger_interview_reminders(db_session, profile.id)
        assert result2["skipped"] == 1
        assert result2["triggered"] == 0

    def test_interview_disabled_skipped(
        self, db_session, profile, pushover_config, interview_event
    ):
        """When interview_reminders is disabled, no notification sent."""
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(interview_reminders=False),
        )
        result = trigger_interview_reminders(db_session, profile.id)
        assert result["skipped"] == 1

    @patch("career_os.services.pushover.PushoverClient")
    def test_custom_lead_time(
        self, mock_client_cls, db_session, profile, pushover_config, application
    ):
        """Custom lead time is respected — short lead time misses far-future interview."""
        # Set very short lead time (30 minutes)
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(interview_lead_time_minutes=30),
        )

        # Create interview 12 hours from now (beyond 30 min lead)
        now = datetime.now(UTC)
        event = CalendarEvent(
            profile_id=profile.id,
            application_id=application.id,
            event_type="interview",
            title="Interview - TestCorp",
            company="TestCorp",
            role="Senior Engineer",
            start_time=now + timedelta(hours=12),
            end_time=now + timedelta(hours=13),
        )
        db_session.add(event)
        db_session.commit()

        result = trigger_interview_reminders(db_session, profile.id)
        # Should NOT trigger (12h > 30min lead)
        assert result["triggered"] == 0


# ---------------------------------------------------------------------------
# Auth Failure Tests (VAL-PUSH-005)
# ---------------------------------------------------------------------------


class TestAuthFailure:
    """Tests for graceful auth failure handling."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_auth_error_logged_not_crash(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up
    ):
        """Auth failure is logged, doesn't crash, surfaces in integration status."""
        mock_instance = MagicMock()
        mock_instance.send_notification.side_effect = PushoverAuthError("Invalid credentials", 401)
        mock_client_cls.return_value = mock_instance

        # Should not raise
        result = trigger_follow_up_reminders(db_session, profile.id)
        assert result["failed"] == 1

        # Check log entry
        log = (
            db_session.query(NotificationLog)
            .filter(
                NotificationLog.category == "follow_up",
                NotificationLog.status == "failed",
            )
            .first()
        )
        assert log is not None
        assert "Auth error" in log.error_message

    @patch("career_os.services.pushover.PushoverClient")
    def test_auth_error_updates_integration_status(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up
    ):
        """Auth failure updates the integration status to 'error'."""
        mock_instance = MagicMock()
        mock_instance.send_notification.side_effect = PushoverAuthError("Invalid", 401)
        mock_client_cls.return_value = mock_instance

        trigger_follow_up_reminders(db_session, profile.id)

        config = (
            db_session.query(IntegrationConfig).filter(IntegrationConfig.name == "pushover").first()
        )
        assert config.status == "error"
        assert "Authentication failed" in config.status_message

    def test_not_configured_graceful(self, db_session, profile, due_follow_up):
        """Pushover not configured doesn't crash."""
        result = trigger_follow_up_reminders(db_session, profile.id)
        assert result["failed"] == 1
        assert "not enabled" in result["details"][0]["reason"]

    def test_send_test_with_invalid_creds(self, db_session, profile, pushover_config):
        """Send test notification with invalid creds logs failure."""
        with patch("career_os.services.pushover.PushoverClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.send_notification.side_effect = PushoverAuthError("Bad creds", 401)
            mock_client_cls.return_value = mock_instance

            result = send_test_notification(
                db_session,
                profile_id=profile.id,
                category="follow_up",
                title="Test",
                message="Test message",
            )
            assert result["status"] == "failed"
            assert "error" in result

    def test_auth_error_surfaced_in_api(self, db_session, profile, pushover_config, due_follow_up):
        """Auth error is visible via integration config API."""
        with patch("career_os.services.pushover.PushoverClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.send_notification.side_effect = PushoverAuthError("Invalid key", 401)
            mock_client_cls.return_value = mock_instance

            # Trigger to create the error state
            client.post(f"/api/notifications/trigger/follow-ups?profile_id={profile.id}")

            # Check integration status shows error
            resp = client.get("/api/integrations/pushover/config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "error"
            assert data["status_message"] is not None


# ---------------------------------------------------------------------------
# Notification Log Tests
# ---------------------------------------------------------------------------


class TestNotificationLog:
    """Tests for notification log API."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_log_entries_created(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up
    ):
        """Sending notifications creates log entries."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        trigger_follow_up_reminders(db_session, profile.id)

        resp = client.get(f"/api/notifications/log?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["notifications"][0]["category"] == "follow_up"
        assert data["notifications"][0]["status"] == "sent"

    def test_log_filter_by_category(self, db_session, profile):
        """Log can be filtered by category."""
        # Create log entries directly
        for cat in ["follow_up", "ghost", "discovery"]:
            log = NotificationLog(
                profile_id=profile.id,
                category=cat,
                title=f"Test {cat}",
                message=f"Message for {cat}",
                status="sent",
            )
            db_session.add(log)
        db_session.commit()

        resp = client.get(f"/api/notifications/log?profile_id={profile.id}&category=ghost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["notifications"][0]["category"] == "ghost"


# ---------------------------------------------------------------------------
# Cross-Area Tests
# ---------------------------------------------------------------------------


class TestCrossArea:
    """Cross-area integration tests."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_ghost_detection_notification_chain(
        self, mock_client_cls, db_session, profile, pushover_config, ghost_application
    ):
        """VAL-CROSS-008: Ghost detection triggers Pushover with same application_id."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        result = trigger_ghost_alerts(db_session, profile.id)
        assert result["triggered"] >= 1

        # Verify log entry references the ghost application ID
        log = (
            db_session.query(NotificationLog)
            .filter(
                NotificationLog.category == "ghost",
                NotificationLog.application_id == ghost_application.id,
            )
            .first()
        )
        assert log is not None
        assert log.status == "sent"

    @patch("career_os.services.pushover.PushoverClient")
    def test_category_disable_honored(
        self,
        mock_client_cls,
        db_session,
        profile,
        pushover_config,
        due_follow_up,
        ghost_application,
    ):
        """VAL-CROSS-018: Per-category disable prevents notification."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        # Disable ghost alerts
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(ghost_alerts=False),
        )

        # Ghost alerts skipped
        ghost_result = trigger_ghost_alerts(db_session, profile.id)
        assert ghost_result["triggered"] == 0
        assert ghost_result["skipped"] == 1

        # Follow-up still works
        fu_result = trigger_follow_up_reminders(db_session, profile.id)
        assert fu_result["triggered"] == 1

    @patch("career_os.services.pushover.PushoverClient")
    def test_quiet_hours_queues_notifications(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up
    ):
        """VAL-CROSS-018: Quiet hours queue notifications instead of dropping them."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        # Set quiet hours covering current hour
        now_hour = datetime.now(UTC).hour
        start = now_hour
        end = (now_hour + 2) % 24
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(quiet_hours_start=start, quiet_hours_end=end),
        )

        result = trigger_follow_up_reminders(db_session, profile.id)
        # Notifications should be queued, not skipped
        assert result["triggered"] >= 1
        assert any(d.get("status") == "queued" for d in result["details"])

        # Verify the notification is persisted with queued status
        queued = (
            db_session.query(NotificationLog)
            .filter(
                NotificationLog.profile_id == profile.id,
                NotificationLog.status == "queued",
            )
            .all()
        )
        assert len(queued) >= 1

        # Pushover client should NOT have been called (notifications queued, not sent)
        mock_instance.send_notification.assert_not_called()


# ---------------------------------------------------------------------------
# Profile Isolation Tests
# ---------------------------------------------------------------------------


class TestDeliverQueuedNotifications:
    """Tests for delivering queued notifications after quiet hours end."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_deliver_queued_sends_and_marks_sent(
        self, mock_client_cls, db_session, profile, pushover_config, due_follow_up
    ):
        """Queued notifications are delivered and marked as sent."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        # Set quiet hours covering current hour to queue notifications
        now_hour = datetime.now(UTC).hour
        start = now_hour
        end = (now_hour + 2) % 24
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(quiet_hours_start=start, quiet_hours_end=end),
        )

        # Trigger to queue
        trigger_follow_up_reminders(db_session, profile.id)

        # Verify queued
        from career_os.services.pushover import deliver_queued_notifications

        queued = (
            db_session.query(NotificationLog).filter(NotificationLog.status == "queued").count()
        )
        assert queued >= 1

        # Now clear quiet hours and deliver
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(quiet_hours_start=None, quiet_hours_end=None),
        )

        result = deliver_queued_notifications(db_session, profile.id)
        assert result["delivered"] >= 1

        # Verify all queued are now sent
        still_queued = (
            db_session.query(NotificationLog).filter(NotificationLog.status == "queued").count()
        )
        assert still_queued == 0

    def test_deliver_during_quiet_hours_does_nothing(self, db_session, profile, pushover_config):
        """Deliver during quiet hours returns without sending."""
        from career_os.services.pushover import deliver_queued_notifications

        now_hour = datetime.now(UTC).hour
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(
                quiet_hours_start=now_hour,
                quiet_hours_end=(now_hour + 2) % 24,
            ),
        )

        result = deliver_queued_notifications(db_session, profile.id)
        assert result["delivered"] == 0
        assert "quiet hours" in result.get("reason", "")


# ---------------------------------------------------------------------------


class TestProfileIsolation:
    """Tests for profile-scoped notification data isolation."""

    def test_preferences_isolated(self, db_session, profile, profile_b):
        """Profile A preferences don't affect Profile B."""
        update_preferences(
            db_session,
            profile.id,
            NotificationPreferenceUpdate(follow_up_reminders=False),
        )
        pref_b = get_preferences(db_session, profile_b.id)
        assert pref_b.follow_up_reminders is True

    def test_notification_log_isolated(self, db_session, profile, profile_b):
        """Profile A logs are not visible to Profile B."""
        log = NotificationLog(
            profile_id=profile.id,
            category="follow_up",
            title="Test",
            message="Private message",
            status="sent",
        )
        db_session.add(log)
        db_session.commit()

        resp = client.get(f"/api/notifications/log?profile_id={profile_b.id}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @patch("career_os.services.pushover.PushoverClient")
    def test_follow_ups_only_for_own_profile(
        self, mock_client_cls, db_session, profile, profile_b, pushover_config
    ):
        """Follow-up trigger only fires for the requesting profile's follow-ups."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        # Create application and follow-up for profile A
        app_obj = Application(profile_id=profile.id, company="ACo", role="Dev", status="applied")
        db_session.add(app_obj)
        db_session.commit()
        fu = FollowUp(
            profile_id=profile.id,
            application_id=app_obj.id,
            due_date=datetime.now(UTC) - timedelta(hours=1),
            follow_up_type="email",
        )
        db_session.add(fu)
        db_session.commit()

        # Trigger for profile B should find nothing
        result = trigger_follow_up_reminders(db_session, profile_b.id)
        assert result["triggered"] == 0


# ---------------------------------------------------------------------------
# Test Connection
# ---------------------------------------------------------------------------


class TestConnectionTest:
    """Tests for Pushover connection testing."""

    def test_test_connection_not_configured(self, db_session):
        """Test connection when not configured returns failure."""
        resp = client.post("/api/notifications/test-connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    @patch("career_os.services.pushover.PushoverClient")
    def test_test_connection_success(self, mock_client_cls, db_session, pushover_config):
        """Test connection with valid credentials succeeds."""
        mock_instance = MagicMock()
        mock_instance.validate_credentials.return_value = True
        mock_client_cls.return_value = mock_instance

        resp = client.post("/api/notifications/test-connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @patch("career_os.services.pushover.PushoverClient")
    def test_test_connection_auth_failure(self, mock_client_cls, db_session, pushover_config):
        """Test connection with invalid credentials shows error."""
        mock_instance = MagicMock()
        mock_instance.validate_credentials.side_effect = PushoverAuthError("Bad key", 401)
        mock_client_cls.return_value = mock_instance

        resp = client.post("/api/notifications/test-connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Auth error" in data["message"]

        # Check integration status updated
        config_resp = client.get("/api/integrations/pushover/config")
        assert config_resp.json()["status"] == "error"


# ---------------------------------------------------------------------------
# Send Notification API
# ---------------------------------------------------------------------------


class TestSendNotificationAPI:
    """Tests for the manual send notification endpoint."""

    @patch("career_os.services.pushover.PushoverClient")
    def test_send_notification_api(self, mock_client_cls, db_session, profile, pushover_config):
        """POST /api/notifications/send sends a notification."""
        mock_instance = MagicMock()
        mock_instance.send_notification.return_value = {"status": 1, "request": "r1"}
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/api/notifications/send",
            json={
                "profile_id": profile.id,
                "category": "follow_up",
                "title": "Test Notification",
                "message": "This is a test",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"

    def test_send_notification_not_configured(self, db_session, profile):
        """Send when not configured returns failure (no crash)."""
        resp = client.post(
            "/api/notifications/send",
            json={
                "profile_id": profile.id,
                "category": "follow_up",
                "title": "Test",
                "message": "Test message",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
