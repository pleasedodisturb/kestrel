"""Pydantic schemas for Career Goals API."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator  # noqa: I001

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GoalType(StrEnum):
    """Valid goal types."""

    realistic = "realistic"
    aspirational = "aspirational"


class GoalStatus(StrEnum):
    """Valid goal statuses."""

    active = "active"
    completed = "completed"
    paused = "paused"
    abandoned = "abandoned"


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


class GoalCreate(BaseModel):
    """Request body for POST /api/goals."""

    profile_id: int = Field(..., description="Profile this goal belongs to")
    title: str = Field(..., min_length=1, description="Goal title")
    goal_type: GoalType = Field(..., description="realistic or aspirational")
    target_date: datetime | None = Field(
        default=None, description="Target date for achieving the goal"
    )
    status: GoalStatus = Field(default=GoalStatus.active, description="Goal status")
    description: str | None = Field(default=None, description="Goal description")


class GoalUpdate(BaseModel):
    """Request body for PUT /api/goals/{id}."""

    title: str | None = Field(default=None, min_length=1, description="Goal title")
    goal_type: GoalType | None = Field(default=None, description="Goal type")
    target_date: datetime | None = Field(default=None, description="Target date")
    status: GoalStatus | None = Field(default=None, description="Goal status")
    description: str | None = Field(default=None, description="Goal description")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class GoalResponse(BaseModel):
    """Response schema for a single goal."""

    id: int
    profile_id: int
    title: str
    goal_type: str
    target_date: datetime | None = None
    status: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", "target_date", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class GoalListResponse(BaseModel):
    """Response schema for list of goals."""

    goals: list[GoalResponse]
    total: int


# ---------------------------------------------------------------------------
# Reality map schemas
# ---------------------------------------------------------------------------


class RealityMapDimension(BaseModel):
    """A single dimension of the reality map."""

    dimension: str = Field(..., description="e.g., skills, experience, connections")
    current_state: str = Field(..., description="Current state description")
    required_state: str = Field(..., description="Required state description")
    delta: str = Field(..., description="What's needed to close the gap")
    progress_pct: float = Field(ge=0, le=100, description="Progress percentage in this dimension")


class RealityMapResponse(BaseModel):
    """Response for GET /api/goals/{id}/reality-map."""

    goal_id: int
    title: str
    goal_type: str
    dimensions: list[RealityMapDimension]
    overall_progress: float = Field(ge=0, le=100, description="Overall progress percentage")


# ---------------------------------------------------------------------------
# Progress schemas
# ---------------------------------------------------------------------------


class ProgressDimension(BaseModel):
    """Progress in a single dimension."""

    dimension: str
    percentage: float = Field(ge=0, le=100)
    detail: str = Field(..., description="Human-readable detail")


class ProgressResponse(BaseModel):
    """Response for GET /api/goals/{id}/progress."""

    goal_id: int
    title: str
    dimensions: list[ProgressDimension]
    overall_progress: float = Field(ge=0, le=100)


# ---------------------------------------------------------------------------
# Recalibration schemas
# ---------------------------------------------------------------------------


class RecalibrationResponse(BaseModel):
    """Response for PUT /api/goals/{id}/recalibrate."""

    goal_id: int
    title: str
    recalibration_notes: str
    suggested_adjustments: list[dict]
    market_reality: str


# ---------------------------------------------------------------------------
# Alternative paths schemas
# ---------------------------------------------------------------------------


class AlternativePath(BaseModel):
    """A single alternative path."""

    path_type: str = Field(..., description="employment, freelance, consulting, etc.")
    title: str = Field(..., description="Path title")
    description: str = Field(..., description="Path description")
    timeline: str = Field(..., description="Estimated timeline")
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    estimated_income: str | None = None


class AlternativesResponse(BaseModel):
    """Response for GET /api/goals/{id}/alternatives."""

    goal_id: int
    title: str
    paths: list[AlternativePath]
