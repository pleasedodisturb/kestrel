"""Tests for TimingsApp integration.

Covers:
- VAL-TIME-001: Track job search activities (start/stop sessions → TimingsApp entry)
- VAL-TIME-002: Activity categorization (auto-assigned from context)
- VAL-TIME-003: Time analytics in dashboard (total hours, category breakdown, 4-week trend)
- Profile isolation tests
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
from career_os.models.integrations import IntegrationConfig
from career_os.models.models import Profile
from career_os.models.timingsapp import TimeSession
from career_os.schemas.timingsapp import (
    ActivityCategory,
    TimeSessionCreate,
    TimeSessionUpdate,
)
from career_os.services.timingsapp import (
    ConcurrentSessionError,
    TimeSessionAlreadyStoppedError,
    TimeSessionNotFoundError,
    auto_categorize,
    check_timingsapp_connection,
    get_running_session,
    get_session,
    get_time_analytics,
    list_sessions,
    start_session,
    stop_session,
    update_session,
)
from career_os.services.timingsapp_client import (
    TimingsAppAPIError,
    TimingsAppClient,
)

api_client = TestClient(app)


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
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

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
def timingsapp_config(db_session) -> IntegrationConfig:
    """Create a configured and enabled TimingsApp integration."""
    config = IntegrationConfig(
        name="timingsapp",
        display_name="TimingsApp",
        enabled=True,
        credentials=json.dumps(
            {
                "api_token": "test-token-abc",
                "api_url": "https://web.timingapp.com/api/v1",
            }
        ),
        status="connected",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture()
def mock_timingsapp_client():
    """Create a mock TimingsApp client."""
    mock_client = MagicMock(spec=TimingsAppClient)
    mock_client.start_timer.return_value = {
        "self": "/time-entries/42",
        "title": "Test Activity",
        "is_running": True,
        "project": {"self": "/projects/1"},
    }
    mock_client.stop_timer.return_value = {
        "self": "/time-entries/42",
        "title": "Test Activity",
        "is_running": False,
        "duration": 3600,
    }
    mock_client.test_connection.return_value = True
    return mock_client


@pytest.fixture()
def sample_sessions(db_session, profile) -> list[TimeSession]:
    """Create sample completed sessions across different weeks and categories."""
    now = datetime.now(UTC)
    sessions = []

    # Week 1 (3 weeks ago) — applying
    s1 = TimeSession(
        profile_id=profile.id,
        activity_name="Submit application to Acme Corp",
        category="applying",
        started_at=now - timedelta(weeks=3, hours=2),
        stopped_at=now - timedelta(weeks=3),
        duration_seconds=7200.0,  # 2 hours
    )
    sessions.append(s1)

    # Week 2 (2 weeks ago) — researching + prepping
    s2 = TimeSession(
        profile_id=profile.id,
        activity_name="Research Stripe engineering",
        category="researching",
        started_at=now - timedelta(weeks=2, hours=1),
        stopped_at=now - timedelta(weeks=2),
        duration_seconds=3600.0,  # 1 hour
    )
    sessions.append(s2)

    s3 = TimeSession(
        profile_id=profile.id,
        activity_name="Interview prep for Google TPM",
        category="prepping",
        started_at=now - timedelta(weeks=2, hours=3),
        stopped_at=now - timedelta(weeks=2, hours=1),
        duration_seconds=7200.0,  # 2 hours
    )
    sessions.append(s3)

    # Week 3 (1 week ago) — networking + learning
    s4 = TimeSession(
        profile_id=profile.id,
        activity_name="Coffee chat with recruiter",
        category="networking",
        started_at=now - timedelta(weeks=1, hours=1),
        stopped_at=now - timedelta(weeks=1),
        duration_seconds=3600.0,  # 1 hour
    )
    sessions.append(s4)

    s5 = TimeSession(
        profile_id=profile.id,
        activity_name="Kubernetes course on Udemy",
        category="learning",
        started_at=now - timedelta(weeks=1, hours=2),
        stopped_at=now - timedelta(weeks=1, hours=1),
        duration_seconds=3600.0,  # 1 hour
    )
    sessions.append(s5)

    # Week 4 (current week) — applying
    s6 = TimeSession(
        profile_id=profile.id,
        activity_name="Tailoring CV for startup role",
        category="applying",
        started_at=now - timedelta(hours=3),
        stopped_at=now - timedelta(hours=1),
        duration_seconds=7200.0,  # 2 hours
    )
    sessions.append(s6)

    for s in sessions:
        db_session.add(s)
    db_session.commit()
    for s in sessions:
        db_session.refresh(s)
    return sessions


# ===========================================================================
# VAL-TIME-001: Track job search activities
# ===========================================================================


class TestStartSession:
    """Starting a tracked session creates a TimingsApp entry."""

    def test_start_session_creates_local_record(self, db_session, profile):
        """Starting a session creates a time_session record."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Apply to Google",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload)

        assert session_record.id is not None
        assert session_record.profile_id == profile.id
        assert session_record.activity_name == "Apply to Google"
        assert session_record.category == "applying"
        assert session_record.started_at is not None
        assert session_record.stopped_at is None
        assert session_record.duration_seconds is None

    def test_start_session_with_timingsapp(
        self, db_session, profile, timingsapp_config, mock_timingsapp_client
    ):
        """Starting a session also starts a timer in TimingsApp."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Research companies",
            category=ActivityCategory.researching,
        )
        session_record = start_session(db_session, payload, client=mock_timingsapp_client)

        assert session_record.timingsapp_entry_id == "/time-entries/42"
        assert session_record.timingsapp_project == "Job Search ▸ Researching"

        mock_timingsapp_client.start_timer.assert_called_once()
        call_kwargs = mock_timingsapp_client.start_timer.call_args
        assert call_kwargs.kwargs["project"] == "Job Search ▸ Researching"
        assert call_kwargs.kwargs["title"] == "Research companies"

    def test_start_session_timingsapp_failure_still_creates_local(
        self, db_session, profile, timingsapp_config, mock_timingsapp_client
    ):
        """TimingsApp API failure doesn't prevent local session creation."""
        mock_timingsapp_client.start_timer.side_effect = TimingsAppAPIError("Server error", 500)
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Submit application",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload, client=mock_timingsapp_client)

        assert session_record.id is not None
        assert session_record.timingsapp_entry_id is None

    def test_start_session_without_timingsapp_config(self, db_session, profile):
        """Session works fine without TimingsApp configuration."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="CV tailoring",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload)

        assert session_record.id is not None
        assert session_record.timingsapp_entry_id is None

    def test_start_session_with_notes(self, db_session, profile):
        """Session can include notes."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Interview prep",
            category=ActivityCategory.prepping,
            notes="Focus on system design questions",
        )
        session_record = start_session(db_session, payload)
        assert session_record.notes == "Focus on system design questions"

    def test_concurrent_session_blocked(self, db_session, profile, mock_timingsapp_client):
        """Starting a second session while one is running raises ConcurrentSessionError."""
        # Start first session
        payload1 = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="First session",
        )
        start_session(db_session, payload1, client=mock_timingsapp_client)

        # Try to start second session - should fail
        payload2 = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Second session",
        )
        with pytest.raises(ConcurrentSessionError):
            start_session(db_session, payload2, client=mock_timingsapp_client)

    def test_concurrent_session_after_stop_ok(self, db_session, profile, mock_timingsapp_client):
        """Starting a new session after stopping the running one succeeds."""
        # Start and stop first session
        payload1 = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="First session",
        )
        session1 = start_session(db_session, payload1, client=mock_timingsapp_client)
        stop_session(db_session, session1.id, profile_id=profile.id, client=mock_timingsapp_client)

        # Start second session - should succeed
        payload2 = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Second session",
        )
        session2 = start_session(db_session, payload2, client=mock_timingsapp_client)
        assert session2.activity_name == "Second session"

    def test_concurrent_session_different_profiles_ok(
        self, db_session, profile, profile_b, mock_timingsapp_client
    ):
        """Different profiles can have concurrent running sessions."""
        payload1 = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Profile A session",
        )
        start_session(db_session, payload1, client=mock_timingsapp_client)

        # Profile B should be able to start its own session
        payload2 = TimeSessionCreate(
            profile_id=profile_b.id,
            activity_name="Profile B session",
        )
        session2 = start_session(db_session, payload2, client=mock_timingsapp_client)
        assert session2.activity_name == "Profile B session"


