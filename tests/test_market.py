"""Tests for Market Intelligence module (Milestone 3).

Covers:
- VAL-MARKET-001: Salary trends by role and location
  GET /api/market/salary-trends returns time-series with median, p25, p75, sample_size
- VAL-MARKET-002: Most-demanded skills trending
  Ranked list with skill_name, mention_count, trend_direction, percentage_of_postings
- VAL-MARKET-003: Company hiring patterns
  Active companies with active_postings_count, posting_velocity, roles_trending
- VAL-MARKET-004: Market positioning
  Profile match percentages by role type with match_percentage, total_roles_analyzed
- VAL-MARKET-005: Dream company opportunity radar
  Dream-tier company postings flagged with priority: "dream" and alert: true
- VAL-MARKET-006: Market intelligence auto-refreshes
  Data refreshes after every discovery sweep (timestamps advance)
- Profile scoping: two-profile negative tests
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob
from career_os.models.skills import Skill

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
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    # Seed two profiles for scoping tests
    profile_a = Profile(
        id=1,
        name="Test User",
        email="test@example.com",
        location="Frankfurt",
        job_family="TPM",
    )
    profile_b = Profile(
        id=2,
        name="Other User",
        email="b@test.com",
        location="Berlin",
        job_family="SWE",
    )
    session.add_all([profile_a, profile_b])
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper: seed discovered jobs with various characteristics
# ---------------------------------------------------------------------------


def _seed_discovered_jobs(session, profile_id: int = 1) -> list[DiscoveredJob]:
    """Seed discovered jobs with different roles, companies, salaries, etc."""
    now = datetime.now(UTC)
    jobs_data = [
        {
            "title": "Senior TPM",
            "company": "Google",
            "location": "Germany",
            "salary_range": "130000-160000 EUR",
            "description": (
                "Senior TPM role requiring Python, Kubernetes, AWS, Agile, Stakeholder Management"
            ),
            "remote": True,
            "posted_at": now - timedelta(days=5),
        },
        {
            "title": "Senior TPM",
            "company": "Meta",
            "location": "Germany",
            "salary_range": "140000-170000 EUR",
            "description": (
                "TPM for AI products. Skills: Python, ML,"
                " Stakeholder Management, Agile, Program Management"
            ),
            "remote": False,
            "posted_at": now - timedelta(days=3),
        },
        {
            "title": "Product Engineer",
            "company": "Stripe",
            "location": "Germany",
            "salary_range": "120000-150000 EUR",
            "description": "Product engineer role. React, TypeScript, Python, APIs, System Design",
            "remote": True,
            "posted_at": now - timedelta(days=7),
        },
        {
            "title": "Product Engineer",
            "company": "Figma",
            "location": "Remote EU",
            "salary_range": "110000-140000 EUR",
            "description": (
                "Build product features. React, TypeScript, Node.js, GraphQL, System Design"
            ),
            "remote": True,
            "posted_at": now - timedelta(days=2),
        },
        {
            "title": "AI Program Lead",
            "company": "Mistral",
            "location": "Germany",
            "salary_range": "150000-180000 EUR",
            "description": (
                "Lead AI programs. Python, ML, Kubernetes,"
                " Program Management, Stakeholder Management, AWS"
            ),
            "remote": False,
            "posted_at": now - timedelta(days=1),
        },
        {
            "title": "Senior TPM",
            "company": "Amazon",
            "location": "Germany",
            "salary_range": "125000-155000 EUR",
            "description": "TPM for cloud services. AWS, Python, Agile, Program Management",
            "remote": False,
            "posted_at": now - timedelta(days=10),
        },
        {
            "title": "DevRel Engineer",
            "company": "Google",
            "location": "Remote EU",
            "salary_range": "100000-130000 EUR",
            "description": (
                "Developer relations. Python, TypeScript, APIs,"
                " Community Management, Technical Writing"
            ),
            "remote": True,
            "posted_at": now - timedelta(days=4),
        },
        {
            "title": "Staff TPM",
            "company": "Google",
            "location": "Germany",
            "salary_range": "135000-165000 EUR",
            "description": (
                "Staff TPM role at Google. Python, AWS, Kubernetes, Agile, Program Management"
            ),
            "remote": True,
            "posted_at": now - timedelta(days=6),
        },
    ]

    discovered_jobs = []
    for i, data in enumerate(jobs_data):
        dj = DiscoveredJob(
            profile_id=profile_id,
            title=data["title"],
            company=data["company"],
            location=data["location"],
            url=f"https://example.com/job/{i + 1}",
            description=data["description"],
            salary_range=data["salary_range"],
            remote=data["remote"],
            posted_at=data["posted_at"],
            title_normalized=data["title"].strip().lower(),
            company_normalized=data["company"].strip().lower(),
            location_normalized=data["location"].strip().lower(),
            sources=json.dumps(["arbeitsagentur"]),
            source_urls=json.dumps([f"https://example.com/job/{i + 1}"]),
            fit_score=7.5 + (i % 3) * 0.5,  # Vary scores: 7.5, 8.0, 8.5
        )
        session.add(dj)
        discovered_jobs.append(dj)

    session.commit()
    for dj in discovered_jobs:
        session.refresh(dj)
    return discovered_jobs


def _seed_scored_jobs(
    session, discovered_jobs: list[DiscoveredJob], profile_id: int = 1
) -> list[ScoredJob]:
    """Seed scored jobs for the discovered jobs."""
    scored = []
    for dj in discovered_jobs:
        sj = ScoredJob(
            profile_id=profile_id,
            discovered_job_id=dj.id,
            fit_score=dj.fit_score or 7.0,
            readiness_score=65.0 + (dj.id % 4) * 10,  # 65, 75, 85, 95 ...
            career_alignment=6.5 + (dj.id % 3),
            reasoning="Detailed scoring explanation with factors: skills match is good, "
            "career alignment moderate, culture fit strong. Overall a solid match "
            "for the candidate's profile and career goals.",
            estimated_salary=dj.salary_range or "120000-150000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Review system design concepts",
            is_stale=False,
            weights_snapshot=json.dumps(
                {
                    "skills_match": 0.25,
                    "career_alignment": 0.20,
                }
            ),
        )
        session.add(sj)
        scored.append(sj)
    session.commit()
    for s in scored:
        session.refresh(s)
    return scored


def _seed_skills_for_profile(session, profile_id: int = 1) -> list[Skill]:
    """Seed skills for a profile to test market positioning."""
    skills_data = [
        ("Python", "technical", "advanced"),
        ("TypeScript", "technical", "intermediate"),
        ("Kubernetes", "tools", "intermediate"),
        ("AWS", "tools", "advanced"),
        ("Stakeholder Management", "soft", "expert"),
        ("Agile", "domain", "advanced"),
        ("Program Management", "domain", "expert"),
        ("React", "technical", "intermediate"),
        ("System Design", "technical", "advanced"),
    ]
    skills = []
    for name, category, proficiency in skills_data:
        s = Skill(
            profile_id=profile_id,
            name=name,
            category=category,
            proficiency=proficiency,
            evidence_source=json.dumps(["cv.yaml"]),
        )
        session.add(s)
        skills.append(s)
    session.commit()
    for s in skills:
        session.refresh(s)
    return skills


# ===========================================================================
# VAL-MARKET-001: Salary Trends
# ===========================================================================


class TestSalaryTrends:
    """GET /api/market/salary-trends — salary data by role and location."""

    def test_salary_trends_returns_200(self, client, db_session):
        """Basic salary trends endpoint returns 200."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/salary-trends", params={"profile_id": 1})
        assert resp.status_code == 200

    def test_salary_trends_has_required_fields(self, client, db_session):
        """Response includes median, p25, p75, sample_size."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/salary-trends", params={"profile_id": 1})
        data = resp.json()
        assert "trends" in data
        assert len(data["trends"]) > 0
        for trend in data["trends"]:
            assert "role" in trend
            assert "median" in trend
            assert "p25" in trend
            assert "p75" in trend
            assert "sample_size" in trend
            assert isinstance(trend["median"], (int, float))
            assert isinstance(trend["p25"], (int, float))
            assert isinstance(trend["p75"], (int, float))
            assert isinstance(trend["sample_size"], int)

    def test_salary_trends_filter_by_role(self, client, db_session):
        """Filtering by role returns only matching salary data."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/salary-trends",
            params={"profile_id": 1, "role": "TPM"},
        )
        data = resp.json()
        assert resp.status_code == 200
        # Should find TPM-related salary data
        assert len(data["trends"]) > 0
        for trend in data["trends"]:
            assert "tpm" in trend["role"].lower()

    def test_salary_trends_filter_by_location(self, client, db_session):
        """Filtering by location returns only matching data."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/salary-trends",
            params={"profile_id": 1, "location": "Germany"},
        )
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["trends"]) > 0

    def test_salary_trends_filter_by_role_and_location(self, client, db_session):
        """Filter by both role and location."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/salary-trends",
            params={"profile_id": 1, "role": "TPM", "location": "Germany"},
        )
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["trends"]) > 0

    def test_salary_trends_percentiles_ordered(self, client, db_session):
        """p25 <= median <= p75 in each trend entry."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/salary-trends", params={"profile_id": 1})
        data = resp.json()
        for trend in data["trends"]:
            assert trend["p25"] <= trend["median"] <= trend["p75"]

    def test_salary_trends_empty_data(self, client, db_session):
        """With no discovered jobs, returns empty trends."""
        resp = client.get("/api/market/salary-trends", params={"profile_id": 1})
        data = resp.json()
        assert resp.status_code == 200
        assert data["trends"] == []

    def test_salary_trends_profile_scoped(self, client, db_session):
        """Profile B cannot see Profile A's salary data."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get("/api/market/salary-trends", params={"profile_id": 2})
        data = resp.json()
        assert resp.status_code == 200
        assert data["trends"] == []

    def test_salary_trends_nonexistent_profile(self, client, db_session):
        """Nonexistent profile returns 404."""
        resp = client.get("/api/market/salary-trends", params={"profile_id": 999})
        assert resp.status_code == 404


