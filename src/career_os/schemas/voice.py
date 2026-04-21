"""Pydantic schemas for Voice Discussion Mode API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


def _ensure_utc(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class VoiceSessionCreate(BaseModel):
    """Create a new voice discussion session."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Active profile ID")
    mode: str = Field(
        ...,
        description="Session mode: cover_letter, coaching, or job_evaluation",
    )
    application_id: int | None = Field(
        default=None,
        ge=1,
        le=INT64_MAX,
        description="Application ID (required for cover_letter and job_evaluation)",
    )
    title: str | None = Field(default=None, description="Optional session title")


class VoiceMessageCreate(BaseModel):
    """Send a message in a voice discussion session."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Active profile ID")
    content: str = Field(..., min_length=1, description="User message text (from STT or typed)")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class VoiceMessageResponse(BaseModel):
    """A single message in a voice session."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    session_id: int = Field(..., ge=1, le=INT64_MAX)
    role: str = Field(..., description="Message sender: user or assistant")
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class VoiceSessionResponse(BaseModel):
    """Voice discussion session summary."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    application_id: int | None = Field(default=None, ge=1, le=INT64_MAX)
    mode: str
    title: str | None = None
    status: str
    messages: list[VoiceMessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class VoiceSessionListResponse(BaseModel):
    """List of voice sessions."""

    sessions: list[VoiceSessionResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


class VoiceSendResponse(BaseModel):
    """Response after sending a message — includes both user and assistant messages."""

    user_message: VoiceMessageResponse
    assistant_message: VoiceMessageResponse
    session: VoiceSessionResponse
