"""Tests for Profile CRUD API (POST/PATCH/DELETE).

Covers:
- VAL-PIPE-017: Profile create/edit/delete flow
- VAL-PIPE-016: Application detail includes packages
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, ApplicationPackage, Profile
from career_os.models.skills import (
    CoachingSuggestion,
    Goal,
    JobRequirement,
    LearningResource,
    Skill,
    SkillHistory,
)

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

    # Seed a default profile for tests that need it
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
# POST /api/profiles — Create
# ---------------------------------------------------------------------------


class TestCreateProfile:
    """Tests for POST /api/profiles."""

    def test_create_returns_201(self, client: TestClient):
        resp = client.post("/api/profiles", json={"name": "Alice"})
        assert resp.status_code == 201

    def test_create_returns_profile(self, client: TestClient):
        resp = client.post(
            "/api/profiles",
            json={
                "name": "Alice",
                "email": "alice@example.com",
                "location": "Berlin",
                "job_family": "Engineering",
            },
        )
        data = resp.json()
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"
        assert data["location"] == "Berlin"
        assert data["job_family"] == "Engineering"
        assert data["id"] is not None

    def test_create_name_only(self, client: TestClient):
        resp = client.post("/api/profiles", json={"name": "Bob"})
        data = resp.json()
        assert data["name"] == "Bob"
        assert data["email"] is None
        assert data["location"] is None
        assert data["job_family"] is None

    def test_create_missing_name_returns_422(self, client: TestClient):
        resp = client.post("/api/profiles", json={})
        assert resp.status_code == 422

    def test_create_empty_name_returns_422(self, client: TestClient):
        resp = client.post("/api/profiles", json={"name": ""})
        assert resp.status_code == 422

    def test_create_has_timestamps(self, client: TestClient):
        resp = client.post("/api/profiles", json={"name": "Timed"})
        data = resp.json()
        assert data["created_at"] is not None
        assert data["updated_at"] is not None


# ---------------------------------------------------------------------------
# PATCH /api/profiles/{id} — Update
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """Tests for PATCH /api/profiles/{id}."""

    def test_update_name(self, client: TestClient):
        resp = client.patch("/api/profiles/1", json={"name": "Updated Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_email(self, client: TestClient):
        resp = client.patch("/api/profiles/1", json={"email": "new@example.com"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@example.com"

    def test_update_location(self, client: TestClient):
        resp = client.patch("/api/profiles/1", json={"location": "Munich"})
        assert resp.status_code == 200
        assert resp.json()["location"] == "Munich"

    def test_update_job_family(self, client: TestClient):
        resp = client.patch("/api/profiles/1", json={"job_family": "Product"})
        assert resp.status_code == 200
        assert resp.json()["job_family"] == "Product"

    def test_update_multiple_fields(self, client: TestClient):
        resp = client.patch(
            "/api/profiles/1",
            json={"name": "Multi", "location": "Berlin", "job_family": "AI"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Multi"
        assert data["location"] == "Berlin"
        assert data["job_family"] == "AI"

    def test_update_nonexistent_returns_404(self, client: TestClient):
        resp = client.patch("/api/profiles/9999", json={"name": "Ghost"})
        assert resp.status_code == 404

    def test_update_empty_name_returns_422(self, client: TestClient):
        resp = client.patch("/api/profiles/1", json={"name": ""})
        assert resp.status_code == 422

    def test_update_preserves_unchanged_fields(self, client: TestClient):
        """Only explicitly set fields should change."""
        resp = client.patch("/api/profiles/1", json={"location": "Munich"})
        data = resp.json()
        assert data["name"] == "Test User"  # unchanged
        assert data["email"] == "test@example.com"  # unchanged
        assert data["location"] == "Munich"  # changed


# ---------------------------------------------------------------------------
# DELETE /api/profiles/{id}
# ---------------------------------------------------------------------------


class TestDeleteProfile:
    """Tests for DELETE /api/profiles/{id}."""

    def test_delete_returns_204(self, client: TestClient):
        # Create a new profile to delete (don't delete the default one)
        create_resp = client.post("/api/profiles", json={"name": "ToDelete"})
        pid = create_resp.json()["id"]
        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204

    def test_delete_removes_profile(self, client: TestClient):
        create_resp = client.post("/api/profiles", json={"name": "Gone"})
        pid = create_resp.json()["id"]
        client.delete(f"/api/profiles/{pid}")
        resp = client.get(f"/api/profiles/{pid}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client: TestClient):
        resp = client.delete("/api/profiles/9999")
        assert resp.status_code == 404

    def test_delete_cascades_skills(self, client: TestClient, db_session: Session):
        """Deleting a profile cascades to its skills (M2 table)."""
        create_resp = client.post("/api/profiles", json={"name": "SkillOwner"})
        pid = create_resp.json()["id"]
        skill = Skill(
            profile_id=pid,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        db_session.add(skill)
        db_session.commit()
        skill_id = skill.id

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        assert db_session.get(Skill, skill_id) is None

    def test_delete_cascades_skill_history(self, client: TestClient, db_session: Session):
        """Deleting a profile cascades to skill history records."""
        create_resp = client.post("/api/profiles", json={"name": "HistOwner"})
        pid = create_resp.json()["id"]
        skill = Skill(
            profile_id=pid,
            name="Go",
            category="technical",
            proficiency="beginner",
            evidence_source="manual",
        )
        db_session.add(skill)
        db_session.flush()
        history = SkillHistory(
            skill_id=skill.id,
            profile_id=pid,
            previous_proficiency=None,
            new_proficiency="beginner",
        )
        db_session.add(history)
        db_session.commit()
        history_id = history.id

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        assert db_session.get(SkillHistory, history_id) is None

    def test_delete_cascades_learning_resources(self, client: TestClient, db_session: Session):
        """Deleting a profile cascades to learning resources."""
        create_resp = client.post("/api/profiles", json={"name": "LearnOwner"})
        pid = create_resp.json()["id"]
        resource = LearningResource(
            profile_id=pid,
            title="Learn Python",
            resource_type="free_course",
        )
        db_session.add(resource)
        db_session.commit()
        resource_id = resource.id

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        assert db_session.get(LearningResource, resource_id) is None

    def test_delete_cascades_goals(self, client: TestClient, db_session: Session):
        """Deleting a profile cascades to goals."""
        create_resp = client.post("/api/profiles", json={"name": "GoalOwner"})
        pid = create_resp.json()["id"]
        goal = Goal(
            profile_id=pid,
            title="Get Senior TPM role",
            goal_type="realistic",
        )
        db_session.add(goal)
        db_session.commit()
        goal_id = goal.id

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        assert db_session.get(Goal, goal_id) is None

    def test_delete_cascades_job_requirements(self, client: TestClient, db_session: Session):
        """Deleting a profile cascades to job requirements."""
        create_resp = client.post("/api/profiles", json={"name": "ReqOwner"})
        pid = create_resp.json()["id"]
        # Need an application for the FK
        app_obj = Application(
            profile_id=pid,
            company="TestCo",
            role="Engineer",
            status="discovered",
        )
        db_session.add(app_obj)
        db_session.flush()
        req = JobRequirement(
            application_id=app_obj.id,
            profile_id=pid,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="critical",
        )
        db_session.add(req)
        db_session.commit()
        req_id = req.id

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        assert db_session.get(JobRequirement, req_id) is None

    def test_delete_cascades_coaching_suggestions(self, client: TestClient, db_session: Session):
        """Deleting a profile cascades to coaching suggestions."""
        create_resp = client.post("/api/profiles", json={"name": "CoachOwner"})
        pid = create_resp.json()["id"]
        suggestion = CoachingSuggestion(
            profile_id=pid,
            action="Study Kubernetes for 2 weeks",
            priority=1,
        )
        db_session.add(suggestion)
        db_session.commit()
        suggestion_id = suggestion.id

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        assert db_session.get(CoachingSuggestion, suggestion_id) is None

    def test_delete_with_all_m2_children_no_500(self, client: TestClient, db_session: Session):
        """Profile with ALL M2 child record types deletes cleanly (no 500)."""
        create_resp = client.post("/api/profiles", json={"name": "FullM2"})
        pid = create_resp.json()["id"]

        # Create one of each M2 child record type
        skill = Skill(
            profile_id=pid,
            name="Docker",
            category="tools",
            proficiency="intermediate",
            evidence_source="manual",
        )
        db_session.add(skill)
        db_session.flush()

        db_session.add(
            SkillHistory(
                skill_id=skill.id,
                profile_id=pid,
                new_proficiency="intermediate",
            )
        )
        db_session.add(
            LearningResource(
                profile_id=pid,
                title="Docker Deep Dive",
                resource_type="paid_course",
            )
        )
        db_session.add(
            Goal(
                profile_id=pid,
                title="Master containers",
                goal_type="aspirational",
            )
        )
        app_obj = Application(
            profile_id=pid,
            company="ContainerCo",
            role="DevOps",
            status="discovered",
        )
        db_session.add(app_obj)
        db_session.flush()
        db_session.add(
            JobRequirement(
                application_id=app_obj.id,
                profile_id=pid,
                skill_name="Docker",
                required_level="expert",
                severity="critical",
            )
        )
        db_session.add(
            CoachingSuggestion(
                profile_id=pid,
                action="Build a Kubernetes cluster",
                priority=2,
            )
        )
        db_session.commit()

        resp = client.delete(f"/api/profiles/{pid}")
        assert resp.status_code == 204
        # Verify profile is gone
        assert client.get(f"/api/profiles/{pid}").status_code == 404


# ---------------------------------------------------------------------------
# GET /api/profiles — List
# ---------------------------------------------------------------------------


class TestListProfiles:
    """Tests for GET /api/profiles — listing."""

    def test_list_returns_seeded_profile(self, client: TestClient):
        resp = client.get("/api/profiles")
        data = resp.json()
        assert data["count"] >= 1
        assert any(p["name"] == "Test User" for p in data["profiles"])

    def test_list_includes_created_profiles(self, client: TestClient):
        client.post("/api/profiles", json={"name": "New Profile"})
        resp = client.get("/api/profiles")
        data = resp.json()
        assert data["count"] >= 2


# ---------------------------------------------------------------------------
# Application detail with packages (VAL-PIPE-016)
# ---------------------------------------------------------------------------


class TestApplicationDetailPackages:
    """Tests for packages in GET /api/applications/{id}."""

    def test_detail_includes_empty_packages(self, client: TestClient):
        """Detail response includes packages field even when empty."""
        create_resp = client.post(
            "/api/applications",
            json={"company": "NoPkgCo", "role": "Eng", "profile_id": 1},
        )
        app_id = create_resp.json()["id"]
        resp = client.get(f"/api/applications/{app_id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "packages" in data
        assert data["packages"] == []

    def test_detail_includes_linked_packages(self, client: TestClient, db_session: Session):
        """Detail response includes packages with correct derived fields."""
        # Create an application
        create_resp = client.post(
            "/api/applications",
            json={"company": "PkgCo", "role": "Eng", "profile_id": 1},
        )
        app_id = create_resp.json()["id"]

        # Link a package
        pkg = ApplicationPackage(
            profile_id=1,
            application_id=app_id,
            package_dir="cv/applications/pkgco-eng",
            cover_letter_path="cv/applications/pkgco-eng/cover_letter.pdf",
            cv_path="cv/applications/pkgco-eng/cv.pdf",
        )
        db_session.add(pkg)
        db_session.commit()

        resp = client.get(f"/api/applications/{app_id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["packages"]) == 1
        pkg_data = data["packages"][0]
        assert pkg_data["package_name"] == "pkgco-eng"
        assert pkg_data["file_path"] == "cv/applications/pkgco-eng"
        assert pkg_data["package_type"] == "full"  # has both cv and cover letter

    def test_package_type_cv_only(self, client: TestClient, db_session: Session):
        """Package with only cv_path → type 'cv'."""
        create_resp = client.post(
            "/api/applications",
            json={"company": "CvOnly", "role": "Eng", "profile_id": 1},
        )
        app_id = create_resp.json()["id"]
        pkg = ApplicationPackage(
            profile_id=1,
            application_id=app_id,
            package_dir="cv/applications/cvonly",
            cv_path="cv/applications/cvonly/cv.pdf",
        )
        db_session.add(pkg)
        db_session.commit()

        resp = client.get(f"/api/applications/{app_id}?profile_id=1")
        data = resp.json()
        assert data["packages"][0]["package_type"] == "cv"

    def test_package_type_cover_letter_only(self, client: TestClient, db_session: Session):
        """Package with only cover_letter_path → type 'cover_letter'."""
        create_resp = client.post(
            "/api/applications",
            json={"company": "ClOnly", "role": "Eng", "profile_id": 1},
        )
        app_id = create_resp.json()["id"]
        pkg = ApplicationPackage(
            profile_id=1,
            application_id=app_id,
            package_dir="cv/applications/clonly",
            cover_letter_path="cv/applications/clonly/cover.pdf",
        )
        db_session.add(pkg)
        db_session.commit()

        resp = client.get(f"/api/applications/{app_id}?profile_id=1")
        data = resp.json()
        assert data["packages"][0]["package_type"] == "cover_letter"

    def test_package_type_directory(self, client: TestClient, db_session: Session):
        """Package with no file paths → type 'directory'."""
        create_resp = client.post(
            "/api/applications",
            json={"company": "DirOnly", "role": "Eng", "profile_id": 1},
        )
        app_id = create_resp.json()["id"]
        pkg = ApplicationPackage(
            profile_id=1,
            application_id=app_id,
            package_dir="cv/applications/dironly",
        )
        db_session.add(pkg)
        db_session.commit()

        resp = client.get(f"/api/applications/{app_id}?profile_id=1")
        data = resp.json()
        assert data["packages"][0]["package_type"] == "directory"