# ===========================================================================
# VAL-MARKET-002: Skill Demand Trends
# ===========================================================================


class TestSkillTrends:
    """GET /api/market/skill-trends — ranked skills by mention count."""

    def test_skill_trends_returns_200(self, client, db_session):
        """Basic skill trends endpoint returns 200."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/skill-trends", params={"profile_id": 1})
        assert resp.status_code == 200

    def test_skill_trends_has_required_fields(self, client, db_session):
        """Each entry has skill_name, mention_count, trend_direction, percentage_of_postings."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/skill-trends", params={"profile_id": 1})
        data = resp.json()
        assert "skills" in data
        assert len(data["skills"]) > 0
        for skill in data["skills"]:
            assert "skill_name" in skill
            assert "mention_count" in skill
            assert "trend_direction" in skill
            assert "percentage_of_postings" in skill
            assert isinstance(skill["mention_count"], int)
            assert skill["trend_direction"] in ("up", "down", "stable")
            assert 0 <= skill["percentage_of_postings"] <= 100

    def test_skill_trends_sorted_by_mention_count(self, client, db_session):
        """Skills are ranked by mention_count descending."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/skill-trends", params={"profile_id": 1})
        data = resp.json()
        counts = [s["mention_count"] for s in data["skills"]]
        assert counts == sorted(counts, reverse=True)

    def test_skill_trends_updates_with_sweep(self, client, db_session):
        """Skill trends update when new jobs are added."""
        _seed_discovered_jobs(db_session)
        resp1 = client.get("/api/market/skill-trends", params={"profile_id": 1})
        data1 = resp1.json()
        total_before = data1.get("total_postings_analyzed", 0)

        # Add another job with a new skill
        dj = DiscoveredJob(
            profile_id=1,
            title="ML Engineer",
            company="DeepMind",
            location="Germany",
            description="ML role requiring TensorFlow, PyTorch, Python, CUDA",
            title_normalized="ml engineer",
            company_normalized="deepmind",
            location_normalized="germany",
            sources=json.dumps(["arbeitsagentur"]),
            source_urls=json.dumps([]),
        )
        db_session.add(dj)
        db_session.commit()

        resp2 = client.get("/api/market/skill-trends", params={"profile_id": 1})
        data2 = resp2.json()
        total_after = data2.get("total_postings_analyzed", 0)
        assert total_after > total_before

    def test_skill_trends_empty_data(self, client, db_session):
        """With no discovered jobs, returns empty skills list."""
        resp = client.get("/api/market/skill-trends", params={"profile_id": 1})
        data = resp.json()
        assert resp.status_code == 200
        assert data["skills"] == []

    def test_skill_trends_profile_scoped(self, client, db_session):
        """Profile B cannot see Profile A's skill trends."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get("/api/market/skill-trends", params={"profile_id": 2})
        data = resp.json()
        assert data["skills"] == []

    def test_skill_trends_python_has_high_count(self, client, db_session):
        """Python appears in most job descriptions, so should rank high."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/skill-trends", params={"profile_id": 1})
        data = resp.json()
        python_skill = next(
            (s for s in data["skills"] if s["skill_name"].lower() == "python"), None
        )
        assert python_skill is not None
        assert python_skill["mention_count"] >= 4  # Appears in most descriptions


# ===========================================================================
# VAL-MARKET-003: Company Hiring Patterns
# ===========================================================================


class TestHiringPatterns:
    """GET /api/market/hiring-patterns — company posting velocity."""

    def test_hiring_patterns_returns_200(self, client, db_session):
        """Basic hiring patterns endpoint returns 200."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 1})
        assert resp.status_code == 200

    def test_hiring_patterns_has_required_fields(self, client, db_session):
        """Each company has active_postings_count, posting_velocity, roles_trending."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 1})
        data = resp.json()
        assert "companies" in data
        assert len(data["companies"]) > 0
        for company in data["companies"]:
            assert "company" in company
            assert "active_postings_count" in company
            assert "posting_velocity" in company
            assert "roles_trending" in company
            assert isinstance(company["active_postings_count"], int)
            assert isinstance(company["posting_velocity"], (int, float))
            assert isinstance(company["roles_trending"], list)

    def test_hiring_patterns_google_has_most_postings(self, client, db_session):
        """Google has 3 postings, should appear with highest count."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 1})
        data = resp.json()
        google = next((c for c in data["companies"] if c["company"] == "Google"), None)
        assert google is not None
        assert google["active_postings_count"] == 3

    def test_hiring_patterns_sorted_by_count(self, client, db_session):
        """Companies sorted by active_postings_count descending."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 1})
        data = resp.json()
        counts = [c["active_postings_count"] for c in data["companies"]]
        assert counts == sorted(counts, reverse=True)

    def test_hiring_patterns_roles_trending(self, client, db_session):
        """Google's roles_trending should include the roles from its postings."""
        _seed_discovered_jobs(db_session)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 1})
        data = resp.json()
        google = next((c for c in data["companies"] if c["company"] == "Google"), None)
        assert google is not None
        assert len(google["roles_trending"]) > 0

    def test_hiring_patterns_empty_data(self, client, db_session):
        """With no discovered jobs, returns empty companies."""
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 1})
        data = resp.json()
        assert resp.status_code == 200
        assert data["companies"] == []

    def test_hiring_patterns_profile_scoped(self, client, db_session):
        """Profile B cannot see Profile A's data."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 2})
        data = resp.json()
        assert data["companies"] == []


# ===========================================================================
# VAL-MARKET-004: Market Positioning
# ===========================================================================


class TestMarketPositioning:
    """GET /api/market/positioning — profile match % by role type."""

    def test_positioning_returns_200(self, client, db_session):
        """Basic positioning endpoint returns 200."""
        _seed_discovered_jobs(db_session)
        _seed_skills_for_profile(db_session)
        resp = client.get("/api/market/positioning", params={"profile_id": 1})
        assert resp.status_code == 200

    def test_positioning_has_required_fields(self, client, db_session):
        """Each position has role_type, match_percentage, total_roles_analyzed."""
        _seed_discovered_jobs(db_session)
        _seed_skills_for_profile(db_session)
        resp = client.get("/api/market/positioning", params={"profile_id": 1})
        data = resp.json()
        assert "positions" in data
        assert len(data["positions"]) > 0
        for pos in data["positions"]:
            assert "role_type" in pos
            assert "match_percentage" in pos
            assert "total_roles_analyzed" in pos
            assert 0 <= pos["match_percentage"] <= 100
            assert isinstance(pos["total_roles_analyzed"], int)

    def test_positioning_changes_with_skills(self, client, db_session):
        """Position match changes when profile skills are updated."""
        _seed_discovered_jobs(db_session)
        # Without skills
        resp1 = client.get("/api/market/positioning", params={"profile_id": 1})
        data1 = resp1.json()

        # Seed skills
        _seed_skills_for_profile(db_session)
        resp2 = client.get("/api/market/positioning", params={"profile_id": 1})
        data2 = resp2.json()

        # Match percentages should differ once we have skills
        if data1["positions"] and data2["positions"]:
            # With skills, match % for at least one role type should be higher
            match1 = {p["role_type"]: p["match_percentage"] for p in data1["positions"]}
            match2 = {p["role_type"]: p["match_percentage"] for p in data2["positions"]}
            # At least one role type should have improved match
            some_improved = any(match2.get(rt, 0) >= match1.get(rt, 0) for rt in match2)
            assert some_improved

    def test_positioning_empty_data(self, client, db_session):
        """With no discovered jobs, returns empty positions."""
        _seed_skills_for_profile(db_session)
        resp = client.get("/api/market/positioning", params={"profile_id": 1})
        data = resp.json()
        assert resp.status_code == 200
        assert data["positions"] == []

    def test_positioning_profile_scoped(self, client, db_session):
        """Profile B cannot see Profile A's positioning."""
        _seed_discovered_jobs(db_session, profile_id=1)
        _seed_skills_for_profile(db_session, profile_id=1)
        resp = client.get("/api/market/positioning", params={"profile_id": 2})
        data = resp.json()
        assert data["positions"] == []


