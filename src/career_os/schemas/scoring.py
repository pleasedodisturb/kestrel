"""Pydantic schemas for Scoring Engine API (Milestone 3)."""

import json as json_mod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from career_os.schemas.ai import ATSKeywordCategory, ScoreBreakdownFactor


def _ensure_utc(v: Any) -> datetime | None:
    """Ensure a datetime value has UTC timezone info."""
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


def score_to_letter_grade(score: float | None) -> str | None:
    """Map a 0-10 fit score to a letter grade (A through F).

    Boundaries are inclusive on the lower bound:
        9.0-10.0 -> A     (dream job)
        8.0-8.9  -> A-    (strong fit, top tier)
        7.0-7.9  -> B+    (strong fit)
        6.0-6.9  -> B     (good fit)
        5.0-5.9  -> C+    (maybe)
        4.0-4.9  -> C     (weak fit)
        3.0-3.9  -> D     (poor fit)
        0.0-2.9  -> F     (no fit)

    Returns ``None`` when ``score`` is ``None``.
    """
    if score is None:
        return None
    if score >= 9.0:
        return "A"
    if score >= 8.0:
        return "A-"
    if score >= 7.0:
        return "B+"
    if score >= 6.0:
        return "B"
    if score >= 5.0:
        return "C+"
    if score >= 4.0:
        return "C"
    if score >= 3.0:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Score Request / Response
# ---------------------------------------------------------------------------


class ScoreRequest(BaseModel):
    """Request body for POST /api/score — score a job against a profile."""

    profile_id: int = Field(..., description="Profile to score against")
    job_url: str | None = Field(default=None, description="Job posting URL (for reference)")
    job_title: str | None = Field(default=None, description="Job title")
    job_company: str | None = Field(default=None, description="Company name")
    job_description: str = Field(..., min_length=1, description="Job description text to score")
    discovered_job_id: int | None = Field(default=None, description="Link to discovered job record")
    application_id: int | None = Field(default=None, description="Link to application record")


class RedFlag(BaseModel):
    """A single rule-based red flag detected in a job description."""

    flag_type: str = Field(..., description="Rule identifier, e.g. 'stale_posting'")
    severity: str = Field(
        ...,
        description="Severity bucket: info | caution | warning | dealbreaker",
    )
    description: str = Field(..., description="Human-readable explanation of the flag")


class DimensionalScoresResponse(BaseModel):
    """Six dimensional sub-scores surfaced on the API."""

    technical_fit: float = Field(..., ge=0, le=10)
    seniority_alignment: float = Field(..., ge=0, le=10)
    compensation_fit: float = Field(..., ge=0, le=10)
    location_fit: float = Field(..., ge=0, le=10)
    career_trajectory: float = Field(..., ge=0, le=10)
    company_fit: float = Field(..., ge=0, le=10)


class ATSKeywordItem(BaseModel):
    """An ATS keyword surfaced on the API response."""

    keyword: str
    category: ATSKeywordCategory
    matched: bool


class ScoreContextResponse(BaseModel):
    """Percentile context for a score relative to a user's scoring history.

    Only populated when the profile has >= 5 non-stale scored jobs.
    """

    percentile: int = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of scored jobs this score is higher than",
    )
    rank: int = Field(..., ge=1, description="Rank among all scored jobs (1 = highest)")
    total_scored: int = Field(..., ge=1, description="Total number of non-stale scored jobs")
    avg_score: float = Field(
        ..., ge=0, le=10, description="Average fit_score across all scored jobs"
    )
    score_band_count: int = Field(
        ...,
        ge=0,
        description="Number of jobs in the same letter grade band as this score",
    )


class ProfileCompletenessResponse(BaseModel):
    """Profile richness and confidence interval for a scored job.

    Computed dynamically at read time — not stored in DB.
    Always present on ScoreResponse GET endpoints.
    """

    completeness: float = Field(
        ...,
        ge=0,
        le=100,
        description="Profile richness 0-100% (higher = more data → tighter range)",
    )
    confidence_range: tuple[float, float] = Field(
        ...,
        description=(
            "Uncertainty interval (low_bound, high_bound) around the fit_score. Clamped to [0, 10]."
        ),
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Fields that would most improve confidence. Only populated when completeness < 50%."
        ),
    )
    improvement_hint: str | None = Field(
        default=None,
        description=(
            "Human-readable hint shown when completeness < 50%. Tells the user what to add."
        ),
    )