class TestStopSession:
    """Stopping a tracked session sets duration and timestamps."""

    def test_stop_session_sets_duration(self, db_session, profile):
        """Stopping a session computes and stores the duration."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Job search",
            category=ActivityCategory.researching,
        )
        session_record = start_session(db_session, payload)

        stopped = stop_session(db_session, session_record.id, profile_id=profile.id)

        assert stopped.stopped_at is not None
        assert stopped.duration_seconds is not None
        assert stopped.duration_seconds >= 0

    def test_stop_session_with_notes(self, db_session, profile):
        """Stopping a session can add notes."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Networking",
            category=ActivityCategory.networking,
        )
        session_record = start_session(db_session, payload)

        stopped = stop_session(
            db_session,
            session_record.id,
            profile_id=profile.id,
            notes="Great chat!",
        )

        assert "Great chat!" in stopped.notes

    def test_stop_session_with_timingsapp(
        self, db_session, profile, timingsapp_config, mock_timingsapp_client
    ):
        """Stopping a session also stops the timer in TimingsApp."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Study",
            category=ActivityCategory.learning,
        )
        session_record = start_session(db_session, payload, client=mock_timingsapp_client)

        stop_session(
            db_session,
            session_record.id,
            profile_id=profile.id,
            client=mock_timingsapp_client,
        )

        mock_timingsapp_client.stop_timer.assert_called_once()

    def test_stop_nonexistent_session_raises(self, db_session, profile):
        """Stopping a non-existent session raises error."""
        with pytest.raises(TimeSessionNotFoundError):
            stop_session(db_session, 99999, profile_id=profile.id)

    def test_stop_already_stopped_raises(self, db_session, profile):
        """Stopping an already-stopped session raises error."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Test",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload)
        stop_session(db_session, session_record.id, profile_id=profile.id)

        with pytest.raises(TimeSessionAlreadyStoppedError):
            stop_session(db_session, session_record.id, profile_id=profile.id)


