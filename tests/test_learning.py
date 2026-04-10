"""Tests for Learning Paths API and service.

Covers:
- VAL-LEARN-001: Per-gap learning recommendations with categorized resources
- VAL-LEARN-002: Learning progress tracking (not_started → in_progress → completed)
- VAL-LEARN-003: Completing learning affects readiness score
- VAL-LEARN-004: Each recommendation includes estimated_hours and difficulty
- VAL-LEARN-005: No recommendations shows empty state with add CTA

State machine fixes:
- Repeated completed calls are idempotent — no double skill upgrade
- Invalid transitions (e.g. not_started→completed) return 422
- Back-transitions (in_progress→not_started) clear timestamps
- Fresh gaps return template-based recommendations
"""

import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _db_engine():
    """Create an in-memory SQLite engine for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_name = tmp.name
    url = f"sqlite:///{tmp_name}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda c, _: c.cursor().execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    import os

    os.unlink(tmp_name)


@pytest.fixture
def test_db(_db_engine):
    """Create a database session for testing."""
    test_session_cls = sessionmaker(bind=_db_engine)
    session = test_session_cls()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_profile(test_db: Session) -> Profile:
    """Seed a test profile."""
    profile = Profile(
        name="Test User",
        email="test@example.com",
        location="Frankfurt",
        job_family="Software Engineering",
    )
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def second_profile(test_db: Session) -> Profile:
    """Create a second profile for scoping tests."""
    profile = Profile(
        name="Other User", email="other@example.com", job_family="Software Engineering"
    )
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def client(_db_engine, test_db: Session):
    """FastAPI test client with test database."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    from career_os.api.applications import router as apps_router
    from career_os.api.gaps import router as gaps_router
    from career_os.api.learning import router as learning_router
    from career_os.api.skills import router as skills_router

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)
    test_app.include_router(apps_router)
    test_app.include_router(gaps_router)
    test_app.include_router(learning_router)
    test_app.include_router(skills_router)

    def override_get_db():
        test_session_cls = sessionmaker(bind=_db_engine)
        session = test_session_cls()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return TestClient(test_app)


@pytest.fixture
def app_with_gaps(test_db: Session, test_profile: Profile) -> Application:
    """Create an application with job requirements where some are unmet gaps."""
    app_obj = Application(
        profile_id=test_profile.id,
        company="Acme Corp",
        role="Senior Engineer",
        status="applied",
    )
    test_db.add(app_obj)
    test_db.flush()

    # Requirements: Python (critical, expert), Kubernetes (critical, advanced)
    requirements = [
        JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="Python",
            required_level="expert",
            severity="critical",
        ),
        JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="critical",
        ),
    ]
    test_db.add_all(requirements)

    # Skills: Python at advanced (gap distance 1), Kubernetes missing (gap distance 3)
    skills = [
        Skill(
            profile_id=test_profile.id,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
    ]
    test_db.add_all(skills)
    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


@pytest.fixture
def gap_id(test_db: Session, app_with_gaps: Application, test_profile: Profile) -> int:
    """Return the ID of a gap (JobRequirement) for Kubernetes."""
    req = (
        test_db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == app_with_gaps.id,
            JobRequirement.profile_id == test_profile.id,
            JobRequirement.skill_name == "Kubernetes",
        )
        .first()
    )
    assert req is not None
    return req.id


@pytest.fixture
def python_gap_id(test_db: Session, app_with_gaps: Application, test_profile: Profile) -> int:
    """Return the ID of the Python gap (partially met)."""
    req = (
        test_db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == app_with_gaps.id,
            JobRequirement.profile_id == test_profile.id,
            JobRequirement.skill_name == "Python",
        )
        .first()
    )
    assert req is not None
    return req.id


# ===========================================================================
# VAL-LEARN-001: Per-gap learning recommendations
# ===========================================================================


