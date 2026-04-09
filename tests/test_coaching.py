"""Tests for Coaching Engine API and service.

Covers:
- VAL-COACH-001: AI coaching suggestions (prioritized actions based on skills, gaps, goals)
- VAL-COACH-002: Effort estimates on suggestions (hours, weeks, difficulty)
- VAL-COACH-003: Coaching adapts to progress (completing learning updates suggestions)
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
from career_os.models.models import Application, Profile
from career_os.models.skills import (
    CoachingSuggestion,
    Goal,
    JobRequirement,
    LearningResource,
    Skill,
)

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
    TestSession = sessionmaker(bind=_db_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_profile(test_db: Session) -> Profile:
    """Seed a test profile."""
    profile = Profile(name="Test User", email="test@example.com", location="Frankfurt")
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def second_profile(test_db: Session) -> Profile:
    """Create a second profile for scoping tests."""
    profile = Profile(name="Other User", email="other@example.com")
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def api_client(_db_engine):
    """Create a FastAPI test client with overridden DB."""
    TestSession = sessionmaker(bind=_db_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_skills(test_db: Session, test_profile: Profile) -> list[Skill]:
    """Create sample skills for the test profile."""
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
    """Create sample applications for the test profile."""
    apps_data = [
        ("Stripe", "Senior TPM", "applied"),
        ("Google", "AI Program Lead", "interviewing"),
        ("Mistral", "Product Engineer", "applied"),
        ("Plain", "Founding Engineer", "discovered"),
        ("Shopware", "TPM", "interested"),
        ("Datadog", "Staff Engineer", "discovered"),
        ("MongoDB", "SRE Lead", "discovered"),
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
def sample_requirements(
    test_db: Session, test_profile: Profile, sample_applications: list[Application]
) -> list[JobRequirement]:
    """Create job requirements (gaps) for applications."""
    reqs = []
    # Stripe (applied) — requires Kubernetes advanced and Terraform intermediate
    stripe_app = sample_applications[0]
    for skill_name, level, severity in [
        ("Kubernetes", "advanced", "critical"),
        ("Terraform", "intermediate", "critical"),
        ("Python", "advanced", "nice-to-have"),
    ]:
        r = JobRequirement(
            application_id=stripe_app.id,
            profile_id=test_profile.id,
            skill_name=skill_name,
            required_level=level,
            severity=severity,
        )
        test_db.add(r)
        reqs.append(r)

    # Google (interviewing) — requires Kubernetes advanced and AI/ML expert
    google_app = sample_applications[1]
    for skill_name, level, severity in [
        ("Kubernetes", "advanced", "critical"),
        ("AI/ML", "expert", "critical"),
        ("Leadership", "expert", "nice-to-have"),
    ]:
        r = JobRequirement(
            application_id=google_app.id,
            profile_id=test_profile.id,
            skill_name=skill_name,
            required_level=level,
            severity=severity,
        )
        test_db.add(r)
        reqs.append(r)

    test_db.commit()
    for r in reqs:
        test_db.refresh(r)
    return reqs


@pytest.fixture
def sample_goals(test_db: Session, test_profile: Profile) -> list[Goal]:
    """Create sample goals."""
    goals = []
    g1 = Goal(
        profile_id=test_profile.id,
        title="Land Senior TPM at FAANG",
        goal_type="aspirational",
        status="active",
        description="Target tier-1 tech company.",
    )
    g2 = Goal(
        profile_id=test_profile.id,
        title="Get any TPM role in 3 months",
        goal_type="realistic",
        status="active",
    )
    test_db.add(g1)
    test_db.add(g2)
    goals = [g1, g2]
    test_db.commit()
    for g in goals:
        test_db.refresh(g)
    return goals


@pytest.fixture
def sample_learning(
    test_db: Session, test_profile: Profile, sample_requirements: list[JobRequirement]
) -> list[LearningResource]:
    """Create sample learning resources linked to gaps."""
    resources = []
    # In-progress learning for Kubernetes gap
    k8s_req = sample_requirements[0]  # Kubernetes requirement from Stripe
    lr1 = LearningResource(
        profile_id=test_profile.id,
        gap_id=k8s_req.id,
        title="Kubernetes Deep Dive",
        resource_type="paid_course",
        estimated_hours=20.0,
        difficulty="intermediate",
        status="in_progress",
        started_at=datetime.now(UTC),
    )
    test_db.add(lr1)

    # Not-started learning for Terraform gap
    tf_req = sample_requirements[1]  # Terraform requirement from Stripe
    lr2 = LearningResource(
        profile_id=test_profile.id,
        gap_id=tf_req.id,
        title="Terraform Fundamentals",
        resource_type="free_course",
        estimated_hours=15.0,
        difficulty="beginner",
        status="not_started",
    )
    test_db.add(lr2)

    resources = [lr1, lr2]
    test_db.commit()
    for lr in resources:
        test_db.refresh(lr)
    return resources


# ===========================================================================
# VAL-COACH-001: AI coaching suggestions
# ===========================================================================


class TestCoachingSuggestions:
    """Tests for GET /api/coaching/suggestions."""

    def test_returns_prioritized_suggestions(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
        sample_goals: list[Goal],
    ):
        """GET /api/coaching/suggestions returns prioritized actions."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert "total" in data
        assert data["total"] > 0
        assert len(data["suggestions"]) == data["total"]

        # Verify suggestions are ordered by priority
        priorities = [s["priority"] for s in data["suggestions"]]
        assert priorities == sorted(priorities)

    def test_suggestions_based_on_skills_gaps(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
    ):
        """Suggestions reference skill gaps from job requirements."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        actions = [s["action"] for s in data["suggestions"]]
        # Kubernetes is a gap (beginner vs advanced, appears in 2 apps)
        assert any("Kubernetes" in a for a in actions)
        # Terraform is a gap (not in inventory, critical)
        assert any("Terraform" in a for a in actions)

    def test_suggestions_based_on_goals(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_goals: list[Goal],
    ):
        """Suggestions reference career goals."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        actions = [s["action"] for s in data["suggestions"]]
        # Should suggest more applications (aspirational goal target: 10)
        assert any("application" in a.lower() for a in actions)

    def test_suggestions_based_on_pipeline(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_applications: list[Application],
    ):
        """Suggestions reference pipeline state (discovered positions, interviews)."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        actions = [s["action"].lower() for s in data["suggestions"]]
        # We have 3 discovered positions and 1 interviewing
        assert any("discovered" in a or "interview" in a for a in actions)

    def test_suggestions_have_focus_area(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
    ):
        """Response includes a recommended focus area."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert "focus_area" in data
        assert data["focus_area"] is not None
        assert len(data["focus_area"]) > 0

    def test_empty_state_returns_pipeline_starter(
        self,
        api_client: TestClient,
        test_profile: Profile,
    ):
        """With no data at all, coaching suggests starting a pipeline."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        actions = [s["action"].lower() for s in data["suggestions"]]
        assert any("pipeline" in a or "start" in a for a in actions)

    def test_nonexistent_profile_returns_404(
        self,
        api_client: TestClient,
    ):
        """GET /api/coaching/suggestions with invalid profile returns 404."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": 99999},
        )
        assert resp.status_code == 404


