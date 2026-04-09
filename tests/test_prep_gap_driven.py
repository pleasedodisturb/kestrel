"""Tests for VAL-CROSS-015: Gap-driven interview prep content.

Verifies that interview prep content changes when skill gaps resolve:
- Unresolved gaps produce focused topics, questions, and checklist items
- When a gap closes (distance 0), those topics are omitted or de-emphasized
- Prep content is textually different after a skill upgrade that closes a gap
"""

import os
import tempfile
from datetime import UTC, datetime, timedelta

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
def app_with_gaps(test_db: Session, test_profile: Profile) -> Application:
    """Create an application with 3 requirements: Kubernetes (missing),
    Program Management (partially met), Python (fully met).
    """
    app_obj = Application(
        profile_id=test_profile.id,
        company="TestCorp",
        role="Senior TPM",
        url="https://testcorp.com/jobs/tpm",
        status="interviewing",
    )
    test_db.add(app_obj)
    test_db.flush()

    # Requirements
    reqs = [
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
            skill_name="Program Management",
            required_level="expert",
            severity="critical",
        ),
        JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="Python",
            required_level="intermediate",
            severity="nice-to-have",
        ),
    ]
    for r in reqs:
        test_db.add(r)

    # Skills: Python advanced (meets intermediate req), Program Mgmt advanced
    # (below expert req), Kubernetes missing entirely
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
            name="Program Management",
            category="domain",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
    ]
    for s in skills:
        test_db.add(s)

    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


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
# VAL-CROSS-015: Prep content changes when skill gaps resolve
# ===========================================================================


class TestPrepContentChangesAfterGapResolution:
    """Core test: prep must be textually different after closing a gap."""

    def test_prep_changes_after_kubernetes_skill_added(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
        test_db: Session,
    ):
        """Generate prep with Kubernetes gap → add Kubernetes skill at advanced
        → regenerate → topics/questions/checklist must change.
        """
        # Step 1: Generate prep with Kubernetes gap (missing entirely)
        resp1 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()

        topics1 = [t["topic"] for t in data1["topics"]]
        questions1 = [q["question"] for q in data1["questions"]]
        checklist1 = [c["item"] for c in data1["checklist"]]

        # Verify initial prep includes Kubernetes gap content
        all_text1 = " ".join(topics1 + questions1 + checklist1)
        assert "Kubernetes" in all_text1, "Initial prep should reference Kubernetes gap"

        # Step 2: Add Kubernetes skill at advanced level (closing the gap)
        future = datetime.now(UTC) + timedelta(seconds=5)
        k8s_skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        test_db.add(k8s_skill)
        test_db.flush()
        k8s_skill.updated_at = future
        test_db.commit()

        # Step 3: Regenerate prep (staleness check triggers regeneration)
        resp2 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()

        topics2 = [t["topic"] for t in data2["topics"]]

        # Step 4: Prep content MUST be different
        assert topics1 != topics2, (
            f"Topics should change after gap resolution.\nBefore: {topics1}\nAfter: {topics2}"
        )

    def test_resolved_gap_topics_omitted(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
        test_db: Session,
    ):
        """After closing a gap, topics for that gap should be omitted."""
        # Step 1: Generate initial prep with gaps
        resp1 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data1 = resp1.json()
        topics1 = [t["topic"] for t in data1["topics"]]

        # Should have gap-specific topic for Kubernetes
        k8s_topics = [t for t in topics1 if "Kubernetes" in t]
        assert len(k8s_topics) > 0, "Should have Kubernetes gap topic initially"

        # Step 2: Close the Kubernetes gap
        future = datetime.now(UTC) + timedelta(seconds=5)
        k8s_skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        test_db.add(k8s_skill)
        test_db.flush()
        k8s_skill.updated_at = future
        test_db.commit()

        # Step 3: Regenerate prep
        resp2 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = resp2.json()
        topics2 = [t["topic"] for t in data2["topics"]]

        # Kubernetes-specific gap topic should be gone
        k8s_gap_topics = [t for t in topics2 if "Kubernetes" in t and "Gap" in t]
        assert len(k8s_gap_topics) == 0, (
            f"Kubernetes gap topic should be omitted after gap resolution. Found: {k8s_gap_topics}"
        )

    def test_checklist_changes_after_gap_resolution(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
        test_db: Session,
    ):
        """Checklist items change when gaps resolve."""
        # Step 1: Initial prep
        resp1 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data1 = resp1.json()
        checklist1 = [c["item"] for c in data1["checklist"]]

        # Should have gap-specific checklist items
        k8s_items = [c for c in checklist1 if "Kubernetes" in c]
        assert len(k8s_items) > 0, "Should have Kubernetes checklist item initially"

        # Step 2: Close the gap
        future = datetime.now(UTC) + timedelta(seconds=5)
        k8s_skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        test_db.add(k8s_skill)
        test_db.flush()
        k8s_skill.updated_at = future
        test_db.commit()

        # Step 3: Regenerate
        resp2 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = resp2.json()
        checklist2 = [c["item"] for c in data2["checklist"]]

        assert checklist1 != checklist2, "Checklist should change after gap resolution"

    def test_questions_change_after_gap_resolution(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
        test_db: Session,
    ):
        """Questions change when gaps resolve."""
        # Step 1: Initial prep
        resp1 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data1 = resp1.json()
        questions1 = [q["question"] for q in data1["questions"]]

        # Should have gap-specific questions
        k8s_questions = [q for q in questions1 if "Kubernetes" in q]
        assert len(k8s_questions) > 0, "Should have Kubernetes gap question initially"

        # Step 2: Close the gap
        future = datetime.now(UTC) + timedelta(seconds=5)
        k8s_skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        test_db.add(k8s_skill)
        test_db.flush()
        k8s_skill.updated_at = future
        test_db.commit()

        # Step 3: Regenerate
        resp2 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = resp2.json()
        questions2 = [q["question"] for q in data2["questions"]]

        assert questions1 != questions2, "Questions should change after gap resolution"