class TestGetRecommendations:
    """VAL-LEARN-001: GET /api/gaps/{id}/recommendations returns categorized resources."""

    def test_returns_200_with_recommendations(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Recommendations endpoint returns 200."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200

    def test_has_categorized_resources(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Response includes free courses, paid courses, and hands-on projects."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert "recommendations" in data
        assert "gap_id" in data
        assert "skill_name" in data

    def test_each_recommendation_has_required_fields(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Each recommendation has title, url, estimated_hours, difficulty, provider."""
        # First add some recommendations
        client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "K8s Deep Dive",
                "url": "https://example.com/k8s",
                "resource_type": "free_course",
                "estimated_hours": 20.0,
                "difficulty": "intermediate",
                "provider": "YouTube",
            },
        )
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert len(data["recommendations"]) >= 1
        rec = data["recommendations"][0]
        assert "title" in rec
        assert "url" in rec
        assert "estimated_hours" in rec
        assert "difficulty" in rec
        assert "provider" in rec
        assert "resource_type" in rec
        assert "status" in rec

    def test_nonexistent_gap_returns_404(self, client: TestClient, test_profile: Profile):
        """404 for non-existent gap."""
        resp = client.get(
            "/api/gaps/99999/recommendations",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_scoping(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        gap_id: int,
    ):
        """Profile B cannot access profile A's gap recommendations."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404


# ===========================================================================
# VAL-LEARN-002: Learning progress tracking
# ===========================================================================


class TestLearningProgressTracking:
    """VAL-LEARN-002: Resources can be marked not_started → in_progress → completed."""

    def test_create_resource_defaults_to_not_started(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """New learning resource has status 'not_started'."""
        resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "Learn Kubernetes",
                "url": "https://example.com/k8s",
                "resource_type": "free_course",
                "estimated_hours": 15.0,
                "difficulty": "beginner",
                "provider": "Coursera",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "not_started"

    def test_transition_to_in_progress(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Status can be changed to in_progress."""
        # Create resource
        create_resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "Learn K8s",
                "url": "https://example.com",
                "resource_type": "free_course",
                "estimated_hours": 10.0,
                "difficulty": "beginner",
                "provider": "YouTube",
            },
        )
        resource_id = create_resp.json()["id"]

        # Update status to in_progress
        resp = client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["started_at"] is not None

    def test_transition_to_completed(self, client: TestClient, test_profile: Profile, gap_id: int):
        """Status can be changed to completed with completed_at timestamp."""
        # Create resource
        create_resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "Learn K8s",
                "url": "https://example.com",
                "resource_type": "paid_course",
                "estimated_hours": 30.0,
                "difficulty": "advanced",
                "provider": "Udemy",
            },
        )
        resource_id = create_resp.json()["id"]

        # Move to in_progress first
        client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "in_progress"},
        )
        # Then to completed
        resp = client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    def test_invalid_status_returns_422(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Invalid status value returns 422."""
        create_resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "Learn K8s",
                "url": "https://example.com",
                "resource_type": "free_course",
                "estimated_hours": 10.0,
                "difficulty": "beginner",
                "provider": "YouTube",
            },
        )
        resource_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "invalid_status"},
        )
        assert resp.status_code == 422

    def test_profile_scoping_on_status_update(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        gap_id: int,
    ):
        """Profile B cannot update status of profile A's learning resource."""
        create_resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "Learn K8s",
                "url": "https://example.com",
                "resource_type": "free_course",
                "estimated_hours": 10.0,
                "difficulty": "beginner",
                "provider": "YouTube",
            },
        )
        resource_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": second_profile.id, "status": "in_progress"},
        )
        assert resp.status_code == 404


# ===========================================================================
# VAL-LEARN-003: Completing learning affects readiness score
# ===========================================================================