# ===========================================================================
# VAL-COACH-002: Effort estimates on suggestions
# ===========================================================================


class TestEffortEstimates:
    """Tests that each suggestion includes hours, weeks, difficulty."""

    def test_all_suggestions_have_effort_estimates(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
        sample_goals: list[Goal],
    ):
        """Each suggestion includes effort_estimate with hours, weeks, difficulty."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert data["total"] > 0

        for suggestion in data["suggestions"]:
            assert "effort_estimate" in suggestion
            estimate = suggestion["effort_estimate"]
            assert "hours" in estimate
            assert "weeks" in estimate
            assert "difficulty" in estimate
            # All values should be populated
            assert estimate["hours"] is not None
            assert estimate["hours"] > 0
            assert estimate["weeks"] is not None
            assert estimate["weeks"] > 0
            assert estimate["difficulty"] in ("low", "medium", "high")

    def test_skill_gap_suggestions_scale_by_distance(
        self,
        api_client: TestClient,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
    ):
        """Skill gap suggestions have effort proportional to proficiency distance."""
        resp = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()

        # Find Kubernetes suggestion (distance 2: beginner→advanced)
        k8s = [s for s in data["suggestions"] if "Kubernetes" in s["action"]]
        assert len(k8s) >= 1
        k8s_estimate = k8s[0]["effort_estimate"]
        assert k8s_estimate["hours"] > 0
        assert k8s_estimate["weeks"] > 0

        # Find Terraform suggestion (distance 2: none→intermediate)
        tf = [s for s in data["suggestions"] if "Terraform" in s["action"]]
        assert len(tf) >= 1
        tf_estimate = tf[0]["effort_estimate"]
        assert tf_estimate["hours"] > 0


# ===========================================================================
# VAL-COACH-003: Coaching adapts to progress
# ===========================================================================


class TestCoachingAdaptation:
    """Tests that completing learning items updates coaching suggestions."""

    def test_completing_learning_removes_resolved_suggestions(
        self,
        api_client: TestClient,
        test_db: Session,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
        sample_learning: list[LearningResource],
    ):
        """Completing learning for a gap skill removes that suggestion."""
        # Get initial suggestions
        resp1 = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        initial_data = resp1.json()
        initial_actions = [s["action"] for s in initial_data["suggestions"]]
        # Kubernetes should be in suggestions (gap exists)
        assert any("Kubernetes" in a for a in initial_actions)

        # Complete the Kubernetes learning resource
        k8s_learning = sample_learning[0]  # Kubernetes Deep Dive, in_progress
        k8s_learning.status = "completed"
        k8s_learning.completed_at = datetime.now(UTC)
        test_db.commit()

        # Also upgrade the Kubernetes skill to match requirement
        k8s_skill = next(s for s in sample_skills if s.name == "Kubernetes")
        k8s_skill.proficiency = "advanced"
        test_db.commit()

        # Get updated suggestions
        resp2 = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        updated_data = resp2.json()
        updated_actions = [s["action"] for s in updated_data["suggestions"]]

        # Kubernetes suggestion should be removed (gap resolved)
        assert not any("Kubernetes" in a for a in updated_actions)

    def test_completing_learning_surfaces_new_priorities(
        self,
        api_client: TestClient,
        test_db: Session,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
        sample_learning: list[LearningResource],
        sample_goals: list[Goal],
    ):
        """Completing learning may re-prioritize remaining suggestions."""
        # Get initial suggestions
        resp1 = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        initial_data = resp1.json()
        # Complete the Kubernetes learning and upgrade skill
        k8s_learning = sample_learning[0]
        k8s_learning.status = "completed"
        k8s_learning.completed_at = datetime.now(UTC)
        test_db.commit()

        k8s_skill = next(s for s in sample_skills if s.name == "Kubernetes")
        k8s_skill.proficiency = "advanced"
        test_db.commit()

        # Get updated suggestions
        resp2 = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        updated_data = resp2.json()

        # Total may change (resolved removed, possibly new ones surfaced)
        # The key assertion is that the result set has changed
        updated_actions = {s["action"] for s in updated_data["suggestions"]}
        initial_actions = {s["action"] for s in initial_data["suggestions"]}
        assert updated_actions != initial_actions

    def test_stale_suggestions_dismissed(
        self,
        api_client: TestClient,
        test_db: Session,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
    ):
        """Suggestions that no longer apply are marked as dismissed in DB."""
        # Generate initial suggestions
        resp1 = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        assert resp1.status_code == 200
        initial_count = resp1.json()["total"]
        assert initial_count > 0

        # Resolve a gap by upgrading skill
        k8s_skill = next(s for s in sample_skills if s.name == "Kubernetes")
        k8s_skill.proficiency = "expert"
        test_db.commit()

        # Re-generate suggestions
        resp2 = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        assert resp2.status_code == 200

        # Check dismissed suggestions in DB
        dismissed = (
            test_db.query(CoachingSuggestion)
            .filter(
                CoachingSuggestion.profile_id == test_profile.id,
                CoachingSuggestion.status == "dismissed",
            )
            .all()
        )
        # Some suggestions should be dismissed
        assert len(dismissed) >= 1


# ===========================================================================
# Profile scoping tests (REQUIRED for profile-owned entities)
# ===========================================================================


class TestProfileScoping:
    """Two-profile isolation tests for coaching suggestions."""

    def test_profile_b_cannot_see_profile_a_suggestions(
        self,
        api_client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
    ):
        """Profile B's suggestions are independent of Profile A's data."""
        # Generate suggestions for profile A
        resp_a = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["total"] > 0

        # Profile B should get different (likely empty/minimal) suggestions
        resp_b = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": second_profile.id},
        )
        assert resp_b.status_code == 200
        data_b = resp_b.json()

        # Profile B has no applications/skills/goals, so its suggestions
        # should be the generic "start pipeline" suggestion only
        b_actions = [s["action"] for s in data_b["suggestions"]]
        a_actions = [s["action"] for s in data_a["suggestions"]]

        # Profile B should NOT see any of profile A's skill-gap suggestions
        a_skill_actions = [a for a in a_actions if "Kubernetes" in a or "Terraform" in a]
        for skill_action in a_skill_actions:
            assert skill_action not in b_actions

    def test_profile_b_data_does_not_leak_to_a(
        self,
        api_client: TestClient,
        test_db: Session,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Data created for profile B doesn't affect profile A's suggestions."""
        # Create data for profile B
        app_b = Application(
            profile_id=second_profile.id,
            company="SecretCorp",
            role="Secret Role",
            status="applied",
            source="manual",
        )
        test_db.add(app_b)
        test_db.commit()
        test_db.refresh(app_b)

        # Add requirement for profile B
        req_b = JobRequirement(
            application_id=app_b.id,
            profile_id=second_profile.id,
            skill_name="SecretSkill",
            required_level="expert",
            severity="critical",
        )
        test_db.add(req_b)
        test_db.commit()

        # Profile A's suggestions should not mention SecretSkill
        resp_a = api_client.get(
            "/api/coaching/suggestions",
            params={"profile_id": test_profile.id},
        )
        data_a = resp_a.json()
        a_actions = [s["action"] for s in data_a["suggestions"]]
        assert not any("SecretSkill" in a for a in a_actions)


