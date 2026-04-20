"""Pydantic schemas for AI provider layer."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from career_os.schemas.constraints import INT64_MAX, INT64_MIN

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AIFeature(StrEnum):
    """Supported AI feature types."""

    complete = "complete"
    score = "score"
    gap_analysis = "gap_analysis"
    coaching = "coaching"
    goal_recalibration = "goal_recalibration"
    interview_prep = "interview_prep"
    company_research = "company_research"
    learning_recommendations = "learning_recommendations"
    interview_format = "interview_format"
    interview_patterns = "interview_patterns"
    voice_cover_letter = "voice_cover_letter"
    voice_coaching = "voice_coaching"
    voice_job_evaluation = "voice_job_evaluation"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Feature → default complexity tier mapping
# ---------------------------------------------------------------------------
# Lazy import to avoid circular dependency — ComplexityTier lives in
# career_os.ai.base which imports AIFeature from this module.  We define the
# map as a module-level function so callers import it after both modules have
# loaded.


def _build_feature_tier_map() -> dict:  # noqa: UP006 — deferred type
    """Build the AIFeature → ComplexityTier mapping.

    Called lazily at first access via :func:`get_feature_tier_map` to avoid
    circular imports between ``schemas.ai`` and ``ai.base``.
    """
    from career_os.ai.base import ComplexityTier

    return {
        AIFeature.score: ComplexityTier.STANDARD,
        AIFeature.gap_analysis: ComplexityTier.STANDARD,
        AIFeature.coaching: ComplexityTier.STANDARD,
        AIFeature.goal_recalibration: ComplexityTier.STANDARD,
        AIFeature.interview_prep: ComplexityTier.STANDARD,
        AIFeature.company_research: ComplexityTier.STANDARD,
        AIFeature.learning_recommendations: ComplexityTier.SIMPLE,
        AIFeature.interview_format: ComplexityTier.SIMPLE,
        AIFeature.interview_patterns: ComplexityTier.SIMPLE,
        AIFeature.complete: ComplexityTier.STANDARD,
        AIFeature.voice_cover_letter: ComplexityTier.STANDARD,
        AIFeature.voice_coaching: ComplexityTier.STANDARD,
        AIFeature.voice_job_evaluation: ComplexityTier.STANDARD,
    }


_FEATURE_TIER_MAP_CACHE: dict | None = None


def get_feature_tier_map() -> dict:
    """Return the AIFeature → ComplexityTier mapping (cached after first call)."""
    global _FEATURE_TIER_MAP_CACHE  # noqa: PLW0603
    if _FEATURE_TIER_MAP_CACHE is None:
        _FEATURE_TIER_MAP_CACHE = _build_feature_tier_map()
    return _FEATURE_TIER_MAP_CACHE


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AICompleteRequest(BaseModel):
    """Request body for POST /api/ai/complete."""

    prompt: str = Field(..., min_length=1, description="The prompt text to send to the AI provider")
    feature: AIFeature = Field(
        default=AIFeature.complete,
        description="AI feature type — controls response schema for mock provider",
    )
    context: dict | None = Field(
        default=None,
        description="Optional context data (e.g. application_id, profile data)",
    )


# ---------------------------------------------------------------------------
# Sub-schemas for structured AI responses
# ---------------------------------------------------------------------------


class ScoreBreakdownFactor(BaseModel):
    """A single factor in the score breakdown."""

    factor: str = Field(..., description="Name of the scoring factor")
    contribution: float = Field(..., description="Positive or negative contribution value")
    description: str = Field(..., description="Explanation of this factor's impact")


class DimensionalScores(BaseModel):
    """Six dimensional sub-scores for a job fit (0-10 each).

    Maps to the scoring weight factors on a per-dimension basis:

    * ``technical_fit`` — skills/tools match and experience alignment
    * ``seniority_alignment`` — over/under-qualified detection
    * ``compensation_fit`` — salary range vs expectations
    * ``location_fit`` — remote policy, commute, relocation
    * ``career_trajectory`` — does the role advance stated goals
    * ``company_fit`` — company stage, industry, culture signals
    """

    technical_fit: float = Field(..., ge=0, le=10)
    seniority_alignment: float = Field(..., ge=0, le=10)
    compensation_fit: float = Field(..., ge=0, le=10)
    location_fit: float = Field(..., ge=0, le=10)
    career_trajectory: float = Field(..., ge=0, le=10)
    company_fit: float = Field(..., ge=0, le=10)


ATSKeywordCategory = Literal["technical", "soft_skill", "tool", "certification", "domain"]


class ATSKeyword(BaseModel):
    """A single ATS keyword extracted from a job description.

    Each keyword is categorized and marked as matched or unmatched against the
    candidate's profile.
    """

    keyword: str = Field(..., description="The extracted keyword or phrase")
    category: ATSKeywordCategory = Field(..., description="Keyword category bucket")
    matched: bool = Field(
        ..., description="True if the candidate profile demonstrates this keyword"
    )


class ScoreResult(BaseModel):
    """Structured scoring response."""

    fit_score: float = Field(..., ge=0, le=10, description="Overall fit score 0-10")
    reasoning: str = Field(..., description="Detailed scoring explanation")
    estimated_salary: str = Field(..., description="Estimated salary range")
    effort_flag: str = Field(..., description="Effort level: low / medium / high")
    prep_level: str = Field(..., description="Preparation required")
    prep_notes: str = Field(..., description="Notes on how to prepare")
    readiness_score: float = Field(..., ge=0, le=100, description="Readiness percentage 0-100")
    career_alignment: float = Field(..., ge=0, le=10, description="Career alignment score 0-10")
    score_breakdown: list[ScoreBreakdownFactor] = Field(
        ...,
        min_length=3,
        description="Detailed breakdown of scoring factors with +/- contributions (≥3 factors)",
    )
    dimensional_scores: DimensionalScores | None = Field(
        default=None,
        description="Six dimensional sub-scores (0-10). None when the AI did not provide them.",
    )
    ats_keywords: list[ATSKeyword] = Field(
        default_factory=list,
        description="10-15 ATS keywords extracted from the JD, categorized and matched",
    )
    desire_score: float | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Desirability score 0-10: how much would the candidate want this job?",
    )
    desire_reasoning: str | None = Field(
        default=None,
        description="Reasoning for the desire score (what makes this job desirable/undesirable)",
    )


class GapAnalysisResult(BaseModel):
    """Structured gap analysis response."""

    gaps: list[dict] = Field(
        ...,
        description=(
            "List of gap items with skill_name, required_level, current_level, severity, distance"
        ),
    )
    readiness_score: float = Field(..., ge=0, le=100, description="Overall readiness 0-100")
    summary: str = Field(..., description="Human-readable summary")


class CoachingResult(BaseModel):
    """Structured coaching suggestions response."""

    suggestions: list[dict] = Field(
        ...,
        description="Prioritized coaching suggestions with action, hours, weeks, difficulty",
    )
    focus_area: str = Field(..., description="Recommended primary focus area")


class GoalRecalibrationResult(BaseModel):
    """Structured goal recalibration response."""

    recalibration_notes: str = Field(..., description="Market-data-backed recalibration notes")
    suggested_adjustments: list[dict] = Field(..., description="Suggested goal adjustments")
    market_reality: str = Field(..., description="Current market reality summary")


class InterviewPrepResult(BaseModel):
    """Structured interview preparation response."""

    topics: list[dict] = Field(
        ..., description="Personalized topic list with topic, relevance, difficulty"
    )
    questions: list[dict] = Field(
        ..., description="Practice questions with question, category, difficulty"
    )
    checklist: list[dict] = Field(
        ..., description="Prep checklist items with item, time_minutes, priority"
    )
    total_prep_hours: float = Field(..., description="Estimated total preparation hours")


class CompanyResearchResult(BaseModel):
    """Structured company research response."""

    tech_stack: dict = Field(..., description="Tech stack by category")
    funding: dict = Field(..., description="Funding information")
    glassdoor: dict = Field(..., description="Glassdoor ratings and culture signals")
    values_alignment: float | dict = Field(
        ..., description="Values alignment score 0-10 or {score, rationale}"
    )
    ats_platform: str | None = Field(default=None, description="Detected ATS platform")
    hiring_patterns: dict = Field(..., description="Hiring velocity and open roles data")
    industry_segment: str | None = Field(default=None, description="Industry classification")
    employee_count: str | None = Field(default=None, description="Estimated employee count")
    news: list[dict] | None = Field(default=None, description="Recent news items about the company")


class LearningRecommendationsResult(BaseModel):
    """Structured learning recommendations response."""

    recommendations: list[dict] = Field(
        ...,
        description="Learning resources with title, url, hours, provider, difficulty, type",
    )
    total_hours: float = Field(..., description="Total estimated hours for all recommendations")


class InterviewFormatResult(BaseModel):
    """Structured interview format response (per company)."""

    rounds: list[dict] = Field(
        ...,
        description="Interview rounds with round_number, type, description, duration_minutes",
    )
    total_duration: str = Field(..., description="Total process duration estimate")
    process_description: str = Field(
        ..., description="High-level description of the interview process"
    )


class InterviewPatternsResult(BaseModel):
    """Structured interview patterns response (per role type)."""

    question_categories: list[dict] = Field(
        ...,
        description="Question categories with name, description, example_questions",
    )
    assessment_criteria: list[dict] = Field(
        ...,
        description="Assessment criteria with name and description",
    )
    frequently_tested_skills: list[str] = Field(
        ...,
        description="Skills frequently tested in interviews for this role",
    )


# ---------------------------------------------------------------------------
# Token usage tracking
# ---------------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Token usage statistics from an AI provider response."""

    input_tokens: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    output_tokens: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    cache_creation_input_tokens: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    cache_read_input_tokens: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AIResponse(BaseModel):
    """Response from an AI provider."""

    content: str = Field(..., description="Raw text response from the AI")
    provider: str = Field(..., description="Provider name that generated this response")
    feature: AIFeature = Field(..., description="Feature type that was requested")
    structured: (
        ScoreResult
        | GapAnalysisResult
        | CoachingResult
        | GoalRecalibrationResult
        | InterviewPrepResult
        | CompanyResearchResult
        | LearningRecommendationsResult
        | InterviewFormatResult
        | InterviewPatternsResult
        | None
    ) = Field(default=None, description="Structured response data (feature-dependent)")
    model: str | None = Field(default=None, description="Model used for generation")
    usage: TokenUsage | None = Field(
        default=None, description="Token usage statistics (None for cache hits)"
    )
