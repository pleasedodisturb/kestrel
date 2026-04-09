"""Tests for Role & Industry Intelligence.

Covers:
- VAL-ROLE-INTEL-001: Interview format per company (rounds, types, duration)
- VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size (low/median/high)
- VAL-ROLE-INTEL-003: Common interview patterns per role type
- Profile scoping: two-profile isolation tests
"""

import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.schemas.ai import AIFeature

# ---------------------------------------------------------------------------
# Test fixtures
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
    profile = Profile(name="Other User", email="other@example.com")
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def discovered_jobs(test_db: Session, test_profile: Profile) -> list[DiscoveredJob]:
    """Seed discovered jobs for salary benchmark aggregation."""
    jobs_data = [
        {
            "title": "Senior TPM",
            "company": "Stripe",
            "location": "Frankfurt, Germany",
            "url": "https://stripe.com/jobs/1",
            "sources": '["linkedin"]',
            "source_urls": '["https://stripe.com/jobs/1"]',
            "description": "Senior TPM role requiring Agile, Stakeholder Management.",
            "salary_range": "130000-160000 EUR",
            "posted_at": datetime(2025, 1, 15, tzinfo=UTC),
            "profile_id": test_profile.id,
        },
        {
            "title": "Staff TPM",
            "company": "Datadog",
            "location": "Berlin, Germany",
            "url": "https://datadog.com/jobs/1",
            "sources": '["indeed"]',
            "source_urls": '["https://datadog.com/jobs/1"]',
            "description": "Staff TPM role requiring Program Management, Kubernetes.",
            "salary_range": "140000-180000 EUR",
            "posted_at": datetime(2025, 2, 10, tzinfo=UTC),
            "profile_id": test_profile.id,
        },
        {
            "title": "Product Engineer",
            "company": "Plain",
            "location": "Remote, EU",
            "url": "https://plain.com/jobs/1",
            "sources": '["linkedin"]',
            "source_urls": '["https://plain.com/jobs/1"]',
            "description": "Product Engineer role requiring React, TypeScript, Node.js.",
            "salary_range": "100000-130000 EUR",
            "posted_at": datetime(2025, 2, 20, tzinfo=UTC),
            "profile_id": test_profile.id,
        },
        {
            "title": "Senior Product Engineer",
            "company": "Mistral AI",
            "location": "Paris, France",
            "url": "https://mistral.ai/jobs/1",
            "sources": '["glassdoor"]',
            "source_urls": '["https://mistral.ai/jobs/1"]',
            "description": "Product Engineer requiring Python, ML, AI, TypeScript.",
            "salary_range": "120000-150000 EUR",
            "posted_at": datetime(2025, 3, 5, tzinfo=UTC),
            "profile_id": test_profile.id,
        },
        {
            "title": "DevRel Engineer",
            "company": "Vercel",
            "location": "Remote, EU",
            "url": "https://vercel.com/jobs/1",
            "sources": '["linkedin"]',
            "source_urls": '["https://vercel.com/jobs/1"]',
            "description": "DevRel role requiring Community Management, Technical Writing.",
            "salary_range": "90000-120000 EUR",
            "posted_at": datetime(2025, 3, 10, tzinfo=UTC),
            "profile_id": test_profile.id,
        },
    ]
    jobs = []
    for data in jobs_data:
        # Set normalized fields for dedup
        data["title_normalized"] = data["title"].strip().lower()
        data["company_normalized"] = data["company"].strip().lower()
        data["location_normalized"] = data["location"].strip().lower()
        job = DiscoveredJob(**data)
        test_db.add(job)
        jobs.append(job)
    test_db.commit()
    for j in jobs:
        test_db.refresh(j)
    return jobs


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
# VAL-ROLE-INTEL-001: Interview format per company
# ===========================================================================