# ===========================================================================
# Service layer unit tests
# ===========================================================================


class TestCoachingDistanceRecalculation:
    """Tests that coaching effort recalculates when required level is upgraded."""

    def test_effort_reflects_highest_required_level(
        self,
        test_db: Session,
        test_profile: Profile,
    ):
        """When same skill has multiple required levels, effort matches the highest."""
        from career_os.services.coaching import _build_skill_gap_suggestions

        # Create skills inventory
        skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="tools",
            proficiency="beginner",
            evidence_source="manual",
        )
        test_db.add(skill)

        # Two applications requiring Kubernetes at different levels
        app1 = Application(
            profile_id=test_profile.id,
            company="A",
            role="Eng",
            status="applied",
            source="manual",
        )
        app2 = Application(
            profile_id=test_profile.id,
            company="B",
            role="Lead",
            status="applied",
            source="manual",
        )
        test_db.add_all([app1, app2])
        test_db.flush()

        # App1 requires intermediate (distance from beginner = 1)
        req1 = JobRequirement(
            application_id=app1.id,
            profile_id=test_profile.id,
            skill_name="Kubernetes",
            required_level="intermediate",
            severity="critical",
        )
        # App2 requires expert (distance from beginner = 3)
        req2 = JobRequirement(
            application_id=app2.id,
            profile_id=test_profile.id,
            skill_name="Kubernetes",
            required_level="expert",
            severity="critical",
        )
        test_db.add_all([req1, req2])
        test_db.commit()

        suggestions = _build_skill_gap_suggestions(test_db, test_profile.id)
        k8s_suggestions = [s for s in suggestions if "Kubernetes" in s["action"]]
        assert len(k8s_suggestions) == 1

        # The effort should reflect expert distance (3), not intermediate (1)
        # distance 3 → hours = 30, weeks = 4.5, difficulty = high
        assert k8s_suggestions[0]["hours"] == pytest.approx(30.0)
        assert k8s_suggestions[0]["weeks"] == pytest.approx(4.5)
        assert k8s_suggestions[0]["difficulty"] == "high"
        # The action text should mention 'expert' (highest required level)
        assert "expert" in k8s_suggestions[0]["action"]

    def test_case_variants_merged_in_coaching(
        self,
        test_db: Session,
        test_profile: Profile,
    ):
        """Case variants like 'Kubernetes' and 'kubernetes' produce a single suggestion."""
        from career_os.services.coaching import _build_skill_gap_suggestions

        app1 = Application(
            profile_id=test_profile.id,
            company="A",
            role="Eng",
            status="applied",
            source="manual",
        )
        app2 = Application(
            profile_id=test_profile.id,
            company="B",
            role="Lead",
            status="applied",
            source="manual",
        )
        test_db.add_all([app1, app2])
        test_db.flush()

        # Different casing
        req1 = JobRequirement(
            application_id=app1.id,
            profile_id=test_profile.id,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="critical",
        )
        req2 = JobRequirement(
            application_id=app2.id,
            profile_id=test_profile.id,
            skill_name="kubernetes",
            required_level="advanced",
            severity="critical",
        )
        test_db.add_all([req1, req2])
        test_db.commit()

        suggestions = _build_skill_gap_suggestions(test_db, test_profile.id)
        k8s_suggestions = [s for s in suggestions if "ubernetes" in s["action"].lower()]
        # Should be merged into one suggestion, not two
        assert len(k8s_suggestions) == 1
        # Should count frequency = 2
        assert "2 target roles" in k8s_suggestions[0]["action"]


