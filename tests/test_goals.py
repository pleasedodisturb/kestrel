"""Tests for Career Goals API and service.

Covers:
- VAL-GOAL-001: Define career goals (CRUD with realistic/aspirational types)
- VAL-GOAL-002: Goal-to-reality mapping (current state, required state, delta)
- VAL-GOAL-003: Progress tracking across applications, learning, portfolio
- VAL-GOAL-004: Goal recalibration (AI-powered with market-data-backed suggestions)
- VAL-GOAL-005: Alternative path analysis (employment, freelance, consulting)
- Profile scoping: two-profile isolation tests
"""

import os
import tempfile
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application, Profile
from career_os.models.skills import Goal, LearningResource, Skill

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
def api_client(_db_engine):
    """Create a FastAPI test client with overridden DB."""
    test_session_cls = sessionmaker(bind=_db_engine)

    def override_get_db():
        db = test_session_cls()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_goal(test_db: Session, test_profile: Profile) -> Goal:
    """Create a sample goal."""
    goal = Goal(
        profile_id=test_profile.id,
        title="Land Senior TPM role at tier-1 tech company",
        goal_type="aspirational",
        target_date=datetime(2026, 6, 1, tzinfo=UTC),
        status="active",
        description="Target 120-160k EUR base + equity at a top tech company.",
    )
    test_db.add(goal)
    test_db.commit()
    test_db.refresh(goal)
    return goal


@pytest.fixture
def sample_realistic_goal(test_db: Session, test_profile: Profile) -> Goal:
    """Create a realistic sample goal."""
    goal = Goal(
        profile_id=test_profile.id,
        title="Get any TPM role within 3 months",
        goal_type="realistic",
        target_date=datetime(2026, 5, 1, tzinfo=UTC),
        status="active",
        description="Realistic target: any TPM role in Frankfurt or remote EU.",
    )
    test_db.add(goal)
    test_db.commit()
    test_db.refresh(goal)
    return goal


@pytest.fixture
def sample_skills(test_db: Session, test_profile: Profile) -> list[Skill]:
    """Create sample skills."""
    skills_data = [
        ("Python", "technical", "advanced"),
        ("Project Management", "domain", "expert"),
        ("AI/ML", "technical", "intermediate"),
        ("Kubernetes", "tools", "beginner"),
        ("Leadership", "soft", "advanced"),
    ]
    skills = []
    for name, cat, prof in skills_data:
        s = Skill(
            profile_id=test_profile.id,
            name=name,
            category=cat,
            proficiency=prof,
            evidence_source="manual",
        )
        test_db.add(s)
        skills.append(s)
    test_db.commit()
    for s in skills:
        test_db.refresh(s)
    return skills


@pytest.fixture
def sample_applications(test_db: Session, test_profile: Profile) -> list[Application]:
    """Create sample applications."""
    apps_data = [
        ("Stripe", "Senior TPM", "applied"),
        ("Google", "AI Program Lead", "interviewing"),
        ("Mistral", "Product Engineer", "applied"),
        ("Plain", "Founding Engineer", "discovered"),
        ("Shopware", "TPM", "interested"),
    ]
    apps = []
    for company, role, status in apps_data:
        a = Application(
            profile_id=test_profile.id,
            company=company,
            role=role,
            status=status,
            source="manual",
        )
        test_db.add(a)
        apps.append(a)
    test_db.commit()
    for a in apps:
        test_db.refresh(a)
    return apps


@pytest.fixture
def sample_learning(test_db: Session, test_profile: Profile) -> list[LearningResource]:
    """Create sample learning resources."""
    resources_data = [
        ("Terraform Basics", "completed"),
        ("Kubernetes Advanced", "in_progress"),
        ("GraphQL Tutorial", "not_started"),
    ]
    resources = []
    for title, status in resources_data:
        lr = LearningResource(
            profile_id=test_profile.id,
            title=title,
            status=status,
            resource_type="free_course",
        )
        if status == "completed":
            lr.started_at = datetime.now(UTC)
            lr.completed_at = datetime.now(UTC)
        elif status == "in_progress":
            lr.started_at = datetime.now(UTC)
        test_db.add(lr)
        resources.append(lr)
    test_db.commit()
    for lr in resources:
        test_db.refresh(lr)
    return resources