class TestLearningAffectsReadiness:
    """VAL-LEARN-003: Completing learning reduces gap distance and improves readiness."""

    def test_completing_learning_improves_readiness(
        self,
        client: TestClient,
        test_db: Session,
        test_profile: Profile,
        app_with_gaps: Application,
        gap_id: int,
    ):
        """Completing learning for a gap skill reduces gap distance and improves readiness."""
        # Step 1: Get initial readiness score
        gaps_resp = client.get(
            f"/api/applications/{app_with_gaps.id}/gaps",
            params={"profile_id": test_profile.id},
        )
        initial_readiness = gaps_resp.json()["readiness_score"]

        # Step 2: Create and complete a learning resource for Kubernetes
        create_resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "K8s Mastery",
                "url": "https://example.com/k8s-master",
                "resource_type": "paid_course",
                "estimated_hours": 40.0,
                "difficulty": "advanced",
                "provider": "O'Reilly",
            },
        )
        resource_id = create_resp.json()["id"]

        # Move to in_progress then completed
        client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "in_progress"},
        )
        client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "completed"},
        )

        # Step 3: Check readiness score improved
        gaps_resp_after = client.get(
            f"/api/applications/{app_with_gaps.id}/gaps",
            params={"profile_id": test_profile.id},
        )
        final_readiness = gaps_resp_after.json()["readiness_score"]

        # Readiness should have improved because the gap was reduced
        assert final_readiness > initial_readiness

    def test_completing_learning_adds_skill_to_inventory(
        self,
        client: TestClient,
        test_profile: Profile,
        gap_id: int,
    ):
        """Completing learning creates or upgrades the skill in inventory."""
        create_resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "K8s Course",
                "url": "https://example.com",
                "resource_type": "free_course",
                "estimated_hours": 20.0,
                "difficulty": "intermediate",
                "provider": "YouTube",
            },
        )
        resource_id = create_resp.json()["id"]

        # Complete the learning
        client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "in_progress"},
        )
        client.patch(
            f"/api/learning/{resource_id}/status",
            json={"profile_id": test_profile.id, "status": "completed"},
        )

        # Verify the skill was added to inventory
        skills_resp = client.get(
            "/api/skills",
            params={"profile_id": test_profile.id, "q": "Kubernetes"},
        )
        skills_data = skills_resp.json()
        k8s_skills = [s for s in skills_data["skills"] if s["name"].lower() == "kubernetes"]
        assert len(k8s_skills) >= 1


# ===========================================================================
# VAL-LEARN-004: Effort estimates
# ===========================================================================


class TestEffortEstimates:
    """VAL-LEARN-004: Each recommendation includes estimated_hours and difficulty."""

    def test_estimated_hours_field_present(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Created resource has estimated_hours."""
        resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "K8s Quick Start",
                "url": "https://example.com/quick",
                "resource_type": "hands_on_project",
                "estimated_hours": 5.0,
                "difficulty": "beginner",
                "provider": "GitHub",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["estimated_hours"] == pytest.approx(5.0)

    def test_difficulty_field_present(self, client: TestClient, test_profile: Profile, gap_id: int):
        """Created resource has difficulty rating."""
        resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "K8s Advanced",
                "url": "https://example.com/adv",
                "resource_type": "paid_course",
                "estimated_hours": 40.0,
                "difficulty": "advanced",
                "provider": "O'Reilly",
            },
        )
        data = resp.json()
        assert data["difficulty"] == "advanced"


# ===========================================================================
# VAL-LEARN-005: Empty learning state
# ===========================================================================


class TestEmptyLearningState:
    """VAL-LEARN-005: No recommendations shows empty state with add CTA."""

    def test_empty_recommendations_returns_cta(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Empty recommendations returns CTA for manual add."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendations"] == []
        assert "cta" in data
        assert data["cta"]["label"] == "Add your own"
        assert data["cta"]["action"] == "add_recommendation"


# ===========================================================================
# Additional: Create resource (manual add)
# ===========================================================================


class TestCreateRecommendation:
    """Test creating learning resources manually (add CTA functionality)."""

    def test_create_returns_201(self, client: TestClient, test_profile: Profile, gap_id: int):
        """POST creates recommendation returns 201."""
        resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "K8s The Hard Way",
                "url": "https://github.com/kelseyhightower/kubernetes-the-hard-way",
                "resource_type": "hands_on_project",
                "estimated_hours": 20.0,
                "difficulty": "advanced",
                "provider": "GitHub",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "K8s The Hard Way"
        assert data["resource_type"] == "hands_on_project"
        assert data["status"] == "not_started"

    def test_create_missing_title_returns_422(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Missing required title field returns 422."""
        resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "url": "https://example.com",
                "resource_type": "free_course",
            },
        )
        assert resp.status_code == 422

    def test_create_nonexistent_gap_returns_404(self, client: TestClient, test_profile: Profile):
        """Creating recommendation for nonexistent gap returns 404."""
        resp = client.post(
            "/api/gaps/99999/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "Something",
                "resource_type": "free_course",
                "estimated_hours": 10.0,
                "difficulty": "beginner",
                "provider": "YouTube",
            },
        )
        assert resp.status_code == 404

    def test_create_with_profile_scoping(
        self,
        client: TestClient,
        second_profile: Profile,
        gap_id: int,
    ):
        """Profile B cannot create recommendation for profile A's gap."""
        resp = client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": second_profile.id,
                "title": "Something",
                "resource_type": "free_course",
                "estimated_hours": 10.0,
                "difficulty": "beginner",
                "provider": "YouTube",
            },
        )
        assert resp.status_code == 404


