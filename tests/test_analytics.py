"""Tests for analytics API endpoints.

Covers:
- VAL-ANALYTICS-001: Conversion funnel with counts and stage-to-stage percentages
- VAL-ANALYTICS-002: Response rate metric, N/A with zero data
- VAL-ANALYTICS-003: Time-in-stage metrics derived from activity_log timestamps
- VAL-ANALYTICS-004: Applications over time (weekly counts)
- VAL-ANALYTICS-005: Score distribution histogram
- VAL-ANALYTICS-006: Analytics with empty data (graceful empty states)
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import ActivityLog, Application, Profile

# ---------------------------------------------------------------------------
# Test database setup (matches project convention from test_pipeline_api.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test.

    Uses a single shared connection so both the test and the app see the
    same in-memory tables.
    """
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

    # Seed default profile
    profile = Profile(id=1, name="Test User", email="test@example.com", location="Frankfurt")
    session.add(profile)
    session.commit()

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


@pytest.fixture
def client(db_session):
    """FastAPI test client — depends on db_session so overrides are in place."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(
    db: Session,
    *,
    company: str = "Acme Corp",
    role: str = "Engineer",
    status: str = "discovered",
    fit_score: float | None = None,
    created_at: datetime | None = None,
    date_applied: datetime | None = None,
) -> Application:
    """Create a test application."""
    app_obj = Application(
        profile_id=1,
        company=company,
        role=role,
        status=status,
        fit_score=fit_score,
        created_at=created_at or datetime.now(UTC),
        updated_at=created_at or datetime.now(UTC),
        date_applied=date_applied,
    )
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_obj


def _make_status_change_log(
    db: Session,
    *,
    application_id: int,
    from_status: str,
    to_status: str,
    created_at: datetime,
) -> ActivityLog:
    """Create an activity_log entry for a status transition.

    Uses the ACTUAL persisted format from the applications service:
    action="status_changed", details="Status changed from 'old' to 'new'"
    """
    log = ActivityLog(
        profile_id=1,
        application_id=application_id,
        action="status_changed",
        details=f"Status changed from '{from_status}' to '{to_status}'",
        source="test",
        created_at=created_at,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ===========================================================================
# VAL-ANALYTICS-006: Empty data
# ===========================================================================


class TestEmptyAnalytics:
    """Analytics with zero applications shows graceful empty states."""

    def test_analytics_returns_200_with_empty_data(self, client):
        resp = client.get("/api/analytics?profile_id=1")
        assert resp.status_code == 200

    def test_funnel_empty(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        assert isinstance(funnel, list)
        assert len(funnel) > 0
        for stage in funnel:
            assert stage["count"] == 0
            assert stage["percentage"] == 0

    def test_response_rate_na(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        assert data["response_rate"] is None

    def test_time_in_stage_no_data(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        assert isinstance(stages, list)
        for stage in stages:
            assert stage["avg_days"] is None

    def test_applications_over_time_empty(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        assert data["applications_over_time"] == []

    def test_score_distribution_empty(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        dist = data["score_distribution"]
        assert isinstance(dist, list)
        for bucket in dist:
            assert bucket["count"] == 0

    def test_no_nan_or_undefined(self, client):
        """Ensure no NaN, undefined, or null where numbers expected."""
        resp = client.get("/api/analytics?profile_id=1")
        text = resp.text
        assert "NaN" not in text
        assert "undefined" not in text
        # Parse to verify valid JSON
        data = json.loads(text)
        assert data is not None


# ===========================================================================
# VAL-ANALYTICS-001: Conversion funnel (stage-to-stage percentages)
# ===========================================================================


class TestConversionFunnel:
    """Conversion funnel shows counts per stage with stage-to-stage percentages.

    The percentage for each stage is computed relative to the *previous*
    stage in the funnel (e.g. Applied / Interested), not relative to total.
    For "discovered" (first stage) and "ghosted" (any-source) it is
    count / total.
    """

    def test_funnel_counts_match_data(self, client, db_session):
        _make_app(db_session, status="discovered")
        _make_app(db_session, status="discovered")
        _make_app(db_session, status="applied")
        _make_app(db_session, status="interviewing")

        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_map = {s["stage"]: s for s in funnel}

        assert stage_map["discovered"]["count"] == 2
        assert stage_map["applied"]["count"] == 1
        assert stage_map["interviewing"]["count"] == 1

    def test_funnel_stage_to_stage_percentages(self, client, db_session):
        """Percentages are stage-to-stage, not relative to total.

        Setup: 10 discovered, 5 interested, 4 applied, 2 interviewing, 1 offer
        Expected:
          discovered: 10/22 * 100 = 45.5% (first stage → relative to total)
          interested: 5/10 * 100 = 50.0% (interested / discovered)
          applied: 4/5 * 100 = 80.0% (applied / interested)
          interviewing: 2/4 * 100 = 50.0% (interviewing / applied)
          offer: 1/2 * 100 = 50.0% (offer / interviewing)
        """
        for _ in range(10):
            _make_app(db_session, status="discovered")
        for _ in range(5):
            _make_app(db_session, status="interested")
        for _ in range(4):
            _make_app(db_session, status="applied")
        for _ in range(2):
            _make_app(db_session, status="interviewing")
        _make_app(db_session, status="offer")

        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_map = {s["stage"]: s for s in funnel}

        total = 22
        # discovered: count/total
        assert stage_map["discovered"]["percentage"] == pytest.approx(10 / total * 100, abs=0.1)
        # interested / discovered
        assert stage_map["interested"]["percentage"] == pytest.approx(5 / 10 * 100, abs=0.1)
        # applied / interested
        assert stage_map["applied"]["percentage"] == pytest.approx(4 / 5 * 100, abs=0.1)
        # interviewing / applied
        assert stage_map["interviewing"]["percentage"] == pytest.approx(2 / 4 * 100, abs=0.1)
        # offer / interviewing
        assert stage_map["offer"]["percentage"] == pytest.approx(1 / 2 * 100, abs=0.1)

    def test_funnel_percentage_zero_when_previous_empty(self, client, db_session):
        """Stage-to-stage % is 0 when previous stage has 0 applications.

        E.g. if there are applied apps but no interested apps, the
        applied percentage (applied/interested) should be 0.
        """
        _make_app(db_session, status="discovered")
        _make_app(db_session, status="applied")  # skip interested

        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_map = {s["stage"]: s for s in funnel}

        # applied / interested = 1 / 0 → 0%
        assert stage_map["applied"]["percentage"] == pytest.approx(0.0)

    def test_funnel_ghosted_relative_to_total(self, client, db_session):
        """Ghosted percentage is relative to total, not a specific previous stage."""
        for _ in range(3):
            _make_app(db_session, status="discovered")
        for _ in range(2):
            _make_app(db_session, status="ghosted")

        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_map = {s["stage"]: s for s in funnel}

        total = 5
        assert stage_map["ghosted"]["percentage"] == pytest.approx(2 / total * 100, abs=0.1)

    def test_funnel_rejected_relative_to_offer(self, client, db_session):
        """Rejected percentage is relative to offer stage (rejected comes from offer)."""
        for _ in range(3):
            _make_app(db_session, status="offer")
        for _ in range(2):
            _make_app(db_session, status="rejected")

        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_map = {s["stage"]: s for s in funnel}

        # rejected / offer = 2 / 3
        assert stage_map["rejected"]["percentage"] == pytest.approx(2 / 3 * 100, abs=0.1)

    def test_funnel_includes_all_stages(self, client, db_session):
        """Funnel includes all pipeline stages even if empty."""
        _make_app(db_session, status="discovered")
        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_names = [s["stage"] for s in funnel]
        expected_stages = [
            "discovered",
            "interested",
            "applied",
            "interviewing",
            "offer",
            "accepted",
            "rejected",
            "ghosted",
        ]
        for expected in expected_stages:
            assert expected in stage_names

    def test_funnel_excludes_archived(self, client, db_session):
        """Archived applications should not be counted in the funnel."""
        app_obj = _make_app(db_session, status="discovered")
        app_obj.archived_at = datetime.now(UTC)
        db_session.commit()

        data = client.get("/api/analytics?profile_id=1").json()
        funnel = data["conversion_funnel"]
        stage_map = {s["stage"]: s for s in funnel}
        assert stage_map["discovered"]["count"] == 0


# ===========================================================================
# VAL-ANALYTICS-002: Response rate
# ===========================================================================


class TestResponseRate:
    """Response rate = (interviewing + offer + accepted) / applied_or_further."""

    def test_response_rate_calculated(self, client, db_session):
        # 3 applied, 1 interviewing, 1 offer = 2 responded out of 5 (applied+)
        for _ in range(3):
            _make_app(db_session, status="applied")
        _make_app(db_session, status="interviewing")
        _make_app(db_session, status="offer")

        data = client.get("/api/analytics?profile_id=1").json()
        # 2 progressed beyond applied out of 5 total at applied+
        assert data["response_rate"] == pytest.approx(2 / 5 * 100, abs=0.1)

    def test_response_rate_zero_applied(self, client, db_session):
        """Zero applied applications → N/A."""
        _make_app(db_session, status="discovered")

        data = client.get("/api/analytics?profile_id=1").json()
        assert data["response_rate"] is None

    def test_response_rate_all_responded(self, client, db_session):
        """All applied moved forward → 100%."""
        _make_app(db_session, status="interviewing")
        _make_app(db_session, status="offer")

        data = client.get("/api/analytics?profile_id=1").json()
        assert data["response_rate"] == pytest.approx(100.0, abs=0.1)


# ===========================================================================
# VAL-ANALYTICS-003: Time-in-stage (from activity_log timestamps)
# ===========================================================================


class TestTimeInStage:
    """Average days in each status stage, derived from activity_log transitions."""

    def test_time_in_stage_discovered_uses_created_at(self, client, db_session):
        """Discovered stage falls back to created_at when no log entry exists."""
        now = datetime.now(UTC)
        _make_app(db_session, status="discovered", created_at=now - timedelta(days=10))
        _make_app(db_session, status="discovered", created_at=now - timedelta(days=20))

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        discovered = stage_map["discovered"]
        assert discovered["avg_days"] is not None
        assert discovered["avg_days"] > 0
        # Average of ~10 and ~20 days should be ~15
        assert discovered["avg_days"] == pytest.approx(15.0, abs=1.0)

    def test_time_in_stage_from_activity_log(self, client, db_session):
        """Time-in-stage uses activity_log transition timestamp, not created_at.

        App created 30 days ago, transitioned to 'applied' 5 days ago.
        Time in 'applied' should be ~5 days, NOT ~30 days.
        """
        now = datetime.now(UTC)
        app_obj = _make_app(
            db_session,
            status="applied",
            created_at=now - timedelta(days=30),
        )
        _make_status_change_log(
            db_session,
            application_id=app_obj.id,
            from_status="interested",
            to_status="applied",
            created_at=now - timedelta(days=5),
        )

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        applied = stage_map["applied"]
        assert applied["avg_days"] is not None
        # Should be ~5 days (from transition log), not ~30 (from created_at)
        assert applied["avg_days"] == pytest.approx(5.0, abs=1.0)

    def test_time_in_stage_empty_returns_null(self, client, db_session):
        """Stages with no apps show null avg_days."""
        _make_app(db_session, status="discovered")

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        assert stage_map["applied"]["avg_days"] is None

    def test_time_in_stage_all_stages_present(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_names = [s["stage"] for s in stages]
        expected_stages = [
            "discovered",
            "interested",
            "applied",
            "interviewing",
            "offer",
            "accepted",
            "rejected",
            "ghosted",
        ]
        for expected in expected_stages:
            assert expected in stage_names

    def test_time_in_stage_multiple_transitions(self, client, db_session):
        """When multiple transition logs exist, use the most recent one into current status."""
        now = datetime.now(UTC)
        app_obj = _make_app(
            db_session,
            status="interviewing",
            created_at=now - timedelta(days=60),
        )
        # First transition into interviewing (older)
        _make_status_change_log(
            db_session,
            application_id=app_obj.id,
            from_status="applied",
            to_status="interviewing",
            created_at=now - timedelta(days=3),
        )

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        interviewing = stage_map["interviewing"]
        assert interviewing["avg_days"] is not None
        # Should be ~3 days from the log, not 60 from created_at
        assert interviewing["avg_days"] == pytest.approx(3.0, abs=1.0)

    def test_time_in_stage_no_log_non_discovered_returns_null(self, client, db_session):
        """Non-discovered stage with no activity log entry returns null."""
        now = datetime.now(UTC)
        _make_app(db_session, status="applied", created_at=now - timedelta(days=10))
        # No activity log entry for this app → no transition timestamp

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        # Without activity_log, non-discovered stages should show null
        assert stage_map["applied"]["avg_days"] is None


# ===========================================================================
# VAL-ANALYTICS-004: Applications over time
# ===========================================================================


class TestApplicationsOverTime:
    """Weekly application counts."""

    def test_weekly_counts(self, client, db_session):
        now = datetime.now(UTC)
        for _ in range(3):
            _make_app(db_session, status="discovered", created_at=now)
        for _ in range(2):
            _make_app(db_session, status="discovered", created_at=now - timedelta(days=7))

        data = client.get("/api/analytics?profile_id=1").json()
        weeks = data["applications_over_time"]

        assert len(weeks) >= 2
        total_count = sum(w["count"] for w in weeks)
        assert total_count == 5

    def test_weekly_counts_correct_format(self, client, db_session):
        now = datetime.now(UTC)
        _make_app(db_session, status="applied", created_at=now)

        data = client.get("/api/analytics?profile_id=1").json()
        weeks = data["applications_over_time"]

        assert len(weeks) >= 1
        week = weeks[0]
        assert "week" in week
        assert "count" in week
        assert isinstance(week["count"], int)


# ===========================================================================
# VAL-ANALYTICS-005: Score distribution
# ===========================================================================


class TestScoreDistribution:
    """Histogram of fit scores."""

    def test_score_distribution_populated(self, client, db_session):
        _make_app(db_session, fit_score=8.5)
        _make_app(db_session, fit_score=9.0)
        _make_app(db_session, fit_score=6.0)
        _make_app(db_session, fit_score=3.0)

        data = client.get("/api/analytics?profile_id=1").json()
        dist = data["score_distribution"]

        total = sum(b["count"] for b in dist)
        assert total == 4

    def test_unscored_not_in_distribution(self, client, db_session):
        """Apps without fit_score should not appear in histogram."""
        _make_app(db_session, fit_score=None)
        _make_app(db_session, fit_score=7.0)

        data = client.get("/api/analytics?profile_id=1").json()
        dist = data["score_distribution"]

        total = sum(b["count"] for b in dist)
        assert total == 1

    def test_score_distribution_has_buckets(self, client):
        data = client.get("/api/analytics?profile_id=1").json()
        dist = data["score_distribution"]
        assert len(dist) > 0
        for bucket in dist:
            assert "range" in bucket
            assert "count" in bucket

    def test_score_distribution_buckets_cover_range(self, client):
        """Buckets should cover 0-10 range."""
        data = client.get("/api/analytics?profile_id=1").json()
        dist = data["score_distribution"]
        assert len(dist) >= 5  # At least 5 buckets


# ===========================================================================
# Profile validation
# ===========================================================================


class TestProfileValidation:
    """Analytics requires profile_id."""

    def test_missing_profile_id_returns_422(self, client):
        resp = client.get("/api/analytics")
        assert resp.status_code == 422


# ===========================================================================
# Regression: time-in-stage parses actual persisted format
# ===========================================================================


class TestTimeInStagePersistedFormat:
    """Verify analytics parses the ACTUAL format persisted by the application service.

    The applications service writes:
      action="status_changed", details="Status changed from 'old' to 'new'"

    The analytics service MUST correctly parse this format.
    """

    def test_time_in_stage_with_actual_persisted_format(self, client, db_session):
        """Analytics correctly parses 'Status changed from X to Y' format.

        This is the format actually written by applications.update_application()
        and the CLI.
        """
        now = datetime.now(UTC)
        app_obj = _make_app(
            db_session,
            status="interviewing",
            created_at=now - timedelta(days=60),
        )
        # This uses the actual persisted format via _make_status_change_log
        _make_status_change_log(
            db_session,
            application_id=app_obj.id,
            from_status="applied",
            to_status="interviewing",
            created_at=now - timedelta(days=7),
        )

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        interviewing = stage_map["interviewing"]
        assert interviewing["avg_days"] is not None
        # Should be ~7 days from the transition log, not ~60 from created_at
        assert interviewing["avg_days"] == pytest.approx(7.0, abs=1.0)

    def test_time_in_stage_ignores_old_arrow_format_mismatch(self, client, db_session):
        """If only old arrow format exists, analytics still handles gracefully."""
        now = datetime.now(UTC)
        app_obj = _make_app(
            db_session,
            status="applied",
            created_at=now - timedelta(days=30),
        )
        # Old format that used arrow notation (for backwards compatibility)
        log = ActivityLog(
            profile_id=1,
            application_id=app_obj.id,
            action="status_changed",
            details="Status: interested → applied",
            source="test",
            created_at=now - timedelta(days=10),
        )
        db_session.add(log)
        db_session.commit()

        data = client.get("/api/analytics?profile_id=1").json()
        stages = data["time_in_stage"]
        stage_map = {s["stage"]: s for s in stages}

        # Should pick up the arrow format via backward compat
        applied = stage_map["applied"]
        assert applied["avg_days"] is not None
        assert applied["avg_days"] == pytest.approx(10.0, abs=1.0)
