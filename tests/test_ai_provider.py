"""Tests for AI provider abstraction layer.

Covers:
- MockProvider deterministic responses for all features
- Provider factory selection via AI_PROVIDER env var
- Unsupported provider error handling
- API endpoint POST /api/ai/complete
- API endpoint GET /api/ai/provider
"""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from career_os.ai.base import AIProvider
from career_os.ai.factory import UnsupportedProviderError, get_ai_provider
from career_os.ai.mock_provider import MockProvider
from career_os.ai.openrouter_provider import OpenRouterProvider
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    CoachingResult,
    CompanyResearchResult,
    GapAnalysisResult,
    GoalRecalibrationResult,
    InterviewPrepResult,
    LearningRecommendationsResult,
    ScoreBreakdownFactor,
    ScoreResult,
)

# ---------------------------------------------------------------------------
# MockProvider unit tests
# ---------------------------------------------------------------------------


class TestMockProvider:
    """Test MockProvider returns deterministic, schema-valid responses."""

    @pytest.fixture
    def provider(self) -> MockProvider:
        return MockProvider()

    def test_name(self, provider: MockProvider) -> None:
        assert provider.name == "mock"

    def test_is_ai_provider(self, provider: MockProvider) -> None:
        assert isinstance(provider, AIProvider)

    @pytest.mark.asyncio
    async def test_complete_generic(self, provider: MockProvider) -> None:
        """Generic complete() returns text response with no structured data."""
        resp = await provider.complete("Hello world")
        assert isinstance(resp, AIResponse)
        assert resp.provider == "mock"
        assert resp.feature == AIFeature.complete
        assert "Hello world" in resp.content
        assert resp.structured is None
        assert resp.model == "mock-v1"

    @pytest.mark.asyncio
    async def test_complete_deterministic(self, provider: MockProvider) -> None:
        """Same prompt produces identical responses."""
        r1 = await provider.complete("test prompt")
        r2 = await provider.complete("test prompt")
        assert r1.content == r2.content

    @pytest.mark.asyncio
    async def test_score(self, provider: MockProvider) -> None:
        """score() returns ScoreResult with valid schema."""
        resp = await provider.score("Software Engineer at Acme", {"name": "Jane"})
        assert isinstance(resp, AIResponse)
        assert resp.feature == AIFeature.score
        assert isinstance(resp.structured, ScoreResult)
        s = resp.structured
        assert 0 <= s.fit_score <= 10
        assert len(s.reasoning) >= 100
        assert s.estimated_salary
        assert s.effort_flag in ("low", "medium", "high")
        assert 0 <= s.readiness_score <= 100
        assert 0 <= s.career_alignment <= 10

    @pytest.mark.asyncio
    async def test_score_deterministic(self, provider: MockProvider) -> None:
        """Same job+profile produces identical score."""
        r1 = await provider.score("Engineer at Acme", {"name": "V"})
        r2 = await provider.score("Engineer at Acme", {"name": "V"})
        assert r1.structured.fit_score == r2.structured.fit_score

    @pytest.mark.asyncio
    async def test_score_varied(self, provider: MockProvider) -> None:
        """Different jobs produce different scores."""
        r1 = await provider.score("Frontend Developer at Small Startup", {"name": "V"})
        r2 = await provider.score("VP Engineering at Enterprise Corp", {"name": "V"})
        # At least one field should differ (with different input text the hash seed differs)
        assert (
            r1.structured.fit_score != r2.structured.fit_score
            or r1.structured.readiness_score != r2.structured.readiness_score
        )

    @pytest.mark.asyncio
    async def test_gap_analysis(self, provider: MockProvider) -> None:
        """gap_analysis feature returns GapAnalysisResult."""
        resp = await provider.complete("Analyze gaps for role X", feature=AIFeature.gap_analysis)
        assert resp.feature == AIFeature.gap_analysis
        assert isinstance(resp.structured, GapAnalysisResult)
        g = resp.structured
        assert len(g.gaps) >= 1
        assert 0 <= g.readiness_score <= 100
        assert g.summary
        # Verify gap structure
        for gap in g.gaps:
            assert "skill_name" in gap
            assert "required_level" in gap
            assert "current_level" in gap
            assert "severity" in gap
            assert "distance" in gap

    @pytest.mark.asyncio
    async def test_coaching(self, provider: MockProvider) -> None:
        """coaching feature returns CoachingResult."""
        resp = await provider.complete("Coaching suggestions", feature=AIFeature.coaching)
        assert resp.feature == AIFeature.coaching
        assert isinstance(resp.structured, CoachingResult)
        c = resp.structured
        assert len(c.suggestions) >= 1
        assert c.focus_area
        for s in c.suggestions:
            assert "action" in s
            assert "hours" in s
            assert "weeks" in s
            assert "difficulty" in s

    @pytest.mark.asyncio
    async def test_goal_recalibration(self, provider: MockProvider) -> None:
        """goal_recalibration feature returns GoalRecalibrationResult."""
        resp = await provider.complete("Recalibrate goals", feature=AIFeature.goal_recalibration)
        assert resp.feature == AIFeature.goal_recalibration
        assert isinstance(resp.structured, GoalRecalibrationResult)
        r = resp.structured
        assert r.recalibration_notes
        assert len(r.suggested_adjustments) >= 1
        assert r.market_reality

    @pytest.mark.asyncio
    async def test_interview_prep(self, provider: MockProvider) -> None:
        """interview_prep feature returns InterviewPrepResult."""
        resp = await provider.complete("Prep for interview", feature=AIFeature.interview_prep)
        assert resp.feature == AIFeature.interview_prep
        assert isinstance(resp.structured, InterviewPrepResult)
        p = resp.structured
        assert len(p.topics) >= 1
        assert len(p.questions) >= 5
        assert len(p.checklist) >= 1
        assert p.total_prep_hours > 0
        for q in p.questions:
            assert "question" in q
            assert "category" in q

    @pytest.mark.asyncio
    async def test_company_research(self, provider: MockProvider) -> None:
        """company_research feature returns CompanyResearchResult."""
        resp = await provider.complete("Research Acme Corp", feature=AIFeature.company_research)
        assert resp.feature == AIFeature.company_research
        assert isinstance(resp.structured, CompanyResearchResult)
        cr = resp.structured
        assert cr.tech_stack
        assert cr.funding
        assert cr.glassdoor
        # values_alignment is now a dict with score and rationale (or a float for backward compat)
        if isinstance(cr.values_alignment, dict):
            assert 0 <= cr.values_alignment["score"] <= 10
            assert len(cr.values_alignment.get("rationale", "")) > 0
        else:
            assert 0 <= cr.values_alignment <= 10
        assert cr.hiring_patterns

    @pytest.mark.asyncio
    async def test_learning_recommendations(self, provider: MockProvider) -> None:
        """learning_recommendations feature returns LearningRecommendationsResult."""
        resp = await provider.complete(
            "Recommend learning", feature=AIFeature.learning_recommendations
        )
        assert resp.feature == AIFeature.learning_recommendations
        assert isinstance(resp.structured, LearningRecommendationsResult)
        lr = resp.structured
        assert len(lr.recommendations) >= 1
        assert lr.total_hours > 0
        for rec in lr.recommendations:
            assert "title" in rec
            assert "url" in rec
            assert "hours" in rec
            assert "provider" in rec


