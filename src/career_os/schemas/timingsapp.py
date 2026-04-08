"""Pydantic schemas for TimingsApp integration."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActivityCategory(StrEnum):
    """Job-search activity categories for time tracking."""

    applying = "applying"
    researching = "researching"
    prepping = "prepping"
    networking = "networking"
    learning = "learning"


# ---------------------------------------------------------------------------
# Session schemas
# ---------------------------------------------------------------------------


class TimeSessionCreate(BaseModel):
    """Request body for starting a new tracked session."""

    profile_id: int
    activity_name: str = Field(..., min_length=1, max_length=500)
    category: ActivityCategory | None = Field(
        default=None,
        description="Activity category; auto-assigned from context if omitted",
    )
    notes: str | None = None


class TimeSessionStop(BaseModel):
    """Request body for stopping a tracked session."""

    notes: str | None = Field(
        default=None, description="Optional notes to add when stopping"
    )


class TimeSessionUpdate(BaseModel):
    """Request body for updating a tracked session."""

    activity_name: str | None = None
    category: ActivityCategory | None = None
    notes: str | None = None


class TimeSessionResponse(BaseModel):
    """Response schema for a tracked session."""

    id: int
    profile_id: int
    activity_name: str
    category: str
    notes: str | None = None
    started_at: datetime
    stopped_at: datetime | None = None
    duration_seconds: float | None = None
    timingsapp_entry_id: str | None = None
    timingsapp_project: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimeSessionListResponse(BaseModel):
    """Response for listing time sessions."""

    sessions: list[TimeSessionResponse]
    total: int


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------


class CategoryBreakdown(BaseModel):
    """Hours breakdown for a single category."""

    category: str
    total_hours: float
    percentage: float
    session_count: int


class WeeklyTrend(BaseModel):
    """Weekly time tracking trend data point."""

    week: str  # ISO week start date (YYYY-MM-DD)
    total_hours: float
    category_hours: dict[str, float]


class TimeAnalyticsResponse(BaseModel):
    """Response for time analytics dashboard."""

    total_hours: float
    total_sessions: int
    category_breakdown: list[CategoryBreakdown]
    weekly_trend: list[WeeklyTrend]  # 4-week trend
    avg_daily_hours: float