# ===========================================================================
# VAL-TIME-002: Activity categorization
# ===========================================================================


class TestAutoCategorization:
    """Categories auto-assigned from context when not provided."""

    def test_applying_category_detected(self):
        """'Apply' and 'submit application' map to applying."""
        assert auto_categorize("Submit application to Google") == "applying"
        assert auto_categorize("Apply for senior role") == "applying"
        assert auto_categorize("Writing cover letter") == "applying"
        assert auto_categorize("Tailoring CV") == "applying"

    def test_researching_category_detected(self):
        """'Research' and 'search' keywords map to researching."""
        assert auto_categorize("Research Stripe engineering culture") == "researching"
        assert auto_categorize("Browse companies in Frankfurt") == "researching"
        assert auto_categorize("Search for startup jobs") == "researching"

    def test_prepping_category_detected(self):
        """'Interview prep' and 'practice' map to prepping."""
        assert auto_categorize("Interview prep for Amazon") == "prepping"
        assert auto_categorize("Practice STAR stories") == "prepping"
        assert auto_categorize("Mock interview session") == "prepping"

    def test_networking_category_detected(self):
        """'Network', 'meetup', 'connect' map to networking."""
        assert auto_categorize("LinkedIn networking") == "networking"
        assert auto_categorize("Attend tech meetup") == "networking"
        assert auto_categorize("Connect with recruiter") == "networking"

    def test_learning_category_detected(self):
        """'Learn', 'course', 'study' map to learning."""
        assert auto_categorize("Learn Kubernetes basics") == "learning"
        assert auto_categorize("Udemy course on React") == "learning"
        assert auto_categorize("Study system design") == "learning"

    def test_default_category_is_researching(self):
        """Ambiguous text defaults to 'researching'."""
        assert auto_categorize("General task") == "researching"

    def test_notes_contribute_to_categorization(self):
        """Notes text also helps determine category."""
        assert auto_categorize("Session", "interview practice") == "prepping"

    def test_auto_categorize_on_session_creation(self, db_session, profile):
        """Session creation without category uses auto-categorization."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Submit application to Stripe",
            # No category provided
        )
        session_record = start_session(db_session, payload)
        assert session_record.category == "applying"

    def test_explicit_category_overrides_auto(self, db_session, profile):
        """Explicitly provided category is used even if auto would differ."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Submit application",
            category=ActivityCategory.learning,  # Override
        )
        session_record = start_session(db_session, payload)
        assert session_record.category == "learning"


