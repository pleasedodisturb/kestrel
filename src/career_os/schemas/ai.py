"""Pydantic schemas for AI provider layer."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

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
    """Six dimensional sub-scores for a job fit.

    **Scale (G-1337, finding E):** these values are STORED and DISPLAYED on a
    0–10 axis (unchanged for back-compat — no data migration), but the model is
    now asked to EMIT each dimension on a 0–5 axis (best human–LLM alignment per
    the 2026 grading-scale study; 0–10 clustered worst). The 0–5→0–10 scaling
    happens exactly once, at the live-provider parse boundary
    (:func:`scale_score_result_dimensions`, called from
    ``ai.openrouter_provider._try_parse_structured``) — never in a schema
    validator, so cached 0–10 responses re-read via ``model_validate_json`` are
    NOT re-scaled. The field bounds therefore stay 0–10.

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


# ---------------------------------------------------------------------------
# Dimensional scale bridge (G-1337, finding E) — model emits 0–5, we store 0–10
# ---------------------------------------------------------------------------

#: The scale the model is *asked to emit* each dimension on.
DIMENSION_EMIT_MAX = 5.0
#: The scale dimensions are *stored and displayed* on (UI + DB, unchanged).
DIMENSION_DISPLAY_MAX = 10.0
#: Multiplier applied on parse to lift a 0–5 emission onto the 0–10 axis.
DIMENSION_SCALE_FACTOR = DIMENSION_DISPLAY_MAX / DIMENSION_EMIT_MAX  # 2.0

#: How many dimensions must exceed :data:`DIMENSION_EMIT_MAX` before the whole
#: set is treated as a legacy/non-compliant 0–10 emission. Requiring ≥2 signals
#: (not just any 1) makes the detector robust to a single sloppy outlier: one
#: dimension emitted as 5.1 or 6 can no longer flip the other five to
#: half-scale. Every prompt path now asks for 0–5, so the default assumption is
#: "0–5, scale it"; only strong evidence (multiple out-of-range dims) overrides.
DIMENSION_LEGACY_TEN_SCALE_MIN_SIGNALS = 2

_DIMENSION_FIELDS = (
    "technical_fit",
    "seniority_alignment",
    "compensation_fit",
    "location_fit",
    "career_trajectory",
    "company_fit",
)


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))


def scale_dimensions_to_display(dims: DimensionalScores) -> DimensionalScores:
    """Lift model-emitted 0–5 dimensional scores onto the 0–10 storage scale.

    Every prompt path (single scorer + batch) now asks the model to score each
    dimension 0–5 (finding E), so the default behavior is to **clamp each
    dimension into ``[0, 5]`` and multiply by** :data:`DIMENSION_SCALE_FACTOR`
    (×2), landing on ``[0, 10]``. Per-dimension clamping means a lone sloppy
    value (e.g. 5.1) is pinned to 5 and scaled with the rest, rather than
    corrupting the set.

    **Defensive back-compat:** only when at least
    :data:`DIMENSION_LEGACY_TEN_SCALE_MIN_SIGNALS` dimensions exceed
    :data:`DIMENSION_EMIT_MAX` (i.e. the emission clearly looks 0–10, not a
    single outlier) is the set treated as a legacy/non-compliant 0–10 response
    and clamped-but-NOT-scaled. This can never be reached by cached rows (cache
    reads bypass this function entirely — see
    :func:`scale_score_result_dimensions`).

    NOT idempotent: applying it twice to a genuine 0–5 emission scales ×4. It is
    called exactly once, at the live-provider parse boundary. Pure (no mutation
    of the input).
    """
    values = {name: getattr(dims, name) for name in _DIMENSION_FIELDS}
    over_max = sum(1 for v in values.values() if v > DIMENSION_EMIT_MAX)
    if over_max >= DIMENSION_LEGACY_TEN_SCALE_MIN_SIGNALS:
        # Clearly a 0–10 emission — keep values as-is, just clamp into range.
        return DimensionalScores(
            **{name: _clamp(v, 0.0, DIMENSION_DISPLAY_MAX) for name, v in values.items()}
        )
    # 0–5 emission (the norm): clamp each into [0, 5] then scale ×2 to [0, 10].
    return DimensionalScores(
        **{
            name: _clamp(v, 0.0, DIMENSION_EMIT_MAX) * DIMENSION_SCALE_FACTOR
            for name, v in values.items()
        }
    )