# ===========================================================================
# State Machine: Transition enforcement
# ===========================================================================


def _create_resource(client: TestClient, gap_id: int, profile_id: int) -> int:
    """Helper: create a learning resource and return its id."""
    resp = client.post(
        f"/api/gaps/{gap_id}/recommendations",
        json={
            "profile_id": profile_id,
            "title": "Test resource",
            "url": "https://example.com",
            "resource_type": "free_course",
            "estimated_hours": 10.0,
            "difficulty": "beginner",
            "provider": "YouTube",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _set_status(client: TestClient, resource_id: int, profile_id: int, status: str):
    """Helper: PATCH status and return the response."""
    return client.patch(
        f"/api/learning/{resource_id}/status",
        json={"profile_id": profile_id, "status": status},
    )


class TestStateMachineTransitions:
    """Enforce strict transition map: not_started→in_progress, in_progress→completed|not_started."""

    def test_not_started_to_in_progress_allowed(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """not_started → in_progress is a valid transition."""
        rid = _create_resource(client, gap_id, test_profile.id)
        resp = _set_status(client, rid, test_profile.id, "in_progress")
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_not_started_to_completed_blocked(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """not_started → completed is an INVALID transition → 422."""
        rid = _create_resource(client, gap_id, test_profile.id)
        resp = _set_status(client, rid, test_profile.id, "completed")
        assert resp.status_code == 422
        assert "Cannot transition" in resp.json()["detail"]

    def test_in_progress_to_completed_allowed(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """in_progress → completed is a valid transition."""
        rid = _create_resource(client, gap_id, test_profile.id)
        _set_status(client, rid, test_profile.id, "in_progress")
        resp = _set_status(client, rid, test_profile.id, "completed")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_at"] is not None

    def test_in_progress_to_not_started_allowed(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """in_progress → not_started is a valid back-transition."""
        rid = _create_resource(client, gap_id, test_profile.id)
        _set_status(client, rid, test_profile.id, "in_progress")
        resp = _set_status(client, rid, test_profile.id, "not_started")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_started"
        assert data["started_at"] is None
        assert data["completed_at"] is None

    def test_completed_to_in_progress_blocked(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """completed → in_progress is INVALID → 422."""
        rid = _create_resource(client, gap_id, test_profile.id)
        _set_status(client, rid, test_profile.id, "in_progress")
        _set_status(client, rid, test_profile.id, "completed")
        resp = _set_status(client, rid, test_profile.id, "in_progress")
        assert resp.status_code == 422

    def test_completed_to_not_started_blocked(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """completed → not_started is INVALID → 422."""
        rid = _create_resource(client, gap_id, test_profile.id)
        _set_status(client, rid, test_profile.id, "in_progress")
        _set_status(client, rid, test_profile.id, "completed")
        resp = _set_status(client, rid, test_profile.id, "not_started")
        assert resp.status_code == 422

    def test_not_started_to_not_started_blocked(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """not_started → not_started is not in the transition map → 422."""
        rid = _create_resource(client, gap_id, test_profile.id)
        resp = _set_status(client, rid, test_profile.id, "not_started")
        assert resp.status_code == 422


# ===========================================================================
# State Machine: Idempotent completed calls
# ===========================================================================


class TestIdempotentCompleted:
    """Repeated completed→completed calls must be idempotent — no double skill upgrade."""

    def test_repeated_completed_is_idempotent(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Calling completed twice returns 200 both times, no error."""
        rid = _create_resource(client, gap_id, test_profile.id)
        _set_status(client, rid, test_profile.id, "in_progress")
        resp1 = _set_status(client, rid, test_profile.id, "completed")
        assert resp1.status_code == 200

        resp2 = _set_status(client, rid, test_profile.id, "completed")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "completed"

    def test_repeated_completed_no_double_skill_upgrade(
        self,
        client: TestClient,
        test_db: Session,
        test_profile: Profile,
        gap_id: int,
    ):
        """Repeated completed calls must NOT re-upgrade the skill."""
        rid = _create_resource(client, gap_id, test_profile.id)
        _set_status(client, rid, test_profile.id, "in_progress")
        _set_status(client, rid, test_profile.id, "completed")

        # Record skill proficiency after first completion
        skill_after_first = (
            test_db.query(Skill)
            .filter(
                Skill.profile_id == test_profile.id,
                Skill.name.ilike("Kubernetes"),
            )
            .first()
        )
        assert skill_after_first is not None
        proficiency_after_first = skill_after_first.proficiency

        # Count history entries after first completion
        from career_os.models.skills import SkillHistory

        history_count_first = (
            test_db.query(SkillHistory)
            .filter(SkillHistory.skill_id == skill_after_first.id)
            .count()
        )

        # Call completed again (idempotent)
        _set_status(client, rid, test_profile.id, "completed")

        # Proficiency must NOT have changed
        test_db.expire_all()
        skill_after_second = test_db.query(Skill).filter(Skill.id == skill_after_first.id).first()
        assert skill_after_second.proficiency == proficiency_after_first

        # History count must NOT have increased
        history_count_second = (
            test_db.query(SkillHistory)
            .filter(SkillHistory.skill_id == skill_after_first.id)
            .count()
        )
        assert history_count_second == history_count_first


# ===========================================================================
# State Machine: Back-transitions clear timestamps
# ===========================================================================


class TestBackTransitionTimestamps:
    """Back-transition in_progress → not_started must clear started_at and completed_at."""

    def test_back_transition_clears_started_at(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Going back to not_started clears started_at."""
        rid = _create_resource(client, gap_id, test_profile.id)
        resp1 = _set_status(client, rid, test_profile.id, "in_progress")
        assert resp1.json()["started_at"] is not None

        resp2 = _set_status(client, rid, test_profile.id, "not_started")
        assert resp2.status_code == 200
        assert resp2.json()["started_at"] is None
        assert resp2.json()["completed_at"] is None


# ===========================================================================
# Template-based recommendations for fresh gaps
# ===========================================================================


class TestTemplateRecommendations:
    """Fresh gaps (no user resources) return template-based suggestions."""

    def test_fresh_gap_returns_template_recommendations(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Gap with no resources gets 3 template recommendations."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendations"] == []
        assert len(data["template_recommendations"]) == 3

    def test_template_types_cover_free_paid_project(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Templates include free_course, paid_course, hands_on_project."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        types = {t["resource_type"] for t in data["template_recommendations"]}
        assert types == {"free_course", "paid_course", "hands_on_project"}

    def test_template_has_required_fields(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Each template has title, url, provider, type, hours, difficulty."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        for tmpl in data["template_recommendations"]:
            assert tmpl["title"]
            assert tmpl["url"]
            assert tmpl["provider"]
            assert tmpl["resource_type"]
            assert tmpl["estimated_hours"] is not None
            assert tmpl["difficulty"] is not None

    def test_template_includes_skill_name(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Template titles include the skill name."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        for tmpl in data["template_recommendations"]:
            assert "Kubernetes" in tmpl["title"]

    def test_templates_disappear_when_user_resources_exist(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Once user adds a resource, templates are no longer returned."""
        # Add a user resource
        client.post(
            f"/api/gaps/{gap_id}/recommendations",
            json={
                "profile_id": test_profile.id,
                "title": "My K8s Resource",
                "url": "https://example.com",
                "resource_type": "free_course",
                "estimated_hours": 10.0,
                "difficulty": "beginner",
                "provider": "YouTube",
            },
        )

        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert len(data["recommendations"]) >= 1
        assert data["template_recommendations"] == []
        assert data["cta"] is None

    def test_template_hours_scale_with_required_level(
        self, client: TestClient, test_profile: Profile, gap_id: int
    ):
        """Template hours for an advanced-level gap are larger than beginner levels."""
        resp = client.get(
            f"/api/gaps/{gap_id}/recommendations",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        # Kubernetes gap requires 'advanced' level → free_course hours should be 30.0
        templates = data["template_recommendations"]
        free = [t for t in templates if t["resource_type"] == "free_course"][0]
        assert free["estimated_hours"] == pytest.approx(30.0)
        assert free["difficulty"] == "advanced"