# ---------------------------------------------------------------------------
# ScoreResult schema validation tests
# ---------------------------------------------------------------------------


class TestScoreResultValidation:
    """Test ScoreResult.score_breakdown requires ≥3 factors."""

    def _base_score_kwargs(self, breakdown: list) -> dict:
        """Return minimal valid ScoreResult kwargs with the given breakdown."""
        return {
            "fit_score": 7.5,
            "reasoning": "Strong technical fit with good culture alignment.",
            "estimated_salary": "120,000-160,000 EUR",
            "effort_flag": "medium",
            "prep_level": "moderate",
            "prep_notes": "Study domain.",
            "readiness_score": 72.0,
            "career_alignment": 8.0,
            "score_breakdown": breakdown,
        }

    def _make_factors(self, n: int) -> list[ScoreBreakdownFactor]:
        """Create n ScoreBreakdownFactor instances."""
        return [
            ScoreBreakdownFactor(
                factor=f"Factor {i + 1}",
                contribution=round((i + 1) * 0.5, 1),
                description=f"Description for factor {i + 1}",
            )
            for i in range(n)
        ]

    def test_score_result_with_3_factors_valid(self) -> None:
        """ScoreResult with exactly 3 factors is valid."""
        result = ScoreResult(**self._base_score_kwargs(self._make_factors(3)))
        assert len(result.score_breakdown) == 3

    def test_score_result_with_5_factors_valid(self) -> None:
        """ScoreResult with 5 factors is valid."""
        result = ScoreResult(**self._base_score_kwargs(self._make_factors(5)))
        assert len(result.score_breakdown) == 5

    def test_score_result_with_0_factors_raises(self) -> None:
        """ScoreResult with 0 factors raises ValidationError."""
        with pytest.raises(ValidationError, match="score_breakdown"):
            ScoreResult(**self._base_score_kwargs([]))

    def test_score_result_with_1_factor_raises(self) -> None:
        """ScoreResult with 1 factor raises ValidationError."""
        with pytest.raises(ValidationError, match="score_breakdown"):
            ScoreResult(**self._base_score_kwargs(self._make_factors(1)))

    def test_score_result_with_2_factors_raises(self) -> None:
        """ScoreResult with 2 factors raises ValidationError."""
        with pytest.raises(ValidationError, match="score_breakdown"):
            ScoreResult(**self._base_score_kwargs(self._make_factors(2)))

    def test_score_result_missing_breakdown_raises(self) -> None:
        """ScoreResult without score_breakdown field raises ValidationError."""
        kwargs = self._base_score_kwargs([])
        del kwargs["score_breakdown"]
        with pytest.raises(ValidationError, match="score_breakdown"):
            ScoreResult(**kwargs)

    @pytest.mark.asyncio
    async def test_mock_provider_returns_at_least_3_factors(self) -> None:
        """MockProvider always returns ≥3 score_breakdown factors."""
        provider = MockProvider()
        prompts = [
            "Frontend Developer at Small Startup",
            "VP Engineering at Enterprise Corp",
            "Senior TPM at AI Company",
            "Junior DevOps at Cloud Platform",
        ]
        for prompt in prompts:
            resp = await provider.score(prompt, {"name": "Test"})
            assert isinstance(resp.structured, ScoreResult)
            breakdown = resp.structured.score_breakdown
            assert len(breakdown) >= 3, (
                f"MockProvider returned {len(breakdown)} factors for '{prompt}'"
            )