class RoleMatch(BaseModel):
    """Explicit role-family match verdict (G-1335 halo fix).

    Emitted *before* the ``fit_score`` so the model commits to a role-family
    judgment with JD-grounded evidence first, rather than rationalizing a
    holistic number after the fact. Used as a hard gate: a ``False`` verdict
    caps ``fit_score`` in code, regardless of any dimensional scores or company
    prestige.
    """

    is_same_role_family: bool = Field(
        default=True,
        description=(
            "True only if the job's role/occupation is the same family as the candidate's "
            "target job family (e.g. PM/TPM ≠ SWE/SRE/designer). Company prestige is irrelevant."
        ),
    )
    evidence: str = Field(
        default="",
        description=(
            "JD-grounded evidence for the verdict — the job's title and core responsibilities "
            "compared against the candidate's target role."
        ),
    )


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

    # Role-fit hard gate (G-1335). Declared first so a reason-before-score
    # provider emits the role-family verdict + disqualifiers before the number.
    # Both are optional/back-compat: legacy cached rows, the mock provider, and
    # models that don't emit them leave the gate a no-op (treated as a pass).
    role_match: RoleMatch | None = Field(
        default=None,
        description=(
            "Explicit role-family gate verdict. None for legacy/cached responses "
            "(treated as a pass — no cap applied)."
        ),
    )
    disqualifiers: list[str] = Field(
        default_factory=list,
        description=(
            "Hard disqualifiers grounded in the JD: missing mandatory license/clearance/visa, "
            "hard location conflict, or seniority off by >1 level. A non-empty list caps fit_score."
        ),
    )

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


# ---------------------------------------------------------------------------
# Role-fit hard gate (G-1335) — the halo fix, enforced in code post-parse
# ---------------------------------------------------------------------------

# A role-family mismatch or a hard disqualifier caps the fit_score at this
# ceiling *after parsing*, so the model cannot rationalize past it with a high
# holistic number or a prestigious company. Chosen so gated jobs land in the
# "D / poor fit" band (3.0-3.9) and can never be a "safe_bet"/"dream_job"
# (quadrant threshold 5.0).
ROLE_FIT_GATE_CEILING = 3.0


def role_fit_gate_failed(result: ScoreResult) -> bool:
    """Return True when the role-fit gate should fire for this result.

    Fires when the model flagged a different role family, or reported any hard
    disqualifier. Back-compat: ``role_match=None`` (legacy/cached/mock) is a
    pass, and an empty ``disqualifiers`` list is a pass.
    """
    role_mismatch = result.role_match is not None and not result.role_match.is_same_role_family
    return role_mismatch or bool(result.disqualifiers)


def apply_role_fit_gate(result: ScoreResult) -> ScoreResult:
    """Cap ``fit_score`` at :data:`ROLE_FIT_GATE_CEILING` when the gate fails.

    Pure and idempotent: returns the input unchanged when the gate passes or the
    score already sits at/below the ceiling; otherwise returns a copy with the
    capped ``fit_score``. Only ``fit_score`` is touched — dimensional scores and
    the desire axis are deliberately left intact (prestige belongs on desire).
    """
    if role_fit_gate_failed(result) and result.fit_score > ROLE_FIT_GATE_CEILING:
        return result.model_copy(update={"fit_score": ROLE_FIT_GATE_CEILING})
    return result


def scale_score_result_dimensions(result: ScoreResult) -> ScoreResult:
    """Return ``result`` with its dimensional scores lifted from 0–5 to 0–10.

    The 0–5→0–10 bridge for finding E (see :func:`scale_dimensions_to_display`).
    A no-op (returns the input unchanged) when ``dimensional_scores`` is None.
    Only ``dimensional_scores`` is touched — the top-level ``fit_score`` /
    ``desire_score`` stay on their native 0–10 axis (finding E does not rescale
    them). Called exactly once, at the real-provider parse boundary
    (``ai.openrouter_provider._try_parse_structured``); the mock/deterministic
    providers construct final display-scale results and never traverse it.
    """
    if result.dimensional_scores is None:
        return result
    return result.model_copy(
        update={"dimensional_scores": scale_dimensions_to_display(result.dimensional_scores)}
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

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


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