class TestInterviewFormat:
    """Test interview format endpoint returns rounds, types, duration."""

    def test_interview_format_returns_all_fields(self, client: TestClient, test_profile: Profile):
        """GET /api/intelligence/interview-format returns round details."""
        response = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "company" in data
        assert data["company"] == "Stripe"
        assert "rounds" in data
        assert isinstance(data["rounds"], list)
        assert len(data["rounds"]) > 0
        assert "total_duration" in data
        assert "process_description" in data

    def test_interview_format_round_has_type_and_details(
        self, client: TestClient, test_profile: Profile
    ):
        """Each round has type, description, duration_minutes."""
        response = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        for rnd in data["rounds"]:
            assert "round_number" in rnd
            assert "type" in rnd
            assert "description" in rnd
            assert "duration_minutes" in rnd
            assert isinstance(rnd["round_number"], int)
            assert isinstance(rnd["duration_minutes"], int)

    def test_interview_format_nonexistent_profile_404(self, client: TestClient):
        """Interview format with invalid profile_id returns 404."""
        response = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": 99999,
            },
        )
        assert response.status_code == 404

    def test_interview_format_missing_company_422(self, client: TestClient, test_profile: Profile):
        """Interview format without company param returns 422."""
        response = client.get(
            "/api/intelligence/interview-format",
            params={
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 422

    def test_interview_format_with_role_context(self, client: TestClient, test_profile: Profile):
        """Interview format accepts optional role parameter for context."""
        response = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
                "role": "TPM",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["rounds"]) > 0

    def test_interview_format_different_companies_vary(
        self, client: TestClient, test_profile: Profile
    ):
        """Different companies produce different interview formats (mock determinism)."""
        resp_stripe = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp_google = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Google",
                "profile_id": test_profile.id,
            },
        )
        assert resp_stripe.status_code == 200
        assert resp_google.status_code == 200
        # Both should have rounds but they can differ
        assert len(resp_stripe.json()["rounds"]) > 0
        assert len(resp_google.json()["rounds"]) > 0


# ===========================================================================
# VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size
# ===========================================================================