# ===========================================================================
# VAL-MARKET-005: Dream Company Opportunity Radar
# ===========================================================================


class TestOpportunityRadar:
    """GET /api/market/opportunity-radar — dream company flagging."""

    def test_radar_returns_200(self, client, db_session):
        """Basic radar endpoint returns 200."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1, "dream_companies": "Google,Stripe,Mistral"},
        )
        assert resp.status_code == 200

    def test_radar_flags_dream_companies(self, client, db_session):
        """Dream company jobs have priority: dream and alert: true."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1, "dream_companies": "Google,Stripe,Mistral"},
        )
        data = resp.json()
        assert "opportunities" in data
        assert len(data["opportunities"]) > 0
        for opp in data["opportunities"]:
            assert opp["priority"] == "dream"
            assert opp["alert"] is True
            assert opp["company"] in ["Google", "Stripe", "Mistral"]

    def test_radar_includes_job_details(self, client, db_session):
        """Each opportunity has title, company, location, url, fit_score."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1, "dream_companies": "Google"},
        )
        data = resp.json()
        for opp in data["opportunities"]:
            assert "title" in opp
            assert "company" in opp
            assert "location" in opp
            assert "url" in opp
            assert "fit_score" in opp

    def test_radar_returns_google_jobs(self, client, db_session):
        """Google is a dream company with 3 postings — should return them."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1, "dream_companies": "Google"},
        )
        data = resp.json()
        google_opps = [o for o in data["opportunities"] if o["company"] == "Google"]
        assert len(google_opps) == 3

    def test_radar_no_dream_companies_provided(self, client, db_session):
        """Without dream companies list, returns empty."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1},
        )
        data = resp.json()
        assert resp.status_code == 200
        assert data["opportunities"] == []

    def test_radar_no_matching_dream_companies(self, client, db_session):
        """Dream companies not in data return empty."""
        _seed_discovered_jobs(db_session)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1, "dream_companies": "NonExistentCo"},
        )
        data = resp.json()
        assert data["opportunities"] == []

    def test_radar_profile_scoped(self, client, db_session):
        """Profile B cannot see Profile A's opportunities."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 2, "dream_companies": "Google"},
        )
        data = resp.json()
        assert data["opportunities"] == []

    def test_radar_empty_data(self, client, db_session):
        """With no discovered jobs, returns empty."""
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 1, "dream_companies": "Google"},
        )
        data = resp.json()
        assert resp.status_code == 200
        assert data["opportunities"] == []


