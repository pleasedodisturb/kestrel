"""Tests for Interview Preparation Engine.

Covers:
- VAL-PREP-001: Personalized topic list per application
- VAL-PREP-002: Practice question generation (≥5 tailored, not generic)
- VAL-PREP-003: Prep checklist with time estimates and total
- VAL-PREP-004: Prep progress tracking (persists on revisit)
- VAL-PREP-005: No-research prompt for un-researched companies
- VAL-CROSS-009: Interview prep uses research and gaps
- Profile scoping: two-profile isolation tests
"""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill

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
    profile = Profile(name="Other User", email="other@example.com", job_family="Software Engineering")
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
        notes="Great opportunity in payments infrastructure",
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
def application_with_gaps(
    test_db: Session, test_profile: Profile, test_application: Application
) -> Application:
    """Create an application with job requirements and skills (for gap context)."""
    # Add job requirements
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
    ]
    for r in reqs:
        test_db.add(r)

    # Add some skills (partial coverage)
    skills = [
        Skill(
            profile_id=test_profile.id,
            name="Program Management",
            category="domain",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
        Skill(
            profile_id=test_profile.id,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
    ]
    for s in skills:
        test_db.add(s)

    test_db.commit()
    return test_application


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
# VAL-PREP-001: Personalized topic list per application
# ===========================================================================


class TestPersonalizedTopicList:
    """Test that interview prep returns personalized topic list."""

    def test_topics_returned(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """GET /api/applications/{id}/interview-prep returns topics list."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert "topics" in data
        assert isinstance(data["topics"], list)
        assert len(data["topics"]) > 0

    def test_topics_have_required_fields(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Each topic has topic, relevance, difficulty."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        for topic in data["topics"]:
            assert "topic" in topic
            assert "relevance" in topic
            assert "difficulty" in topic
            assert topic["relevance"] in ("high", "medium", "low")
            assert topic["difficulty"] in ("high", "medium", "low")

    def test_topics_reference_application_context(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Topics are contextualized (not generic empty list)."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        topics = data["topics"]
        # At least one topic should exist with descriptive text
        assert any(len(t["topic"]) > 10 for t in topics)

    def test_topics_with_gap_context(
        self,
        client: TestClient,
        test_profile: Profile,
        application_with_gaps: Application,
    ):
        """Topics should reflect role requirements and skill gaps context."""
        response = client.get(
            f"/api/applications/{application_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["topics"]) > 0


# ===========================================================================
# VAL-PREP-002: Practice question generation (≥5 tailored)
# ===========================================================================


class TestPracticeQuestions:
    """Test that interview prep generates ≥5 tailored practice questions."""

    def test_at_least_five_questions(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Response includes ≥5 practice questions."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert "questions" in data
        assert len(data["questions"]) >= 5, f"Expected ≥5 questions, got {len(data['questions'])}"

    def test_questions_have_required_fields(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Each question has question, category, difficulty."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        for q in data["questions"]:
            assert "question" in q
            assert "category" in q
            assert "difficulty" in q
            assert len(q["question"]) > 10  # Not generic

    def test_questions_are_specific(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Questions are specific to role/company (not generic)."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        questions = data["questions"]
        # At least one question should be over 30 chars (specific, not generic)
        assert any(len(q["question"]) > 30 for q in questions)

    def test_questions_have_varied_categories(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Questions span multiple categories (not all the same)."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        categories = {q["category"] for q in data["questions"]}
        assert len(categories) >= 2, (
            f"Expected ≥2 question categories, got {len(categories)}: {categories}"
        )


# ===========================================================================
# VAL-PREP-003: Prep checklist with time estimates and total
# ===========================================================================


class TestPrepChecklist:
    """Test prep checklist with per-item time estimates."""

    def test_checklist_returned(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Response includes checklist items."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert "checklist" in data
        assert isinstance(data["checklist"], list)
        assert len(data["checklist"]) >= 5, (
            f"Expected ≥5 checklist items, got {len(data['checklist'])}"
        )

    def test_checklist_items_have_time_estimates(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Each checklist item has time_minutes and priority."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        for item in data["checklist"]:
            assert "id" in item
            assert "item" in item
            assert "time_minutes" in item
            assert "priority" in item
            assert isinstance(item["time_minutes"], int)
            assert item["time_minutes"] >= 0
            assert item["priority"] in ("high", "medium", "low")

    def test_total_prep_time_calculated(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Response includes total prep time."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert "total_prep_minutes" in data
        assert "total_prep_hours" in data
        assert data["total_prep_minutes"] > 0
        assert data["total_prep_hours"] > 0

    def test_total_prep_minutes_matches_sum(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Total prep minutes equals sum of item times."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        item_sum = sum(item["time_minutes"] for item in data["checklist"])
        assert data["total_prep_minutes"] == item_sum


# ===========================================================================
# VAL-PREP-004: Prep progress tracking (persists on revisit)
# ===========================================================================


class TestProgressTracking:
    """Test that prep progress persists across sessions."""

    def test_initial_progress_zero(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Initial prep has 0% progress."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["progress_percentage"] == pytest.approx(0.0)
        assert data["completed_items"] == 0

    def test_mark_item_complete(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Marking an item complete updates its state."""
        # Generate prep first
        prep_response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = prep_response.json()
        first_item_id = data["checklist"][0]["id"]

        # Mark item as complete
        update_response = client.patch(
            f"/api/applications/interview-prep/items/{first_item_id}",
            params={"profile_id": test_profile.id},
            json={"completed": True},
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["completed"] is True
        assert updated["completed_at"] is not None

    def test_progress_persists_on_revisit(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Progress state persists when revisiting the prep."""
        # Generate prep
        prep1 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data1 = prep1.json()

        # Mark 2 items complete
        item_ids = [data1["checklist"][0]["id"], data1["checklist"][1]["id"]]
        for item_id in item_ids:
            client.patch(
                f"/api/applications/interview-prep/items/{item_id}",
                params={"profile_id": test_profile.id},
                json={"completed": True},
            )

        # Revisit - progress should persist
        prep2 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = prep2.json()

        assert data2["completed_items"] == 2
        assert data2["progress_percentage"] > 0
        # The specific items should be marked as completed
        completed_ids = {c["id"] for c in data2["checklist"] if c["completed"]}
        assert set(item_ids) == completed_ids

    def test_unmark_item(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Unmarking an item reduces progress."""
        # Generate and complete an item
        prep = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        item_id = prep.json()["checklist"][0]["id"]
        client.patch(
            f"/api/applications/interview-prep/items/{item_id}",
            params={"profile_id": test_profile.id},
            json={"completed": True},
        )

        # Unmark
        update = client.patch(
            f"/api/applications/interview-prep/items/{item_id}",
            params={"profile_id": test_profile.id},
            json={"completed": False},
        )
        assert update.status_code == 200
        assert update.json()["completed"] is False
        assert update.json()["completed_at"] is None

    def test_progress_percentage_calculation(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Progress percentage reflects completed/total ratio."""
        prep = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = prep.json()
        total = data["total_items"]
        assert total > 0

        # Complete one item
        item_id = data["checklist"][0]["id"]
        client.patch(
            f"/api/applications/interview-prep/items/{item_id}",
            params={"profile_id": test_profile.id},
            json={"completed": True},
        )

        # Check progress
        prep2 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = prep2.json()
        expected = round((1 / total) * 100, 1)
        assert data2["progress_percentage"] == expected


# ===========================================================================
# VAL-PREP-005: Un-researched company triggers research prompt
# ===========================================================================


class TestNoResearchPrompt:
    """Test that un-researched companies trigger a research prompt."""

    def test_researched_company_no_prompt(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
        test_db: Session,
    ):
        """Known company with research data doesn't show research prompt."""
        # Seed a research report for Stripe so the gate passes
        from career_os.models.company_research import CompanyResearchReportModel

        report = CompanyResearchReportModel(
            profile_id=test_profile.id,
            company_name="Stripe",
            values_alignment_score=8.5,
            industry_segment="Fintech",
        )
        test_db.add(report)
        test_db.commit()

        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        # Stripe has research data, should be marked as researched
        assert data["company_researched"] is True

    def test_non_empty_company_without_research_triggers_prompt(
        self, client: TestClient, test_profile: Profile, test_db: Session
    ):
        """Company with non-empty name but no research data triggers prompt."""
        app_obj = Application(
            profile_id=test_profile.id,
            company="UnresearchedCorp",
            role="Engineer",
            status="interested",
        )
        test_db.add(app_obj)
        test_db.commit()
        test_db.refresh(app_obj)

        response = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        # No research report exists, should NOT be marked as researched
        assert data["company_researched"] is False
        assert data["research_prompt"] is not None
        assert "research" in data["research_prompt"].lower()

    def test_empty_company_triggers_prompt(
        self, client: TestClient, test_profile: Profile, test_db: Session
    ):
        """Application with empty company name triggers research prompt."""
        app_obj = Application(
            profile_id=test_profile.id,
            company="",
            role="Engineer",
            status="interested",
        )
        test_db.add(app_obj)
        test_db.commit()
        test_db.refresh(app_obj)

        response = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["company_researched"] is False
        assert data["research_prompt"] is not None
        assert "research" in data["research_prompt"].lower()


# ===========================================================================
# Error handling tests
# ===========================================================================


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_nonexistent_application_404(self, client: TestClient, test_profile: Profile):
        """Nonexistent application returns 404."""
        response = client.get(
            "/api/applications/99999/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert response.status_code == 404

    def test_nonexistent_profile_404(self, client: TestClient, test_application: Application):
        """Nonexistent profile returns 404."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": 99999},
        )
        assert response.status_code == 404

    def test_nonexistent_item_404(self, client: TestClient, test_profile: Profile):
        """Updating nonexistent prep item returns 404."""
        response = client.patch(
            "/api/applications/interview-prep/items/99999",
            params={"profile_id": test_profile.id},
            json={"completed": True},
        )
        assert response.status_code == 404

    def test_missing_profile_id_422(self, client: TestClient, test_application: Application):
        """Missing profile_id query param returns 422."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
        )
        assert response.status_code == 422


# ===========================================================================
# Profile scoping tests
# ===========================================================================


class TestProfileScoping:
    """Test that interview prep data is scoped by profile."""

    def test_profile_cannot_see_others_prep(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        test_application: Application,
    ):
        """Profile B cannot access Profile A's application prep."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": second_profile.id},
        )
        assert response.status_code == 404

    def test_profile_cannot_update_others_item(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        test_application: Application,
    ):
        """Profile B cannot update Profile A's prep items."""
        # Generate prep for profile A
        prep = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        item_id = prep.json()["checklist"][0]["id"]

        # Profile B tries to update
        response = client.patch(
            f"/api/applications/interview-prep/items/{item_id}",
            params={"profile_id": second_profile.id},
            json={"completed": True},
        )
        assert response.status_code == 404

    def test_both_profiles_independent_prep(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        test_application: Application,
        second_application: Application,
    ):
        """Both profiles can independently generate prep for their applications."""
        resp1 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        resp2 = client.get(
            f"/api/applications/{second_application.id}/interview-prep",
            params={"profile_id": second_profile.id},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Different application IDs
        assert resp1.json()["application_id"] == test_application.id
        assert resp2.json()["application_id"] == second_application.id


# ===========================================================================
# AI provider failure tests
# ===========================================================================


class TestAIProviderFailure:
    """Test graceful handling when AI provider fails."""

    def test_ai_failure_returns_empty_prep(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
        _db_engine,
    ):
        """When AI provider fails, returns empty but valid prep structure."""
        with patch("career_os.services.interview_prep.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("AI unavailable")
            mock_factory.return_value = mock_provider

            response = client.get(
                f"/api/applications/{test_application.id}/interview-prep",
                params={"profile_id": test_profile.id},
            )

        assert response.status_code == 200
        data = response.json()
        assert "topics" in data
        assert "questions" in data
        assert "checklist" in data
        # Empty but valid
        assert isinstance(data["topics"], list)
        assert isinstance(data["questions"], list)
        assert isinstance(data["checklist"], list)


# ===========================================================================
# Determinism tests
# ===========================================================================


class TestDeterministicResponses:
    """Test that returning existing prep is deterministic."""

    def test_same_application_returns_same_prep(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Revisiting same application returns same prep data."""
        resp1 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        resp2 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        # Topics and questions should be identical (persisted)
        assert resp1.json()["topics"] == resp2.json()["topics"]
        assert resp1.json()["questions"] == resp2.json()["questions"]


# ===========================================================================
# Response metadata tests
# ===========================================================================


class TestResponseMetadata:
    """Test response contains correct metadata."""

    def test_response_includes_application_info(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """Response includes company and role from application."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["application_id"] == test_application.id
        assert data["company"] == "Stripe"
        assert data["role"] == "Senior TPM"

    def test_total_items_matches_checklist_length(
        self, client: TestClient, test_profile: Profile, test_application: Application
    ):
        """total_items field matches checklist length."""
        response = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = response.json()
        assert data["total_items"] == len(data["checklist"])


# ===========================================================================
# Fix #1: Mock prep varies by application company/role
# ===========================================================================


class TestMockPrepVariesByApplication:
    """Test that mock interview prep varies by company/role."""

    def test_different_companies_get_different_topics(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """Different companies produce different prep content."""
        app1 = Application(
            profile_id=test_profile.id,
            company="Stripe",
            role="Senior TPM",
            status="applied",
        )
        app2 = Application(
            profile_id=test_profile.id,
            company="Datadog",
            role="Product Engineer",
            status="applied",
        )
        test_db.add_all([app1, app2])
        test_db.commit()
        test_db.refresh(app1)
        test_db.refresh(app2)

        resp1 = client.get(
            f"/api/applications/{app1.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        resp2 = client.get(
            f"/api/applications/{app2.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # Topics should reference respective companies
        topics1 = [t["topic"] for t in resp1.json()["topics"]]
        topics2 = [t["topic"] for t in resp2.json()["topics"]]

        # At least one topic should mention the specific company
        assert any("Stripe" in t for t in topics1)
        assert any("Datadog" in t for t in topics2)

        # Topics should not be identical
        assert topics1 != topics2

    def test_prep_references_role_in_content(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """Prep content references the specific role."""
        app_obj = Application(
            profile_id=test_profile.id,
            company="Acme",
            role="AI Program Lead",
            status="applied",
        )
        test_db.add(app_obj)
        test_db.commit()
        test_db.refresh(app_obj)

        resp = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Questions should mention the role or company
        questions_text = " ".join(q["question"] for q in data["questions"])
        assert "Acme" in questions_text or "AI Program Lead" in questions_text


# ===========================================================================
# Fix #2: Prep regenerates when skills or research change
# ===========================================================================


class TestPrepFreshnessCheck:
    """Test that prep regenerates when dependent data changes."""

    def test_prep_regenerates_after_company_research_added(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
        test_db: Session,
    ):
        """Regression: generate prep -> create research -> GET prep regenerates.

        _is_prep_stale() must check CompanyResearchReportModel.updated_at
        for the application's company. When research is added/refreshed
        after prep was created, prep should be marked stale and regenerated.
        """
        from career_os.models.company_research import CompanyResearchReportModel

        # Step 1: Generate initial prep (no research exists)
        resp1 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["company_researched"] is False

        # Step 2: Create company research report AFTER prep was generated
        future = datetime.now(UTC) + timedelta(seconds=5)
        report = CompanyResearchReportModel(
            profile_id=test_profile.id,
            company_name=test_application.company,
            report_json='{"tech_stack": ["Python", "Go"]}',
            values_alignment_score=8.0,
            industry_segment="Fintech",
        )
        test_db.add(report)
        test_db.flush()
        # Force future timestamp to ensure it's after the prep session
        report.updated_at = future
        test_db.commit()

        # Step 3: GET prep again — should regenerate (stale detection)
        resp2 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        # Prep should now show company_researched=True (regenerated with research)
        assert data2["company_researched"] is True
        # Research prompt should be gone after regeneration
        assert data2["research_prompt"] is None
        # Topics should be regenerated (new session)
        assert len(data2["topics"]) > 0

    def test_prep_regenerates_after_company_research_updated(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """Prep regenerates when existing company research is refreshed."""
        from career_os.models.company_research import CompanyResearchReportModel
        from career_os.models.interview_prep import InterviewPrepSession

        # Create app and initial research
        app_obj = Application(
            profile_id=test_profile.id,
            company="FreshCorp",
            role="Engineer",
            status="interviewing",
        )
        test_db.add(app_obj)
        report = CompanyResearchReportModel(
            profile_id=test_profile.id,
            company_name="FreshCorp",
            values_alignment_score=6.0,
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(app_obj)

        # Generate prep (with research already present)
        resp1 = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp1.status_code == 200
        assert resp1.json()["company_researched"] is True

        # Record the original session's created_at for comparison
        test_db.expire_all()
        original_session = (
            test_db.query(InterviewPrepSession)
            .filter(
                InterviewPrepSession.application_id == app_obj.id,
                InterviewPrepSession.profile_id == test_profile.id,
            )
            .first()
        )
        assert original_session is not None
        original_created_at = original_session.created_at

        # Update the research report with future timestamp
        future = datetime.now(UTC) + timedelta(seconds=5)
        report.report_json = '{"tech_stack": ["Rust", "Go"]}'
        report.values_alignment_score = 9.0
        report.updated_at = future
        test_db.commit()

        # GET prep again — should regenerate due to research update
        resp2 = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp2.status_code == 200
        assert resp2.json()["company_researched"] is True

        # Verify the session was regenerated (new created_at > original)
        test_db.expire_all()
        new_session = (
            test_db.query(InterviewPrepSession)
            .filter(
                InterviewPrepSession.application_id == app_obj.id,
                InterviewPrepSession.profile_id == test_profile.id,
            )
            .first()
        )
        assert new_session is not None
        assert new_session.created_at > original_created_at, (
            "Prep session should have been regenerated after research update "
            f"(original: {original_created_at}, new: {new_session.created_at})"
        )

    def test_prep_regenerates_after_skill_update(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
        test_db: Session,
    ):
        """Prep regenerates when skills are updated after generation."""
        # Generate initial prep
        resp1 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp1.status_code == 200

        # Add a skill with updated_at in the future
        future = datetime.now(UTC) + timedelta(seconds=5)
        new_skill = Skill(
            profile_id=test_profile.id,
            name="New Skill",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        test_db.add(new_skill)
        test_db.flush()
        # Force future timestamp
        new_skill.updated_at = future
        test_db.commit()

        # Regenerate prep - should get fresh content
        resp2 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp2.status_code == 200
        # The prep was regenerated (new session created)
        new_topics = resp2.json()["topics"]
        assert len(new_topics) > 0

    def test_prep_not_regenerated_when_fresh(
        self,
        client: TestClient,
        test_profile: Profile,
        test_application: Application,
    ):
        """Prep is returned from cache when no data has changed."""
        resp1 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        resp2 = client.get(
            f"/api/applications/{test_application.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        # Should return same persisted data
        assert resp1.json()["topics"] == resp2.json()["topics"]
        assert resp1.json()["questions"] == resp2.json()["questions"]


# ===========================================================================
# Fix #3: Research gate checks actual research data
# ===========================================================================


class TestResearchGateChecksData:
    """Test that the research gate checks actual research presence."""

    def test_unresearched_company_gets_prompt(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """Company with no research report triggers research prompt."""
        app_obj = Application(
            profile_id=test_profile.id,
            company="NoResearchCompany",
            role="Engineer",
            status="applied",
        )
        test_db.add(app_obj)
        test_db.commit()
        test_db.refresh(app_obj)

        resp = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert data["company_researched"] is False
        assert data["research_prompt"] is not None

    def test_researched_company_no_prompt(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """Company with actual research report shows no prompt."""
        from career_os.models.company_research import CompanyResearchReportModel

        app_obj = Application(
            profile_id=test_profile.id,
            company="ResearchedCorp",
            role="Engineer",
            status="applied",
        )
        test_db.add(app_obj)
        report = CompanyResearchReportModel(
            profile_id=test_profile.id,
            company_name="ResearchedCorp",
            values_alignment_score=7.5,
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(app_obj)

        resp = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert data["company_researched"] is True
        assert data["research_prompt"] is None

    def test_research_gate_case_insensitive(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """Research gate matches company name case-insensitively."""
        from career_os.models.company_research import CompanyResearchReportModel

        app_obj = Application(
            profile_id=test_profile.id,
            company="STRIPE",
            role="Engineer",
            status="applied",
        )
        test_db.add(app_obj)
        report = CompanyResearchReportModel(
            profile_id=test_profile.id,
            company_name="stripe",
            values_alignment_score=8.0,
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(app_obj)

        resp = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        assert data["company_researched"] is True