# ===========================================================================
# VAL-TIME-003: Time analytics in dashboard
# ===========================================================================


class TestTimeAnalytics:
    """Dashboard shows total hours, category breakdown, 4-week trend."""

    def test_analytics_total_hours(self, db_session, profile, sample_sessions):
        """Total hours computed from all completed sessions."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)

        # Sample sessions total: 2+1+2+1+1+2 = 9 hours = 32400 seconds
        expected_hours = 9.0
        assert analytics.total_hours == expected_hours

    def test_analytics_total_sessions(self, db_session, profile, sample_sessions):
        """Total session count is correct."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)
        assert analytics.total_sessions == 6

    def test_analytics_category_breakdown(self, db_session, profile, sample_sessions):
        """Category breakdown shows hours and percentages per category."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)

        # Build a lookup
        by_cat = {cb.category: cb for cb in analytics.category_breakdown}

        # applying: 2+2 = 4 hours
        assert by_cat["applying"].total_hours == 4.0
        assert by_cat["applying"].session_count == 2

        # researching: 1 hour
        assert by_cat["researching"].total_hours == 1.0
        assert by_cat["researching"].session_count == 1

        # prepping: 2 hours
        assert by_cat["prepping"].total_hours == 2.0
        assert by_cat["prepping"].session_count == 1

        # networking: 1 hour
        assert by_cat["networking"].total_hours == 1.0
        assert by_cat["networking"].session_count == 1

        # learning: 1 hour
        assert by_cat["learning"].total_hours == 1.0
        assert by_cat["learning"].session_count == 1

    def test_analytics_category_percentages_sum_to_100(self, db_session, profile, sample_sessions):
        """Category percentages should roughly sum to 100."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)
        total_pct = sum(cb.percentage for cb in analytics.category_breakdown)
        assert 99.0 <= total_pct <= 101.0  # allow rounding

    def test_analytics_weekly_trend_has_4_weeks(self, db_session, profile, sample_sessions):
        """Weekly trend returns 4 data points."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)
        assert len(analytics.weekly_trend) == 4

    def test_analytics_weekly_trend_has_category_breakdown(
        self, db_session, profile, sample_sessions
    ):
        """Each week in the trend includes category-level hours."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)
        for week_data in analytics.weekly_trend:
            assert isinstance(week_data.category_hours, dict)
            # All categories should be present
            assert "applying" in week_data.category_hours
            assert "researching" in week_data.category_hours
            assert "prepping" in week_data.category_hours
            assert "networking" in week_data.category_hours
            assert "learning" in week_data.category_hours

    def test_analytics_avg_daily_hours(self, db_session, profile, sample_sessions):
        """Average daily hours calculated correctly."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)
        # 9 hours over 28 days = ~0.32
        expected = round(9.0 / 28, 2)
        assert analytics.avg_daily_hours == expected

    def test_analytics_empty_data(self, db_session, profile):
        """Empty data returns zeros, no errors."""
        analytics = get_time_analytics(db_session, profile_id=profile.id)
        assert analytics.total_hours == 0.0
        assert analytics.total_sessions == 0
        assert analytics.avg_daily_hours == 0.0
        assert len(analytics.category_breakdown) == 5
        assert all(cb.total_hours == 0.0 for cb in analytics.category_breakdown)
        assert len(analytics.weekly_trend) == 4

    def test_analytics_includes_running_sessions(self, db_session, profile):
        """Running (unstopped) sessions count toward analytics."""
        # Create a running session started 1 hour ago
        s = TimeSession(
            profile_id=profile.id,
            activity_name="Active research",
            category="researching",
            started_at=datetime.now(UTC) - timedelta(hours=1),
            stopped_at=None,
            duration_seconds=None,
        )
        db_session.add(s)
        db_session.commit()

        analytics = get_time_analytics(db_session, profile_id=profile.id)
        assert analytics.total_hours >= 0.9  # At least ~1 hour
        assert analytics.total_sessions == 1


# ===========================================================================
# Session CRUD operations
# ===========================================================================


class TestSessionCRUD:
    """Session listing, retrieval, updating."""

    def test_list_sessions(self, db_session, profile, sample_sessions):
        """List returns sessions ordered by most recent first."""
        sessions, total = list_sessions(db_session, profile_id=profile.id)
        assert total == 6
        assert len(sessions) == 6
        # Most recent first
        assert sessions[0].activity_name == "Tailoring CV for startup role"

    def test_list_sessions_filter_by_category(self, db_session, profile, sample_sessions):
        """Filter by category works correctly."""
        sessions, total = list_sessions(db_session, profile_id=profile.id, category="applying")
        assert total == 2
        assert all(s.category == "applying" for s in sessions)

    def test_list_sessions_with_pagination(self, db_session, profile, sample_sessions):
        """Pagination works correctly."""
        sessions, total = list_sessions(db_session, profile_id=profile.id, limit=2, offset=0)
        assert total == 6
        assert len(sessions) == 2

    def test_get_session(self, db_session, profile, sample_sessions):
        """Get a specific session by ID."""
        session_record = get_session(db_session, sample_sessions[0].id, profile_id=profile.id)
        assert session_record.activity_name == sample_sessions[0].activity_name

    def test_get_nonexistent_session_raises(self, db_session, profile):
        """Getting a non-existent session raises error."""
        with pytest.raises(TimeSessionNotFoundError):
            get_session(db_session, 99999, profile_id=profile.id)

    def test_get_running_session(self, db_session, profile):
        """Get the currently running session."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Active task",
            category=ActivityCategory.applying,
        )
        started = start_session(db_session, payload)

        running = get_running_session(db_session, profile_id=profile.id)
        assert running is not None
        assert running.id == started.id
        assert running.stopped_at is None

    def test_no_running_session(self, db_session, profile):
        """Returns None when no session is running."""
        running = get_running_session(db_session, profile_id=profile.id)
        assert running is None

    def test_update_session(self, db_session, profile):
        """Update session fields."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Original name",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload)

        updated = update_session(
            db_session,
            session_record.id,
            TimeSessionUpdate(
                activity_name="Updated name",
                category=ActivityCategory.prepping,
            ),
            profile_id=profile.id,
        )

        assert updated.activity_name == "Updated name"
        assert updated.category == "prepping"


# ===========================================================================
# Profile isolation
# ===========================================================================


class TestProfileIsolation:
    """Profile B cannot access Profile A's sessions."""

    def test_profile_b_cannot_read_profile_a_session(self, db_session, profile, profile_b):
        """Profile B cannot read Profile A's sessions."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Profile A task",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload)

        with pytest.raises(TimeSessionNotFoundError):
            get_session(db_session, session_record.id, profile_id=profile_b.id)

    def test_profile_b_cannot_stop_profile_a_session(self, db_session, profile, profile_b):
        """Profile B cannot stop Profile A's sessions."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Profile A task",
            category=ActivityCategory.applying,
        )
        session_record = start_session(db_session, payload)

        with pytest.raises(TimeSessionNotFoundError):
            stop_session(db_session, session_record.id, profile_id=profile_b.id)

    def test_profile_b_cannot_list_profile_a_sessions(self, db_session, profile, profile_b):
        """Profile B cannot see Profile A's sessions in list."""
        payload = TimeSessionCreate(
            profile_id=profile.id,
            activity_name="Profile A task",
            category=ActivityCategory.applying,
        )
        start_session(db_session, payload)

        sessions, total = list_sessions(db_session, profile_id=profile_b.id)
        assert total == 0
        assert len(sessions) == 0

    def test_analytics_scoped_by_profile(self, db_session, profile, profile_b, sample_sessions):
        """Analytics data is scoped to the requesting profile."""
        analytics_a = get_time_analytics(db_session, profile_id=profile.id)
        analytics_b = get_time_analytics(db_session, profile_id=profile_b.id)

        assert analytics_a.total_hours > 0
        assert analytics_b.total_hours == 0.0


