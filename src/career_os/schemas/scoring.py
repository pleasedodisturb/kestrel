"""Pydantic schemas for Scoring Engine API (Milestone 3)."""

import json as json_mod
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from career_os.schemas.ai import ScoreBreakdownFactor


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
    reasoning: str = Field(
        ..., min_length=100, description="Scoring explanation (≥100 chars, ≥3 factors)"
    )
    estimated_salary: str = Field(..., description="Estimated salary range")
    effort_flag: str = Field(..., description="Effort level: low / medium / high")
    prep_level: str = Field(..., description="Preparation level: light / moderate / intensive")
    prep_notes: str = Field(..., description="Prep recommendations")

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


# ---------------------------------------------------------------------------
# Scoring Weights
# ---------------------------------------------------------------------------


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
