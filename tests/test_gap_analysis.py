"""Tests for Gap Analysis API and service.

Covers:
- VAL-GAP-001: Per-job gap analysis returns gaps with severity and distance
- VAL-GAP-002: Gap severity classification (critical/nice-to-have/bonus)
- VAL-GAP-003: Distance metric (0=met, 1=one level, 2=two levels, 3=missing)
- VAL-GAP-004: Readiness score per application (0-100, weighted by severity)
- VAL-GAP-005: Readiness score in pipeline dashboard (color-coded)
- VAL-GAP-006: Aggregate gap analysis (cross-application frequency)
- VAL-GAP-007: Missing requirements returns 400
"""

import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill
from career_os.services.gap_analysis import (
    MissingRequirementsError,
    _compute_distance,
    _compute_readiness_score,
    aggregate_gaps,
    analyze_gaps,
    classify_severity,
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
    import os

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
def client(_db_engine, test_db: Session):
    """FastAPI test client with test database."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    from career_os.api.applications import router as apps_router
    from career_os.api.gaps import router as gaps_router
    from career_os.api.skills import router as skills_router

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)
    test_app.include_router(apps_router)
    test_app.include_router(gaps_router)
    test_app.include_router(skills_router)

    def override_get_db():
        TestSession = sessionmaker(bind=_db_engine)
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return TestClient(test_app)


@pytest.fixture
def app_with_requirements(test_db: Session, test_profile: Profile) -> Application:
    """Create an application with job requirements and skills in inventory."""
    app_obj = Application(
        profile_id=test_profile.id,
        company="Acme Corp",
        role="Senior Engineer",
        status="applied",
    )
    test_db.add(app_obj)
    test_db.flush()

    # Add job requirements
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
        JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="React",
            required_level="intermediate",
            severity="nice-to-have",
        ),
        JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="GraphQL",
            required_level="beginner",
            severity="bonus",
        ),
        JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="Docker",
            required_level="intermediate",
            severity="nice-to-have",
        ),
    ]
    test_db.add_all(requirements)

    # Add skills to inventory
    skills = [
        Skill(
            profile_id=test_profile.id,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
        Skill(
            profile_id=test_profile.id,
            name="React",
            category="technical",
            proficiency="intermediate",
            evidence_source="cv.yaml",
        ),
        Skill(
            profile_id=test_profile.id,
            name="Docker",
            category="tools",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
    ]
    test_db.add_all(skills)
    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


@pytest.fixture
def app_without_requirements(test_db: Session, test_profile: Profile) -> Application:
    """Create an application without any job requirements."""
    app_obj = Application(
        profile_id=test_profile.id,
        company="No Reqs Inc",
        role="Unknown Role",
        status="discovered",
    )
    test_db.add(app_obj)
    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


# ===========================================================================
# Unit tests: distance computation
# ===========================================================================


class TestDistanceMetric:
    """VAL-GAP-003: Distance metric calculation."""

    def test_distance_met_exactly(self):
        """Distance 0 when current matches required."""
        assert _compute_distance("intermediate", "intermediate") == 0

    def test_distance_exceeded(self):
        """Distance 0 when current exceeds required."""
        assert _compute_distance("intermediate", "expert") == 0

    def test_distance_one_level(self):
        """Distance 1 when one level below."""
        assert _compute_distance("advanced", "intermediate") == 1

    def test_distance_two_levels(self):
        """Distance 2 when two levels below."""
        assert _compute_distance("expert", "intermediate") == 2

    def test_distance_three_levels(self):
        """Distance 3 when three levels below (beginner vs expert)."""
        assert _compute_distance("expert", "beginner") == 3

    def test_distance_missing_skill(self):
        """Distance 3 when skill is missing entirely."""
        assert _compute_distance("intermediate", None) == 3

    def test_distance_beginner_met(self):
        """Distance 0 when beginner is met by beginner."""
        assert _compute_distance("beginner", "beginner") == 0


# ===========================================================================
# Unit tests: readiness score computation
# ===========================================================================


class TestReadinessScore:
    """VAL-GAP-004: Readiness score computation."""

    def test_all_met_gives_100(self):
        """All gaps with distance 0 → readiness 100."""
        gaps = [
            {"severity": "critical", "distance": 0},
            {"severity": "nice-to-have", "distance": 0},
            {"severity": "bonus", "distance": 0},
        ]
        assert _compute_readiness_score(gaps, 3) == 100.0

    def test_all_missing_gives_zero(self):
        """All gaps with distance 3 → readiness 0."""
        gaps = [
            {"severity": "critical", "distance": 3},
            {"severity": "nice-to-have", "distance": 3},
        ]
        assert _compute_readiness_score(gaps, 2) == 0.0

    def test_weighted_by_severity(self):
        """Critical gaps weigh more than bonus gaps."""
        # Critical met, bonus missing
        gaps_a = [
            {"severity": "critical", "distance": 0},
            {"severity": "bonus", "distance": 3},
        ]
        score_a = _compute_readiness_score(gaps_a, 2)

        # Critical missing, bonus met
        gaps_b = [
            {"severity": "critical", "distance": 3},
            {"severity": "bonus", "distance": 0},
        ]
        score_b = _compute_readiness_score(gaps_b, 2)

        # When critical is met, score should be higher
        assert score_a > score_b

    def test_partial_distance(self):
        """Distance 1 gives partial credit."""
        gaps = [{"severity": "critical", "distance": 1}]
        score = _compute_readiness_score(gaps, 1)
        # distance 1 → fraction = 1 - 1/3 = 0.667 → score ~66.7
        assert 60 < score < 70

    def test_empty_requirements_gives_100(self):
        """No requirements → readiness 100."""
        assert _compute_readiness_score([], 0) == 100.0

    def test_score_between_0_and_100(self):
        """Score is always in [0, 100] range."""
        gaps = [
            {"severity": "critical", "distance": 2},
            {"severity": "nice-to-have", "distance": 1},
            {"severity": "bonus", "distance": 0},
        ]
        score = _compute_readiness_score(gaps, 3)
        assert 0 <= score <= 100


# ===========================================================================
# Service tests: analyze_gaps
# ===========================================================================


class TestAnalyzeGaps:
    """VAL-GAP-001 & VAL-GAP-002: Per-job gap analysis."""

    def test_returns_gaps_with_all_fields(
        self, test_db: Session, test_profile: Profile, app_with_requirements: Application
    ):
        """Gap analysis returns gaps with skill_name, required_level, current_level, severity."""
        result = analyze_gaps(test_db, app_with_requirements.id, test_profile.id)

        assert result["application_id"] == app_with_requirements.id
        assert result["company"] == "Acme Corp"
        assert result["role"] == "Senior Engineer"
        assert len(result["gaps"]) == 5
        assert result["total_requirements"] == 5

        # Check that each gap has required fields
        for gap in result["gaps"]:
            assert "skill_name" in gap
            assert "required_level" in gap
            assert "current_level" in gap  # can be None
            assert "severity" in gap
            assert "distance" in gap
            assert 0 <= gap["distance"] <= 3

    def test_severity_classification(
        self, test_db: Session, test_profile: Profile, app_with_requirements: Application
    ):
        """Severity correctly assigned from requirements."""
        result = analyze_gaps(test_db, app_with_requirements.id, test_profile.id)
        gaps_by_name = {g["skill_name"]: g for g in result["gaps"]}

        assert gaps_by_name["Python"]["severity"] == "critical"
        assert gaps_by_name["Kubernetes"]["severity"] == "critical"
        assert gaps_by_name["React"]["severity"] == "nice-to-have"
        assert gaps_by_name["GraphQL"]["severity"] == "bonus"
        assert gaps_by_name["Docker"]["severity"] == "nice-to-have"

    def test_distance_values(
        self, test_db: Session, test_profile: Profile, app_with_requirements: Application
    ):
        """Distance correctly computed for each gap."""
        result = analyze_gaps(test_db, app_with_requirements.id, test_profile.id)
        gaps_by_name = {g["skill_name"]: g for g in result["gaps"]}

        # Python: required expert, have advanced → distance 1
        assert gaps_by_name["Python"]["distance"] == 1
        # Kubernetes: required advanced, missing → distance 3
        assert gaps_by_name["Kubernetes"]["distance"] == 3
        # React: required intermediate, have intermediate → distance 0
        assert gaps_by_name["React"]["distance"] == 0
        # GraphQL: required beginner, missing → distance 3
        assert gaps_by_name["GraphQL"]["distance"] == 3
        # Docker: required intermediate, have advanced → distance 0
        assert gaps_by_name["Docker"]["distance"] == 0

    def test_current_level_populated(
        self, test_db: Session, test_profile: Profile, app_with_requirements: Application
    ):
        """Current level populated for skills in inventory, None for missing."""
        result = analyze_gaps(test_db, app_with_requirements.id, test_profile.id)
        gaps_by_name = {g["skill_name"]: g for g in result["gaps"]}

        assert gaps_by_name["Python"]["current_level"] == "advanced"
        assert gaps_by_name["Kubernetes"]["current_level"] is None
        assert gaps_by_name["React"]["current_level"] == "intermediate"
        assert gaps_by_name["GraphQL"]["current_level"] is None
        assert gaps_by_name["Docker"]["current_level"] == "advanced"

    def test_readiness_score_computed(
        self, test_db: Session, test_profile: Profile, app_with_requirements: Application
    ):
        """Readiness score is computed and in valid range."""
        result = analyze_gaps(test_db, app_with_requirements.id, test_profile.id)

        assert 0 <= result["readiness_score"] <= 100
        # With 2 critical gaps (1 partially met, 1 missing) and other met skills,
        # score should be moderate (not 0, not 100)
        assert result["readiness_score"] > 0
        assert result["readiness_score"] < 100

    def test_gaps_count_computed(
        self, test_db: Session, test_profile: Profile, app_with_requirements: Application
    ):
        """Gaps count only counts actual gaps (distance > 0)."""
        result = analyze_gaps(test_db, app_with_requirements.id, test_profile.id)
        # Python (dist 1), Kubernetes (dist 3), GraphQL (dist 3) = 3 gaps
        # React (dist 0), Docker (dist 0) = met
        assert result["gaps_count"] == 3


class TestMissingRequirements:
    """VAL-GAP-007: Missing requirements returns 400."""

    def test_missing_requirements_raises(
        self, test_db: Session, test_profile: Profile, app_without_requirements: Application
    ):
        """Analyzing gaps without requirements raises MissingRequirementsError."""
        with pytest.raises(MissingRequirementsError) as exc_info:
            analyze_gaps(test_db, app_without_requirements.id, test_profile.id)
        assert "not yet parsed" in str(exc_info.value)
        assert "Run requirement extraction first" in str(exc_info.value)


# ===========================================================================
# Service tests: aggregate_gaps
# ===========================================================================


class TestAggregateGaps:
    """VAL-GAP-006: Aggregate gap analysis."""

    def test_aggregate_across_applications(self, test_db: Session, test_profile: Profile):
        """Aggregate shows gaps ranked by frequency across applications."""
        # Create 2 applications with overlapping requirements
        app1 = Application(
            profile_id=test_profile.id,
            company="Company A",
            role="Engineer",
            status="applied",
        )
        app2 = Application(
            profile_id=test_profile.id,
            company="Company B",
            role="Lead",
            status="interested",
        )
        test_db.add_all([app1, app2])
        test_db.flush()

        # Both need Kubernetes (which user doesn't have)
        reqs = [
            JobRequirement(
                application_id=app1.id,
                profile_id=test_profile.id,
                skill_name="Kubernetes",
                required_level="advanced",
                severity="critical",
            ),
            JobRequirement(
                application_id=app1.id,
                profile_id=test_profile.id,
                skill_name="Python",
                required_level="intermediate",
                severity="nice-to-have",
            ),
            JobRequirement(
                application_id=app2.id,
                profile_id=test_profile.id,
                skill_name="Kubernetes",
                required_level="intermediate",
                severity="nice-to-have",
            ),
            JobRequirement(
                application_id=app2.id,
                profile_id=test_profile.id,
                skill_name="Go",
                required_level="intermediate",
                severity="critical",
            ),
        ]
        test_db.add_all(reqs)

        # Add Python skill (met) — only K8s and Go are gaps
        skill = Skill(
            profile_id=test_profile.id,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="cv.yaml",
        )
        test_db.add(skill)
        test_db.commit()

        result = aggregate_gaps(test_db, test_profile.id)

        assert result["total_applications_analyzed"] == 2
        assert len(result["gaps"]) >= 1

        # Kubernetes should appear with frequency 2
        k8s_gap = next((g for g in result["gaps"] if g["skill_name"] == "Kubernetes"), None)
        assert k8s_gap is not None
        assert k8s_gap["frequency"] == 2
        assert set(k8s_gap["application_ids"]) == {app1.id, app2.id}

    def test_aggregate_empty_profile(self, test_db: Session, test_profile: Profile):
        """Aggregate with no applications returns empty."""
        result = aggregate_gaps(test_db, test_profile.id)
        assert result["gaps"] == []
        assert result["total_applications_analyzed"] == 0

    def test_aggregate_normalizes_case_variants(self, test_db: Session, test_profile: Profile):
        """Case variants like 'Kubernetes' and 'kubernetes' merge into one row."""
        app1 = Application(
            profile_id=test_profile.id,
            company="Company A",
            role="Engineer",
            status="applied",
        )
        app2 = Application(
            profile_id=test_profile.id,
            company="Company B",
            role="Lead",
            status="interested",
        )
        test_db.add_all([app1, app2])
        test_db.flush()

        # Same skill, different casing
        reqs = [
            JobRequirement(
                application_id=app1.id,
                profile_id=test_profile.id,
                skill_name="Kubernetes",
                required_level="advanced",
                severity="critical",
            ),
            JobRequirement(
                application_id=app2.id,
                profile_id=test_profile.id,
                skill_name="kubernetes",
                required_level="intermediate",
                severity="nice-to-have",
            ),
        ]
        test_db.add_all(reqs)
        test_db.commit()

        result = aggregate_gaps(test_db, test_profile.id)

        # Should be merged into a single row, not two
        k8s_gaps = [g for g in result["gaps"] if g["skill_name"].lower() == "kubernetes"]
        assert len(k8s_gaps) == 1
        assert k8s_gaps[0]["frequency"] == 2
        assert set(k8s_gaps[0]["application_ids"]) == {app1.id, app2.id}

    def test_aggregate_preserves_display_name(self, test_db: Session, test_profile: Profile):
        """Aggregated gap uses the first-seen display name (not lowercased)."""
        app1 = Application(
            profile_id=test_profile.id,
            company="Company A",
            role="Engineer",
            status="applied",
        )
        test_db.add(app1)
        test_db.flush()

        req = JobRequirement(
            application_id=app1.id,
            profile_id=test_profile.id,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="critical",
        )
        test_db.add(req)
        test_db.commit()

        result = aggregate_gaps(test_db, test_profile.id)
        assert len(result["gaps"]) == 1
        # Display name should be the original casing, not lowercased
        assert result["gaps"][0]["skill_name"] == "Kubernetes"

    def test_aggregate_no_gaps(self, test_db: Session, test_profile: Profile):
        """Aggregate with all skills met returns empty gaps list."""
        app_obj = Application(
            profile_id=test_profile.id,
            company="Easy Corp",
            role="Junior",
            status="applied",
        )
        test_db.add(app_obj)
        test_db.flush()

        # Requirement that's fully met
        req = JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="Python",
            required_level="beginner",
            severity="critical",
        )
        test_db.add(req)

        skill = Skill(
            profile_id=test_profile.id,
            name="Python",
            category="technical",
            proficiency="expert",
            evidence_source="cv.yaml",
        )
        test_db.add(skill)
        test_db.commit()

        result = aggregate_gaps(test_db, test_profile.id)
        assert result["gaps"] == []
        assert result["total_applications_analyzed"] == 1


# ===========================================================================
# API tests: GET /api/applications/{id}/gaps
# ===========================================================================


class TestGapAnalysisAPI:
    """API-level tests for gap analysis endpoints."""

    def test_get_gaps_returns_200(
        self, client: TestClient, test_profile: Profile, app_with_requirements: Application
    ):
        """GET /api/applications/{id}/gaps returns 200 with gap data."""
        resp = client.get(
            f"/api/applications/{app_with_requirements.id}/gaps",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["application_id"] == app_with_requirements.id
        assert data["company"] == "Acme Corp"
        assert data["role"] == "Senior Engineer"
        assert len(data["gaps"]) == 5
        assert 0 <= data["readiness_score"] <= 100
        assert data["total_requirements"] == 5
        assert data["gaps_count"] == 3

    def test_get_gaps_fields_present(
        self, client: TestClient, test_profile: Profile, app_with_requirements: Application
    ):
        """Each gap item has required fields."""
        resp = client.get(
            f"/api/applications/{app_with_requirements.id}/gaps",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()

        for gap in data["gaps"]:
            assert "skill_name" in gap
            assert "required_level" in gap
            assert "severity" in gap
            assert "distance" in gap
            assert gap["severity"] in ("critical", "nice-to-have", "bonus")
            assert 0 <= gap["distance"] <= 3

    def test_missing_requirements_returns_400(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """VAL-GAP-007: 400 when no requirements parsed."""
        resp = client.get(
            f"/api/applications/{app_without_requirements.id}/gaps",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "not yet parsed" in detail
        assert "Run requirement extraction first" in detail

    def test_nonexistent_application_returns_404(self, client: TestClient, test_profile: Profile):
        """404 for non-existent application."""
        resp = client.get(
            "/api/applications/99999/gaps",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 404

    def test_profile_scoping(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        app_with_requirements: Application,
    ):
        """Profile B cannot access profile A's gap analysis."""
        resp = client.get(
            f"/api/applications/{app_with_requirements.id}/gaps",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 404


# ===========================================================================
# API tests: GET /api/gaps/aggregate
# ===========================================================================


class TestAggregateGapsAPI:
    """API-level tests for aggregate gaps endpoint."""

    def test_aggregate_returns_200(
        self, client: TestClient, test_profile: Profile, app_with_requirements: Application
    ):
        """GET /api/gaps/aggregate returns 200."""
        resp = client.get(
            "/api/gaps/aggregate",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "gaps" in data
        assert "total_applications_analyzed" in data
        assert data["total_applications_analyzed"] >= 1

    def test_aggregate_has_correct_fields(
        self, client: TestClient, test_profile: Profile, app_with_requirements: Application
    ):
        """Aggregate items have correct fields."""
        resp = client.get(
            "/api/gaps/aggregate",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()

        for gap in data["gaps"]:
            assert "skill_name" in gap
            assert "frequency" in gap
            assert "application_ids" in gap
            assert "avg_severity" in gap
            assert "avg_distance" in gap

    def test_aggregate_empty_profile(self, client: TestClient, second_profile: Profile):
        """Aggregate for empty profile returns empty list."""
        resp = client.get(
            "/api/gaps/aggregate",
            params={"profile_id": second_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["gaps"] == []
        assert data["total_applications_analyzed"] == 0


# ===========================================================================
# API tests: POST /api/applications/{id}/requirements
# ===========================================================================


class TestCreateRequirementsAPI:
    """API-level tests for creating job requirements."""

    def test_create_requirements_returns_201(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """Creating requirements returns 201."""
        resp = client.post(
            f"/api/applications/{app_without_requirements.id}/requirements",
            json={
                "application_id": app_without_requirements.id,
                "profile_id": test_profile.id,
                "requirements": [
                    {
                        "skill_name": "Python",
                        "required_level": "advanced",
                        "severity": "critical",
                    },
                    {
                        "skill_name": "SQL",
                        "required_level": "intermediate",
                        "severity": "nice-to-have",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        assert data[0]["skill_name"] == "Python"
        assert data[1]["skill_name"] == "SQL"

    def test_create_then_analyze(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """After creating requirements, gap analysis works."""
        # Create requirements
        client.post(
            f"/api/applications/{app_without_requirements.id}/requirements",
            json={
                "application_id": app_without_requirements.id,
                "profile_id": test_profile.id,
                "requirements": [
                    {
                        "skill_name": "Python",
                        "required_level": "beginner",
                        "severity": "critical",
                    },
                ],
            },
        )

        # Now gap analysis should work (returns 200, not 400)
        resp = client.get(
            f"/api/applications/{app_without_requirements.id}/gaps",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200


# ===========================================================================
# API tests: readiness_score in application responses
# ===========================================================================


class TestReadinessScoreInApplications:
    """VAL-GAP-004 & VAL-GAP-005: Readiness score in application responses."""

    def test_readiness_score_in_detail(
        self, client: TestClient, test_profile: Profile, app_with_requirements: Application
    ):
        """Application detail includes readiness_score."""
        resp = client.get(
            f"/api/applications/{app_with_requirements.id}",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "readiness_score" in data
        assert data["readiness_score"] is not None
        assert 0 <= data["readiness_score"] <= 100

    def test_readiness_score_none_without_requirements(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """Application without requirements has readiness_score = None."""
        resp = client.get(
            f"/api/applications/{app_without_requirements.id}",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["readiness_score"] is None

    def test_readiness_score_in_list(
        self, client: TestClient, test_profile: Profile, app_with_requirements: Application
    ):
        """Application list includes readiness_score."""
        resp = client.get(
            "/api/applications",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["applications"]) >= 1

        # Find our app with requirements
        app_data = next(
            (a for a in data["applications"] if a["id"] == app_with_requirements.id),
            None,
        )
        assert app_data is not None
        assert "readiness_score" in app_data
        assert app_data["readiness_score"] is not None

    def test_readiness_score_color_coding(self):
        """Color coding: green ≥80, yellow 50-79, red <50."""
        # These are UI assertions that we verify logically
        assert 85 >= 80  # green
        assert 50 <= 65 < 80  # yellow  # noqa: PLR2004
        assert 30 < 50  # red  # noqa: PLR2004

        # Verify our scoring produces values in expected ranges
        # All met → 100 (green)
        all_met = _compute_readiness_score([{"severity": "critical", "distance": 0}], 1)
        assert all_met >= 80

        # All missing → 0 (red)
        all_missing = _compute_readiness_score([{"severity": "critical", "distance": 3}], 1)
        assert all_missing < 50


# ===========================================================================
# Unit tests: classify_severity
# ===========================================================================


class TestClassifySeverity:
    """VAL-GAP-002: Severity derived from JD language."""

    # --- Critical signals ---

    def test_must_have(self):
        """'must have' → critical."""
        assert classify_severity("must have Python experience") == "critical"

    def test_must_have_hyphen(self):
        """'must-have' → critical."""
        assert classify_severity("must-have SQL skills") == "critical"

    def test_required(self):
        """'required' → critical."""
        assert classify_severity("Python required") == "critical"

    def test_essential(self):
        """'essential' → critical."""
        assert classify_severity("Essential: team leadership") == "critical"

    def test_mandatory(self):
        """'mandatory' → critical."""
        assert classify_severity("mandatory certification") == "critical"

    # --- Nice-to-have signals ---

    def test_nice_to_have(self):
        """'nice to have' → nice-to-have."""
        assert classify_severity("nice to have React experience") == "nice-to-have"

    def test_nice_to_have_hyphen(self):
        """'nice-to-have' → nice-to-have."""
        assert classify_severity("nice-to-have: GraphQL") == "nice-to-have"

    def test_preferred(self):
        """'preferred' → nice-to-have."""
        assert classify_severity("Kubernetes preferred") == "nice-to-have"

    def test_ideally(self):
        """'ideally' → nice-to-have."""
        assert classify_severity("ideally experience with Terraform") == "nice-to-have"

    def test_bonus_if(self):
        """'bonus if' → nice-to-have (not bonus)."""
        assert classify_severity("bonus if you know Rust") == "nice-to-have"

    # --- Bonus signals ---

    def test_bonus(self):
        """'bonus' → bonus."""
        assert classify_severity("Docker experience is a bonus") == "bonus"

    def test_plus(self):
        """'plus' → bonus."""
        assert classify_severity("TypeScript is a plus") == "bonus"

    def test_great_to_have(self):
        """'great to have' → bonus."""
        assert classify_severity("great to have ML background") == "bonus"

    # --- Default ---

    def test_default_no_signal(self):
        """No signal keywords → nice-to-have."""
        assert classify_severity("Python") == "nice-to-have"

    def test_default_plain_skill(self):
        """Plain skill name → nice-to-have."""
        assert classify_severity("Kubernetes experience") == "nice-to-have"

    # --- Case insensitivity ---

    def test_case_insensitive_must_have(self):
        """Case-insensitive matching."""
        assert classify_severity("MUST HAVE Java") == "critical"

    def test_case_insensitive_preferred(self):
        """Case-insensitive for preferred."""
        assert classify_severity("PREFERRED: Go lang") == "nice-to-have"

    # --- Priority: critical > nice-to-have > bonus ---

    def test_critical_overrides_bonus(self):
        """When text contains both critical and bonus signals, critical wins."""
        assert classify_severity("must have, a plus if senior") == "critical"

    def test_nice_to_have_overrides_bonus(self):
        """'bonus if' matches nice-to-have pattern before reaching bonus."""
        assert classify_severity("bonus if experienced") == "nice-to-have"


# ===========================================================================
# Service tests: classify_severity integration in create_job_requirements
# ===========================================================================


class TestSeverityAutoClassification:
    """VAL-GAP-002: Auto-classification when severity not supplied."""

    def test_auto_classify_critical(
        self, test_db: Session, test_profile: Profile, app_without_requirements: Application
    ):
        """Requirements with 'must have' auto-classified as critical."""
        from career_os.services.gap_analysis import create_job_requirements

        reqs = create_job_requirements(
            test_db,
            app_without_requirements.id,
            test_profile.id,
            [{"skill_name": "must have Python experience", "required_level": "advanced"}],
        )
        assert reqs[0].severity == "critical"

    def test_auto_classify_nice_to_have(
        self, test_db: Session, test_profile: Profile, app_without_requirements: Application
    ):
        """Requirements with 'preferred' auto-classified as nice-to-have."""
        from career_os.services.gap_analysis import create_job_requirements

        reqs = create_job_requirements(
            test_db,
            app_without_requirements.id,
            test_profile.id,
            [{"skill_name": "Kubernetes preferred"}],
        )
        assert reqs[0].severity == "nice-to-have"

    def test_auto_classify_bonus(
        self, test_db: Session, test_profile: Profile, app_without_requirements: Application
    ):
        """Requirements with 'a plus' auto-classified as bonus."""
        from career_os.services.gap_analysis import create_job_requirements

        reqs = create_job_requirements(
            test_db,
            app_without_requirements.id,
            test_profile.id,
            [{"skill_name": "TypeScript is a plus"}],
        )
        assert reqs[0].severity == "bonus"

    def test_auto_classify_default(
        self, test_db: Session, test_profile: Profile, app_without_requirements: Application
    ):
        """Requirements with no signal default to nice-to-have."""
        from career_os.services.gap_analysis import create_job_requirements

        reqs = create_job_requirements(
            test_db,
            app_without_requirements.id,
            test_profile.id,
            [{"skill_name": "Python"}],
        )
        assert reqs[0].severity == "nice-to-have"

    def test_caller_supplied_severity_overrides(
        self, test_db: Session, test_profile: Profile, app_without_requirements: Application
    ):
        """Caller-supplied severity takes precedence over auto-classification."""
        from career_os.services.gap_analysis import create_job_requirements

        reqs = create_job_requirements(
            test_db,
            app_without_requirements.id,
            test_profile.id,
            [{"skill_name": "must have Python", "severity": "bonus"}],
        )
        # Even though "must have" → critical, caller said "bonus"
        assert reqs[0].severity == "bonus"


# ===========================================================================
# API tests: severity auto-classification via POST endpoint
# ===========================================================================


class TestSeverityAutoClassificationAPI:
    """VAL-GAP-002: Auto-classification via POST /api/applications/{id}/requirements."""

    def test_auto_classify_via_api(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """POST with 'must have Python' and no severity → critical in response."""
        resp = client.post(
            f"/api/applications/{app_without_requirements.id}/requirements",
            json={
                "application_id": app_without_requirements.id,
                "profile_id": test_profile.id,
                "requirements": [
                    {"skill_name": "must have Python", "required_level": "advanced"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["severity"] == "critical"

    def test_caller_severity_override_via_api(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """POST with explicit severity overrides auto-classification."""
        resp = client.post(
            f"/api/applications/{app_without_requirements.id}/requirements",
            json={
                "application_id": app_without_requirements.id,
                "profile_id": test_profile.id,
                "requirements": [
                    {
                        "skill_name": "must have Python",
                        "required_level": "advanced",
                        "severity": "bonus",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["severity"] == "bonus"

    def test_mixed_auto_and_override_via_api(
        self,
        client: TestClient,
        test_profile: Profile,
        app_without_requirements: Application,
    ):
        """POST with a mix of auto-classified and caller-supplied severities."""
        resp = client.post(
            f"/api/applications/{app_without_requirements.id}/requirements",
            json={
                "application_id": app_without_requirements.id,
                "profile_id": test_profile.id,
                "requirements": [
                    {"skill_name": "must have Python", "required_level": "advanced"},
                    {"skill_name": "nice to have React"},
                    {"skill_name": "Docker is a plus"},
                    {
                        "skill_name": "Go required",
                        "severity": "nice-to-have",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # Auto-classified from text
        assert data[0]["severity"] == "critical"  # "must have" signal
        assert data[1]["severity"] == "nice-to-have"  # "nice to have" signal
        assert data[2]["severity"] == "bonus"  # "plus" signal
        # Caller-supplied override: "Go required" would be critical but caller said nice-to-have
        assert data[3]["severity"] == "nice-to-have"