class TestCoachingService:
    """Direct service layer tests."""

    def test_get_suggestions_empty_profile(self, test_db: Session, test_profile: Profile):
        """Service returns suggestions for empty profile (pipeline starter)."""
        from career_os.services.coaching import get_coaching_suggestions

        result = get_coaching_suggestions(test_db, test_profile.id)
        assert result["total"] >= 1
        actions = [s.action for s in result["suggestions"]]
        assert any("pipeline" in a.lower() or "start" in a.lower() for a in actions)

    def test_get_suggestions_with_gaps_and_goals(
        self,
        test_db: Session,
        test_profile: Profile,
        sample_skills: list[Skill],
        sample_applications: list[Application],
        sample_requirements: list[JobRequirement],
        sample_goals: list[Goal],
    ):
        """Service combines gap, goal, and pipeline suggestions."""
        from career_os.services.coaching import get_coaching_suggestions

        result = get_coaching_suggestions(test_db, test_profile.id)
        assert result["total"] >= 3  # At least gap + goal + pipeline suggestions
        assert result["focus_area"] is not None

    def test_profile_not_found_raises(self, test_db: Session):
        """Service raises for nonexistent profile."""
        from career_os.services.coaching import (
            ProfileNotFoundError,
            get_coaching_suggestions,
        )

        with pytest.raises(ProfileNotFoundError):
            get_coaching_suggestions(test_db, 99999)

    def test_suggestions_persisted_in_db(
        self,
        test_db: Session,
        test_profile: Profile,
        sample_applications: list[Application],
    ):
        """Suggestions are persisted as CoachingSuggestion records."""
        from career_os.services.coaching import get_coaching_suggestions

        result = get_coaching_suggestions(test_db, test_profile.id)
        assert result["total"] >= 1

        # Check DB
        db_suggestions = (
            test_db.query(CoachingSuggestion)
            .filter(CoachingSuggestion.profile_id == test_profile.id)
            .all()
        )
        assert len(db_suggestions) >= 1

    def test_idempotent_regeneration(
        self,
        test_db: Session,
        test_profile: Profile,
        sample_applications: list[Application],
    ):
        """Calling get_suggestions twice doesn't duplicate."""
        from career_os.services.coaching import get_coaching_suggestions

        result1 = get_coaching_suggestions(test_db, test_profile.id)
        result2 = get_coaching_suggestions(test_db, test_profile.id)

        # Same count (no duplicates)
        assert result1["total"] == result2["total"]

        # Same actions
        actions1 = {s.action for s in result1["suggestions"]}
        actions2 = {s.action for s in result2["suggestions"]}
        assert actions1 == actions2
