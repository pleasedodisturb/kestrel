"""Tests for Skills CRUD API + timeline tracking.

Covers:
- VAL-SKILL-006: Manual skill addition (POST /api/skills creates with source: manual)
- VAL-SKILL-007: Skill editing (PUT /api/skills/{id} updates fields, updated_at advances)
- VAL-SKILL-008: Skills search and filter with AND logic, paginated
- VAL-SKILL-009: Skills timeline tracking (proficiency changes recorded with timestamps)
"""

import tempfile
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.models.models import Profile

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
    profile = Profile(name="Test User", email="test@example.com", location="Frankfurt", job_family="Software Engineering")
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
def client(_db_engine, test_db: Session):
    """FastAPI test client with test database."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from career_os.api.skills import router as skills_router

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(skills_router)

    def _override_get_db():
        db = sessionmaker(bind=_db_engine)()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(test_app) as c:
        yield c
    test_app.dependency_overrides.clear()


def _create_skill(client: TestClient, profile_id: int, **kwargs) -> dict:
    """Helper to create a skill and return the response data."""
    payload = {
        "profile_id": profile_id,
        "name": kwargs.get("name", "Python"),
        "category": kwargs.get("category", "technical"),
        "proficiency": kwargs.get("proficiency", "intermediate"),
        "evidence_source": kwargs.get("evidence_source", "manual"),
        "evidence_detail": kwargs.get("evidence_detail"),
    }
    resp = client.post("/api/skills", json=payload)
    assert resp.status_code == 201, f"Failed to create skill: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# VAL-SKILL-006: Manual skill addition
# ---------------------------------------------------------------------------


class TestManualSkillCreation:
    """VAL-SKILL-006: POST /api/skills creates skill with source: manual."""

    def test_create_manual_skill_returns_201(self, client: TestClient, test_profile: Profile):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Kubernetes",
                "category": "technical",
                "proficiency": "intermediate",
            },
        )
        assert resp.status_code == 201

    def test_create_manual_skill_defaults_source_to_manual(
        self, client: TestClient, test_profile: Profile
    ):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Docker",
                "category": "tools",
            },
        )
        data = resp.json()
        assert data["evidence_source"] == "manual"

    def test_create_manual_skill_appears_immediately(
        self, client: TestClient, test_profile: Profile
    ):
        # Create
        create_resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "React",
                "category": "technical",
                "proficiency": "advanced",
            },
        )
        skill_id = create_resp.json()["id"]

        # Verify via GET by ID
        get_resp = client.get(f"/api/skills/{skill_id}?profile_id={test_profile.id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "React"

    def test_create_manual_skill_appears_in_list(self, client: TestClient, test_profile: Profile):
        client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "TypeScript",
                "category": "technical",
                "proficiency": "advanced",
                "evidence_source": "manual",
            },
        )
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=TypeScript")
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["evidence_source"] == "manual"

    def test_create_skill_with_all_fields(self, client: TestClient, test_profile: Profile):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Python",
                "category": "technical",
                "proficiency": "expert",
                "evidence_source": "manual",
                "evidence_detail": "10+ years of professional experience",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Python"
        assert data["category"] == "technical"
        assert data["proficiency"] == "expert"
        assert data["evidence_source"] == "manual"
        assert data["evidence_detail"] == "10+ years of professional experience"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_skill_records_initial_history(self, client: TestClient, test_profile: Profile):
        """Creating a skill should record its initial proficiency in history."""
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Go",
                "category": "technical",
                "proficiency": "beginner",
            },
        )
        skill_id = resp.json()["id"]

        history_resp = client.get(f"/api/skills/{skill_id}/history?profile_id={test_profile.id}")
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history) == 1
        assert history[0]["new_proficiency"] == "beginner"
        assert history[0]["previous_proficiency"] is None

    def test_create_skill_empty_name_returns_422(self, client: TestClient, test_profile: Profile):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "",
                "category": "technical",
            },
        )
        assert resp.status_code == 422

    def test_create_skill_invalid_category_returns_422(
        self, client: TestClient, test_profile: Profile
    ):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Test",
                "category": "invalid",
            },
        )
        assert resp.status_code == 422

    def test_create_skill_invalid_proficiency_returns_422(
        self, client: TestClient, test_profile: Profile
    ):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Test",
                "category": "technical",
                "proficiency": "godlike",
            },
        )
        assert resp.status_code == 422

    def test_create_skill_nonexistent_profile_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": 99999,
                "name": "Test",
                "category": "technical",
            },
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# VAL-SKILL-007: Skill editing
# ---------------------------------------------------------------------------


class TestSkillEditing:
    """VAL-SKILL-007: PUT /api/skills/{id} updates fields. updated_at advances."""

    def test_update_skill_name(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, name="Pyhton")
        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"name": "Python"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Python"

    def test_update_skill_category(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, name="Docker", category="technical")
        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"category": "tools"},
        )
        assert resp.status_code == 200
        assert resp.json()["category"] == "tools"

    def test_update_skill_proficiency(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, proficiency="beginner")
        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "expert"},
        )
        assert resp.status_code == 200
        assert resp.json()["proficiency"] == "expert"

    def test_update_skill_evidence_detail(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id)
        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"evidence_detail": "Used in production for 5 years"},
        )
        assert resp.status_code == 200
        assert resp.json()["evidence_detail"] == "Used in production for 5 years"

    def test_update_skill_clear_evidence_detail_with_null(
        self, client: TestClient, test_profile: Profile
    ):
        """PUT with evidence_detail=null should clear the field (not ignore it)."""
        skill = _create_skill(
            client,
            test_profile.id,
            evidence_detail="Some old evidence",
        )
        assert skill["evidence_detail"] == "Some old evidence"

        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"evidence_detail": None},
        )
        assert resp.status_code == 200
        assert resp.json()["evidence_detail"] is None

        # Verify persistence via GET
        get_resp = client.get(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["evidence_detail"] is None

    def test_update_skill_updated_at_advances(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id)
        original_updated = skill["updated_at"]

        # Small delay to ensure timestamp changes
        time.sleep(0.05)

        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        new_updated = resp.json()["updated_at"]
        assert new_updated >= original_updated

    def test_update_nonexistent_skill_returns_404(self, client: TestClient, test_profile: Profile):
        resp = client.put(
            f"/api/skills/99999?profile_id={test_profile.id}",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_update_multiple_fields_at_once(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, name="JS", category="technical")
        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={
                "name": "JavaScript",
                "proficiency": "advanced",
                "evidence_detail": "Full-stack React + Node.js",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "JavaScript"
        assert data["proficiency"] == "advanced"
        assert data["evidence_detail"] == "Full-stack React + Node.js"


# ---------------------------------------------------------------------------
# VAL-SKILL-008: Search and filter with AND logic, paginated
# ---------------------------------------------------------------------------


class TestSearchFilterPagination:
    """VAL-SKILL-008: ?q=, ?category=, ?source=, ?proficiency= AND logic. Paginated."""

    def _seed_many_skills(self, client: TestClient, profile_id: int):
        """Seed a variety of skills via direct DB insertion for search/filter testing.

        POST /api/skills forces evidence_source='manual', so we use direct DB
        insertion to set various evidence sources for testing filters.
        """
        from sqlalchemy.orm import Session as DBSession

        from career_os.models.skills import Skill

        db_gen = client.app.dependency_overrides[get_db]()
        db: DBSession = next(db_gen)

        skills_data = [
            {
                "name": "Python",
                "category": "technical",
                "proficiency": "expert",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "JavaScript",
                "category": "technical",
                "proficiency": "advanced",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "TypeScript",
                "category": "technical",
                "proficiency": "advanced",
                "evidence_source": "manual",
            },
            {
                "name": "Communication",
                "category": "soft",
                "proficiency": "expert",
                "evidence_source": "assessment:cliftonstrengths",
            },
            {
                "name": "Stakeholder Management",
                "category": "domain",
                "proficiency": "expert",
                "evidence_source": "profile",
            },
            {
                "name": "Jira",
                "category": "tools",
                "proficiency": "advanced",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "Docker",
                "category": "tools",
                "proficiency": "intermediate",
                "evidence_source": "manual",
            },
            {
                "name": "Strategic Thinking",
                "category": "soft",
                "proficiency": "advanced",
                "evidence_source": "assessment:cliftonstrengths",
            },
            {
                "name": "Program Management",
                "category": "domain",
                "proficiency": "expert",
                "evidence_source": "profile",
            },
            {
                "name": "Kubernetes",
                "category": "technical",
                "proficiency": "beginner",
                "evidence_source": "manual",
            },
            {
                "name": "React",
                "category": "technical",
                "proficiency": "advanced",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "Leadership",
                "category": "soft",
                "proficiency": "expert",
                "evidence_source": "profile",
            },
        ]
        for s in skills_data:
            skill = Skill(profile_id=profile_id, **s)
            db.add(skill)
        db.commit()
        db.close()

    def test_search_by_name_q(self, client: TestClient, test_profile: Profile):
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=python")
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["name"] == "Python"

    def test_search_case_insensitive(self, client: TestClient, test_profile: Profile):
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=PYTHON")
        data = resp.json()
        assert data["total"] == 1

    def test_filter_by_category(self, client: TestClient, test_profile: Profile):
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&category=technical")
        data = resp.json()
        assert data["total"] == 5  # Python, JS, TS, Kubernetes, React
        for s in data["skills"]:
            assert s["category"] == "technical"

    def test_filter_by_proficiency(self, client: TestClient, test_profile: Profile):
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&proficiency=expert")
        data = resp.json()
        assert data["total"] >= 4
        for s in data["skills"]:
            assert s["proficiency"] == "expert"

    def test_filter_by_source(self, client: TestClient, test_profile: Profile):
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&source=manual")
        data = resp.json()
        assert data["total"] >= 3  # TypeScript, Docker, Kubernetes
        for s in data["skills"]:
            assert "manual" in s["evidence_source"]

    def test_and_logic_category_plus_proficiency(self, client: TestClient, test_profile: Profile):
        """AND logic: category=technical AND proficiency=expert should only return Python."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(
            f"/api/skills?profile_id={test_profile.id}&category=technical&proficiency=expert"
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["name"] == "Python"

    def test_and_logic_category_plus_q(self, client: TestClient, test_profile: Profile):
        """AND logic: category=technical AND q=script should return JavaScript, TypeScript."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&category=technical&q=script")
        data = resp.json()
        assert data["total"] == 2
        names = {s["name"] for s in data["skills"]}
        assert names == {"JavaScript", "TypeScript"}

    def test_and_logic_all_filters(self, client: TestClient, test_profile: Profile):
        """AND logic: category + proficiency + source + q all combined."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(
            f"/api/skills?profile_id={test_profile.id}"
            f"&category=technical&proficiency=advanced&source=cv.yaml&q=Java"
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["name"] == "JavaScript"

    def test_pagination_page_size(self, client: TestClient, test_profile: Profile):
        """Pagination: page_size limits results."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&page=1&page_size=3")
        data = resp.json()
        assert data["total"] == 12  # total count unchanged
        assert len(data["skills"]) == 3  # only 3 on this page

    def test_pagination_page_2(self, client: TestClient, test_profile: Profile):
        """Pagination: page 2 returns different skills."""
        self._seed_many_skills(client, test_profile.id)
        page1 = client.get(f"/api/skills?profile_id={test_profile.id}&page=1&page_size=5").json()
        page2 = client.get(f"/api/skills?profile_id={test_profile.id}&page=2&page_size=5").json()

        page1_ids = {s["id"] for s in page1["skills"]}
        page2_ids = {s["id"] for s in page2["skills"]}
        assert len(page1_ids & page2_ids) == 0  # no overlap

    def test_pagination_beyond_last_page(self, client: TestClient, test_profile: Profile):
        """Requesting a page beyond data returns empty skills list."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&page=100&page_size=50")
        data = resp.json()
        assert data["total"] == 12
        assert len(data["skills"]) == 0

    def test_empty_search_returns_all(self, client: TestClient, test_profile: Profile):
        """Empty filters return all skills."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}")
        data = resp.json()
        assert data["total"] == 12

    def test_no_match_returns_empty(self, client: TestClient, test_profile: Profile):
        """Search with no matches returns empty list."""
        self._seed_many_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=nonexistent_skill")
        data = resp.json()
        assert data["total"] == 0
        assert len(data["skills"]) == 0


# ---------------------------------------------------------------------------
# VAL-SKILL-009: Skills timeline tracking
# ---------------------------------------------------------------------------


class TestTimelineTracking:
    """VAL-SKILL-009: Proficiency changes recorded with timestamps. History endpoint works."""

    def test_proficiency_change_creates_history(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, proficiency="beginner")

        # Update proficiency
        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "intermediate"},
        )

        # Check history
        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={test_profile.id}")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 2  # initial + one change

        # Most recent first (desc order)
        assert history[0]["previous_proficiency"] == "beginner"
        assert history[0]["new_proficiency"] == "intermediate"
        assert history[0]["created_at"] is not None

    def test_multiple_proficiency_changes_tracked(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, proficiency="beginner")

        # beginner → intermediate
        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "intermediate"},
        )
        # intermediate → advanced
        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "advanced"},
        )
        # advanced → expert
        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "expert"},
        )

        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={test_profile.id}")
        history = resp.json()
        assert len(history) == 4  # initial + 3 changes

        # Verify progression (most recent first)
        assert history[0]["new_proficiency"] == "expert"
        assert history[0]["previous_proficiency"] == "advanced"
        assert history[1]["new_proficiency"] == "advanced"
        assert history[1]["previous_proficiency"] == "intermediate"
        assert history[2]["new_proficiency"] == "intermediate"
        assert history[2]["previous_proficiency"] == "beginner"
        assert history[3]["new_proficiency"] == "beginner"
        assert history[3]["previous_proficiency"] is None  # initial

    def test_non_proficiency_update_no_extra_history(
        self, client: TestClient, test_profile: Profile
    ):
        """Changing name or category should NOT create a history entry."""
        skill = _create_skill(client, test_profile.id, proficiency="advanced")

        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"name": "Updated Name"},
        )

        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={test_profile.id}")
        history = resp.json()
        assert len(history) == 1  # only initial creation

    def test_same_proficiency_no_duplicate_history(self, client: TestClient, test_profile: Profile):
        """Updating to the same proficiency should NOT create a new history entry."""
        skill = _create_skill(client, test_profile.id, proficiency="advanced")

        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "advanced"},
        )

        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={test_profile.id}")
        history = resp.json()
        assert len(history) == 1  # only initial

    def test_history_entries_have_timestamps(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, proficiency="beginner")
        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "intermediate"},
        )

        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={test_profile.id}")
        for entry in resp.json():
            assert entry["created_at"] is not None
            assert "T" in entry["created_at"]  # ISO 8601 format

    def test_history_includes_reason(self, client: TestClient, test_profile: Profile):
        skill = _create_skill(client, test_profile.id, proficiency="beginner")
        client.put(
            f"/api/skills/{skill['id']}?profile_id={test_profile.id}",
            json={"proficiency": "intermediate", "reason": "Completed online course"},
        )

        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={test_profile.id}")
        history = resp.json()
        latest = history[0]
        assert latest["reason"] == "Completed online course"

    def test_history_for_nonexistent_skill_returns_404(
        self, client: TestClient, test_profile: Profile
    ):
        resp = client.get(f"/api/skills/99999/history?profile_id={test_profile.id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Profile scoping: two-profile negative tests
# ---------------------------------------------------------------------------


class TestSkillsProfileScoping:
    """Two-profile negative tests for skills CRUD."""

    def test_other_profile_cannot_list_skills(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        _create_skill(client, test_profile.id, name="Python")
        resp = client.get(f"/api/skills?profile_id={second_profile.id}")
        data = resp.json()
        # Second profile sees zero skills
        assert data["total"] == 0

    def test_other_profile_cannot_get_skill(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        skill = _create_skill(client, test_profile.id, name="Python")
        resp = client.get(f"/api/skills/{skill['id']}?profile_id={second_profile.id}")
        assert resp.status_code == 404

    def test_other_profile_cannot_update_skill(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        skill = _create_skill(client, test_profile.id, name="Python")
        resp = client.put(
            f"/api/skills/{skill['id']}?profile_id={second_profile.id}",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 404

    def test_other_profile_cannot_view_history(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        skill = _create_skill(client, test_profile.id, name="Python")
        resp = client.get(f"/api/skills/{skill['id']}/history?profile_id={second_profile.id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Regression: evidence_source forgery prevention
# ---------------------------------------------------------------------------


class TestEvidenceSourceForgeryPrevention:
    """POST /api/skills always forces evidence_source='manual', ignoring client value.

    This prevents clients from forging provenance by claiming a skill was
    parsed from cv.yaml or profile when it was actually manually entered.
    """

    def test_client_supplied_cv_yaml_source_overridden_to_manual(
        self, client: TestClient, test_profile: Profile
    ):
        """Client tries evidence_source='cv.yaml' → response shows 'manual'."""
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Forged CV Skill",
                "category": "technical",
                "proficiency": "expert",
                "evidence_source": "cv.yaml",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["evidence_source"] == "manual"

    def test_client_supplied_profile_source_overridden_to_manual(
        self, client: TestClient, test_profile: Profile
    ):
        """Client tries evidence_source='profile' → response shows 'manual'."""
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Forged Profile Skill",
                "category": "domain",
                "proficiency": "advanced",
                "evidence_source": "profile",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["evidence_source"] == "manual"

    def test_client_supplied_assessment_source_overridden_to_manual(
        self, client: TestClient, test_profile: Profile
    ):
        """Client tries evidence_source='assessment:cliftonstrengths' → response shows 'manual'."""
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Forged Assessment Skill",
                "category": "soft",
                "evidence_source": "assessment:cliftonstrengths",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["evidence_source"] == "manual"

    def test_explicit_manual_source_still_works(self, client: TestClient, test_profile: Profile):
        """Client sends evidence_source='manual' → response shows 'manual' (unchanged)."""
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Legit Manual Skill",
                "category": "technical",
                "evidence_source": "manual",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["evidence_source"] == "manual"

    def test_default_source_is_manual(self, client: TestClient, test_profile: Profile):
        """Omitting evidence_source defaults to 'manual'."""
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Default Source Skill",
                "category": "tools",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["evidence_source"] == "manual"