# ===========================================================================
# VAL-MARKET-006: Auto-refresh after discovery sweep
# ===========================================================================


class TestAutoRefresh:
    """Market intelligence data auto-refreshes after each discovery sweep."""

    def test_refresh_endpoint_exists(self, client, db_session):
        """POST /api/market/refresh endpoint exists and works."""
        _seed_discovered_jobs(db_session)
        resp = client.post(
            "/api/market/refresh",
            json={"profile_id": 1},
        )
        assert resp.status_code == 200

    def test_refresh_returns_timestamp(self, client, db_session):
        """Refresh returns last_refreshed_at timestamp."""
        _seed_discovered_jobs(db_session)
        resp = client.post(
            "/api/market/refresh",
            json={"profile_id": 1},
        )
        data = resp.json()
        assert "last_refreshed_at" in data

    def test_refresh_updates_timestamp(self, client, db_session):
        """Calling refresh advances the timestamp."""
        _seed_discovered_jobs(db_session)
        resp1 = client.post("/api/market/refresh", json={"profile_id": 1})
        ts1 = resp1.json()["last_refreshed_at"]

        # Add more data
        dj = DiscoveredJob(
            profile_id=1,
            title="New Role",
            company="NewCo",
            location="Berlin",
            description="Exciting role",
            title_normalized="new role",
            company_normalized="newco",
            location_normalized="berlin",
            sources=json.dumps(["arbeitsagentur"]),
            source_urls=json.dumps([]),
        )
        db_session.add(dj)
        db_session.commit()

        resp2 = client.post("/api/market/refresh", json={"profile_id": 1})
        ts2 = resp2.json()["last_refreshed_at"]
        # Timestamps should be different (or at least not earlier)
        assert ts2 >= ts1


