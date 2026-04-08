"""Tests for Follow-Up engine: CRUD, overdue detection, ghost detection."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile

# ---------------------------------------------------------------------------
# Test database setup (same pattern as test_pipeline_api.py)
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
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    # Seed a default profile
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
    """FastAPI test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_application(
    client: TestClient,
    company: str = "Acme Corp",
    role: str = "Senior Engineer",
    **overrides,
) -> dict:
    """Create an application and return the response dict."""
    payload = {
        "company": company,
        "role": role,
        "profile_id": 1,
        **overrides,
    }
    resp = client.post("/api/applications", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _create_follow_up(
    client: TestClient,
    application_id: int,
    due_date: datetime | None = None,
    follow_up_type: str = "email",
    notes: str | None = None,
) -> dict:
    """Create a follow-up and return the response dict."""
    if due_date is None:
        due_date = datetime.now(UTC) + timedelta(days=3)
    payload = {
        "application_id": application_id,
        "profile_id": 1,
        "due_date": due_date.isoformat(),
        "follow_up_type": follow_up_type,
        "notes": notes,
    }
    resp = client.post("/api/follow-ups", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _update_status(client: TestClient, app_id: int, status: str) -> dict:
    """Update application status via PATCH."""
    resp = client.patch(f"/api/applications/{app_id}?profile_id=1", json={"status": status})
    return resp.json()


def _make_ghost_applied(db_session: Session) -> Application:
    """Create an application in 'applied' status 15 days ago (ghost candidate)."""
    app_obj = Application(
        profile_id=1,
        company="Ghost Inc",
        role="Ghost Role",
        status="applied",
        date_applied=datetime.now(UTC) - timedelta(days=15),
        updated_at=datetime.now(UTC) - timedelta(days=15),
    )
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


def _make_ghost_interviewing(db_session: Session) -> Application:
    """Create an application in 'interviewing' status 8 days ago (ghost candidate)."""
    app_obj = Application(
        profile_id=1,
        company="Silent Ltd",
        role="Interviewing Role",
        status="interviewing",
        updated_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


# ---------------------------------------------------------------------------
# Follow-Up CRUD Tests
# ---------------------------------------------------------------------------


class TestCreateFollowUp:
    """POST /api/follow-ups"""

    def test_create_returns_201(self, client):
        app_data = _create_application(client)
        payload = {
            "application_id": app_data["id"],
            "profile_id": 1,
            "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "follow_up_type": "email",
            "notes": "Send follow-up email to recruiter",
        }
        resp = client.post("/api/follow-ups", json=payload)
        assert resp.status_code == 201

    def test_create_returns_follow_up_data(self, client):
        app_data = _create_application(client)
        due = (datetime.now(UTC) + timedelta(days=3)).isoformat()
        payload = {
            "application_id": app_data["id"],
            "profile_id": 1,
            "due_date": due,
            "follow_up_type": "email",
            "notes": "Send follow-up email",
        }
        resp = client.post("/api/follow-ups", json=payload)
        data = resp.json()
        assert data["id"] > 0
        assert data["application_id"] == app_data["id"]
        assert data["follow_up_type"] == "email"
        assert data["notes"] == "Send follow-up email"
        assert data["completed_at"] is None

    def test_create_with_different_types(self, client):
        app_data = _create_application(client)
        for ftype in ["email", "phone", "linkedin", "other"]:
            payload = {
                "application_id": app_data["id"],
                "profile_id": 1,
                "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "follow_up_type": ftype,
            }
            resp = client.post("/api/follow-ups", json=payload)
            assert resp.status_code == 201
            assert resp.json()["follow_up_type"] == ftype

    def test_create_missing_due_date_returns_422(self, client):
        app_data = _create_application(client)
        payload = {
            "application_id": app_data["id"],
            "profile_id": 1,
            "follow_up_type": "email",
        }
        resp = client.post("/api/follow-ups", json=payload)
        assert resp.status_code == 422

    def test_create_missing_type_returns_422(self, client):
        app_data = _create_application(client)
        payload = {
            "application_id": app_data["id"],
            "profile_id": 1,
            "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        }
        resp = client.post("/api/follow-ups", json=payload)
        assert resp.status_code == 422

    def test_create_invalid_application_returns_404(self, client):
        payload = {
            "application_id": 9999,
            "profile_id": 1,
            "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "follow_up_type": "email",
        }
        resp = client.post("/api/follow-ups", json=payload)
        assert resp.status_code == 404

    def test_create_creates_activity_log(self, client):
        app_data = _create_application(client)
        _create_follow_up(client, app_data["id"], notes="Follow up on application")
        # Check activity log on the application detail
        detail = client.get(f"/api/applications/{app_data['id']}?profile_id=1")
        logs = detail.json()["activity_log"]
        assert any(
            "follow" in log["action"].lower() or "follow" in (log["details"] or "").lower()
            for log in logs
        )

    def test_create_includes_application_context(self, client):
        app_data = _create_application(client, company="TestCo", role="Dev")
        fu = _create_follow_up(client, app_data["id"])
        assert fu["application_company"] == "TestCo"
        assert fu["application_role"] == "Dev"


class TestListFollowUps:
    """GET /api/follow-ups"""

    def test_list_empty(self, client):
        resp = client.get("/api/follow-ups?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["follow_ups"] == []
        assert data["total"] == 0

    def test_list_returns_created_follow_ups(self, client):
        app_data = _create_application(client)
        for i in range(2):
            _create_follow_up(
                client,
                app_data["id"],
                due_date=datetime.now(UTC) + timedelta(days=i + 1),
                notes=f"Follow-up #{i + 1}",
            )
        resp = client.get("/api/follow-ups?profile_id=1")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["follow_ups"]) == 2

    def test_list_includes_application_context(self, client):
        app_data = _create_application(client, company="ContextCo", role="PM")
        _create_follow_up(client, app_data["id"])
        resp = client.get("/api/follow-ups?profile_id=1")
        fu = resp.json()["follow_ups"][0]
        assert fu["application_company"] == "ContextCo"
        assert fu["application_role"] == "PM"

    def test_list_overdue_only(self, client):
        app_data = _create_application(client)
        # One overdue
        _create_follow_up(
            client,
            app_data["id"],
            due_date=datetime.now(UTC) - timedelta(days=1),
            notes="Overdue one",
        )
        # One future
        _create_follow_up(
            client,
            app_data["id"],
            due_date=datetime.now(UTC) + timedelta(days=5),
            follow_up_type="phone",
            notes="Future one",
        )
        resp = client.get("/api/follow-ups?profile_id=1&overdue=true")
        data = resp.json()
        assert data["total"] == 1
        assert data["follow_ups"][0]["notes"] == "Overdue one"

    def test_list_excludes_completed_when_overdue(self, client):
        app_data = _create_application(client)
        # Create overdue and complete it
        fu = _create_follow_up(
            client,
            app_data["id"],
            due_date=datetime.now(UTC) - timedelta(days=1),
        )
        client.patch(f"/api/follow-ups/{fu['id']}?profile_id=1", json={"completed": True})

        resp = client.get("/api/follow-ups?profile_id=1&overdue=true")
        data = resp.json()
        assert data["total"] == 0


class TestCompleteFollowUp:
    """PATCH /api/follow-ups/{id}"""

    def test_complete_sets_completed_at(self, client):
        app_data = _create_application(client)
        fu = _create_follow_up(client, app_data["id"])
        resp = client.patch(f"/api/follow-ups/{fu['id']}?profile_id=1", json={"completed": True})
        assert resp.status_code == 200
        assert resp.json()["completed_at"] is not None

    def test_complete_nonexistent_returns_404(self, client):
        resp = client.patch("/api/follow-ups/9999?profile_id=1", json={"completed": True})
        assert resp.status_code == 404

    def test_complete_creates_activity_log(self, client):
        app_data = _create_application(client)
        fu = _create_follow_up(client, app_data["id"])
        client.patch(f"/api/follow-ups/{fu['id']}?profile_id=1", json={"completed": True})

        detail = client.get(f"/api/applications/{app_data['id']}?profile_id=1")
        logs = detail.json()["activity_log"]
        assert any(
            "complet" in (log["details"] or "").lower() or "complet" in log["action"].lower()
            for log in logs
        )


class TestOverdueCount:
    """GET /api/follow-ups/overdue-count"""

    def test_overdue_count_zero(self, client):
        resp = client.get("/api/follow-ups/overdue-count?profile_id=1")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_overdue_count_correct(self, client):
        app_data = _create_application(client)
        # 2 overdue
        for i in range(2):
            _create_follow_up(
                client,
                app_data["id"],
                due_date=datetime.now(UTC) - timedelta(days=i + 1),
            )
        # 1 future
        _create_follow_up(
            client,
            app_data["id"],
            due_date=datetime.now(UTC) + timedelta(days=5),
            follow_up_type="phone",
        )
        resp = client.get("/api/follow-ups/overdue-count?profile_id=1")
        assert resp.json()["count"] == 2

    def test_overdue_count_excludes_completed(self, client):
        app_data = _create_application(client)
        fu = _create_follow_up(
            client,
            app_data["id"],
            due_date=datetime.now(UTC) - timedelta(days=1),
        )
        client.patch(f"/api/follow-ups/{fu['id']}?profile_id=1", json={"completed": True})

        resp = client.get("/api/follow-ups/overdue-count?profile_id=1")
        assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# Ghost Detection Tests
# ---------------------------------------------------------------------------


class TestGhostDetection:
    """GET /api/applications?ghost_alert=true"""

    def test_ghost_alert_applied_14d(self, client, db_session):
        ghost = _make_ghost_applied(db_session)
        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        assert resp.status_code == 200
        ghost_ids = [a["id"] for a in resp.json()["applications"]]
        assert ghost.id in ghost_ids

    def test_ghost_alert_interviewing_7d(self, client, db_session):
        ghost = _make_ghost_interviewing(db_session)
        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        ghost_ids = [a["id"] for a in resp.json()["applications"]]
        assert ghost.id in ghost_ids

    def test_ghost_alert_excludes_recent_applied(self, client, db_session):
        # Recent applied (5 days) — not a ghost
        recent = Application(
            profile_id=1,
            company="Recent Co",
            role="Role",
            status="applied",
            date_applied=datetime.now(UTC) - timedelta(days=5),
            updated_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(recent)
        db_session.commit()
        db_session.refresh(recent)

        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        ghost_ids = [a["id"] for a in resp.json()["applications"]]
        assert recent.id not in ghost_ids

    def test_ghost_alert_excludes_non_applied_non_interviewing(self, client, db_session):
        old_app = Application(
            profile_id=1,
            company="Old Discovery",
            role="Some Role",
            status="discovered",
            updated_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(old_app)
        db_session.commit()
        db_session.refresh(old_app)

        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        ghost_ids = [a["id"] for a in resp.json()["applications"]]
        assert old_app.id not in ghost_ids

    def test_ghost_response_includes_ghost_flag(self, client, db_session):
        _make_ghost_applied(db_session)
        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        for app_data in resp.json()["applications"]:
            assert "is_ghost" in app_data
            assert app_data["is_ghost"] is True

    def test_ghost_alert_empty_when_no_ghosts(self, client):
        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        data = resp.json()
        assert data["total"] == 0
        assert data["applications"] == []

    def test_ghost_detection_configurable_thresholds(self, client, db_session):
        # 10 days old in applied — NOT ghost with default 14d, IS ghost with 7d
        app_10d = Application(
            profile_id=1,
            company="Ten Day Co",
            role="Role",
            status="applied",
            date_applied=datetime.now(UTC) - timedelta(days=10),
            updated_at=datetime.now(UTC) - timedelta(days=10),
        )
        db_session.add(app_10d)
        db_session.commit()
        db_session.refresh(app_10d)

        # Default threshold
        resp = client.get("/api/applications?profile_id=1&ghost_alert=true")
        ghost_ids = [a["id"] for a in resp.json()["applications"]]
        assert app_10d.id not in ghost_ids

        # Custom threshold
        resp = client.get("/api/applications?profile_id=1&ghost_alert=true&applied_threshold=7")
        ghost_ids = [a["id"] for a in resp.json()["applications"]]
        assert app_10d.id in ghost_ids


class TestApplicationDetailFollowUps:
    """Verify follow-ups appear in application detail."""

    def test_detail_includes_follow_ups(self, client):
        app_data = _create_application(client)
        _create_follow_up(client, app_data["id"], notes="Check in with recruiter")
        resp = client.get(f"/api/applications/{app_data['id']}?profile_id=1")
        data = resp.json()
        assert "follow_ups" in data
        assert len(data["follow_ups"]) == 1
        assert data["follow_ups"][0]["follow_up_type"] == "email"
        assert data["follow_ups"][0]["notes"] == "Check in with recruiter"


class TestApplicationListGhostFlag:
    """Regular application list includes ghost flag for ghost candidates."""

    def test_list_includes_is_ghost_field(self, client, db_session):
        _make_ghost_applied(db_session)
        _create_application(client)
        resp = client.get("/api/applications?profile_id=1")
        for app_data in resp.json()["applications"]:
            assert "is_ghost" in app_data

    def test_ghost_flag_true_for_ghost_app(self, client, db_session):
        ghost = _make_ghost_applied(db_session)
        resp = client.get("/api/applications?profile_id=1")
        ghost_app = next(a for a in resp.json()["applications"] if a["id"] == ghost.id)
        assert ghost_app["is_ghost"] is True

    def test_ghost_flag_false_for_recent_app(self, client):
        app_data = _create_application(client)
        resp = client.get("/api/applications?profile_id=1")
        recent_app = next(a for a in resp.json()["applications"] if a["id"] == app_data["id"])
        assert recent_app["is_ghost"] is False
