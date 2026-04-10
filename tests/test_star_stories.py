"""Tests for STAR Story management.

Covers:
- VAL-STAR-001: STAR story CRUD (create, list, view, update, delete)
- VAL-STAR-002: Skill-to-company relevance mapping (recommended stories)
- VAL-STAR-003: Story gap identification
- Profile scoping: two-profile isolation tests
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _db_engine():
    """Create a temporary SQLite database for testing."""
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
        job_family="Senior TPM",
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
def test_application(test_db: Session, test_profile: Profile) -> Application:
    """Create a test application."""
    app_obj = Application(
        profile_id=test_profile.id,
        company="Stripe",
        role="Senior TPM",
        url="https://stripe.com/careers/tpm",
        status="interviewing",
    )
    test_db.add(app_obj)
    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


@pytest.fixture
def second_application(test_db: Session, second_profile: Profile) -> Application:
    """Create an application for the second profile."""
    app_obj = Application(
        profile_id=second_profile.id,
        company="Datadog",
        role="Product Engineer",
        status="applied",
    )
    test_db.add(app_obj)
    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


@pytest.fixture
def application_with_requirements(
    test_db: Session, test_profile: Profile, test_application: Application
) -> Application:
    """Application with parsed job requirements."""
    reqs = [
        JobRequirement(
            application_id=test_application.id,
            profile_id=test_profile.id,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="critical",
        ),
        JobRequirement(
            application_id=test_application.id,
            profile_id=test_profile.id,
            skill_name="Program Management",
            required_level="expert",
            severity="critical",
        ),
        JobRequirement(
            application_id=test_application.id,
            profile_id=test_profile.id,
            skill_name="Python",
            required_level="intermediate",
            severity="nice-to-have",
        ),
        JobRequirement(
            application_id=test_application.id,
            profile_id=test_profile.id,
            skill_name="Stakeholder Communication",
            required_level="advanced",
            severity="nice-to-have",
        ),
    ]
    for r in reqs:
        test_db.add(r)
    test_db.commit()
    return test_application


@pytest.fixture
def sample_story_data() -> dict:
    """Sample STAR story creation data."""
    return {
        "title": "Led Kubernetes Migration at Scale",
        "situation": ("Our company needed to migrate 200+ microservices from VMs to Kubernetes."),
        "task": (
            "As TPM, I was responsible for planning and executing the migration across 5 teams."
        ),
        "action": (
            "Created a phased migration plan, established rollback "
            "procedures, and ran weekly syncs."
        ),
        "result": ("Completed migration 2 weeks ahead of schedule with zero downtime incidents."),
        "skill_tags": ["Kubernetes", "Program Management", "Cross-functional Leadership"],
    }


@pytest.fixture
def client(_db_engine, test_db) -> TestClient:
    """Create a test client with overridden DB dependency."""
    test_session_cls = sessionmaker(bind=_db_engine)

    def _override_get_db():
        session = test_session_cls()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===========================================================================
# VAL-STAR-001: STAR story CRUD
# ===========================================================================


class TestStarStoryCRUD:
    """Tests for STAR story CRUD operations."""

    def test_create_story(
        self,
        client: TestClient,
        test_profile: Profile,
        sample_story_data: dict,
    ):
        """POST /api/star-stories creates a story with all 4 sections and skill tags."""
        response = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json=sample_story_data,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == sample_story_data["title"]
        assert data["situation"] == sample_story_data["situation"]
        assert data["task"] == sample_story_data["task"]
        assert data["action"] == sample_story_data["action"]
        assert data["result"] == sample_story_data["result"]
        assert set(data["skill_tags"]) == set(sample_story_data["skill_tags"])
        assert data["profile_id"] == test_profile.id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_story_empty_tags(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Story can be created with no skill tags."""
        response = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Basic Story",
                "situation": "A situation",
                "task": "A task",
                "action": "An action",
                "result": "A result",
                "skill_tags": [],
            },
        )
        assert response.status_code == 201
        assert response.json()["skill_tags"] == []

    def test_create_story_missing_required_fields_422(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Missing required fields return 422."""
        response = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={"title": "Incomplete Story"},
        )
        assert response.status_code == 422

    def test_create_story_nonexistent_profile_404(
        self,
        client: TestClient,
    ):
        """Creating with nonexistent profile returns 404."""
        response = client.post(
            "/api/star-stories",
            params={"profile_id": 99999},
            json={
                "title": "Test",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )
        assert response.status_code == 404

    def test_list_stories(
        self,
        client: TestClient,
        test_profile: Profile,
        sample_story_data: dict,
    ):
        """GET /api/star-stories lists all stories for a profile."""
        # Create two stories
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json=sample_story_data,
        )
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Second Story",
                "situation": "S2",
                "task": "T2",
                "action": "A2",
                "result": "R2",
                "skill_tags": ["Python"],
            },
        )

        response = client.get(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["stories"]) == 2

    def test_list_stories_empty(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Empty list returns correctly."""
        response = client.get(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["stories"] == []

    def test_get_story_by_id(
        self,
        client: TestClient,
        test_profile: Profile,
        sample_story_data: dict,
    ):
        """GET /api/star-stories/{id} returns a single story."""
        create_resp = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json=sample_story_data,
        )
        story_id = create_resp.json()["id"]

        response = client.get(
            f"/api/star-stories/{story_id}",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == story_id
        assert data["title"] == sample_story_data["title"]
        assert data["situation"] == sample_story_data["situation"]
        assert data["task"] == sample_story_data["task"]
        assert data["action"] == sample_story_data["action"]
        assert data["result"] == sample_story_data["result"]

    def test_get_nonexistent_story_404(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Getting a nonexistent story returns 404."""
        response = client.get(
            "/api/star-stories/99999",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 404

    def test_update_story(
        self,
        client: TestClient,
        test_profile: Profile,
        sample_story_data: dict,
    ):
        """PUT /api/star-stories/{id} updates fields."""
        create_resp = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json=sample_story_data,
        )
        story_id = create_resp.json()["id"]

        update_resp = client.put(
            f"/api/star-stories/{story_id}",
            params={"profile_id": test_profile.id},
            json={"title": "Updated Title", "skill_tags": ["Python", "Docker"]},
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["title"] == "Updated Title"
        assert set(data["skill_tags"]) == {"Python", "Docker"}
        # Other fields unchanged
        assert data["situation"] == sample_story_data["situation"]

    def test_update_nonexistent_story_404(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Updating nonexistent story returns 404."""
        response = client.put(
            "/api/star-stories/99999",
            params={"profile_id": test_profile.id},
            json={"title": "Updated"},
        )
        assert response.status_code == 404

    def test_delete_story(
        self,
        client: TestClient,
        test_profile: Profile,
        sample_story_data: dict,
    ):
        """DELETE /api/star-stories/{id} removes the story."""
        create_resp = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json=sample_story_data,
        )
        story_id = create_resp.json()["id"]

        delete_resp = client.delete(
            f"/api/star-stories/{story_id}",
            params={"profile_id": test_profile.id},
        )
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = client.get(
            f"/api/star-stories/{story_id}",
            params={"profile_id": test_profile.id},
        )
        assert get_resp.status_code == 404

    def test_delete_nonexistent_story_404(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Deleting nonexistent story returns 404."""
        response = client.delete(
            "/api/star-stories/99999",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 404


# ===========================================================================
# VAL-STAR-002: Skill-to-company relevance mapping
# ===========================================================================


class TestRecommendedStories:
    """Tests for recommended stories per application based on skill tag matching."""

    def test_matching_story_recommended(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Stories with matching skill tags are recommended."""
        # Create a story matching 'Kubernetes' and 'Program Management'
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "K8s Migration",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Kubernetes", "Program Management"],
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommended_stories"]) == 1
        rec = data["recommended_stories"][0]
        assert rec["match_count"] == 2
        assert "kubernetes" in [s.lower() for s in rec["matching_skills"]]
        assert "program management" in [s.lower() for s in rec["matching_skills"]]

    def test_non_matching_story_excluded(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Stories without matching skill tags are NOT recommended."""
        # Create a story with unrelated tags
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Unrelated Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Rust", "WebAssembly"],
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommended_stories"]) == 0

    def test_sorted_by_match_count(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Recommended stories sorted by match count descending."""
        # Story matching 1 skill
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Python Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Python"],
            },
        )
        # Story matching 3 skills
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Multi-skill Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Kubernetes", "Python", "Program Management"],
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert len(data["recommended_stories"]) == 2
        first = data["recommended_stories"][0]["match_count"]
        second = data["recommended_stories"][1]["match_count"]
        assert first >= second

    def test_covered_skills_populated(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Response includes list of covered skills."""
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "K8s Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Kubernetes"],
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert "kubernetes" in [s.lower() for s in data["covered_skills"]]

    def test_no_requirements_returns_empty(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
    ):
        """Application with no requirements returns empty recommendations."""
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Python"],
            },
        )

        response = client.get(
            f"/api/applications/{test_application.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommended_stories"]) == 0
        assert data["total_requirements"] == 0

    def test_case_insensitive_matching(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Skill tag matching is case-insensitive."""
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "K8s Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["kubernetes"],  # lowercase, requirement has "Kubernetes"
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert len(data["recommended_stories"]) == 1

    def test_response_includes_application_metadata(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Response includes application_id, company, role."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["application_id"] == application_with_requirements.id
        assert data["company"] == "Stripe"
        assert data["role"] == "Senior TPM"

    def test_nonexistent_application_404(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Nonexistent application returns 404."""
        response = client.get(
            "/api/applications/99999/recommended-stories",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 404


# ===========================================================================
# VAL-STAR-003: Story gap identification
# ===========================================================================


class TestStoryGaps:
    """Tests for story gap identification."""

    def test_all_gaps_when_no_stories(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """All requirements flagged as gaps when no stories exist."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["gap_count"] == 4  # 4 requirements, 0 stories
        assert data["covered_count"] == 0
        assert data["total_requirements"] == 4

    def test_partial_coverage_shows_remaining_gaps(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Story covering some skills reduces gap count."""
        # Create story covering Kubernetes and Python
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "K8s + Python Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Kubernetes", "Python"],
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["covered_count"] == 2
        assert data["gap_count"] == 2  # Program Management and Stakeholder Communication
        gap_names = [g["skill_name"] for g in data["story_gaps"]]
        assert "Program Management" in gap_names
        assert "Stakeholder Communication" in gap_names

    def test_full_coverage_no_gaps(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """When all requirements have stories, gap count is 0."""
        # Cover all 4 requirements across stories
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Technical Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Kubernetes", "Python"],
            },
        )
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Leadership Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["Program Management", "Stakeholder Communication"],
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["gap_count"] == 0
        assert data["covered_count"] == 4
        assert len(data["story_gaps"]) == 0

    def test_gaps_include_create_prompt(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Each gap includes a create prompt with skill name and company."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        for gap in data["story_gaps"]:
            assert "create_prompt" in gap
            assert gap["skill_name"].lower() in gap["create_prompt"].lower()
            assert "Stripe" in gap["create_prompt"]

    def test_gaps_include_severity(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Each gap includes the requirement severity."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        severities = {g["skill_name"]: g["severity"] for g in data["story_gaps"]}
        assert severities.get("Kubernetes") == "critical"
        assert severities.get("Python") == "nice-to-have"

    def test_no_requirements_empty_gaps(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
    ):
        """Application with no requirements returns empty gaps."""
        response = client.get(
            f"/api/applications/{test_application.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["gap_count"] == 0
        assert data["total_requirements"] == 0

    def test_case_insensitive_gap_matching(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Gap matching is case-insensitive."""
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "K8s Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": ["kubernetes"],  # lowercase
            },
        )

        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        gap_names = [g["skill_name"].lower() for g in data["story_gaps"]]
        assert "kubernetes" not in gap_names  # covered by the story

    def test_response_includes_application_metadata(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_requirements: Application,
    ):
        """Response includes application_id, company, role."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["application_id"] == application_with_requirements.id
        assert data["company"] == "Stripe"
        assert data["role"] == "Senior TPM"

    def test_nonexistent_application_404(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Nonexistent application returns 404."""
        response = client.get(
            "/api/applications/99999/story-gaps",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 404


# ===========================================================================
# Profile scoping tests
# ===========================================================================


class TestProfileScoping:
    """Test that STAR story data is fully scoped by profile."""

    def test_profile_b_cannot_see_profile_a_stories(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Profile B cannot list Profile A's stories."""
        # Create story for profile A
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "A's Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )

        # Profile B sees empty list
        response = client.get(
            "/api/star-stories",
            params={"profile_id": second_profile.id},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_profile_b_cannot_get_profile_a_story(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Profile B cannot get Profile A's story by ID."""
        create_resp = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "A's Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )
        story_id = create_resp.json()["id"]

        response = client.get(
            f"/api/star-stories/{story_id}",
            params={"profile_id": second_profile.id},
        )
        assert response.status_code == 404

    def test_profile_b_cannot_update_profile_a_story(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Profile B cannot update Profile A's story."""
        create_resp = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "A's Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )
        story_id = create_resp.json()["id"]

        response = client.put(
            f"/api/star-stories/{story_id}",
            params={"profile_id": second_profile.id},
            json={"title": "Hacked"},
        )
        assert response.status_code == 404

    def test_profile_b_cannot_delete_profile_a_story(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Profile B cannot delete Profile A's story."""
        create_resp = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "A's Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )
        story_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/star-stories/{story_id}",
            params={"profile_id": second_profile.id},
        )
        assert response.status_code == 404

    def test_profile_b_cannot_see_profile_a_recommended_stories(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        application_with_requirements: Application,
    ):
        """Profile B cannot access recommended stories for Profile A's application."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/recommended-stories",
            params={"profile_id": second_profile.id},
        )
        assert response.status_code == 404

    def test_profile_b_cannot_see_profile_a_story_gaps(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        application_with_requirements: Application,
    ):
        """Profile B cannot access story gaps for Profile A's application."""
        response = client.get(
            f"/api/applications/{application_with_requirements.id}/story-gaps",
            params={"profile_id": second_profile.id},
        )
        assert response.status_code == 404

    def test_both_profiles_independent_stories(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Both profiles can create and see their own stories independently."""
        client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "A's Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )
        client.post(
            "/api/star-stories",
            params={"profile_id": second_profile.id},
            json={
                "title": "B's Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )

        resp_a = client.get(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
        )
        resp_b = client.get(
            "/api/star-stories",
            params={"profile_id": second_profile.id},
        )
        assert resp_a.json()["total"] == 1
        assert resp_b.json()["total"] == 1
        assert resp_a.json()["stories"][0]["title"] == "A's Story"
        assert resp_b.json()["stories"][0]["title"] == "B's Story"


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and validation."""

    def test_missing_profile_id_422(
        self,
        client: TestClient,
    ):
        """Missing profile_id query param returns 422."""
        response = client.get("/api/star-stories")
        assert response.status_code == 422

    def test_empty_title_422(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Empty title returns 422."""
        response = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        )
        assert response.status_code == 422

    def test_story_with_many_tags(
        self,
        client: TestClient,
        test_profile: Profile,
    ):
        """Story with many skill tags works correctly."""
        tags = ["Python", "Kubernetes", "Docker", "AWS", "Program Management", "SQL"]
        response = client.post(
            "/api/star-stories",
            params={"profile_id": test_profile.id},
            json={
                "title": "Multi-tag Story",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
                "skill_tags": tags,
            },
        )
        assert response.status_code == 201
        assert set(response.json()["skill_tags"]) == set(tags)


# ===========================================================================
# Fix #4: STAR story update rejects empty required fields
# ===========================================================================


class TestStarStoryUpdateValidation:
    """Test that PUT /api/star-stories/{id} with empty fields returns 422."""

    def _create_story(self, client: TestClient, profile_id: int) -> dict:
        """Helper to create a story for testing."""
        resp = client.post(
            "/api/star-stories",
            params={"profile_id": profile_id},
            json={
                "title": "Test Story",
                "situation": "A situation",
                "task": "A task",
                "action": "An action",
                "result": "A result",
                "skill_tags": ["Python"],
            },
        )
        assert resp.status_code == 201
        return resp.json()

    def test_update_empty_situation_422(self, client: TestClient, test_profile: Profile):
        """PUT with empty situation returns 422."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={"situation": ""},
        )
        assert response.status_code == 422

    def test_update_empty_task_422(self, client: TestClient, test_profile: Profile):
        """PUT with empty task returns 422."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={"task": ""},
        )
        assert response.status_code == 422

    def test_update_empty_action_422(self, client: TestClient, test_profile: Profile):
        """PUT with empty action returns 422."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={"action": ""},
        )
        assert response.status_code == 422

    def test_update_empty_result_422(self, client: TestClient, test_profile: Profile):
        """PUT with empty result returns 422."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={"result": ""},
        )
        assert response.status_code == 422

    def test_update_empty_title_422(self, client: TestClient, test_profile: Profile):
        """PUT with empty title returns 422."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={"title": ""},
        )
        assert response.status_code == 422

    def test_update_null_fields_allowed(self, client: TestClient, test_profile: Profile):
        """PUT with null/missing fields is OK (no change)."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={"skill_tags": ["Python", "Go"]},
        )
        assert response.status_code == 200
        assert "Go" in response.json()["skill_tags"]

    def test_update_non_empty_fields_ok(self, client: TestClient, test_profile: Profile):
        """PUT with valid non-empty fields succeeds."""
        story = self._create_story(client, test_profile.id)
        response = client.put(
            f"/api/star-stories/{story['id']}",
            params={"profile_id": test_profile.id},
            json={
                "situation": "A new situation",
                "task": "A new task",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["situation"] == "A new situation"
        assert data["task"] == "A new task"
