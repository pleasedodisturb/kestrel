"""Tests for Company Research Engine.

Covers:
- VAL-RESEARCH-001: One-click company deep-dive with all report sections
- VAL-RESEARCH-002: Tech stack categorized by frontend/backend/infra/analytics
- VAL-RESEARCH-003: Funding data (stage, amount, investors)
- VAL-RESEARCH-004: Glassdoor rating + culture signals (≥3 keywords)
- VAL-RESEARCH-005: Values alignment scores differ for aligned vs misaligned
- VAL-RESEARCH-006: ATS detection (Greenhouse/Lever/Ashby/Workday)
- VAL-RESEARCH-007: Hiring patterns (velocity, departments)
- VAL-RESEARCH-008: Obscure companies get partial report with 'No data found'
- VAL-RESEARCH-009: API failure returns partial report + warning
- VAL-RESEARCH-010: Industry segment classification
- Profile scoping: two-profile isolation tests
"""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Profile

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
    TestSession = sessionmaker(bind=_db_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_profile(test_db: Session) -> Profile:
    """Seed a test profile with values-relevant data."""
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
def client(_db_engine, test_db) -> TestClient:
    """Create a test client with overridden DB dependency."""
    TestSession = sessionmaker(bind=_db_engine)

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===========================================================================
# VAL-RESEARCH-001: One-click company deep-dive with all report sections
# ===========================================================================


class TestOneClickDeepDive:
    """Test that research returns structured report with all sections."""

    def test_research_returns_all_sections(self, client: TestClient, test_profile: Profile):
        """POST /api/research/company returns report with all required sections."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        data = response.json()

        # All top-level sections must be present
        assert "company_name" in data
        assert data["company_name"] == "Stripe"
        assert "tech_stack" in data
        assert "funding" in data
        assert "glassdoor" in data
        assert "values_alignment" in data
        assert "ats_platform" in data
        assert "hiring_patterns" in data
        assert "industry_segment" in data
        assert "warnings" in data

    def test_research_with_company_url(self, client: TestClient, test_profile: Profile):
        """Research with optional company_url accepted."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
                "company_url": "https://stripe.com",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "Stripe"

    def test_research_nonexistent_profile_404(self, client: TestClient):
        """Research with invalid profile_id returns 404."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": 99999,
            },
        )
        assert response.status_code == 404

    def test_research_empty_company_name_422(self, client: TestClient, test_profile: Profile):
        """Research with empty company name returns 422 validation error."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 422

    def test_research_missing_company_name_422(self, client: TestClient, test_profile: Profile):
        """Research without company_name returns 422."""
        response = client.post(
            "/api/research/company",
            json={
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 422


# ===========================================================================
# VAL-RESEARCH-002: Tech stack categorized
# ===========================================================================


class TestTechStackDetection:
    """Test tech stack is categorized by frontend/backend/infra/analytics."""

    def test_tech_stack_has_four_categories(self, client: TestClient, test_profile: Profile):
        """Tech stack report includes all 4 categories."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        tech = response.json()["tech_stack"]
        assert "frontend" in tech
        assert "backend" in tech
        assert "infrastructure" in tech
        assert "analytics" in tech

    def test_tech_stack_categories_populated(self, client: TestClient, test_profile: Profile):
        """Known company has populated tech stack categories (≥3 populated)."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        tech = response.json()["tech_stack"]
        populated = sum(
            1
            for cat in ["frontend", "backend", "infrastructure", "analytics"]
            if len(tech[cat]) > 0
        )
        assert populated >= 3, f"Only {populated} categories populated"

    def test_tech_stack_values_are_strings(self, client: TestClient, test_profile: Profile):
        """Tech stack values are lists of strings."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        tech = response.json()["tech_stack"]
        for category in ["frontend", "backend", "infrastructure", "analytics"]:
            assert isinstance(tech[category], list)
            for item in tech[category]:
                assert isinstance(item, str)


# ===========================================================================
# VAL-RESEARCH-003: Funding data
# ===========================================================================


class TestFundingData:
    """Test funding data includes stage, amount, investors."""

    def test_funding_has_required_fields(self, client: TestClient, test_profile: Profile):
        """Funding report includes stage, total_raised, lead_investor."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200
        funding = response.json()["funding"]
        assert "stage" in funding
        assert "total_raised" in funding
        assert "lead_investor" in funding
        assert "last_round_date" in funding

    def test_funding_values_populated_for_known_company(
        self, client: TestClient, test_profile: Profile
    ):
        """Known company has populated funding data."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        funding = response.json()["funding"]
        assert funding["stage"] is not None
        assert funding["total_raised"] is not None
        assert funding["lead_investor"] is not None


# ===========================================================================
# VAL-RESEARCH-004: Glassdoor and culture signals
# ===========================================================================


class TestGlassdoorCulture:
    """Test Glassdoor rating and culture keywords."""

    def test_glassdoor_has_rating(self, client: TestClient, test_profile: Profile):
        """Glassdoor includes overall_rating (numeric)."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        glassdoor = response.json()["glassdoor"]
        assert glassdoor["overall_rating"] is not None
        assert isinstance(glassdoor["overall_rating"], (int, float))
        assert 0 <= glassdoor["overall_rating"] <= 5

    def test_glassdoor_has_ceo_approval(self, client: TestClient, test_profile: Profile):
        """Glassdoor includes CEO approval percentage."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        glassdoor = response.json()["glassdoor"]
        assert glassdoor["ceo_approval"] is not None
        assert isinstance(glassdoor["ceo_approval"], int)

    def test_glassdoor_has_culture_keywords(self, client: TestClient, test_profile: Profile):
        """Glassdoor includes ≥3 culture keywords."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        glassdoor = response.json()["glassdoor"]
        assert "culture_keywords" in glassdoor
        assert isinstance(glassdoor["culture_keywords"], list)
        assert len(glassdoor["culture_keywords"]) >= 3


# ===========================================================================
# VAL-RESEARCH-005: Values alignment scoring
# ===========================================================================


class TestValuesAlignment:
    """Test values alignment scoring differs for aligned vs misaligned companies."""

    def test_values_alignment_has_score_and_rationale(
        self, client: TestClient, test_profile: Profile
    ):
        """Values alignment includes numeric score and text rationale."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        va = response.json()["values_alignment"]
        assert "score" in va
        assert "rationale" in va
        assert isinstance(va["score"], (int, float))
        assert 0 <= va["score"] <= 10
        assert len(va["rationale"]) > 0

    def test_aligned_company_higher_score(self, client: TestClient, test_profile: Profile):
        """Aligned company (Stripe) has higher score than misaligned company."""
        # Research aligned company
        resp_aligned = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        aligned_score = resp_aligned.json()["values_alignment"]["score"]

        # Research misaligned company
        resp_misaligned = client.post(
            "/api/research/company",
            json={
                "company_name": "EvilCorp Misaligned",
                "profile_id": test_profile.id,
            },
        )
        misaligned_score = resp_misaligned.json()["values_alignment"]["score"]

        assert aligned_score > misaligned_score, (
            f"Aligned company score ({aligned_score}) should be higher "
            f"than misaligned ({misaligned_score})"
        )

    def test_different_companies_different_scores(self, client: TestClient, test_profile: Profile):
        """Different companies produce different values alignment scores."""
        resp_stripe = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp_datadog = client.post(
            "/api/research/company",
            json={
                "company_name": "Datadog",
                "profile_id": test_profile.id,
            },
        )
        stripe_score = resp_stripe.json()["values_alignment"]["score"]
        datadog_score = resp_datadog.json()["values_alignment"]["score"]

        # Both should be valid scores, and they differ
        assert 0 <= stripe_score <= 10
        assert 0 <= datadog_score <= 10
        # They are set to different fixed values in mock
        assert stripe_score != datadog_score


# ===========================================================================
# VAL-RESEARCH-006: ATS platform detection
# ===========================================================================


class TestATSDetection:
    """Test ATS platform detection."""

    def test_ats_detected_for_known_company(self, client: TestClient, test_profile: Profile):
        """Known company returns detected ATS platform."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        ats = response.json()["ats_platform"]
        assert ats is not None
        assert ats in [
            "Greenhouse",
            "Lever",
            "Ashby",
            "Workday",
            "Taleo",
            "iCIMS",
            "SmartRecruiters",
            "Personio",
        ]

    def test_ats_identifies_greenhouse(self, client: TestClient, test_profile: Profile):
        """Stripe mock returns Greenhouse ATS."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.json()["ats_platform"] == "Greenhouse"

    def test_ats_identifies_workday(self, client: TestClient, test_profile: Profile):
        """Misaligned company mock returns Workday ATS."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "EvilCorp Misaligned",
                "profile_id": test_profile.id,
            },
        )
        assert response.json()["ats_platform"] == "Workday"

    def test_ats_null_for_obscure_company(self, client: TestClient, test_profile: Profile):
        """Obscure company may have null ATS."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Startup XYZ",
                "profile_id": test_profile.id,
            },
        )
        # Obscure companies should have null ATS
        assert response.json()["ats_platform"] is None


# ===========================================================================
# VAL-RESEARCH-007: Hiring patterns
# ===========================================================================


class TestHiringPatterns:
    """Test hiring patterns include velocity and departments."""

    def test_hiring_patterns_has_required_fields(self, client: TestClient, test_profile: Profile):
        """Hiring patterns include active_postings, velocity, departments."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        hp = response.json()["hiring_patterns"]
        assert "active_postings" in hp
        assert "posting_velocity" in hp
        assert "top_departments" in hp

    def test_hiring_patterns_populated_for_known_company(
        self, client: TestClient, test_profile: Profile
    ):
        """Known company has numeric hiring data."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        hp = response.json()["hiring_patterns"]
        assert hp["active_postings"] is not None
        assert isinstance(hp["active_postings"], int)
        assert hp["posting_velocity"] is not None
        assert len(hp["top_departments"]) > 0


# ===========================================================================
# VAL-RESEARCH-008: Partial report for obscure companies
# ===========================================================================


class TestObscureCompanyPartialReport:
    """Test that obscure companies get partial report without crash."""

    def test_obscure_company_returns_200(self, client: TestClient, test_profile: Profile):
        """Obscure company research returns 200 (no crash)."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200

    def test_obscure_company_has_all_sections(self, client: TestClient, test_profile: Profile):
        """Obscure company report has all sections (possibly empty)."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert "tech_stack" in data
        assert "funding" in data
        assert "glassdoor" in data
        assert "values_alignment" in data
        assert "ats_platform" in data
        assert "hiring_patterns" in data
        assert "industry_segment" in data

    def test_obscure_company_empty_tech_stack(self, client: TestClient, test_profile: Profile):
        """Obscure company has empty tech stack lists."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        tech = response.json()["tech_stack"]
        assert tech["frontend"] == []
        assert tech["backend"] == []
        assert tech["infrastructure"] == []
        assert tech["analytics"] == []

    def test_obscure_company_null_funding(self, client: TestClient, test_profile: Profile):
        """Obscure company has null funding fields."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        funding = response.json()["funding"]
        assert funding["stage"] is None
        assert funding["total_raised"] is None

    def test_obscure_company_null_glassdoor(self, client: TestClient, test_profile: Profile):
        """Obscure company has null glassdoor rating."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        glassdoor = response.json()["glassdoor"]
        assert glassdoor["overall_rating"] is None

    def test_obscure_company_null_industry(self, client: TestClient, test_profile: Profile):
        """Obscure company has null industry segment."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        assert response.json()["industry_segment"] is None


# ===========================================================================
# VAL-RESEARCH-009: API failure graceful degradation
# ===========================================================================


class TestGracefulDegradation:
    """Test that source failures produce warnings not crashes."""

    def test_ai_provider_failure_returns_partial_report(
        self, client: TestClient, test_profile: Profile, _db_engine
    ):
        """When AI provider fails, returns partial report with warning."""
        # Patch get_ai_provider to raise an exception
        with patch("career_os.services.company_research.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("AI provider unavailable")
            mock_factory.return_value = mock_provider

            response = client.post(
                "/api/research/company",
                json={
                    "company_name": "SomeCompany",
                    "profile_id": test_profile.id,
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Report is partial with warnings
        assert len(data["warnings"]) > 0
        warning_sources = [w["source"] for w in data["warnings"]]
        assert "ai_provider" in warning_sources

        # All sections still present (with defaults)
        assert "tech_stack" in data
        assert "funding" in data
        assert "values_alignment" in data

    def test_partial_report_has_default_values_alignment(
        self, client: TestClient, test_profile: Profile, _db_engine
    ):
        """When AI fails, values alignment defaults to 5.0."""
        with patch("career_os.services.company_research.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("fail")
            mock_factory.return_value = mock_provider

            response = client.post(
                "/api/research/company",
                json={
                    "company_name": "SomeCompany",
                    "profile_id": test_profile.id,
                },
            )

        data = response.json()
        assert data["values_alignment"]["score"] == pytest.approx(5.0)

    def test_warnings_include_error_description(
        self, client: TestClient, test_profile: Profile, _db_engine
    ):
        """Warnings include descriptive error messages."""
        with patch("career_os.services.company_research.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("Connection timeout")
            mock_factory.return_value = mock_provider

            response = client.post(
                "/api/research/company",
                json={
                    "company_name": "SomeCompany",
                    "profile_id": test_profile.id,
                },
            )

        warnings = response.json()["warnings"]
        assert any("Connection timeout" in w["error"] for w in warnings)


# ===========================================================================
# VAL-RESEARCH-010: Industry segment classification
# ===========================================================================


class TestIndustryClassification:
    """Test industry segment classification."""

    def test_industry_segment_present(self, client: TestClient, test_profile: Profile):
        """Known company has industry segment."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        segment = response.json()["industry_segment"]
        assert segment is not None
        assert len(segment) > 0

    def test_different_companies_different_industries(
        self, client: TestClient, test_profile: Profile
    ):
        """Different companies get distinct industry classifications."""
        resp_stripe = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp_datadog = client.post(
            "/api/research/company",
            json={
                "company_name": "Datadog",
                "profile_id": test_profile.id,
            },
        )
        stripe_industry = resp_stripe.json()["industry_segment"]
        datadog_industry = resp_datadog.json()["industry_segment"]

        assert stripe_industry is not None
        assert datadog_industry is not None
        assert stripe_industry != datadog_industry, (
            f"Industries should differ: Stripe='{stripe_industry}', Datadog='{datadog_industry}'"
        )

    def test_three_companies_distinct_classifications(
        self, client: TestClient, test_profile: Profile
    ):
        """Three different companies get distinct classifications (VAL-RESEARCH-010)."""
        companies = ["Stripe", "Datadog", "EvilCorp Misaligned"]
        industries = set()

        for name in companies:
            resp = client.post(
                "/api/research/company",
                json={
                    "company_name": name,
                    "profile_id": test_profile.id,
                },
            )
            assert resp.status_code == 200
            segment = resp.json()["industry_segment"]
            assert segment is not None
            industries.add(segment)

        assert len(industries) == 3, (
            f"Expected 3 distinct industries, got {len(industries)}: {industries}"
        )


# ===========================================================================
# Profile scoping tests
# ===========================================================================


class TestProfileScoping:
    """Test that company research requires valid profile ownership."""

    def test_research_with_valid_profile(self, client: TestClient, test_profile: Profile):
        """Research succeeds with a valid profile."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert response.status_code == 200

    def test_research_with_nonexistent_profile_404(self, client: TestClient):
        """Research with nonexistent profile returns 404."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": 99999,
            },
        )
        assert response.status_code == 404

    def test_both_profiles_can_research(
        self,
        client: TestClient,
        test_profile: Profile,
        second_profile: Profile,
    ):
        """Both profiles can independently research the same company."""
        resp1 = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp2 = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": second_profile.id,
            },
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ===========================================================================
# Determinism tests
# ===========================================================================