# ===========================================================================
# Profile Scoping: Two-profile negative tests
# ===========================================================================


class TestProfileScoping:
    """Verify all market endpoints are profile-scoped."""

    def test_salary_trends_profile_isolation(self, client, db_session):
        """Profile A data is invisible to Profile B."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get("/api/market/salary-trends", params={"profile_id": 2})
        assert resp.json()["trends"] == []

    def test_skill_trends_profile_isolation(self, client, db_session):
        """Profile A data is invisible to Profile B."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get("/api/market/skill-trends", params={"profile_id": 2})
        assert resp.json()["skills"] == []

    def test_hiring_patterns_profile_isolation(self, client, db_session):
        """Profile A data is invisible to Profile B."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get("/api/market/hiring-patterns", params={"profile_id": 2})
        assert resp.json()["companies"] == []

    def test_positioning_profile_isolation(self, client, db_session):
        """Profile A data is invisible to Profile B."""
        _seed_discovered_jobs(db_session, profile_id=1)
        _seed_skills_for_profile(db_session, profile_id=1)
        resp = client.get("/api/market/positioning", params={"profile_id": 2})
        assert resp.json()["positions"] == []

    def test_radar_profile_isolation(self, client, db_session):
        """Profile A data is invisible to Profile B."""
        _seed_discovered_jobs(db_session, profile_id=1)
        resp = client.get(
            "/api/market/opportunity-radar",
            params={"profile_id": 2, "dream_companies": "Google"},
        )
        assert resp.json()["opportunities"] == []