class ScoreResponse(BaseModel):
    """Full scoring breakdown response."""

    id: int | None = None
    profile_id: int
    discovered_job_id: int | None = None
    application_id: int | None = None

    # Core scores
    fit_score: float = Field(..., ge=0, le=10, description="Overall fit 1-10")
    readiness_score: float = Field(..., ge=0, le=100, description="Skills readiness 0-100")
    career_alignment: float = Field(..., ge=0, le=10, description="Career alignment 0-10")

    # Desire score (dual-score architecture, G-275)
    desire_score: float | None = Field(
        default=None, ge=0, le=10, description="Desirability score 0-10 (how much user wants job)"
    )
    desire_score_method: str | None = Field(
        default=None, description="Method used: 'derived' or 'ai_generated'"
    )
    desire_reasoning: str | None = Field(
        default=None, description="Reasoning for desire score (Option B only)"
    )

    # Letter grade derived from fit_score (A, A-, B+, B, C+, C, D, F)
    letter_grade: str | None = Field(
        default=None,
        description="Letter grade derived from fit_score (computed automatically)",
    )

    # Detailed breakdown
    score_breakdown: list[ScoreBreakdownFactor] = Field(
        default_factory=list,
        description="Breakdown of scoring factors with +/- contributions (≥3 factors)",
    )
    red_flags: list[RedFlag] = Field(
        default_factory=list,
        description="Rule-based red flags detected in the JD (zero AI cost)",
    )
    dimensional_scores: DimensionalScoresResponse | None = Field(
        default=None,
        description="Six dimensional sub-scores (0-10). None for legacy rows.",
    )
    ats_keywords: list[ATSKeywordItem] = Field(
        default_factory=list,
        description="ATS keywords extracted by the AI, categorized and matched",
    )

    # Hidden fields — pydantic populates these from the ``ScoredJob`` ORM row
    # via ``from_attributes=True``, and an after-validator collapses them into
    # ``dimensional_scores``. They are excluded from serialized output so
    # clients only see the nested object.
    dim_technical_fit: float | None = Field(default=None, exclude=True)
    dim_seniority_alignment: float | None = Field(default=None, exclude=True)
    dim_compensation_fit: float | None = Field(default=None, exclude=True)
    dim_location_fit: float | None = Field(default=None, exclude=True)
    dim_career_trajectory: float | None = Field(default=None, exclude=True)
    dim_company_fit: float | None = Field(default=None, exclude=True)
    reasoning: str = Field(
        ..., min_length=100, description="Scoring explanation (≥100 chars, ≥3 factors)"
    )
    estimated_salary: str = Field(..., description="Estimated salary range")
    effort_flag: str = Field(..., description="Effort level: low / medium / high")
    prep_level: str = Field(..., description="Preparation level: light / moderate / intensive")
    prep_notes: str = Field(..., description="Prep recommendations")

    # Score context — percentile/rank relative to this profile's history.
    # Computed dynamically on GET; not stored in DB. None when < 5 scored jobs exist.
    score_context: ScoreContextResponse | None = Field(
        default=None,
        description=(
            "Percentile context relative to profile's scoring history (null when < 5 scores)"
        ),
    )

    # Profile completeness + confidence interval (Epic 10 / G-278).
    # Computed dynamically on GET; not stored in DB. Always present on GET endpoints.
    profile_completeness: ProfileCompletenessResponse | None = Field(
        default=None,
        description=(
            "Profile richness score (0-100) and confidence interval around fit_score. "
            "Computed at read time; null immediately after POST /api/score."
        ),
    )

    is_stale: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("score_breakdown", mode="before")
    @classmethod
    def _parse_score_breakdown(cls, v: Any) -> list[ScoreBreakdownFactor]:
        """Parse score_breakdown from JSON string if it comes from DB."""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json_mod.loads(v)
                return [ScoreBreakdownFactor(**item) for item in parsed]
            except (json_mod.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("red_flags", mode="before")
    @classmethod
    def _parse_red_flags(cls, v: Any) -> list[RedFlag]:
        """Parse red_flags from JSON string if it comes from DB."""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json_mod.loads(v)
                return [RedFlag(**item) for item in parsed]
            except (json_mod.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("ats_keywords", mode="before")
    @classmethod
    def _parse_ats_keywords(cls, v: Any) -> list[ATSKeywordItem]:
        """Parse ats_keywords from JSON string if it comes from DB."""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json_mod.loads(v)
                return [ATSKeywordItem(**item) for item in parsed]
            except (json_mod.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)

    @model_validator(mode="after")
    def _populate_letter_grade(self) -> "ScoreResponse":
        """Derive letter_grade from fit_score whenever it is not set."""
        if self.letter_grade is None:
            self.letter_grade = score_to_letter_grade(self.fit_score)
        return self

    @model_validator(mode="after")
    def _assemble_dimensional_scores(self) -> "ScoreResponse":
        """Collapse the six ``dim_*`` hidden fields into ``dimensional_scores``.

        Only fires when ``dimensional_scores`` was not already provided and
        all six dimensional columns are populated. Legacy rows with any NULL
        dimension leave ``dimensional_scores`` as ``None``.
        """
        if self.dimensional_scores is not None:
            return self
        dims = (
            self.dim_technical_fit,
            self.dim_seniority_alignment,
            self.dim_compensation_fit,
            self.dim_location_fit,
            self.dim_career_trajectory,
            self.dim_company_fit,
        )
        if all(d is not None for d in dims):
            self.dimensional_scores = DimensionalScoresResponse(
                technical_fit=self.dim_technical_fit,  # type: ignore[arg-type]
                seniority_alignment=self.dim_seniority_alignment,  # type: ignore[arg-type]
                compensation_fit=self.dim_compensation_fit,  # type: ignore[arg-type]
                location_fit=self.dim_location_fit,  # type: ignore[arg-type]
                career_trajectory=self.dim_career_trajectory,  # type: ignore[arg-type]
                company_fit=self.dim_company_fit,  # type: ignore[arg-type]
            )
        return self


# ---------------------------------------------------------------------------
# Scoring Weights
# ---------------------------------------------------------------------------


def classify_quadrant(fit_score: float | None, desire_score: float | None) -> str | None:
    """Classify a job into a 2D quadrant based on fit and desire scores.

    Quadrants (threshold = 5.0):
        - "dream_job"   — high fit, high desire
        - "stretch_goal" — low fit, high desire
        - "safe_bet"    — high fit, low desire
        - "skip"        — low fit, low desire

    Returns None if either score is None.
    """
    if fit_score is None or desire_score is None:
        return None
    threshold = 5.0
    if fit_score >= threshold and desire_score >= threshold:
        return "dream_job"
    if fit_score < threshold and desire_score >= threshold:
        return "stretch_goal"
    if fit_score >= threshold and desire_score < threshold:
        return "safe_bet"
    return "skip"


class DesireScoreResponse(BaseModel):
    """Standalone desire score response for the dual-score API."""

    desire_score: float | None = Field(default=None, ge=0, le=10, description="Desirability 0-10")
    desire_score_method: str | None = Field(default=None, description="'derived' or 'ai_generated'")
    desire_reasoning: str | None = Field(default=None, description="Reasoning (ai_generated only)")
    quadrant: str | None = Field(
        default=None, description="2D quadrant: dream_job / stretch_goal / safe_bet / skip"
    )
    fit_score: float | None = Field(
        default=None, ge=0, le=10, description="Corresponding fit_score for context"
    )


class ScoringWeightsResponse(BaseModel):
    """Response schema for scoring weight configuration."""

    id: int
    profile_id: int
    skills_match: float = Field(default=0.25, ge=0, le=1)
    career_alignment: float = Field(default=0.20, ge=0, le=1)
    culture_fit: float = Field(default=0.15, ge=0, le=1)
    salary_match: float = Field(default=0.15, ge=0, le=1)
    location_match: float = Field(default=0.10, ge=0, le=1)
    growth_potential: float = Field(default=0.10, ge=0, le=1)
    remote_preference: float = Field(default=0.05, ge=0, le=1)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class ScoringWeightsUpdate(BaseModel):
    """Request body for PUT /api/scoring-weights — update weight configuration."""

    skills_match: float | None = Field(default=None, ge=0, le=1)
    career_alignment: float | None = Field(default=None, ge=0, le=1)
    culture_fit: float | None = Field(default=None, ge=0, le=1)
    salary_match: float | None = Field(default=None, ge=0, le=1)
    location_match: float | None = Field(default=None, ge=0, le=1)
    growth_potential: float | None = Field(default=None, ge=0, le=1)
    remote_preference: float | None = Field(default=None, ge=0, le=1)


# ---------------------------------------------------------------------------
# Batch Scoring
# ---------------------------------------------------------------------------


class BatchScoreRequest(BaseModel):
    """Request body for POST /api/score/batch."""

    profile_id: int = Field(..., description="Profile to score against")
    discovered_job_ids: list[int] = Field(
        default_factory=list,
        description="Specific discovered job IDs to score (empty = all unscored)",
    )
    rescore_stale: bool = Field(default=False, description="Also re-score stale scores")


class BatchScoreResponse(BaseModel):
    """Response for batch scoring operation."""

    scored_count: int = Field(..., description="Number of jobs scored")
    total_time_seconds: float = Field(..., description="Total time taken in seconds")
    scores: list[ScoreResponse] = Field(
        default_factory=list, description="Individual score results"
    )
    errors: list[dict[str, str]] = Field(
        default_factory=list, description="Scoring errors for individual jobs"
    )
    credits_exhausted: bool = Field(
        default=False,
        description="True if scoring stopped due to AI provider credits being exhausted",
    )


# ---------------------------------------------------------------------------
# Scoring Feedback
# ---------------------------------------------------------------------------


class FeedbackDirection(StrEnum):
    """Valid directions for scoring feedback."""

    TOO_HIGH = "too_high"
    TOO_LOW = "too_low"
    CORRECT = "correct"
    IMPLICIT_POSITIVE = "implicit_positive"
    IMPLICIT_NEGATIVE = "implicit_negative"
    IMPLICIT_STRONG_POSITIVE = "implicit_strong_positive"


class FeedbackCreate(BaseModel):
    """Request body for POST /api/score/{scored_job_id}/feedback."""

    direction: FeedbackDirection = Field(..., description="Feedback direction")
    user_score: float | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Optional: what the user thinks the score should be (0–10)",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional: free-text explanation",
    )


class FeedbackResponse(BaseModel):
    """Response schema for a single feedback record."""

    id: int
    scored_job_id: int
    profile_id: int
    direction: str
    user_score: float | None = None
    reason: str | None = None
    original_fit_score: float
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class FeedbackStats(BaseModel):
    """Summary statistics for feedback submitted by a profile."""

    total_count: int = Field(..., description="Total number of feedback records")
    explicit_count: int = Field(..., description="Explicit corrections (too_high/too_low/correct)")
    implicit_count: int = Field(..., description="Implicit signals (promoted/dismissed/interview)")
    avg_deviation: float | None = Field(
        default=None,
        description="Average |user_score - original_fit_score| for records with user_score",
    )
    direction_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of feedback records per direction",
    )