# ---------------------------------------------------------------------------
# Provider factory tests
# ---------------------------------------------------------------------------


class TestProviderFactory:
    """Test get_ai_provider factory function."""

    def test_default_is_mock(self) -> None:
        """Default provider (no env var) is mock."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_PROVIDER", None)
            provider = get_ai_provider()
            assert isinstance(provider, MockProvider)

    def test_explicit_mock(self) -> None:
        """AI_PROVIDER=mock returns MockProvider."""
        provider = get_ai_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_explicit_openrouter(self) -> None:
        """AI_PROVIDER=openrouter with key returns OpenRouterProvider."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-key"}):
            provider = get_ai_provider("openrouter")
            assert isinstance(provider, OpenRouterProvider)

    def test_env_var_selection(self) -> None:
        """AI_PROVIDER env var controls provider selection."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            provider = get_ai_provider()
            assert isinstance(provider, MockProvider)

    def test_unsupported_provider_raises(self) -> None:
        """Unsupported provider raises UnsupportedProviderError."""
        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_ai_provider("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "mock" in str(exc_info.value)
        assert "openrouter" in str(exc_info.value)

    def test_case_insensitive(self) -> None:
        """Provider names are case-insensitive."""
        provider = get_ai_provider("Mock")
        assert isinstance(provider, MockProvider)

    def test_whitespace_trimmed(self) -> None:
        """Leading/trailing whitespace is trimmed."""
        provider = get_ai_provider("  mock  ")
        assert isinstance(provider, MockProvider)

    def test_openrouter_without_key_raises(self) -> None:
        """OpenRouter without API key raises ValueError."""
        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False),
            pytest.raises(ValueError, match="OPENROUTER_API_KEY"),
        ):
            get_ai_provider("openrouter")


# ---------------------------------------------------------------------------
# OpenRouterProvider unit tests
# ---------------------------------------------------------------------------


class TestOpenRouterProvider:
    """Test OpenRouterProvider initialization."""

    def test_name(self) -> None:
        provider = OpenRouterProvider(api_key="sk-test")
        assert provider.name == "openrouter"

    def test_is_ai_provider(self) -> None:
        provider = OpenRouterProvider(api_key="sk-test")
        assert isinstance(provider, AIProvider)

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            OpenRouterProvider(api_key="")

    def test_custom_model(self) -> None:
        provider = OpenRouterProvider(api_key="sk-test", model="openai/gpt-4o")
        assert provider._model == "openai/gpt-4o"


# ---------------------------------------------------------------------------
# OpenRouter structured response parsing tests
# ---------------------------------------------------------------------------


class TestOpenRouterStructuredParsing:
    """Test _try_parse_structured handles ALL AI feature types, not just score."""

    def test_parse_score_result(self) -> None:
        """Score JSON is parsed into ScoreResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "fit_score": 7.5,
                "reasoning": "x" * 100,
                "estimated_salary": "120k EUR",
                "effort_flag": "medium",
                "prep_level": "moderate",
                "prep_notes": "Study X.",
                "readiness_score": 72.0,
                "career_alignment": 8.0,
                "score_breakdown": [
                    {
                        "factor": "Technical Skills",
                        "contribution": 2.0,
                        "description": "Strong match",
                    },
                    {"factor": "Culture Fit", "contribution": 1.5, "description": "Good alignment"},
                    {
                        "factor": "Location",
                        "contribution": -0.5,
                        "description": "Remote preference",
                    },
                ],
            }
        )
        result = _try_parse_structured(content, AIFeature.score)
        assert isinstance(result, ScoreResult)
        assert result.fit_score == pytest.approx(7.5)

    def test_parse_gap_analysis_result(self) -> None:
        """Gap analysis JSON is parsed into GapAnalysisResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "gaps": [
                    {
                        "skill_name": "Python",
                        "required_level": "advanced",
                        "current_level": "intermediate",
                        "severity": "critical",
                        "distance": 1,
                    }
                ],
                "readiness_score": 65.0,
                "summary": "Some gaps identified.",
            }
        )
        result = _try_parse_structured(content, AIFeature.gap_analysis)
        assert isinstance(result, GapAnalysisResult)
        assert len(result.gaps) == 1
        assert result.readiness_score == pytest.approx(65.0)

    def test_parse_coaching_result(self) -> None:
        """Coaching JSON is parsed into CoachingResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "suggestions": [
                    {
                        "action": "Do X",
                        "hours": 10,
                        "weeks": 2,
                        "difficulty": "medium",
                        "priority": 1,
                    }
                ],
                "focus_area": "Infrastructure",
            }
        )
        result = _try_parse_structured(content, AIFeature.coaching)
        assert isinstance(result, CoachingResult)
        assert len(result.suggestions) == 1
        assert result.focus_area == "Infrastructure"

    def test_parse_goal_recalibration_result(self) -> None:
        """Goal recalibration JSON is parsed into GoalRecalibrationResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "recalibration_notes": "Market suggests adjustments.",
                "suggested_adjustments": [{"goal": "G1", "adjustment": "A1", "reason": "R1"}],
                "market_reality": "Demand is high.",
            }
        )
        result = _try_parse_structured(content, AIFeature.goal_recalibration)
        assert isinstance(result, GoalRecalibrationResult)
        assert result.recalibration_notes

    def test_parse_interview_prep_result(self) -> None:
        """Interview prep JSON is parsed into InterviewPrepResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "topics": [{"topic": "AI", "relevance": "high", "difficulty": "medium"}],
                "questions": [
                    {"question": f"Q{i}?", "category": "behavioral", "difficulty": "medium"}
                    for i in range(5)
                ],
                "checklist": [{"item": "Review blog", "time_minutes": 30, "priority": "high"}],
                "total_prep_hours": 3.5,
            }
        )
        result = _try_parse_structured(content, AIFeature.interview_prep)
        assert isinstance(result, InterviewPrepResult)
        assert len(result.questions) == 5

    def test_parse_company_research_result(self) -> None:
        """Company research JSON is parsed into CompanyResearchResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "tech_stack": {"backend": ["Python"]},
                "funding": {"stage": "Series B"},
                "glassdoor": {"overall_rating": 4.0},
                "values_alignment": 7.0,
                "ats_platform": "Greenhouse",
                "hiring_patterns": {"active_postings": 20},
                "industry_segment": "SaaS",
            }
        )
        result = _try_parse_structured(content, AIFeature.company_research)
        assert isinstance(result, CompanyResearchResult)
        assert result.ats_platform == "Greenhouse"

    def test_parse_learning_recommendations_result(self) -> None:
        """Learning recommendations JSON is parsed into LearningRecommendationsResult."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = json.dumps(
            {
                "recommendations": [
                    {
                        "title": "Course A",
                        "url": "https://example.com",
                        "hours": 10,
                        "provider": "Udemy",
                        "difficulty": "intermediate",
                        "type": "paid",
                    }
                ],
                "total_hours": 10.0,
            }
        )
        result = _try_parse_structured(content, AIFeature.learning_recommendations)
        assert isinstance(result, LearningRecommendationsResult)
        assert len(result.recommendations) == 1

    def test_parse_complete_returns_none(self) -> None:
        """complete feature always returns None (unstructured)."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        result = _try_parse_structured("Hello world", AIFeature.complete)
        assert result is None

    def test_parse_markdown_code_block(self) -> None:
        """JSON wrapped in markdown code fences is extracted correctly."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        content = (
            "```json\n"
            + json.dumps(
                {
                    "suggestions": [
                        {
                            "action": "Do X",
                            "hours": 5,
                            "weeks": 1,
                            "difficulty": "low",
                            "priority": 1,
                        }
                    ],
                    "focus_area": "Skills",
                }
            )
            + "\n```"
        )
        result = _try_parse_structured(content, AIFeature.coaching)
        assert isinstance(result, CoachingResult)

    def test_parse_invalid_json_returns_none(self) -> None:
        """Invalid JSON gracefully returns None instead of crashing."""
        from career_os.ai.openrouter_provider import _try_parse_structured

        result = _try_parse_structured("not valid json {{{", AIFeature.score)
        assert result is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestAICompleteEndpoint:
    """Test POST /api/ai/complete and GET /api/ai/provider."""

    @pytest.fixture
    def client(self) -> TestClient:
        from career_os.main import app

        return TestClient(app)

    def test_complete_mock_200(self, client: TestClient) -> None:
        """POST /api/ai/complete with mock provider returns 200."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Hello", "feature": "complete"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "mock"
        assert data["feature"] == "complete"
        assert "Hello" in data["content"]

    def test_complete_score_structured(self, client: TestClient) -> None:
        """POST /api/ai/complete with score feature returns structured ScoreResult."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Score this job", "feature": "score"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature"] == "score"
        assert data["structured"] is not None
        s = data["structured"]
        assert "fit_score" in s
        assert "reasoning" in s
        assert "readiness_score" in s

    def test_complete_gap_analysis_structured(self, client: TestClient) -> None:
        """POST /api/ai/complete with gap_analysis feature returns structured data."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Analyze gaps", "feature": "gap_analysis"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["structured"] is not None
        assert "gaps" in data["structured"]
        assert "readiness_score" in data["structured"]

    def test_complete_coaching_structured(self, client: TestClient) -> None:
        """POST /api/ai/complete with coaching feature returns structured data."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Coach me", "feature": "coaching"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["structured"] is not None
        assert "suggestions" in data["structured"]

    def test_complete_interview_prep_structured(self, client: TestClient) -> None:
        """POST /api/ai/complete with interview_prep feature returns structured data."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Prep me", "feature": "interview_prep"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["structured"] is not None
        assert "topics" in data["structured"]
        assert "questions" in data["structured"]
        assert len(data["structured"]["questions"]) >= 5

    def test_complete_company_research_structured(self, client: TestClient) -> None:
        """POST /api/ai/complete with company_research feature returns structured data."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Research Acme", "feature": "company_research"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["structured"] is not None
        assert "tech_stack" in data["structured"]
        assert "funding" in data["structured"]

    def test_complete_unsupported_provider_422(self, client: TestClient) -> None:
        """POST /api/ai/complete with unsupported provider returns 422."""
        with patch.dict(os.environ, {"AI_PROVIDER": "nonexistent"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Hello", "feature": "complete"},
            )
        assert resp.status_code == 422
        data = resp.json()
        assert "nonexistent" in data["detail"]
        assert "Supported providers" in data["detail"]

    def test_complete_empty_prompt_422(self, client: TestClient) -> None:
        """POST /api/ai/complete with empty prompt returns 422."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "", "feature": "complete"},
            )
        assert resp.status_code == 422

    def test_get_provider(self, client: TestClient) -> None:
        """GET /api/ai/provider returns current provider name."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 200
        assert resp.json()["provider"] == "mock"

    def test_get_provider_unsupported_422(self, client: TestClient) -> None:
        """GET /api/ai/provider with unsupported provider returns 422."""
        with patch.dict(os.environ, {"AI_PROVIDER": "nonexistent"}):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 422

    def test_complete_all_features_valid(self, client: TestClient) -> None:
        """Every AIFeature returns 200 with valid structured data from mock provider."""
        features = [
            "complete",
            "score",
            "gap_analysis",
            "coaching",
            "goal_recalibration",
            "interview_prep",
            "company_research",
            "learning_recommendations",
        ]
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            for feature in features:
                resp = client.post(
                    "/api/ai/complete",
                    json={"prompt": f"Test {feature}", "feature": feature},
                )
                assert resp.status_code == 200, f"Feature {feature} returned {resp.status_code}"
                data = resp.json()
                assert data["provider"] == "mock"
                assert data["feature"] == feature
                # All features except 'complete' should have structured data
                if feature != "complete":
                    assert data["structured"] is not None, (
                        f"Feature {feature} missing structured data"
                    )

    def test_complete_with_context(self, client: TestClient) -> None:
        """POST /api/ai/complete accepts optional context field."""
        with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
            resp = client.post(
                "/api/ai/complete",
                json={
                    "prompt": "Test with context",
                    "feature": "complete",
                    "context": {"application_id": 42},
                },
            )
        assert resp.status_code == 200

    def test_complete_missing_api_key_422(self, client: TestClient) -> None:
        """POST /api/ai/complete with openrouter and no API key returns 422, not 500."""
        with patch.dict(os.environ, {"AI_PROVIDER": "openrouter", "OPENROUTER_API_KEY": ""}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Hello", "feature": "complete"},
            )
        assert resp.status_code == 422
        data = resp.json()
        assert "OPENROUTER_API_KEY" in data["detail"]
        assert "configuration error" in data["detail"].lower()

    def test_get_provider_missing_api_key_422(self, client: TestClient) -> None:
        """GET /api/ai/provider with openrouter and no API key returns 422, not 500."""
        with patch.dict(os.environ, {"AI_PROVIDER": "openrouter", "OPENROUTER_API_KEY": ""}):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 422
        data = resp.json()
        assert "OPENROUTER_API_KEY" in data["detail"]