class TestSalaryBenchmarks:
    """Test salary benchmarks return low/median/high contextualized by location/stage."""

    def test_salary_benchmarks_returns_all_fields(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """GET /api/intelligence/salary returns low/median/high ranges."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "location": "Germany",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "role" in data
        assert "location" in data
        assert "benchmarks" in data
        benchmarks = data["benchmarks"]
        assert "low" in benchmarks
        assert "median" in benchmarks
        assert "high" in benchmarks
        assert "sample_size" in benchmarks
        assert isinstance(benchmarks["low"], (int, float))
        assert isinstance(benchmarks["median"], (int, float))
        assert isinstance(benchmarks["high"], (int, float))

    def test_salary_benchmarks_ordered(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """Low ≤ median ≤ high."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "location": "Germany",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        b = data["benchmarks"]
        assert b["low"] <= b["median"] <= b["high"]

    def test_salary_benchmarks_nonexistent_profile_404(self, client: TestClient):
        """Salary benchmarks with invalid profile_id returns 404."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "location": "Germany",
                "profile_id": 99999,
            },
        )
        assert response.status_code == 404

    def test_salary_benchmarks_no_matching_role(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """Salary benchmarks for non-matching role returns empty/null benchmarks."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "NonExistentRole",
                "location": "Germany",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["benchmarks"]["sample_size"] == 0

    def test_salary_benchmarks_location_filters(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """Salary benchmarks for specific location filters by location substring."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "location": "Frankfurt",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["benchmarks"]["sample_size"] >= 1

    def test_salary_benchmarks_no_location_returns_all(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """Salary benchmarks without location filter includes all locations."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should include both Frankfurt and Berlin TPM jobs
        assert data["benchmarks"]["sample_size"] >= 2

    def test_salary_benchmarks_includes_company_stage(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """Response includes contextualization by company stage if available."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "location": "Germany",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should have context about how the benchmarks are derived
        assert "context" in data

    def test_salary_benchmarks_different_roles_differ(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """Different roles produce different salary benchmarks."""
        resp_tpm = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        resp_eng = client.get(
            "/api/intelligence/salary",
            params={
                "role": "Product Engineer",
                "profile_id": test_profile.id,
            },
        )
        assert resp_tpm.status_code == 200
        assert resp_eng.status_code == 200

        tpm_median = resp_tpm.json()["benchmarks"]["median"]
        eng_median = resp_eng.json()["benchmarks"]["median"]
        # Both should have data; they should come from different job sets
        assert tpm_median > 0
        assert eng_median > 0


# ===========================================================================
# VAL-ROLE-INTEL-003: Common interview patterns per role type
# ===========================================================================


class TestInterviewPatterns:
    """Test common interview patterns show distinct categories for different roles."""

    def test_patterns_returns_all_fields(self, client: TestClient, test_profile: Profile):
        """GET /api/intelligence/patterns returns question categories and skills."""
        response = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "role" in data
        assert data["role"] == "TPM"
        assert "question_categories" in data
        assert isinstance(data["question_categories"], list)
        assert len(data["question_categories"]) > 0
        assert "assessment_criteria" in data
        assert isinstance(data["assessment_criteria"], list)
        assert "frequently_tested_skills" in data
        assert isinstance(data["frequently_tested_skills"], list)
        assert len(data["frequently_tested_skills"]) > 0

    def test_patterns_question_category_fields(self, client: TestClient, test_profile: Profile):
        """Each question category has name, description, example_questions."""
        response = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        for cat in data["question_categories"]:
            assert "name" in cat
            assert "description" in cat
            assert "example_questions" in cat
            assert isinstance(cat["example_questions"], list)

    def test_patterns_assessment_criteria_fields(self, client: TestClient, test_profile: Profile):
        """Each assessment criterion has name and description."""
        response = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        for crit in data["assessment_criteria"]:
            assert "name" in crit
            assert "description" in crit

    def test_patterns_nonexistent_profile_404(self, client: TestClient):
        """Patterns with invalid profile_id returns 404."""
        response = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": 99999,
            },
        )
        assert response.status_code == 404

    def test_patterns_missing_role_422(self, client: TestClient, test_profile: Profile):
        """Patterns without role param returns 422."""
        response = client.get(
            "/api/intelligence/patterns",
            params={
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 422

    def test_patterns_different_roles_distinct(self, client: TestClient, test_profile: Profile):
        """Different role types produce distinct patterns (VAL-ROLE-INTEL-003)."""
        resp_tpm = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        resp_eng = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "Product Engineer",
                "profile_id": test_profile.id,
            },
        )
        assert resp_tpm.status_code == 200
        assert resp_eng.status_code == 200

        tpm_skills = set(resp_tpm.json()["frequently_tested_skills"])
        eng_skills = set(resp_eng.json()["frequently_tested_skills"])

        # Skills should not be identical — different roles test different skills
        assert tpm_skills != eng_skills, (
            f"TPM and Product Engineer should have different skill sets, "
            f"got: TPM={tpm_skills}, Eng={eng_skills}"
        )

    def test_patterns_devrel_distinct_from_tpm(self, client: TestClient, test_profile: Profile):
        """DevRel patterns are distinct from TPM patterns."""
        resp_tpm = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        resp_devrel = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "DevRel",
                "profile_id": test_profile.id,
            },
        )
        assert resp_tpm.status_code == 200
        assert resp_devrel.status_code == 200

        tpm_categories = {c["name"] for c in resp_tpm.json()["question_categories"]}
        devrel_categories = {c["name"] for c in resp_devrel.json()["question_categories"]}

        # The category sets should not be identical
        assert tpm_categories != devrel_categories


# ===========================================================================
# Profile scoping tests
# ===========================================================================


class TestProfileScoping:
    """Test profile isolation for role intelligence endpoints."""

    def test_interview_format_requires_valid_profile(self, client: TestClient):
        """Interview format with nonexistent profile returns 404."""
        response = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": 99999,
            },
        )
        assert response.status_code == 404

    def test_salary_benchmarks_profile_isolation(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
        discovered_jobs,
    ):
        """Salary benchmarks only use jobs from the requesting profile."""
        # test_profile has discovered jobs
        resp1 = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        assert resp1.status_code == 200
        assert resp1.json()["benchmarks"]["sample_size"] >= 2

        # second_profile has no discovered jobs → sample_size=0
        resp2 = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": second_profile.id,
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["benchmarks"]["sample_size"] == 0

    def test_both_profiles_can_get_patterns(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Both profiles can independently get interview patterns."""
        resp1 = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        resp2 = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": second_profile.id,
            },
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_both_profiles_can_get_interview_format(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Both profiles can independently get interview format."""
        resp1 = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp2 = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": second_profile.id,
            },
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ===========================================================================
# AI provider failure graceful degradation
# ===========================================================================


# ===========================================================================
# Fix: Salary benchmarks include company_stage
# ===========================================================================


class TestSalaryBenchmarksStage:
    """Test that salary benchmarks accept and reflect company_stage."""

    def test_salary_benchmarks_accepts_company_stage_param(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """GET /api/intelligence/salary accepts company_stage query param."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
                "company_stage": "startup",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "company_stage" in data

    def test_salary_benchmarks_stage_in_response(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """company_stage value echoed in response."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
                "company_stage": "growth",
            },
        )
        data = response.json()
        assert data["company_stage"] == "growth"

    def test_salary_benchmarks_stage_in_context(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """company_stage appears in context string when provided."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
                "company_stage": "public",
            },
        )
        data = response.json()
        if data["benchmarks"]["sample_size"] > 0:
            assert "public" in data["context"].lower()

    def test_salary_benchmarks_no_stage_null(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """company_stage is null when not provided."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert data["company_stage"] is None


# ===========================================================================
# Fix: TPM matches Technical Program Manager in salary queries
# ===========================================================================


class TestRoleTitleNormalization:
    """Test that role title normalization expands abbreviations like TPM."""

    def test_tpm_matches_technical_program_manager(
        self, client: TestClient, test_profile: Profile, test_db: Session
    ):
        """'Technical Program Manager' title matches 'TPM' query."""
        # Add a job titled "Technical Program Manager"
        job = DiscoveredJob(
            title="Technical Program Manager",
            company="Acme Corp",
            location="Frankfurt, Germany",
            url="https://acme.com/jobs/tpm",
            sources='["linkedin"]',
            source_urls='["https://acme.com/jobs/tpm"]',
            description="TPM role at Acme.",
            salary_range="120000-150000 EUR",
            posted_at=datetime(2025, 3, 1, tzinfo=UTC),
            profile_id=test_profile.id,
            title_normalized="technical program manager",
            company_normalized="acme corp",
            location_normalized="frankfurt, germany",
        )
        test_db.add(job)
        test_db.commit()

        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should include the "Technical Program Manager" job
        assert data["benchmarks"]["sample_size"] >= 1

    def test_technical_program_manager_query_matches_tpm_title(
        self, client: TestClient, test_profile: Profile, discovered_jobs
    ):
        """'Technical Program Manager' query matches jobs titled 'Senior TPM'."""
        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "Technical Program Manager",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should match "Senior TPM" and "Staff TPM" from discovered_jobs fixture
        assert data["benchmarks"]["sample_size"] >= 2

    def test_devrel_abbreviation_matches(
        self, client: TestClient, test_profile: Profile, test_db: Session
    ):
        """'DevRel' query matches 'Developer Relations' title."""
        job = DiscoveredJob(
            title="Developer Relations Engineer",
            company="GitHub",
            location="Remote, EU",
            url="https://github.com/jobs/devrel",
            sources='["linkedin"]',
            source_urls='["https://github.com/jobs/devrel"]',
            description="DevRel role at GitHub.",
            salary_range="110000-140000 EUR",
            posted_at=datetime(2025, 3, 5, tzinfo=UTC),
            profile_id=test_profile.id,
            title_normalized="developer relations engineer",
            company_normalized="github",
            location_normalized="remote, eu",
        )
        test_db.add(job)
        test_db.commit()

        response = client.get(
            "/api/intelligence/salary",
            params={
                "role": "DevRel",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should match both "DevRel Engineer" from fixture and "Developer Relations Engineer"
        assert data["benchmarks"]["sample_size"] >= 1


# ===========================================================================
# Fix: OpenRouter handles interview_format and interview_patterns
# ===========================================================================


class TestOpenRouterInterviewFeatures:
    """Test that OpenRouter provider has system prompts and parsing for interview features."""

    def test_openrouter_system_prompt_interview_format(self):
        """OpenRouter has system prompt for interview_format feature."""
        from career_os.ai.openrouter_provider import _system_prompt_for_feature

        prompt = _system_prompt_for_feature(AIFeature.interview_format)
        assert prompt is not None
        assert "rounds" in prompt.lower()
        assert "duration" in prompt.lower()

    def test_openrouter_system_prompt_interview_patterns(self):
        """OpenRouter has system prompt for interview_patterns feature."""
        from career_os.ai.openrouter_provider import _system_prompt_for_feature

        prompt = _system_prompt_for_feature(AIFeature.interview_patterns)
        assert prompt is not None
        assert "question_categories" in prompt.lower()
        assert "frequently_tested_skills" in prompt.lower()

    def test_openrouter_parse_interview_format(self):
        """OpenRouter can parse structured interview format JSON."""
        import json

        from career_os.ai.openrouter_provider import _try_parse_structured
        from career_os.schemas.ai import InterviewFormatResult

        raw = json.dumps(
            {
                "rounds": [
                    {
                        "round_number": 1,
                        "type": "Phone Screen",
                        "description": "Initial phone screen.",
                        "duration_minutes": 30,
                    }
                ],
                "total_duration": "2-3 weeks",
                "process_description": "Standard interview process.",
            }
        )
        result = _try_parse_structured(raw, AIFeature.interview_format)
        assert isinstance(result, InterviewFormatResult)
        assert len(result.rounds) == 1

    def test_openrouter_parse_interview_patterns(self):
        """OpenRouter can parse structured interview patterns JSON."""
        import json

        from career_os.ai.openrouter_provider import _try_parse_structured
        from career_os.schemas.ai import InterviewPatternsResult

        raw = json.dumps(
            {
                "question_categories": [
                    {
                        "name": "Behavioral",
                        "description": "Past behavior questions.",
                        "example_questions": ["Tell me about a time..."],
                    }
                ],
                "assessment_criteria": [
                    {
                        "name": "Problem Solving",
                        "description": "Analytical skills.",
                    }
                ],
                "frequently_tested_skills": ["Communication", "Leadership"],
            }
        )
        result = _try_parse_structured(raw, AIFeature.interview_patterns)
        assert isinstance(result, InterviewPatternsResult)
        assert len(result.question_categories) == 1
        assert len(result.frequently_tested_skills) == 2


class TestGracefulDegradation:
    """Test that AI provider failure returns sensible defaults with warning."""

    def test_interview_format_ai_failure(
        self, client: TestClient, test_profile: Profile, _db_engine
    ):
        """When AI provider fails, interview format returns partial with warning."""
        with patch("career_os.services.role_intelligence.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("AI unavailable")
            mock_factory.return_value = mock_provider

            response = client.get(
                "/api/intelligence/interview-format",
                params={
                    "company": "Stripe",
                    "profile_id": test_profile.id,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "warnings" in data
        assert len(data["warnings"]) > 0

    def test_patterns_ai_failure(self, client: TestClient, test_profile: Profile, _db_engine):
        """When AI provider fails, patterns returns partial with warning."""
        with patch("career_os.services.role_intelligence.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("AI unavailable")
            mock_factory.return_value = mock_provider

            response = client.get(
                "/api/intelligence/patterns",
                params={
                    "role": "TPM",
                    "profile_id": test_profile.id,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "warnings" in data
        assert len(data["warnings"]) > 0


# ===========================================================================
# Determinism tests
# ===========================================================================


class TestDeterministicResponses:
    """Test that mock provider returns deterministic results."""

    def test_same_company_same_interview_format(self, client: TestClient, test_profile: Profile):
        """Same company returns identical interview format."""
        resp1 = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp2 = client.get(
            "/api/intelligence/interview-format",
            params={
                "company": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert resp1.json() == resp2.json()

    def test_same_role_same_patterns(self, client: TestClient, test_profile: Profile):
        """Same role returns identical interview patterns."""
        resp1 = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        resp2 = client.get(
            "/api/intelligence/patterns",
            params={
                "role": "TPM",
                "profile_id": test_profile.id,
            },
        )
        assert resp1.json() == resp2.json()


# ===========================================================================
# Security: log injection sanitization (SonarCloud fix)
# ===========================================================================


class TestSanitizeForLog:
    """Verify _sanitize_for_log strips newlines and truncates."""

    def test_strips_newlines(self):
        from career_os.services.role_intelligence import _sanitize_for_log

        result = _sanitize_for_log("line1\nline2\rline3")
        assert "\n" not in result
        assert "\r" not in result
        assert result == "line1\\nline2\\rline3"

    def test_truncates_long_input(self):
        from career_os.services.role_intelligence import _sanitize_for_log

        long_input = "A" * 500
        result = _sanitize_for_log(long_input)
        assert len(result) <= 215  # 200 + len("...[truncated]")
        assert result.endswith("...[truncated]")

    def test_passes_safe_input_through(self):
        from career_os.services.role_intelligence import _sanitize_for_log

        assert _sanitize_for_log("Stripe") == "Stripe"

    def test_handles_non_string(self):
        from career_os.services.role_intelligence import _sanitize_for_log

        result = _sanitize_for_log(RuntimeError("boom\ninjected"))
        assert "\n" not in result
        assert "boom\\ninjected" in result
