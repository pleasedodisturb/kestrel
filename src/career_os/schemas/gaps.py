"""Pydantic schemas for Gap Analysis API."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GapSeverity(StrEnum):
    """Severity levels for skill gaps."""

    critical = "critical"
    nice_to_have = "nice-to-have"
    bonus = "bonus"


class RequiredLevel(StrEnum):
    """Valid required proficiency levels."""

    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_utc(v: Any) -> datetime | None:
    """Ensure a datetime value has UTC timezone info."""
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class JobRequirementCreate(BaseModel):
    """Request body for creating a job requirement."""

    skill_name: str = Field(..., min_length=1, description="Required skill name")
    required_level: RequiredLevel = Field(
        default=RequiredLevel.intermediate,
        description="Required proficiency level",
    )
    severity: GapSeverity | None = Field(
        default=None,
        description="How critical this requirement is. "
        "If omitted, auto-classified from skill_name text.",
    )


class JobRequirementBulkCreate(BaseModel):
    """Request body for bulk-creating job requirements for an application."""

    application_id: int = Field(..., description="Application to add requirements to")
    profile_id: int = Field(..., description="Profile ID")
    requirements: list[JobRequirementCreate] = Field(
        ..., min_length=1, description="List of job requirements"
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class GapItem(BaseModel):
    """A single skill gap comparing a job requirement against the user's inventory."""

    skill_name: str
    required_level: str
    current_level: str | None = None  # None if skill not in inventory
    severity: str  # critical, nice-to-have, bonus
    distance: int = Field(ge=0, le=3, description="0=met, 1=one level, 2=two levels, 3=missing")


class GapAnalysisResponse(BaseModel):
    """Response for GET /api/applications/{id}/gaps."""

    application_id: int
    company: str
    role: str
    gaps: list[GapItem]
    readiness_score: float = Field(ge=0, le=100, description="Weighted readiness 0-100")
    total_requirements: int
    gaps_count: int


class AggregateGapItem(BaseModel):
    """A skill gap aggregated across multiple applications."""

    skill_name: str
    frequency: int = Field(description="Number of applications with this gap")
    application_ids: list[int]
    avg_severity: str
    avg_distance: float


class AggregateGapResponse(BaseModel):
    """Response for GET /api/gaps/aggregate."""

    gaps: list[AggregateGapItem]
    total_applications_analyzed: int


class JobRequirementResponse(BaseModel):
    """Response schema for a job requirement."""

    id: int
    application_id: int
    profile_id: int
    skill_name: str
    required_level: str
    severity: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_created_at_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)