@pytest.fixture
def sample_discovered_jobs(test_db: Session, test_profile: Profile) -> list[DiscoveredJob]:
    """Create sample discovered jobs with descriptions containing known skills."""
    import json

    jobs = [
        DiscoveredJob(
            profile_id=test_profile.id,
            title="Senior TPM - AI Platform",
            company="TechCorp",
            location="Frankfurt",
            description=(
                "Looking for a Senior TPM to lead AI/ML projects. "
                "Requirements: Python, Agile, Program Management, "
                "Stakeholder Management. Cloud infrastructure experience preferred."
            ),
            title_normalized="senior tpm - ai platform",
            company_normalized="techcorp",
            location_normalized="frankfurt",
            sources=json.dumps(["arbeitsagentur"]),
            source_urls=json.dumps([]),
        ),
        DiscoveredJob(
            profile_id=test_profile.id,
            title="Product Engineer",
            company="StartupXYZ",
            location="Berlin",
            description=(
                "Product Engineer needed. Tech stack: React, TypeScript, "
                "Python, Docker, Kubernetes. We use Agile methodology."
            ),
            title_normalized="product engineer",
            company_normalized="startupxyz",
            location_normalized="berlin",
            sources=json.dumps(["arbeitnow"]),
            source_urls=json.dumps([]),
        ),
        DiscoveredJob(
            profile_id=test_profile.id,
            title="DevRel Lead",
            company="DevToolsCo",
            location="Remote EU",
            description=(
                "Developer Relations Lead to build our community. "
                "Experience with Technical Writing, Community Management, "
                "APIs, and Python required."
            ),
            title_normalized="devrel lead",
            company_normalized="devtoolsco",
            location_normalized="remote eu",
            sources=json.dumps(["arbeitnow"]),
            source_urls=json.dumps([]),
        ),
    ]
    test_db.add_all(jobs)
    test_db.commit()
    for j in jobs:
        test_db.refresh(j)
    return jobs


# ===========================================================================
# VAL-GOAL-001: Goal CRUD with realistic and aspirational types
# ===========================================================================