class TestDeterministicResponses:
    """Test that mock provider returns deterministic results."""

    def test_same_company_same_results(self, client: TestClient, test_profile: Profile):
        """Same company name returns identical results across calls."""
        resp1 = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        resp2 = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert resp1.json() == resp2.json()


# ===========================================================================
# Schema validation tests
# ===========================================================================


class TestSchemaValidation:
    """Test Pydantic schema validation on request/response."""

    def test_missing_profile_id_422(self, client: TestClient):
        """Missing profile_id returns 422."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
            },
        )
        assert response.status_code == 422

    def test_invalid_json_422(self, client: TestClient):
        """Invalid JSON body returns 422."""
        response = client.post(
            "/api/research/company",
            content="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_response_values_alignment_is_object(self, client: TestClient, test_profile: Profile):
        """Values alignment in response is an object with score and rationale."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        va = response.json()["values_alignment"]
        assert isinstance(va, dict)
        assert "score" in va
        assert "rationale" in va

    def test_warnings_is_list(self, client: TestClient, test_profile: Profile):
        """Warnings field is always a list."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        assert isinstance(response.json()["warnings"], list)


# ===========================================================================
# Mock provider AI feature integration
# ===========================================================================


class TestMockProviderCompanyResearch:
    """Test the mock AI provider's company research feature directly."""

    def test_mock_provider_stripe_response(self, client: TestClient, test_profile: Profile):
        """Mock provider returns full data for Stripe."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()

        # Stripe-specific assertions
        assert "Fintech" in data["industry_segment"]
        assert data["ats_platform"] == "Greenhouse"
        assert data["values_alignment"]["score"] == pytest.approx(8.5)
        assert data["funding"]["stage"] == "Series I"
        assert len(data["glassdoor"]["culture_keywords"]) >= 3

    def test_mock_provider_datadog_response(self, client: TestClient, test_profile: Profile):
        """Mock provider returns full data for Datadog."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Datadog",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()

        assert "Observability" in data["industry_segment"]
        assert data["ats_platform"] == "Greenhouse"
        assert data["values_alignment"]["score"] == pytest.approx(7.0)

    def test_mock_provider_evilcorp_response(self, client: TestClient, test_profile: Profile):
        """Mock provider returns low-aligned data for misaligned company."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "EvilCorp Misaligned",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()

        assert data["values_alignment"]["score"] == pytest.approx(2.0)
        assert data["ats_platform"] == "Workday"
        assert "Legacy" in data["industry_segment"]
        assert data["glassdoor"]["overall_rating"] == pytest.approx(2.3)


# ===========================================================================
# Fix: values_alignment rationale field
# ===========================================================================


class TestValuesAlignmentRationale:
    """Test that values_alignment includes rationale referencing user values."""

    def test_stripe_rationale_non_empty(self, client: TestClient, test_profile: Profile):
        """Stripe values alignment has meaningful rationale text."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        va = response.json()["values_alignment"]
        assert len(va["rationale"]) > 20
        # Rationale should reference user's values
        rationale_lower = va["rationale"].lower()
        assert any(
            kw in rationale_lower
            for kw in ["innovation", "autonomy", "collaborative", "impact", "transparency"]
        ), f"Rationale should reference user values: {va['rationale']}"

    def test_misaligned_rationale_references_conflicts(
        self, client: TestClient, test_profile: Profile
    ):
        """Misaligned company rationale explains poor alignment."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "EvilCorp Misaligned",
                "profile_id": test_profile.id,
            },
        )
        va = response.json()["values_alignment"]
        assert len(va["rationale"]) > 20
        assert va["score"] < 5.0

    def test_ai_failure_rationale_fallback(
        self, client: TestClient, test_profile: Profile, _db_engine
    ):
        """When AI fails, rationale has fallback text (not empty)."""
        with patch("career_os.services.company_research.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("fail")
            mock_factory.return_value = mock_provider

            response = client.post(
                "/api/research/company",
                json={
                    "company_name": "SomeCompany",
                    "profile_id": test_profile.id,
                },
            )

        va = response.json()["values_alignment"]
        assert len(va["rationale"]) > 0


# ===========================================================================
# Fix: employee_count and news fields
# ===========================================================================


class TestEmployeeCountAndNews:
    """Test that report includes employee_count and news section."""

    def test_stripe_has_employee_count(self, client: TestClient, test_profile: Profile):
        """Known company includes employee_count string."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert "employee_count" in data
        assert data["employee_count"] is not None
        assert isinstance(data["employee_count"], str)
        assert len(data["employee_count"]) > 0

    def test_stripe_has_news(self, client: TestClient, test_profile: Profile):
        """Known company includes news section with items."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Stripe",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert "news" in data
        assert isinstance(data["news"], list)
        assert len(data["news"]) > 0
        # Each news item has title
        for item in data["news"]:
            assert "title" in item
            assert len(item["title"]) > 0

    def test_datadog_has_employee_count_and_news(self, client: TestClient, test_profile: Profile):
        """Datadog includes employee_count and news."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Datadog",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert data["employee_count"] is not None
        assert isinstance(data["news"], list)
        assert len(data["news"]) > 0

    def test_obscure_company_null_employee_count(self, client: TestClient, test_profile: Profile):
        """Obscure company has null employee_count."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert data["employee_count"] is None

    def test_obscure_company_empty_news(self, client: TestClient, test_profile: Profile):
        """Obscure company has empty news list."""
        response = client.post(
            "/api/research/company",
            json={
                "company_name": "Obscure Unknown Startup ABC",
                "profile_id": test_profile.id,
            },
        )
        data = response.json()
        assert data["news"] == []

    def test_ai_failure_defaults_employee_count_and_news(
        self, client: TestClient, test_profile: Profile, _db_engine
    ):
        """When AI fails, employee_count is null and news is empty."""
        with patch("career_os.services.company_research.get_ai_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = RuntimeError("fail")
            mock_factory.return_value = mock_provider

            response = client.post(
                "/api/research/company",
                json={
                    "company_name": "SomeCompany",
                    "profile_id": test_profile.id,
                },
            )

        data = response.json()
        assert data["employee_count"] is None
        assert data["news"] == []
