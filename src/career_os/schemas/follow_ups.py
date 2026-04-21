"""Pydantic schemas for Follow-Up API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


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


class FollowUpCreate(BaseModel):
    """Request body for POST /api/follow-ups."""

    application_id: int = Field(
        ..., ge=1, le=INT64_MAX, description="Application this follow-up belongs to"
    )
    profile_id: int = Field(
        ..., ge=1, le=INT64_MAX, description="Profile this follow-up belongs to"
    )
    due_date: datetime = Field(..., description="When the follow-up is due")
    follow_up_type: str = Field(
        ..., min_length=1, description="Type: email, phone, linkedin, other"
    )
    notes: str | None = Field(default=None, description="Free-form notes")


class FollowUpComplete(BaseModel):
    """Request body for PATCH /api/follow-ups/{id}."""

    completed: bool = Field(..., description="Mark as completed")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class FollowUpResponse(BaseModel):
    """Response schema for a single follow-up."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    application_id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    due_date: datetime
    follow_up_type: str
    notes: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    # Application context (for list views)
    application_company: str | None = None
    application_role: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("due_date", "completed_at", "created_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class FollowUpListResponse(BaseModel):
    """Response schema for list of follow-ups."""

    follow_ups: list[FollowUpResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


class OverdueCountResponse(BaseModel):
    """Response schema for overdue follow-ups count."""

    count: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