# ===========================================================================
# API endpoint tests
# ===========================================================================


class TestTimingsAppAPI:
    """Tests for the TimingsApp API routes."""

    def test_create_session_api(self, db_session, profile):
        """POST /api/timingsapp/sessions creates a session."""
        resp = api_client.post(
            "/api/timingsapp/sessions",
            json={
                "profile_id": profile.id,
                "activity_name": "API test: Apply to company",
                "category": "applying",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["activity_name"] == "API test: Apply to company"
        assert data["category"] == "applying"
        assert data["stopped_at"] is None
        assert data["id"] is not None

    def test_create_session_auto_category(self, db_session, profile):
        """POST without category auto-categorizes."""
        resp = api_client.post(
            "/api/timingsapp/sessions",
            json={
                "profile_id": profile.id,
                "activity_name": "Interview prep for Google",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "prepping"

    def test_stop_session_api(self, db_session, profile):
        """PUT /api/timingsapp/sessions/{id}/stop stops the session."""
        # Create
        resp = api_client.post(
            "/api/timingsapp/sessions",
            json={
                "profile_id": profile.id,
                "activity_name": "Test session",
                "category": "applying",
            },
        )
        session_id = resp.json()["id"]

        # Stop
        resp = api_client.put(
            f"/api/timingsapp/sessions/{session_id}/stop?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stopped_at"] is not None
        assert data["duration_seconds"] is not None

    def test_stop_nonexistent_session_api(self, db_session, profile):
        """PUT stop on non-existent session returns 404."""
        resp = api_client.put(
            f"/api/timingsapp/sessions/99999/stop?profile_id={profile.id}",
        )
        assert resp.status_code == 404

    def test_stop_already_stopped_api(self, db_session, profile):
        """PUT stop on already-stopped session returns 400."""
        resp = api_client.post(
            "/api/timingsapp/sessions",
            json={
                "profile_id": profile.id,
                "activity_name": "Test",
                "category": "applying",
            },
        )
        session_id = resp.json()["id"]

        api_client.put(
            f"/api/timingsapp/sessions/{session_id}/stop?profile_id={profile.id}",
        )
        resp = api_client.put(
            f"/api/timingsapp/sessions/{session_id}/stop?profile_id={profile.id}",
        )
        assert resp.status_code == 400

    def test_list_sessions_api(self, db_session, profile, sample_sessions):
        """GET /api/timingsapp/sessions returns paginated list."""
        resp = api_client.get(
            f"/api/timingsapp/sessions?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["sessions"]) == 6

    def test_list_sessions_filter_category(self, db_session, profile, sample_sessions):
        """GET sessions with category filter works."""
        resp = api_client.get(
            f"/api/timingsapp/sessions?profile_id={profile.id}&category=applying",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(s["category"] == "applying" for s in data["sessions"])

    def test_get_session_api(self, db_session, profile, sample_sessions):
        """GET /api/timingsapp/sessions/{id} returns session details."""
        session_id = sample_sessions[0].id
        resp = api_client.get(
            f"/api/timingsapp/sessions/{session_id}?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id

    def test_get_running_session_api(self, db_session, profile):
        """GET /api/timingsapp/sessions/running returns active session."""
        # Create a running session
        api_client.post(
            "/api/timingsapp/sessions",
            json={
                "profile_id": profile.id,
                "activity_name": "Running task",
                "category": "applying",
            },
        )

        resp = api_client.get(
            f"/api/timingsapp/sessions/running?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert data["stopped_at"] is None

    def test_get_running_session_none(self, db_session, profile):
        """GET running returns null when no active session."""
        resp = api_client.get(
            f"/api/timingsapp/sessions/running?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        # null response
        assert resp.json() is None

    def test_update_session_api(self, db_session, profile):
        """PATCH /api/timingsapp/sessions/{id} updates fields."""
        resp = api_client.post(
            "/api/timingsapp/sessions",
            json={
                "profile_id": profile.id,
                "activity_name": "Original",
                "category": "applying",
            },
        )
        session_id = resp.json()["id"]

        resp = api_client.patch(
            f"/api/timingsapp/sessions/{session_id}?profile_id={profile.id}",
            json={"activity_name": "Updated", "category": "prepping"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["activity_name"] == "Updated"
        assert data["category"] == "prepping"

    def test_analytics_api(self, db_session, profile, sample_sessions):
        """GET /api/timingsapp/analytics returns analytics data."""
        resp = api_client.get(
            f"/api/timingsapp/analytics?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hours"] == 9.0
        assert data["total_sessions"] == 6
        assert len(data["category_breakdown"]) == 5
        assert len(data["weekly_trend"]) == 4
        assert data["avg_daily_hours"] > 0

    def test_analytics_empty_api(self, db_session, profile):
        """GET analytics with no data returns zeros."""
        resp = api_client.get(
            f"/api/timingsapp/analytics?profile_id={profile.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hours"] == 0.0
        assert data["total_sessions"] == 0

    def test_test_connection_not_configured(self, db_session):
        """POST /api/timingsapp/test without config returns failure."""
        resp = api_client.post("/api/timingsapp/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_test_connection_configured(self, db_session, timingsapp_config):
        """POST /api/timingsapp/test with mock returns success."""
        with patch("career_os.services.timingsapp.TimingsAppClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.test_connection.return_value = True

            resp = api_client.post("/api/timingsapp/test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True


# ===========================================================================
# TimingsApp client unit tests
# ===========================================================================


class TestTimingsAppClient:
    """Unit tests for the TimingsApp API client."""

    def test_start_timer_formats_request(self):
        """Client formats start_timer request correctly."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data": {"self": "/time-entries/1", "is_running": true}}'
            mock_resp.json.return_value = {"data": {"self": "/time-entries/1", "is_running": True}}
            mock_req.return_value = mock_resp

            client = TimingsAppClient("test-token")
            result = client.start_timer(
                project="Job Search ▸ Applying",
                title="Test Activity",
                notes="Some notes",
            )

            assert result["self"] == "/time-entries/1"
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            assert call_args.kwargs["json"]["project"] == "Job Search ▸ Applying"
            assert call_args.kwargs["json"]["title"] == "Test Activity"
            assert call_args.kwargs["json"]["notes"] == "Some notes"

    def test_stop_timer(self):
        """Client calls stop timer endpoint."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data": {"self": "/time-entries/1", "is_running": false}}'
            mock_resp.json.return_value = {"data": {"self": "/time-entries/1", "is_running": False}}
            mock_req.return_value = mock_resp

            client = TimingsAppClient("test-token")
            result = client.stop_timer()

            assert result["is_running"] is False
            call_args = mock_req.call_args
            assert call_args.args[0] == "PUT"

    def test_create_time_entry(self):
        """Client creates a completed time entry."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data": {"self": "/time-entries/2"}}'
            mock_resp.json.return_value = {"data": {"self": "/time-entries/2"}}
            mock_req.return_value = mock_resp

            client = TimingsAppClient("test-token")
            now = datetime.now(UTC)
            result = client.create_time_entry(
                project="Job Search",
                title="Completed task",
                start_date=now - timedelta(hours=1),
                end_date=now,
            )

            assert result["self"] == "/time-entries/2"
            call_args = mock_req.call_args
            body = call_args.kwargs["json"]
            assert "start_date" in body
            assert "end_date" in body

    def test_unauthorized_raises_error(self):
        """401 response raises TimingsAppAPIError."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_req.return_value = mock_resp

            client = TimingsAppClient("bad-token")
            with pytest.raises(TimingsAppAPIError) as exc_info:
                client.start_timer(project="Test", title="Test")
            assert exc_info.value.status_code == 401

    def test_rate_limit_raises_error(self):
        """429 response raises TimingsAppAPIError."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.text = "Too Many Requests"
            mock_req.return_value = mock_resp

            client = TimingsAppClient("test-token")
            with pytest.raises(TimingsAppAPIError) as exc_info:
                client.start_timer(project="Test", title="Test")
            assert exc_info.value.status_code == 429

    def test_custom_base_url(self):
        """Client uses custom base URL when provided."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data": []}'
            mock_resp.json.return_value = {"data": []}
            mock_req.return_value = mock_resp

            client = TimingsAppClient("test-token", base_url="http://custom:8000/api/v1")
            client.list_time_entries()

            call_args = mock_req.call_args
            assert "http://custom:8000/api/v1" in call_args.args[1]

    def test_test_connection_success(self):
        """test_connection returns True on successful project list."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data": [{"self": "/projects/1"}]}'
            mock_resp.json.return_value = {"data": [{"self": "/projects/1"}]}
            mock_req.return_value = mock_resp

            client = TimingsAppClient("good-token")
            assert client.test_connection() is True

    def test_test_connection_failure(self):
        """test_connection returns False on API error."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_req.return_value = mock_resp

            client = TimingsAppClient("bad-token")
            assert client.test_connection() is False

    def test_get_running_timer_none(self):
        """get_running_timer returns None when 404."""
        with patch("career_os.services.timingsapp_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.text = "Not Found"
            mock_req.return_value = mock_resp

            client = TimingsAppClient("test-token")
            result = client.get_running_timer()
            assert result is None


# ===========================================================================
# Connection test
# ===========================================================================


class TestConnectionTest:
    """Test TimingsApp connection testing."""

    def test_not_configured_returns_false(self, db_session):
        """Not configured integration returns failure."""
        success, msg = check_timingsapp_connection(db_session)
        assert success is False

    def test_configured_and_connected(self, db_session, timingsapp_config):
        """Configured integration with mocked API returns success."""
        with patch("career_os.services.timingsapp.TimingsAppClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.test_connection.return_value = True

            success, msg = check_timingsapp_connection(db_session)
            assert success is True
            assert "successful" in msg.lower()

    def test_configured_but_api_fails(self, db_session, timingsapp_config):
        """Configured integration with API failure returns failure."""
        with patch("career_os.services.timingsapp.TimingsAppClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.test_connection.return_value = False

            success, msg = check_timingsapp_connection(db_session)
            assert success is False