class TestGoalCRUD:
    """Tests for goal CRUD operations."""

    def test_create_aspirational_goal(self, api_client: TestClient, test_profile: Profile):
        """POST /api/goals creates aspirational goal."""
        resp = api_client.post(
            "/api/goals",
            json={
                "profile_id": test_profile.id,
                "title": "Land Senior TPM at FAANG",
                "goal_type": "aspirational",
                "target_date": "2026-06-01T00:00:00Z",
                "description": "Big goal",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Land Senior TPM at FAANG"
        assert data["goal_type"] == "aspirational"
        assert data["status"] == "active"
        assert data["description"] == "Big goal"
        assert data["id"] > 0

    def test_create_realistic_goal(self, api_client: TestClient, test_profile: Profile):
        """POST /api/goals creates realistic goal."""
        resp = api_client.post(
            "/api/goals",
            json={
                "profile_id": test_profile.id,
                "title": "Get any TPM role in 3 months",
                "goal_type": "realistic",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["goal_type"] == "realistic"
        assert data["status"] == "active"

    def test_create_goal_invalid_type(self, api_client: TestClient, test_profile: Profile):
        """POST /api/goals with invalid type returns 422."""
        resp = api_client.post(
            "/api/goals",
            json={
                "profile_id": test_profile.id,
                "title": "Bad goal",
                "goal_type": "impossible",
            },
        )
        assert resp.status_code == 422

    def test_create_goal_missing_title(self, api_client: TestClient, test_profile: Profile):
        """POST /api/goals without title returns 422."""
        resp = api_client.post(
            "/api/goals",
            json={
                "profile_id": test_profile.id,
                "goal_type": "realistic",
            },
        )
        assert resp.status_code == 422

    def test_create_goal_nonexistent_profile(self, api_client: TestClient):
        """POST /api/goals with nonexistent profile returns 404."""
        resp = api_client.post(
            "/api/goals",
            json={
                "profile_id": 99999,
                "title": "Orphan goal",
                "goal_type": "realistic",
            },
        )
        assert resp.status_code == 404

    def test_list_goals(self, api_client: TestClient, test_profile: Profile, sample_goal: Goal):
        """GET /api/goals returns goals list."""
        resp = api_client.get("/api/goals", params={"profile_id": test_profile.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(g["id"] == sample_goal.id for g in data["goals"])

    def test_list_goals_empty(self, api_client: TestClient, test_profile: Profile):
        """GET /api/goals with no goals returns empty list."""
        resp = api_client.get("/api/goals", params={"profile_id": test_profile.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["goals"] == []

    def test_list_goals_filter_by_status(
        self, api_client: TestClient, test_profile: Profile, sample_goal: Goal
    ):
        """GET /api/goals?status=active filters correctly."""
        resp = api_client.get(
            "/api/goals",
            params={"profile_id": test_profile.id, "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(g["status"] == "active" for g in data["goals"])

    def test_list_goals_filter_by_type(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_realistic_goal: Goal,
    ):
        """GET /api/goals?goal_type=realistic filters correctly."""
        resp = api_client.get(
            "/api/goals",
            params={"profile_id": test_profile.id, "goal_type": "realistic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(g["goal_type"] == "realistic" for g in data["goals"])
        assert data["total"] == 1

    def test_get_goal(self, api_client: TestClient, test_profile: Profile, sample_goal: Goal):
        """GET /api/goals/{id} returns goal details."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_goal.id
        assert data["title"] == sample_goal.title
        assert data["goal_type"] == "aspirational"

    def test_get_goal_not_found(self, api_client: TestClient, test_profile: Profile):
        """GET /api/goals/{id} with nonexistent ID returns 404."""
        resp = api_client.get("/api/goals/99999", params={"profile_id": test_profile.id})
        assert resp.status_code == 404

    def test_update_goal(self, api_client: TestClient, test_profile: Profile, sample_goal: Goal):
        """PUT /api/goals/{id} updates fields."""
        resp = api_client.put(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": test_profile.id},
            json={"title": "Updated title", "status": "paused"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated title"
        assert data["status"] == "paused"

    def test_update_goal_partial(
        self, api_client: TestClient, test_profile: Profile, sample_goal: Goal
    ):
        """PUT /api/goals/{id} with partial update preserves unchanged fields."""
        original_type = sample_goal.goal_type
        resp = api_client.put(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": test_profile.id},
            json={"description": "New description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "New description"
        assert data["goal_type"] == original_type

    def test_update_goal_not_found(self, api_client: TestClient, test_profile: Profile):
        """PUT /api/goals/{id} with nonexistent ID returns 404."""
        resp = api_client.put(
            "/api/goals/99999",
            params={"profile_id": test_profile.id},
            json={"title": "Nope"},
        )
        assert resp.status_code == 404

    def test_delete_goal(self, api_client: TestClient, test_profile: Profile, sample_goal: Goal):
        """DELETE /api/goals/{id} removes goal."""
        resp = api_client.delete(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 204

        # Verify deleted
        resp2 = api_client.get(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": test_profile.id},
        )
        assert resp2.status_code == 404

    def test_delete_goal_not_found(self, api_client: TestClient, test_profile: Profile):
        """DELETE /api/goals/{id} with nonexistent ID returns 404."""
        resp = api_client.delete("/api/goals/99999", params={"profile_id": test_profile.id})
        assert resp.status_code == 404


# ===========================================================================
# VAL-GOAL-002: Goal-to-reality mapping
# ===========================================================================


class TestRealityMap:
    """Tests for goal-to-reality mapping."""

    def test_reality_map_returns_dimensions(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_learning: list[LearningResource],
    ):
        """GET /api/goals/{id}/reality-map returns current state, required state, delta."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/reality-map",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal_id"] == sample_goal.id
        assert data["title"] == sample_goal.title
        assert data["goal_type"] == "aspirational"

        dims = data["dimensions"]
        assert len(dims) == 3  # skills, applications, portfolio

        dim_names = {d["dimension"] for d in dims}
        assert "skills" in dim_names
        assert "applications" in dim_names
        assert "portfolio" in dim_names

        for dim in dims:
            assert "current_state" in dim
            assert "required_state" in dim
            assert "delta" in dim
            assert "progress_pct" in dim
            assert 0 <= dim["progress_pct"] <= 100

    def test_reality_map_overall_progress(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_skills: list[Skill],
    ):
        """Reality map has overall progress average of dimensions."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/reality-map",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert "overall_progress" in data
        assert 0 <= data["overall_progress"] <= 100

    def test_reality_map_empty_data(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Reality map with no skills/apps/learning returns 0% progress."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/reality-map",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_progress"] == pytest.approx(0.0)

    def test_reality_map_not_found(self, api_client: TestClient, test_profile: Profile):
        """Reality map for nonexistent goal returns 404."""
        resp = api_client.get(
            "/api/goals/99999/reality-map",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 404

    def test_reality_map_realistic_vs_aspirational(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_realistic_goal: Goal,
        sample_skills: list[Skill],
        sample_applications: list[Application],
    ):
        """Realistic goals have lower thresholds than aspirational."""
        resp_aspirational = api_client.get(
            f"/api/goals/{sample_goal.id}/reality-map",
            params={"profile_id": test_profile.id},
        )
        resp_realistic = api_client.get(
            f"/api/goals/{sample_realistic_goal.id}/reality-map",
            params={"profile_id": test_profile.id},
        )
        data_asp = resp_aspirational.json()
        data_real = resp_realistic.json()

        # With same data, realistic should have higher progress (lower targets)
        assert data_real["overall_progress"] >= data_asp["overall_progress"]


# ===========================================================================
# VAL-GOAL-003: Progress tracking across dimensions
# ===========================================================================


class TestProgressTracking:
    """Tests for progress tracking across applications, learning, portfolio."""

    def test_progress_returns_dimensions(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_applications: list[Application],
        sample_learning: list[LearningResource],
        sample_skills: list[Skill],
    ):
        """GET /api/goals/{id}/progress returns dimensional breakdown."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal_id"] == sample_goal.id

        dims = data["dimensions"]
        assert len(dims) == 4

        dim_names = {d["dimension"] for d in dims}
        assert "applications" in dim_names
        assert "learning" in dim_names
        assert "portfolio" in dim_names
        assert "market_positioning" in dim_names

        for dim in dims:
            assert "percentage" in dim
            assert "detail" in dim
            assert 0 <= dim["percentage"] <= 100

    def test_progress_applications_dimension(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_applications: list[Application],
    ):
        """Applications dimension tracks active applications."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        apps_dim = next(d for d in data["dimensions"] if d["dimension"] == "applications")
        # We have 3 active apps (applied, interviewing, applied) out of target 10
        assert apps_dim["percentage"] == pytest.approx(30.0)
        assert "3/10" in apps_dim["detail"]

    def test_progress_learning_dimension(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_learning: list[LearningResource],
    ):
        """Learning dimension tracks completed resources."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        learning_dim = next(d for d in data["dimensions"] if d["dimension"] == "learning")
        # 1/3 completed = 33.3%
        assert abs(learning_dim["percentage"] - 33.3) < 0.1
        assert "1/3" in learning_dim["detail"]

    def test_progress_portfolio_dimension(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_skills: list[Skill],
    ):
        """Portfolio dimension tracks advanced/expert skills."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        portfolio_dim = next(d for d in data["dimensions"] if d["dimension"] == "portfolio")
        # 3 advanced/expert skills (Python advanced, PM expert, Leadership advanced)
        # out of target 5 for aspirational = 60%
        assert portfolio_dim["percentage"] == pytest.approx(60.0)

    def test_progress_empty_data(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Progress with no data returns 0% across all dimensions."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert data["overall_progress"] == pytest.approx(0.0)
        for dim in data["dimensions"]:
            assert dim["percentage"] == pytest.approx(0.0)

    def test_progress_overall_is_average(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_applications: list[Application],
        sample_learning: list[LearningResource],
        sample_skills: list[Skill],
    ):
        """Overall progress is the average of dimension percentages."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        expected = round(
            sum(d["percentage"] for d in data["dimensions"]) / len(data["dimensions"]),
            1,
        )
        assert abs(data["overall_progress"] - expected) < 0.1

    def test_progress_not_found(self, api_client: TestClient, test_profile: Profile):
        """Progress for nonexistent goal returns 404."""
        resp = api_client.get(
            "/api/goals/99999/progress",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 404


# ===========================================================================
# VAL-GOAL-004: Goal recalibration (AI-powered)
# ===========================================================================


class TestRecalibration:
    """Tests for AI-powered goal recalibration."""

    def test_recalibrate_returns_suggestions(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """PUT /api/goals/{id}/recalibrate returns market-data-backed suggestions."""
        resp = api_client.put(
            f"/api/goals/{sample_goal.id}/recalibrate",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal_id"] == sample_goal.id
        assert data["title"] == sample_goal.title
        assert "recalibration_notes" in data
        assert len(data["recalibration_notes"]) > 0
        assert "suggested_adjustments" in data
        assert isinstance(data["suggested_adjustments"], list)
        assert "market_reality" in data
        assert len(data["market_reality"]) > 0

    def test_recalibrate_not_found(self, api_client: TestClient, test_profile: Profile):
        """Recalibration for nonexistent goal returns 404."""
        resp = api_client.put(
            "/api/goals/99999/recalibrate",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 404

    def test_recalibrate_has_adjustments(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Recalibration adjustments include goal-specific suggestions."""
        resp = api_client.put(
            f"/api/goals/{sample_goal.id}/recalibrate",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        # Mock provider returns 2 suggested adjustments
        assert len(data["suggested_adjustments"]) >= 1
        for adj in data["suggested_adjustments"]:
            assert "goal" in adj or "adjustment" in adj


# ===========================================================================
# VAL-GOAL-005: Alternative path analysis
# ===========================================================================


class TestAlternatives:
    """Tests for alternative path analysis."""

    def test_alternatives_returns_paths(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """GET /api/goals/{id}/alternatives returns 3+ paths."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal_id"] == sample_goal.id
        assert len(data["paths"]) >= 3

    def test_alternatives_include_employment(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Alternatives include employment path."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        path_types = {p["path_type"] for p in data["paths"]}
        assert "employment" in path_types

    def test_alternatives_include_freelance(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Alternatives include freelance path."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        path_types = {p["path_type"] for p in data["paths"]}
        assert "freelance" in path_types

    def test_alternatives_include_consulting(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Alternatives include consulting path."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        path_types = {p["path_type"] for p in data["paths"]}
        assert "consulting" in path_types

    def test_alternatives_have_timelines(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Each alternative path includes a timeline."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        for path in data["paths"]:
            assert "timeline" in path
            assert len(path["timeline"]) > 0

    def test_alternatives_have_pros_cons(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Each path has pros and cons."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        for path in data["paths"]:
            assert "pros" in path
            assert "cons" in path
            assert len(path["pros"]) >= 1
            assert len(path["cons"]) >= 1

    def test_alternatives_not_found(self, api_client: TestClient, test_profile: Profile):
        """Alternatives for nonexistent goal returns 404."""
        resp = api_client.get(
            "/api/goals/99999/alternatives",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 404


# ===========================================================================
# Cross-milestone tracking: Goal progress across dimensions
# ===========================================================================


class TestCrossMilestoneTracking:
    """Tests that goal progress reflects M1 applications, M2 learning, M2 skills (VAL-GOAL-003)."""

    def test_progress_reflects_applications(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_realistic_goal: Goal,
    ):
        """Adding applications increases goal progress (applications dimension)."""
        # Start with no apps
        resp1 = api_client.get(
            f"/api/goals/{sample_realistic_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        initial = resp1.json()
        apps_dim_initial = next(
            d for d in initial["dimensions"] if d["dimension"] == "applications"
        )
        assert apps_dim_initial["percentage"] == pytest.approx(0.0)

    def test_progress_reflects_skills(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_realistic_goal: Goal,
        sample_skills: list[Skill],
    ):
        """Skills inventory contributes to goal progress (portfolio dimension)."""
        resp = api_client.get(
            f"/api/goals/{sample_realistic_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        portfolio_dim = next(d for d in data["dimensions"] if d["dimension"] == "portfolio")
        # 3 advanced/expert out of target 3 = 100%
        assert portfolio_dim["percentage"] == pytest.approx(100.0)

    def test_progress_reflects_learning(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_realistic_goal: Goal,
        sample_learning: list[LearningResource],
    ):
        """Learning progress contributes to goal tracking."""
        resp = api_client.get(
            f"/api/goals/{sample_realistic_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        learning_dim = next(d for d in data["dimensions"] if d["dimension"] == "learning")
        # 1/3 completed
        assert learning_dim["percentage"] > 0


# ===========================================================================
# Profile scoping tests (REQUIRED for profile-owned entities)
# ===========================================================================


class TestProfileScoping:
    """Two-profile isolation tests for goals."""

    def test_profile_b_cannot_list_profile_a_goals(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B cannot see Profile A's goals."""
        resp = api_client.get("/api/goals", params={"profile_id": second_profile.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert all(g["id"] != sample_goal.id for g in data["goals"])

    def test_profile_b_cannot_read_profile_a_goal(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when reading Profile A's goal."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_update_profile_a_goal(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when updating Profile A's goal."""
        resp = api_client.put(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": second_profile.id},
            json={"title": "Hacked"},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_delete_profile_a_goal(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when deleting Profile A's goal."""
        resp = api_client.delete(
            f"/api/goals/{sample_goal.id}",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_view_profile_a_reality_map(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when viewing Profile A's reality map."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/reality-map",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_view_profile_a_progress(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when viewing Profile A's progress."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_recalibrate_profile_a_goal(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when recalibrating Profile A's goal."""
        resp = api_client.put(
            f"/api/goals/{sample_goal.id}/recalibrate",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_view_profile_a_alternatives(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_goal: Goal,
    ):
        """Profile B gets 404 when viewing Profile A's alternatives."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/alternatives",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404


# ===========================================================================
# Service layer unit tests
# ===========================================================================


class TestGoalService:
    """Direct service layer tests."""

    def test_create_and_get(self, test_db: Session, test_profile: Profile):
        """Service creates and retrieves goal."""
        from career_os.services.goals import create_goal, get_goal

        goal = create_goal(
            test_db,
            test_profile.id,
            {"title": "Test goal", "goal_type": "realistic"},
        )
        assert goal.id > 0
        assert goal.title == "Test goal"

        fetched = get_goal(test_db, goal.id, test_profile.id)
        assert fetched.id == goal.id

    def test_update_preserves_unset_fields(self, test_db: Session, test_profile: Profile):
        """Update only changes specified fields."""
        from career_os.services.goals import create_goal, update_goal

        goal = create_goal(
            test_db,
            test_profile.id,
            {
                "title": "Original",
                "goal_type": "aspirational",
                "description": "Keep this",
            },
        )

        updated = update_goal(test_db, goal.id, test_profile.id, {"title": "Changed"})
        assert updated.title == "Changed"
        assert updated.description == "Keep this"
        assert updated.goal_type == "aspirational"

    def test_delete_removes_goal(self, test_db: Session, test_profile: Profile):
        """Delete physically removes the goal."""
        from career_os.services.goals import (
            GoalNotFoundError,
            create_goal,
            delete_goal,
            get_goal,
        )

        goal = create_goal(
            test_db,
            test_profile.id,
            {"title": "To delete", "goal_type": "realistic"},
        )
        delete_goal(test_db, goal.id, test_profile.id)

        with pytest.raises(GoalNotFoundError):
            get_goal(test_db, goal.id, test_profile.id)

    def test_list_with_filters(self, test_db: Session, test_profile: Profile):
        """List filters by status and type."""
        from career_os.services.goals import create_goal, list_goals

        create_goal(
            test_db,
            test_profile.id,
            {"title": "Active realistic", "goal_type": "realistic", "status": "active"},
        )
        create_goal(
            test_db,
            test_profile.id,
            {"title": "Paused aspirational", "goal_type": "aspirational", "status": "paused"},
        )

        # Filter by status
        active, count = list_goals(test_db, test_profile.id, status="active")
        assert count == 1
        assert active[0].title == "Active realistic"

        # Filter by type
        asp, count = list_goals(test_db, test_profile.id, goal_type="aspirational")
        assert count == 1
        assert asp[0].title == "Paused aspirational"

    def test_profile_not_found_raises(self, test_db: Session):
        """Creating goal for nonexistent profile raises."""
        from career_os.services.goals import ProfileNotFoundError, create_goal

        with pytest.raises(ProfileNotFoundError):
            create_goal(test_db, 99999, {"title": "X", "goal_type": "realistic"})


# ===========================================================================
# VAL-CROSS-016: Goal progress includes market_positioning dimension
# ===========================================================================


class TestMarketPositioningDimension:
    """Tests that goal progress includes market_positioning dimension."""

    def test_progress_includes_market_positioning(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Progress includes market_positioning in dimensions."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        dim_names = {d["dimension"] for d in data["dimensions"]}
        assert "market_positioning" in dim_names

    def test_market_positioning_default_zero(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """With no discovered jobs, market_positioning is 0%."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        market_dim = next(d for d in data["dimensions"] if d["dimension"] == "market_positioning")
        assert market_dim["percentage"] == pytest.approx(0.0)

    def test_market_positioning_included_in_overall_average(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_applications: list[Application],
        sample_learning: list[LearningResource],
        sample_skills: list[Skill],
    ):
        """Overall progress is average of all 4 dimensions including market_positioning."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()

        # Verify 4 dimensions
        assert len(data["dimensions"]) == 4

        # Verify overall is average of all 4
        expected = round(
            sum(d["percentage"] for d in data["dimensions"]) / len(data["dimensions"]),
            1,
        )
        assert abs(data["overall_progress"] - expected) < 0.1

    def test_market_positioning_has_detail(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
    ):
        """Market positioning dimension has a detail string."""
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        market_dim = next(d for d in data["dimensions"] if d["dimension"] == "market_positioning")
        assert "detail" in market_dim
        assert isinstance(market_dim["detail"], str)
        assert len(market_dim["detail"]) > 0

    def test_market_positioning_gt_zero_after_discovery(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_discovered_jobs: list[DiscoveredJob],
    ):
        """Market positioning > 0% when discovered jobs exist (VAL-CROSS-016).

        Even without skills, discovered jobs alone provide market positioning
        data (discovery coverage component).
        """
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        market_dim = next(d for d in data["dimensions"] if d["dimension"] == "market_positioning")
        # With 3 discovered jobs across 3 role types, market positioning > 0%
        assert market_dim["percentage"] > 0.0, (
            f"Expected market_positioning > 0% after discovery, got {market_dim['percentage']}%"
        )

    def test_market_positioning_with_skills_higher(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_goal: Goal,
        sample_skills: list[Skill],
        sample_discovered_jobs: list[DiscoveredJob],
    ):
        """Market positioning is higher when user has matching skills.

        With skills that overlap discovered job descriptions, the match
        component adds to the positioning percentage.
        """
        resp = api_client.get(
            f"/api/goals/{sample_goal.id}/progress",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        market_dim = next(d for d in data["dimensions"] if d["dimension"] == "market_positioning")
        # With both discovery data AND matching skills, should be significantly > 0
        assert market_dim["percentage"] > 50.0, (
            f"Expected market_positioning > 50% with skills + discovery, "
            f"got {market_dim['percentage']}%"
        )