class CalibrationExample(BaseModel):
    """A single calibration example for the scoring prompt."""

    job_title: str | None = None
    company: str | None = None
    ai_score: float
    user_score: float
    reason: str | None = None
    deviation: float


# ---------------------------------------------------------------------------
# Bayesian Preference Learning (Epic 11 / G-279)
# ---------------------------------------------------------------------------


class WeightSuggestionResponse(BaseModel):
    """A single weight adjustment suggestion from the preference model."""

    dimension: str = Field(..., description="Weight dimension name (e.g. 'skills_match')")
    current_weight: float = Field(..., ge=0, le=1, description="Current configured weight")
    suggested_weight: float = Field(..., ge=0, le=1, description="Suggested new weight")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in the suggestion (0-1)")
    reason: str = Field(..., description="Human-readable explanation of the suggestion")


class SuggestionsResponse(BaseModel):
    """Response for GET /api/score/suggestions — weight adjustment suggestions."""

    suggestions: list[WeightSuggestionResponse] = Field(
        default_factory=list,
        description="Weight adjustment suggestions based on feedback patterns",
    )
    feedback_count: int = Field(
        ..., description="Total feedback records used to generate suggestions"
    )
    min_feedback_required: int = Field(
        ..., description="Minimum feedback records needed before suggestions appear"
    )
    ready: bool = Field(..., description="True when enough feedback exists to generate suggestions")


class ActiveQueryResponse(BaseModel):
    """Optional active query suggestion returned with a score."""

    should_query: bool = Field(..., description="Whether to prompt the user for feedback")
    uncertain_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimensions with highest uncertainty that would benefit from feedback",
    )
    message: str | None = Field(
        default=None,
        description="Suggested prompt message for the user (e.g. 'Would you apply to this?')",
    )
