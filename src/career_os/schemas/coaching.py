"""Pydantic schemas for Coaching Engine API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

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
# Nested schemas
# ---------------------------------------------------------------------------


class EffortEstimate(BaseModel):
    """Effort estimate for a coaching suggestion."""

    hours: float | None = Field(default=None, description="Estimated hours to complete")
    weeks: float | None = Field(default=None, description="Estimated weeks to complete")
    difficulty: str | None = Field(
        default=None, description="Difficulty: low, medium, high"
    )


class CoachingSuggestionResponse(BaseModel):
    """A single coaching suggestion."""

    id: int
    profile_id: int
    action: str = Field(..., description="Actionable recommendation")
    priority: int = Field(..., description="Priority rank (1 = highest)")
    effort_estimate: EffortEstimate = Field(
        ..., description="Effort estimate with hours, weeks, difficulty"
    )
    status: str = Field(..., description="active, completed, dismissed")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CoachingSuggestionsResponse(BaseModel):
    """Response for GET /api/coaching/suggestions."""

    suggestions: list[CoachingSuggestionResponse]
    total: int
    focus_area: str | None = Field(
        default=None, description="AI-recommended primary focus area"
    )
