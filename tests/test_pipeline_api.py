"""Tests for the Pipeline CRUD API (applications endpoints)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import ActivityLog, Application, FollowUp, Profile

# ---------------------------------------------------------------------------
# Test database setup
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

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Use a single connection for tests so in-memory db is shared
    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    # Seed a default profile
    profile = Profile(id=1, name="Test User", email="test@example.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    def override_get_db():
        yield session

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
# Helper
# ---------------------------------------------------------------------------


def _create_app(client: TestClient, **overrides) -> dict:
    """Helper to create an application with defaults."""
    payload = {
        "company": "Acme Corp",
        "role": "Senior Engineer",
        "profile_id": 1,
        **overrides,
    }
    resp = client.post("/api/applications", json=payload)
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/applications — Create
# ---------------------------------------------------------------------------


class TestCreateApplication:
    """Tests for POST /api/applications."""

    def test_create_returns_201(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"company": "Acme Corp", "role": "Senior Engineer", "profile_id": 1},
        )
        assert resp.status_code == 201

    def test_create_returns_application(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"company": "Acme Corp", "role": "Senior Engineer", "profile_id": 1},
        )
        data = resp.json()
        assert data["company"] == "Acme Corp"
        assert data["role"] == "Senior Engineer"
        assert data["status"] == "discovered"
        assert data["id"] is not None

    def test_create_with_all_fields(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={
                "company": "Acme Corp",
                "role": "Senior Engineer",
                "profile_id": 1,
                "url": "https://acme.com/jobs/123",
                "source": "linkedin",
                "salary_range": "120k-160k EUR",
                "notes": "Great opportunity",
                "fit_score": 8.5,
            },
        )
        data = resp.json()
        assert resp.status_code == 201
        assert data["url"] == "https://acme.com/jobs/123"
        assert data["source"] == "linkedin"
        assert data["salary_range"] == "120k-160k EUR"
        assert data["notes"] == "Great opportunity"
        assert data["fit_score"] == pytest.approx(8.5)

    def test_create_default_status_discovered(self, client: TestClient):
        data = _create_app(client)
        assert data["status"] == "discovered"

    def test_create_missing_company_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"role": "Engineer", "profile_id": 1},
        )
        assert resp.status_code == 422
        body = resp.json()
        # Pydantic field-level errors
        assert body["detail"] is not None

    def test_create_empty_company_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"company": "", "role": "Engineer", "profile_id": 1},
        )
        assert resp.status_code == 422

    def test_create_missing_role_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"company": "Acme Corp", "profile_id": 1},
        )
        assert resp.status_code == 422

    def test_create_missing_profile_id_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"company": "Acme Corp", "role": "Engineer"},
        )
        assert resp.status_code == 422

    def test_create_invalid_profile_id_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={"company": "Acme Corp", "role": "Engineer", "profile_id": 9999},
        )
        assert resp.status_code == 404

    def test_create_timestamps_utc_iso8601(self, client: TestClient):
        data = _create_app(client)
        # Should parse as valid ISO 8601 UTC datetime
        created = datetime.fromisoformat(data["created_at"])
        assert created.tzinfo is not None  # timezone-aware
        updated = datetime.fromisoformat(data["updated_at"])
        assert updated.tzinfo is not None

    def test_create_creates_activity_log(self, client: TestClient, db_session: Session):
        data = _create_app(client)
        logs = db_session.query(ActivityLog).filter(ActivityLog.application_id == data["id"]).all()
        assert len(logs) == 1
        assert logs[0].action == "created"

    def test_create_fit_score_out_of_range(self, client: TestClient):
        resp = client.post(
            "/api/applications",
            json={
                "company": "Acme",
                "role": "Eng",
                "profile_id": 1,
                "fit_score": 11.0,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/applications — List
# ---------------------------------------------------------------------------


class TestListApplications:
    """Tests for GET /api/applications."""

    def test_list_empty_returns_200(self, client: TestClient):
        resp = client.get("/api/applications?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["applications"] == []
        assert data["total"] == 0

    def test_list_returns_created_apps(self, client: TestClient):
        _create_app(client, company="Alpha")
        _create_app(client, company="Beta")
        resp = client.get("/api/applications?profile_id=1")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["applications"]) == 2

    def test_list_excludes_archived(self, client: TestClient):
        app_data = _create_app(client, company="Archived Co")
        client.delete(f"/api/applications/{app_data['id']}?profile_id=1")
        resp = client.get("/api/applications?profile_id=1")
        data = resp.json()
        assert data["total"] == 0

    def test_filter_by_status(self, client: TestClient):
        _create_app(client, company="Alpha")  # discovered
        app2 = _create_app(client, company="Beta")
        # Move Beta to interested
        client.patch(f"/api/applications/{app2['id']}?profile_id=1", json={"status": "interested"})
        resp = client.get("/api/applications?profile_id=1&status=interested")
        data = resp.json()
        assert data["total"] == 1
        assert data["applications"][0]["company"] == "Beta"

    def test_search_by_company(self, client: TestClient):
        _create_app(client, company="Alpha Inc")
        _create_app(client, company="Beta LLC")
        resp = client.get("/api/applications?profile_id=1&search=alpha")
        data = resp.json()
        assert data["total"] == 1
        assert data["applications"][0]["company"] == "Alpha Inc"

    def test_sort_by_score_desc(self, client: TestClient):
        _create_app(client, company="Low", fit_score=3.0)
        _create_app(client, company="High", fit_score=9.0)
        resp = client.get("/api/applications?profile_id=1&sort=score&order=desc")
        data = resp.json()
        assert data["applications"][0]["company"] == "High"
        assert data["applications"][1]["company"] == "Low"

    def test_sort_by_score_asc(self, client: TestClient):
        _create_app(client, company="Low", fit_score=3.0)
        _create_app(client, company="High", fit_score=9.0)
        resp = client.get("/api/applications?profile_id=1&sort=score&order=asc")
        data = resp.json()
        assert data["applications"][0]["company"] == "Low"

    def test_sort_by_date_desc(self, client: TestClient):
        _create_app(client, company="First")
        _create_app(client, company="Second")
        resp = client.get("/api/applications?profile_id=1&sort=date&order=desc")
        data = resp.json()
        # Most recent first
        assert data["applications"][0]["company"] == "Second"

    def test_sort_by_date_asc(self, client: TestClient):
        _create_app(client, company="First")
        _create_app(client, company="Second")
        resp = client.get("/api/applications?profile_id=1&sort=date&order=asc")
        data = resp.json()
        assert data["applications"][0]["company"] == "First"

    def test_list_missing_profile_id_returns_422(self, client: TestClient):
        resp = client.get("/api/applications")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/applications/{id} — Detail
# ---------------------------------------------------------------------------


class TestGetApplication:
    """Tests for GET /api/applications/{id}."""

    def test_get_existing(self, client: TestClient):
        created = _create_app(client)
        resp = client.get(f"/api/applications/{created['id']}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["company"] == "Acme Corp"

    def test_get_includes_activity_log(self, client: TestClient):
        created = _create_app(client)
        resp = client.get(f"/api/applications/{created['id']}?profile_id=1")
        data = resp.json()
        assert "activity_log" in data
        assert len(data["activity_log"]) >= 1

    def test_get_nonexistent_returns_404(self, client: TestClient):
        resp = client.get("/api/applications/9999?profile_id=1")
        assert resp.status_code == 404

    def test_get_archived_returns_404(self, client: TestClient):
        created = _create_app(client)
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        resp = client.get(f"/api/applications/{created['id']}?profile_id=1")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/applications/{id} — Update
# ---------------------------------------------------------------------------


class TestUpdateApplication:
    """Tests for PATCH /api/applications/{id}."""

    def test_update_notes(self, client: TestClient):
        created = _create_app(client)
        resp = client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"notes": "Updated notes"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated notes"

    def test_update_salary(self, client: TestClient):
        created = _create_app(client)
        resp = client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"salary_range": "150k EUR"},
        )
        assert resp.status_code == 200
        assert resp.json()["salary_range"] == "150k EUR"

    def test_update_creates_activity_log(self, client: TestClient, db_session: Session):
        created = _create_app(client)
        client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"notes": "Changed"},
        )
        logs = (
            db_session.query(ActivityLog)
            .filter(
                ActivityLog.application_id == created["id"],
                ActivityLog.action == "updated",
            )
            .all()
        )
        assert len(logs) == 1

    def test_update_status_valid_transition(self, client: TestClient):
        created = _create_app(client)  # discovered
        resp = client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"status": "interested"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "interested"

    def test_update_status_creates_status_change_log(self, client: TestClient, db_session: Session):
        created = _create_app(client)
        client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"status": "interested"},
        )
        logs = (
            db_session.query(ActivityLog)
            .filter(
                ActivityLog.application_id == created["id"],
                ActivityLog.action == "status_changed",
            )
            .all()
        )
        assert len(logs) == 1
        assert "discovered" in logs[0].details
        assert "interested" in logs[0].details

    def test_update_nonexistent_returns_404(self, client: TestClient):
        resp = client.patch("/api/applications/9999?profile_id=1", json={"notes": "test"})
        assert resp.status_code == 404

    def test_update_archived_returns_404(self, client: TestClient):
        created = _create_app(client)
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        resp = client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    def test_update_timestamps_advance(self, client: TestClient):
        created = _create_app(client)
        resp = client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"notes": "new"},
        )
        data = resp.json()
        assert data["updated_at"] >= created["updated_at"]


# ---------------------------------------------------------------------------
# Status workflow validation (VAL-PIPE-005)
# ---------------------------------------------------------------------------


class TestStatusWorkflow:
    """Tests for status transition validation."""

    # Valid forward transitions — contract:
    # discovered→interested→applied→interviewing→offer→accepted/rejected
    # any→ghosted.  Pre-offer states CANNOT go directly to rejected.
    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("discovered", "interested"),
            ("interested", "applied"),
            ("applied", "interviewing"),
            ("interviewing", "offer"),
            ("offer", "accepted"),
            ("offer", "rejected"),
            # Any → ghosted
            ("discovered", "ghosted"),
            ("interested", "ghosted"),
            ("applied", "ghosted"),
            ("interviewing", "ghosted"),
            ("offer", "ghosted"),
        ],
    )
    def test_valid_transitions(self, client: TestClient, from_status: str, to_status: str):
        """Valid status transitions should succeed."""
        # Create at discovered, then walk to from_status
        created = _create_app(client)
        current = "discovered"
        # Path to reach from_status
        path = _transition_path(current, from_status)
        app_id = created["id"]
        for step in path:
            resp = client.patch(f"/api/applications/{app_id}?profile_id=1", json={"status": step})
            assert resp.status_code == 200, f"Failed transition to {step}"

        # Now do the actual transition under test
        resp = client.patch(f"/api/applications/{app_id}?profile_id=1", json={"status": to_status})
        assert resp.status_code == 200
        assert resp.json()["status"] == to_status

    # Invalid transitions — pre-offer→rejected is now forbidden
    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("discovered", "offer"),
            ("discovered", "accepted"),
            ("discovered", "interviewing"),
            ("discovered", "rejected"),
            ("interested", "offer"),
            ("interested", "accepted"),
            ("interested", "interviewing"),
            ("interested", "rejected"),
            ("applied", "accepted"),
            ("applied", "offer"),
            ("applied", "rejected"),
            ("interviewing", "rejected"),
            ("rejected", "applied"),
            ("ghosted", "applied"),
        ],
    )
    def test_invalid_transitions_return_422(
        self, client: TestClient, from_status: str, to_status: str
    ):
        """Invalid status transitions should return 422."""
        created = _create_app(client)
        app_id = created["id"]
        # Walk to from_status
        path = _transition_path("discovered", from_status)
        for step in path:
            resp = client.patch(f"/api/applications/{app_id}?profile_id=1", json={"status": step})
            assert resp.status_code == 200, f"Failed transition to {step}"

        resp = client.patch(f"/api/applications/{app_id}?profile_id=1", json={"status": to_status})
        assert resp.status_code == 422
        detail = resp.json()["detail"].lower()
        assert "transition" in detail or "status" in detail

    # Status normalization — title-cased values from Kanban DnD
    @pytest.mark.parametrize(
        "status_input,expected",
        [
            ("Interested", "interested"),
            ("APPLIED", "applied"),
            ("Interviewing", "interviewing"),
            ("Ghosted", "ghosted"),
        ],
    )
    def test_title_cased_status_normalized(
        self, client: TestClient, status_input: str, expected: str
    ):
        """Title-cased or uppercased status values are normalized to lowercase."""
        created = _create_app(client)
        app_id = created["id"]
        # Walk to the state before the target if needed
        path = _transition_path("discovered", expected)
        # For the last step, use the un-normalized input
        if path:
            for step in path[:-1]:
                resp = client.patch(
                    f"/api/applications/{app_id}?profile_id=1",
                    json={"status": step},
                )
                assert resp.status_code == 200, f"Prep transition to {step} failed"
            # Final step with title-cased input
            resp = client.patch(
                f"/api/applications/{app_id}?profile_id=1",
                json={"status": status_input},
            )
        else:
            # Direct transition (e.g., discovered→interested via "Interested")
            resp = client.patch(
                f"/api/applications/{app_id}?profile_id=1",
                json={"status": status_input},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == expected

    def test_discovered_to_rejected_returns_422(self, client: TestClient):
        """Explicit test: discovered→rejected MUST return 422 (not allowed)."""
        created = _create_app(client)
        resp = client.patch(
            f"/api/applications/{created['id']}?profile_id=1",
            json={"status": "rejected"},
        )
        assert resp.status_code == 422


def _transition_path(current: str, target: str) -> list[str]:
    """Get the minimal valid transition path from current to target status."""
    if current == target:
        return []
    forward_chain = ["discovered", "interested", "applied", "interviewing", "offer"]
    if current in forward_chain and target in forward_chain:
        start = forward_chain.index(current)
        end = forward_chain.index(target)
        if end > start:
            return forward_chain[start + 1 : end + 1]
    # Special terminal statuses
    if target in ("accepted", "rejected"):
        # Walk to offer first if needed, then to target
        path = _transition_path(current, "offer")
        if target == "accepted":
            return path + ["accepted"]
        return path + ["rejected"]
    if target == "ghosted":
        return ["ghosted"]
    return []


# ---------------------------------------------------------------------------
# DELETE /api/applications/{id} — Soft delete
# ---------------------------------------------------------------------------


class TestDeleteApplication:
    """Tests for DELETE /api/applications/{id}."""

    def test_delete_returns_200(self, client: TestClient):
        created = _create_app(client)
        resp = client.delete(f"/api/applications/{created['id']}?profile_id=1")
        assert resp.status_code == 200

    def test_delete_sets_archived_at(self, client: TestClient, db_session: Session):
        created = _create_app(client)
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        app_obj = db_session.get(Application, created["id"])
        assert app_obj.archived_at is not None

    def test_delete_creates_activity_log(self, client: TestClient, db_session: Session):
        created = _create_app(client)
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        logs = (
            db_session.query(ActivityLog)
            .filter(
                ActivityLog.application_id == created["id"],
                ActivityLog.action == "archived",
            )
            .all()
        )
        assert len(logs) == 1

    def test_delete_nonexistent_returns_404(self, client: TestClient):
        resp = client.delete("/api/applications/9999?profile_id=1")
        assert resp.status_code == 404

    def test_delete_already_archived_returns_404(self, client: TestClient):
        created = _create_app(client)
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        resp = client.delete(f"/api/applications/{created['id']}?profile_id=1")
        assert resp.status_code == 404

    def test_delete_does_not_destroy_follow_ups(self, client: TestClient, db_session: Session):
        """VAL-CROSS-019: Soft delete does not orphan follow-ups."""
        created = _create_app(client)
        fu = FollowUp(
            profile_id=1,
            application_id=created["id"],
            due_date=datetime.now(UTC),
            follow_up_type="email",
            notes="Follow up",
        )
        db_session.add(fu)
        db_session.commit()
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        # Follow-up still exists (not orphaned)
        existing = (
            db_session.query(FollowUp).filter(FollowUp.application_id == created["id"]).first()
        )
        assert existing is not None

    def test_delete_does_not_destroy_activity_logs(self, client: TestClient, db_session: Session):
        """VAL-CROSS-019: Soft delete preserves activity logs."""
        created = _create_app(client)
        client.delete(f"/api/applications/{created['id']}?profile_id=1")
        logs = (
            db_session.query(ActivityLog).filter(ActivityLog.application_id == created["id"]).all()
        )
        assert len(logs) >= 2  # created + archived


# ---------------------------------------------------------------------------
# Timestamps (VAL-PIPE-019)
# ---------------------------------------------------------------------------


class TestTimestamps:
    """Tests for UTC ISO 8601 timestamp handling."""

    def test_created_at_is_utc(self, client: TestClient):
        data = _create_app(client)
        ts = data["created_at"]
        # Must contain timezone info (ends with +00:00 or Z)
        assert "+" in ts or "Z" in ts

    def test_updated_at_is_utc(self, client: TestClient):
        data = _create_app(client)
        ts = data["updated_at"]
        assert "+" in ts or "Z" in ts

    def test_activity_log_timestamps_utc(self, client: TestClient):
        created = _create_app(client)
        resp = client.get(f"/api/applications/{created['id']}?profile_id=1")
        data = resp.json()
        for log_entry in data["activity_log"]:
            ts = log_entry["created_at"]
            assert "+" in ts or "Z" in ts


# ===========================================================================
# Regression: Status normalization — API always returns lowercase
# ===========================================================================


class TestStatusNormalization:
    """All API responses must return lowercase status values."""

    def test_create_returns_lowercase_status(self, client: TestClient):
        """POST /api/applications returns lowercase status."""
        data = _create_app(client)
        assert data["status"] == "discovered"

    def test_list_returns_lowercase_status(self, client: TestClient):
        """GET /api/applications returns all statuses in lowercase."""
        _create_app(client)
        resp = client.get("/api/applications?profile_id=1")
        assert resp.status_code == 200
        for app_item in resp.json()["applications"]:
            assert app_item["status"] == app_item["status"].lower()

    def test_update_status_returns_lowercase(self, client: TestClient):
        """PATCH with title-case status still returns lowercase."""
        data = _create_app(client)
        resp = client.patch(
            f"/api/applications/{data['id']}?profile_id=1",
            json={"status": "Interested"},  # title-case input
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "interested"

    def test_detail_returns_lowercase_status(self, client: TestClient):
        """GET /api/applications/{id} returns lowercase status."""
        data = _create_app(client)
        resp = client.get(f"/api/applications/{data['id']}?profile_id=1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "discovered"

    def test_legacy_titlecase_in_db_returns_lowercase(
        self, client: TestClient, db_session: Session
    ):
        """Even if DB has title-case status, API returns lowercase."""
        app_obj = Application(
            profile_id=1,
            company="LegacyCo",
            role="Eng",
            status="Interested",  # legacy title-case in DB
        )
        db_session.add(app_obj)
        db_session.commit()
        db_session.refresh(app_obj)

        resp = client.get(f"/api/applications/{app_obj.id}?profile_id=1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "interested"
