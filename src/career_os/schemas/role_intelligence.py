"""Pydantic schemas for Role & Industry Intelligence API.

Covers:
- VAL-ROLE-INTEL-001: Interview format per company (rounds, types, duration)
- VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size (low/median/high)
- VAL-ROLE-INTEL-003: Common interview patterns per role type
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-001: Interview Format
# ---------------------------------------------------------------------------


class InterviewRound(BaseModel):
    """A single interview round."""

    round_number: int = Field(..., description="Round sequence number (1-based)")
    type: str = Field(
        ..., description="Round type (e.g., 'Phone Screen', 'Technical', 'Behavioral')"
    )
    description: str = Field(..., description="Description of what this round covers")
    duration_minutes: int = Field(..., ge=0, description="Expected duration in minutes")


class SourceWarning(BaseModel):
    """Warning for a failed data source."""

    source: str = Field(..., description="Name of the failed data source")
    error: str = Field(..., description="Brief description of the failure")


class InterviewFormatResponse(BaseModel):
    """Response for GET /api/intelligence/interview-format."""

    company: str = Field(..., description="Company name")
    rounds: list[InterviewRound] = Field(
        default_factory=list, description="Interview rounds with types and durations"
    )
    total_duration: str = Field(
        default="Unknown",
        description="Total estimated process duration (e.g., '3-4 weeks')",
    )
    process_description: str = Field(
        default="",
        description="High-level description of the interview process",
    )
    warnings: list[SourceWarning] = Field(
        default_factory=list, description="Warnings for failed data sources"
    )


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-002: Salary Benchmarks
# ---------------------------------------------------------------------------


class SalaryBenchmark(BaseModel):
    """Low/median/high salary benchmarks."""

    low: float = Field(default=0.0, description="Low end salary (25th percentile)")
    median: float = Field(default=0.0, description="Median salary")
    high: float = Field(default=0.0, description="High end salary (75th percentile)")
    sample_size: int = Field(default=0, ge=0, description="Number of data points")


class SalaryBenchmarkResponse(BaseModel):
    """Response for GET /api/intelligence/salary."""

    role: str = Field(..., description="Role type queried")
    location: str | None = Field(default=None, description="Location filter applied")
    company_stage: str | None = Field(
        default=None, description="Company stage filter applied (e.g., 'startup', 'public')"
    )
    benchmarks: SalaryBenchmark = Field(
        default_factory=SalaryBenchmark,
        description="Salary benchmarks (low/median/high)",
    )
    context: str = Field(
        default="",
        description="Contextualization notes (location, company stage, etc.)",
    )


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-003: Interview Patterns per Role Type
# ---------------------------------------------------------------------------


class QuestionCategory(BaseModel):
    """A category of interview questions."""

    name: str = Field(..., description="Category name (e.g., 'Behavioral', 'Technical')")
    description: str = Field(..., description="What this category covers")
    example_questions: list[str] = Field(
        default_factory=list, description="Example questions in this category"
    )


class AssessmentCriterion(BaseModel):
    """A criterion used to assess candidates for a role type."""

    name: str = Field(..., description="Criterion name")
    description: str = Field(..., description="What interviewers evaluate")


class InterviewPatternsResponse(BaseModel):
    """Response for GET /api/intelligence/patterns."""

    role: str = Field(..., description="Role type queried")
    question_categories: list[QuestionCategory] = Field(
        default_factory=list,
        description="Common question categories for this role type",
    )
    assessment_criteria: list[AssessmentCriterion] = Field(
        default_factory=list,
        description="Common assessment criteria for this role type",
    )
    frequently_tested_skills: list[str] = Field(
        default_factory=list,
        description="Skills frequently tested in interviews for this role",
    )
    warnings: list[SourceWarning] = Field(
        default_factory=list, description="Warnings for failed data sources"
    )
