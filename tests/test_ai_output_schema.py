"""AI output schema validation tests (G-461).

Validates that AI provider responses conform to expected schemas:
- score() returns valid fit_score, explanation, token_usage
- complete() returns valid string response with token_usage
- batch_score() raises NotImplementedError for mock (no batch support)
- Edge cases: empty prompts, special characters, very long prompts

All tests run against MockProvider (no API calls, < 1s each).
"""

import pytest

from career_os.ai.mock_provider import MockProvider
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
    TokenUsage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider() -> MockProvider:
    """Return a fresh MockProvider for each test."""
    return MockProvider()


@pytest.fixture
def sample_profile() -> dict:
    """Minimal profile data for scoring tests."""
    return {
        "name": "Jane Doe",
        "skills": ["Python", "FastAPI", "Docker"],
        "experience_years": 5,
        "location": "Berlin",
    }


# ---------------------------------------------------------------------------
# AIResponse base schema tests
# ---------------------------------------------------------------------------


class TestAIResponseBaseSchema:
    """AIResponse must always have required fields regardless of feature."""

    @pytest.mark.asyncio
    async def test_complete_response_has_content_string(self, provider: MockProvider) -> None:
        """complete() response content must be a non-empty string."""
        resp = await provider.complete("Tell me about FastAPI")
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.content, str)
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_complete_response_has_provider_field(self, provider: MockProvider) -> None:
        """complete() response must identify the provider."""
        resp = await provider.complete("Hello")
        assert resp.provider == "mock"

    @pytest.mark.asyncio
    async def test_complete_response_has_feature_field(self, provider: MockProvider) -> None:
        """complete() response feature must be AIFeature.complete."""
        resp = await provider.complete("Hello")
        assert resp.feature == AIFeature.complete

    @pytest.mark.asyncio
    async def test_complete_response_model_field(self, provider: MockProvider) -> None:
        """complete() response must have a model field."""
        resp = await provider.complete("Hello")
        assert isinstance(resp.model, str)
        assert len(resp.model) > 0

    @pytest.mark.asyncio
    async def test_score_response_is_ai_response(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """score() must return an AIResponse instance."""
        resp = await provider.score("Software Engineer at Acme", sample_profile)
        assert isinstance(resp, AIResponse)

    @pytest.mark.asyncio
    async def test_score_response_has_provider_field(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """score() response must identify the provider."""
        resp = await provider.score("Software Engineer at Acme", sample_profile)
        assert resp.provider == "mock"

    @pytest.mark.asyncio
    async def test_score_response_has_score_feature(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """score() response feature must be AIFeature.score."""
        resp = await provider.score("Software Engineer at Acme", sample_profile)
        assert resp.feature == AIFeature.score

    @pytest.mark.asyncio
    async def test_score_response_content_is_string(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """score() response content must be a non-empty string."""
        resp = await provider.score("Software Engineer at Acme", sample_profile)
        assert isinstance(resp.content, str)
        assert len(resp.content) > 0


# ---------------------------------------------------------------------------
# TokenUsage schema tests
# ---------------------------------------------------------------------------


class TestTokenUsageSchema:
    """TokenUsage fields when present must have valid integer values >= 0."""

    @pytest.mark.asyncio
    async def test_complete_usage_field_type(self, provider: MockProvider) -> None:
        """usage field on complete() response is None or TokenUsage instance."""
        resp = await provider.complete("Hello world")
        # Mock provider does not populate usage — it is allowed to be None
        assert resp.usage is None or isinstance(resp.usage, TokenUsage)

    @pytest.mark.asyncio
    async def test_score_usage_field_type(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """usage field on score() response is None or TokenUsage instance."""
        resp = await provider.score("Senior Python developer role", sample_profile)
        assert resp.usage is None or isinstance(resp.usage, TokenUsage)

    def test_token_usage_default_values(self) -> None:
        """TokenUsage defaults all token counts to 0."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_creation_input_tokens == 0
        assert usage.cache_read_input_tokens == 0

    def test_token_usage_explicit_values(self) -> None:
        """TokenUsage accepts valid non-negative integer token counts."""
        usage = TokenUsage(input_tokens=150, output_tokens=200)
        assert usage.input_tokens == 150
        assert usage.output_tokens == 200

    def test_token_usage_all_fields_non_negative(self) -> None:
        """All TokenUsage integer fields must be >= 0."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=30,
            cache_read_input_tokens=20,
        )
        assert usage.input_tokens >= 0
        assert usage.output_tokens >= 0
        assert usage.cache_creation_input_tokens >= 0
        assert usage.cache_read_input_tokens >= 0

    def test_token_usage_is_pydantic_model(self) -> None:
        """TokenUsage is a valid Pydantic model."""
        from pydantic import BaseModel

        assert issubclass(TokenUsage, BaseModel)


# ---------------------------------------------------------------------------
# ScoreResult schema tests
# ---------------------------------------------------------------------------


class TestScoreResultSchema:
    """score() structured field must conform to ScoreResult schema."""

    @pytest.mark.asyncio
    async def test_score_structured_is_score_result(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """score() structured data must be a ScoreResult instance."""
        resp = await provider.score("Product Manager at StartupCo", sample_profile)
        assert isinstance(resp.structured, ScoreResult)

    @pytest.mark.asyncio
    async def test_fit_score_in_range(self, provider: MockProvider, sample_profile: dict) -> None:
        """fit_score must be a float in [0, 10]."""
        resp = await provider.score("Data Scientist at BigTech", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        score = resp.structured.fit_score
        assert isinstance(score, float)
        assert 0.0 <= score <= 10.0

    @pytest.mark.asyncio
    async def test_readiness_score_in_range(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """readiness_score must be a float in [0, 100]."""
        resp = await provider.score("Backend Engineer at Corp", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        assert 0.0 <= resp.structured.readiness_score <= 100.0

    @pytest.mark.asyncio
    async def test_career_alignment_in_range(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """career_alignment must be a float in [0, 10]."""
        resp = await provider.score("DevOps at Cloud Inc", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        assert 0.0 <= resp.structured.career_alignment <= 10.0

    @pytest.mark.asyncio
    async def test_reasoning_is_non_empty_string(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """reasoning (explanation) must be a non-empty string."""
        resp = await provider.score("Full Stack Developer at Agency", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        reasoning = resp.structured.reasoning
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

    @pytest.mark.asyncio
    async def test_reasoning_meets_minimum_length(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """reasoning must be >= 100 chars (schema enforced in ScoreResponse)."""
        resp = await provider.score("Site Reliability Engineer at Platform", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        # Mock provider always produces multi-factor reasoning well above 100 chars
        assert len(resp.structured.reasoning) >= 100

    @pytest.mark.asyncio
    async def test_score_breakdown_has_at_least_three_factors(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """score_breakdown must have at least 3 ScoreBreakdownFactor entries."""
        resp = await provider.score("Machine Learning Engineer at AI Corp", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        breakdown = resp.structured.score_breakdown
        assert len(breakdown) >= 3
        for factor in breakdown:
            assert isinstance(factor, ScoreBreakdownFactor)

    @pytest.mark.asyncio
    async def test_score_breakdown_factors_have_required_fields(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """Each ScoreBreakdownFactor must have factor, contribution, description."""
        resp = await provider.score("TPM at Enterprise", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        for factor in resp.structured.score_breakdown:
            assert isinstance(factor.factor, str)
            assert len(factor.factor) > 0
            assert isinstance(factor.contribution, float)
            assert isinstance(factor.description, str)
            assert len(factor.description) > 0

    @pytest.mark.asyncio
    async def test_dimensional_scores_present_and_valid(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """dimensional_scores must be a DimensionalScores with all values in [0, 10]."""
        resp = await provider.score("Cloud Architect at TechFirm", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        dims = resp.structured.dimensional_scores
        assert isinstance(dims, DimensionalScores)
        for field_name in (
            "technical_fit",
            "seniority_alignment",
            "compensation_fit",
            "location_fit",
            "career_trajectory",
            "company_fit",
        ):
            value = getattr(dims, field_name)
            assert isinstance(value, float), f"{field_name} should be float"
            assert 0.0 <= value <= 10.0, f"{field_name}={value} out of [0, 10]"

    @pytest.mark.asyncio
    async def test_ats_keywords_list_of_ats_keyword(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """ats_keywords must be a list of ATSKeyword instances."""
        resp = await provider.score("iOS Developer at Mobile Startup", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        keywords = resp.structured.ats_keywords
        assert isinstance(keywords, list)
        for kw in keywords:
            assert isinstance(kw, ATSKeyword)
            assert isinstance(kw.keyword, str)
            assert len(kw.keyword) > 0
            assert isinstance(kw.matched, bool)

    @pytest.mark.asyncio
    async def test_ats_keyword_categories_are_valid(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """Each ATSKeyword category must be one of the allowed literals."""
        valid_categories = {"technical", "soft_skill", "tool", "certification", "domain"}
        resp = await provider.score("Frontend Engineer at SaaS", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        for kw in resp.structured.ats_keywords:
            assert kw.category in valid_categories, (
                f"Unexpected ATS keyword category: {kw.category!r}"
            )

    @pytest.mark.asyncio
    async def test_effort_flag_is_valid_value(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """effort_flag must be one of: low, medium, high."""
        resp = await provider.score("Sales Engineer at B2B", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        assert resp.structured.effort_flag in ("low", "medium", "high")

    @pytest.mark.asyncio
    async def test_prep_level_is_valid_value(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """prep_level must be one of: light, moderate, intensive."""
        resp = await provider.score("DevRel Engineer at Open Source Co", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        assert resp.structured.prep_level in ("light", "moderate", "intensive")

    @pytest.mark.asyncio
    async def test_estimated_salary_is_non_empty_string(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """estimated_salary must be a non-empty string."""
        resp = await provider.score("Staff Engineer at Growth Stage", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        assert isinstance(resp.structured.estimated_salary, str)
        assert len(resp.structured.estimated_salary) > 0

    @pytest.mark.asyncio
    async def test_desire_score_in_range_when_present(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """desire_score when present must be a float in [0, 10]."""
        resp = await provider.score("Principal Engineer at Late Stage", sample_profile)
        assert isinstance(resp.structured, ScoreResult)
        desire = resp.structured.desire_score
        if desire is not None:
            assert isinstance(desire, float)
            assert 0.0 <= desire <= 10.0


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same inputs must produce identical outputs (mock provider is deterministic)."""

    @pytest.mark.asyncio
    async def test_score_same_jd_same_profile_produces_same_score(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """Identical job description + profile produces identical fit_score."""
        jd = "Senior Python Engineer at TechCorp — Berlin, full remote option"
        resp1 = await provider.score(jd, sample_profile)
        resp2 = await provider.score(jd, sample_profile)
        assert isinstance(resp1.structured, ScoreResult)
        assert isinstance(resp2.structured, ScoreResult)
        assert resp1.structured.fit_score == resp2.structured.fit_score

    @pytest.mark.asyncio
    async def test_score_different_jds_produce_different_scores(
        self, provider: MockProvider, sample_profile: dict
    ) -> None:
        """Different job descriptions should generally produce different scores.

        The mock uses an MD5 seed so two distinct strings are extremely unlikely
        to collide — this tests that the seed-based variation mechanism works.
        """
        resp1 = await provider.score(
            "Senior Python Engineer at StartupA — machine learning focus", sample_profile
        )
        resp2 = await provider.score(
            "Golang Backend Developer at EnterpriseB — financial services platform", sample_profile
        )
        assert isinstance(resp1.structured, ScoreResult)
        assert isinstance(resp2.structured, ScoreResult)
        # Scores are derived from MD5 hash seeds — they should differ for distinct inputs
        assert resp1.structured.fit_score != resp2.structured.fit_score

    @pytest.mark.asyncio
    async def test_complete_same_prompt_same_content(self, provider: MockProvider) -> None:
        """Same prompt produces identical complete() response content."""
        r1 = await provider.complete("What are the key skills for a TPM role?")
        r2 = await provider.complete("What are the key skills for a TPM role?")
        assert r1.content == r2.content


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Validate provider handles edge-case inputs gracefully."""

    @pytest.mark.asyncio
    async def test_complete_empty_string_prompt(self, provider: MockProvider) -> None:
        """complete() with an empty string prompt must return a valid AIResponse."""
        resp = await provider.complete("")
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.content, str)

    @pytest.mark.asyncio
    async def test_complete_special_characters(self, provider: MockProvider) -> None:
        """complete() handles special characters in prompt without crashing."""
        special = "Hello <world> & 'friends' — €100 \n\t\r 中文 🎉"
        resp = await provider.complete(special)
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.content, str)

    @pytest.mark.asyncio
    async def test_complete_very_long_prompt(self, provider: MockProvider) -> None:
        """complete() handles very long prompts (10,000 chars) without crashing."""
        long_prompt = "A " * 5000  # 10,000 chars
        resp = await provider.complete(long_prompt)
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.content, str)
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_score_empty_job_description(self, provider: MockProvider) -> None:
        """score() with empty JD still returns a valid ScoreResult."""
        resp = await provider.score("", {"name": "Test User"})
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.structured, ScoreResult)
        assert 0.0 <= resp.structured.fit_score <= 10.0

    @pytest.mark.asyncio
    async def test_score_empty_profile_data(self, provider: MockProvider) -> None:
        """score() with minimal/empty profile dict still returns valid schema."""
        resp = await provider.score("Senior Engineer at Acme", {})
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.structured, ScoreResult)
        assert 0.0 <= resp.structured.fit_score <= 10.0

    @pytest.mark.asyncio
    async def test_score_very_long_job_description(self, provider: MockProvider) -> None:
        """score() handles very long job descriptions (10,000 chars) without crashing."""
        long_jd = "Requirement: " * 800
        resp = await provider.score(long_jd, {"name": "Candidate"})
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.structured, ScoreResult)
        assert 0.0 <= resp.structured.fit_score <= 10.0

    @pytest.mark.asyncio
    async def test_score_special_characters_in_jd(self, provider: MockProvider) -> None:
        """score() handles special characters in job description without crashing."""
        special_jd = (
            "Senior Engineer — €120k salary\n"
            "Requirements: <Python>, 'FastAPI', & Docker\n"
            "Location: Zürich/Berlin 中文 🚀"
        )
        resp = await provider.score(special_jd, {"name": "Candidate"})
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.structured, ScoreResult)

    @pytest.mark.asyncio
    async def test_score_unicode_profile_data(self, provider: MockProvider) -> None:
        """score() handles unicode in profile data without crashing."""
        unicode_profile = {
            "name": "Ünïcödë Nämé",
            "location": "Zürich",
            "skills": ["Python", "机器学习"],
        }
        resp = await provider.score("AI Engineer at GlobalCo", unicode_profile)
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.structured, ScoreResult)
        assert 0.0 <= resp.structured.fit_score <= 10.0


# ---------------------------------------------------------------------------
# Batch scoring tests (mock has no batch support)
# ---------------------------------------------------------------------------


class TestBatchScoring:
    """batch_score() is not supported by MockProvider — should raise NotImplementedError."""

    @pytest.mark.asyncio
    async def test_batch_score_raises_not_implemented(self, provider: MockProvider) -> None:
        """batch_score() raises NotImplementedError for mock provider."""
        jobs = [
            {"id": 1, "description": "Engineer at Acme"},
            {"id": 2, "description": "Engineer at BetaCo"},
        ]
        with pytest.raises(NotImplementedError):
            await provider.batch_score(jobs, {"name": "Test"})

    @pytest.mark.asyncio
    async def test_get_batch_results_raises_not_implemented(self, provider: MockProvider) -> None:
        """get_batch_results() raises NotImplementedError for mock provider."""
        with pytest.raises(NotImplementedError):
            await provider.get_batch_results("fake-batch-id-123")


# ---------------------------------------------------------------------------
# complete() structured field for non-score features
# ---------------------------------------------------------------------------


class TestCompleteStructuredField:
    """complete() with explicit feature types returns correct structured data or None."""

    @pytest.mark.asyncio
    async def test_complete_feature_returns_none_structured(self, provider: MockProvider) -> None:
        """AIFeature.complete returns no structured data."""
        resp = await provider.complete("Write a cover letter", feature=AIFeature.complete)
        assert resp.structured is None

    @pytest.mark.asyncio
    async def test_score_feature_via_complete_returns_score_result(
        self, provider: MockProvider
    ) -> None:
        """AIFeature.score via complete() returns ScoreResult structured data."""
        resp = await provider.complete("Software Engineer at Tech Inc", feature=AIFeature.score)
        assert isinstance(resp.structured, ScoreResult)

    @pytest.mark.asyncio
    async def test_gap_analysis_feature_returns_structured(self, provider: MockProvider) -> None:
        """AIFeature.gap_analysis returns GapAnalysisResult structured data."""
        from career_os.schemas.ai import GapAnalysisResult

        resp = await provider.complete("Analyze skill gaps", feature=AIFeature.gap_analysis)
        assert isinstance(resp.structured, GapAnalysisResult)

    @pytest.mark.asyncio
    async def test_coaching_feature_returns_structured(self, provider: MockProvider) -> None:
        """AIFeature.coaching returns CoachingResult structured data."""
        from career_os.schemas.ai import CoachingResult

        resp = await provider.complete("Coaching suggestions", feature=AIFeature.coaching)
        assert isinstance(resp.structured, CoachingResult)

    @pytest.mark.asyncio
    async def test_voice_cover_letter_returns_no_structured(self, provider: MockProvider) -> None:
        """Voice features with no structured data return None for structured."""
        resp = await provider.complete("Write a cover letter", feature=AIFeature.voice_cover_letter)
        assert resp.structured is None
        assert isinstance(resp.content, str)
        assert len(resp.content) > 0