class TestGapDrivenTopicGeneration:
    """Test that topic generation is driven by gap distances."""

    def test_unresolved_gaps_produce_gap_topics(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
    ):
        """Unresolved gaps appear as explicit gap topics with distance info."""
        resp = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        topics = [t["topic"] for t in data["topics"]]
        all_text = " ".join(topics)

        # Kubernetes (missing entirely, distance 3) should appear
        assert "Kubernetes" in all_text, "Kubernetes gap should produce a topic"

    def test_met_requirement_not_in_gap_topics(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
    ):
        """Python (met, distance 0) should NOT appear as a gap topic."""
        resp = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        topics = [t["topic"] for t in data["topics"]]

        # Python should not appear as a gap topic
        python_gap_topics = [t for t in topics if "Python" in t and "Gap" in t]
        assert len(python_gap_topics) == 0, (
            f"Python (met requirement) should not appear as gap topic. Found: {python_gap_topics}"
        )

    def test_fewer_gap_topics_when_all_gaps_resolved(
        self,
        client: TestClient,
        test_profile: Profile,
        test_db: Session,
    ):
        """When all gaps are resolved, no gap-specific topics appear."""
        # Create application with one requirement that is already met
        app_obj = Application(
            profile_id=test_profile.id,
            company="AllMetCorp",
            role="Engineer",
            status="applied",
        )
        test_db.add(app_obj)
        test_db.flush()

        req = JobRequirement(
            application_id=app_obj.id,
            profile_id=test_profile.id,
            skill_name="Python",
            required_level="intermediate",
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
        test_db.refresh(app_obj)

        resp = client.get(
            f"/api/applications/{app_obj.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        topics = [t["topic"] for t in data["topics"]]

        # No gap-specific topics should appear
        gap_topics = [t for t in topics if "Gap area:" in t]
        assert len(gap_topics) == 0, (
            f"No gap topics expected when all requirements met. Found: {gap_topics}"
        )

    def test_partial_gap_upgrade_changes_content(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
        test_db: Session,
    ):
        """Upgrading a skill from missing to intermediate (but still gap)
        should change the content (different distance in output).
        """
        # Step 1: Initial prep (Kubernetes missing → distance 3)
        resp1 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data1 = resp1.json()
        topics1 = [t["topic"] for t in data1["topics"]]

        # Step 2: Add Kubernetes at intermediate (still below advanced, distance 1)
        future = datetime.now(UTC) + timedelta(seconds=5)
        k8s_skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="technical",
            proficiency="intermediate",
            evidence_source="manual",
        )
        test_db.add(k8s_skill)
        test_db.flush()
        k8s_skill.updated_at = future
        test_db.commit()

        # Step 3: Regenerate
        resp2 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = resp2.json()
        topics2 = [t["topic"] for t in data2["topics"]]

        # Topics should differ because the distance changed (3 → 1)
        assert topics1 != topics2, (
            f"Topics should change when gap distance changes.\nBefore: {topics1}\nAfter: {topics2}"
        )

        # Kubernetes should still appear since it's still a gap
        k8s_topics = [t for t in topics2 if "Kubernetes" in t]
        assert len(k8s_topics) > 0, "Kubernetes should still appear as gap topic (distance 1)"


class TestGapDrivenQuestionsAndChecklist:
    """Test that questions and checklist items are gap-driven."""

    def test_unresolved_gap_generates_question(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
    ):
        """Unresolved gap generates a specific question about that skill."""
        resp = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        questions = [q["question"] for q in data["questions"]]

        # Should have a question about Kubernetes
        k8s_questions = [q for q in questions if "Kubernetes" in q]
        assert len(k8s_questions) > 0, "Should have a gap-targeted question for Kubernetes"

    def test_unresolved_gap_generates_checklist_item(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
    ):
        """Unresolved gap generates a checklist item to study that skill."""
        resp = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data = resp.json()
        checklist = [c["item"] for c in data["checklist"]]

        # Should have a checklist item for Kubernetes
        k8s_items = [c for c in checklist if "Kubernetes" in c]
        assert len(k8s_items) > 0, "Should have a gap-targeted checklist item for Kubernetes"

    def test_total_prep_time_changes_with_gap_resolution(
        self,
        client: TestClient,
        test_profile: Profile,
        app_with_gaps: Application,
        test_db: Session,
    ):
        """Total prep time changes when a gap is resolved (fewer items)."""
        # Step 1: Initial prep time
        resp1 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data1 = resp1.json()
        total_minutes1 = data1["total_prep_minutes"]

        # Step 2: Close Kubernetes gap
        future = datetime.now(UTC) + timedelta(seconds=5)
        k8s_skill = Skill(
            profile_id=test_profile.id,
            name="Kubernetes",
            category="technical",
            proficiency="advanced",
            evidence_source="manual",
        )
        test_db.add(k8s_skill)
        test_db.flush()
        k8s_skill.updated_at = future
        test_db.commit()

        # Step 3: Regenerate
        resp2 = client.get(
            f"/api/applications/{app_with_gaps.id}/interview-prep",
            params={"profile_id": test_profile.id},
        )
        data2 = resp2.json()
        total_minutes2 = data2["total_prep_minutes"]

        assert total_minutes1 != total_minutes2, (
            f"Total prep minutes should change after gap resolution. "
            f"Before: {total_minutes1}, After: {total_minutes2}"
        )
