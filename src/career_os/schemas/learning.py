"""Pydantic schemas for Learning Paths API."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LearningStatus(StrEnum):
    """Valid statuses for a learning resource."""

    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class ResourceType(StrEnum):
    """Valid resource types."""

    free_course = "free_course"
    paid_course = "paid_course"
    hands_on_project = "hands_on_project"


class Difficulty(StrEnum):
    """Valid difficulty levels."""

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


class LearningResourceCreate(BaseModel):
    """Request body for creating a learning resource."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile ID")
    title: str = Field(..., min_length=1, description="Resource title")
    url: str | None = Field(default=None, description="Resource URL")
    resource_type: ResourceType = Field(
        default=ResourceType.free_course, description="Type of resource"
    )
    estimated_hours: float | None = Field(
        default=None, ge=0, description="Estimated hours to complete"
    )
    difficulty: Difficulty | None = Field(default=None, description="Difficulty level")
    provider: str | None = Field(default=None, description="Provider (e.g. Coursera, YouTube)")


class LearningStatusUpdate(BaseModel):
    """Request body for updating learning resource status."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile ID")
    status: LearningStatus = Field(..., description="New status")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LearningResourceResponse(BaseModel):
    """Response schema for a learning resource."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    gap_id: int | None = Field(default=None, ge=1, le=INT64_MAX)
    skill_id: int | None = Field(default=None, ge=1, le=INT64_MAX)
    title: str
    url: str | None = None
    provider: str | None = None
    resource_type: str
    estimated_hours: float | None = None
    difficulty: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", "started_at", "completed_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class TemplateRecommendation(BaseModel):
    """A template-based recommendation generated for fresh gaps."""

    title: str
    url: str | None = None
    provider: str | None = None
    resource_type: str
    estimated_hours: float | None = None
    difficulty: str | None = None


class RecommendationsCTA(BaseModel):
    """Call to action for empty state."""

    label: str = "Add your own"
    action: str = "add_recommendation"


class GapRecommendationsResponse(BaseModel):
    """Response for GET /api/gaps/{id}/recommendations."""

    gap_id: int = Field(..., ge=1, le=INT64_MAX)
    skill_name: str
    recommendations: list[LearningResourceResponse]
    template_recommendations: list[TemplateRecommendation] = Field(default_factory=list)
    cta: RecommendationsCTA | None = None
