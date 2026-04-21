"""Pydantic schemas for Skills Intelligence API."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SkillCategory(StrEnum):
    """Valid skill categories."""

    technical = "technical"
    domain = "domain"
    soft = "soft"
    tools = "tools"


class SkillProficiency(StrEnum):
    """Valid proficiency levels."""

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


class SkillCreate(BaseModel):
    """Request body for POST /api/skills."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile this skill belongs to")
    name: str = Field(..., min_length=1, description="Skill name")
    category: SkillCategory = Field(..., description="Skill category")
    proficiency: SkillProficiency = Field(
        default=SkillProficiency.beginner, description="Proficiency level"
    )
    evidence_source: str = Field(
        default="manual", description="Evidence source (e.g., cv.yaml, profile, manual)"
    )
    evidence_detail: str | None = Field(default=None, description="Evidence detail/quote")


class SkillUpdate(BaseModel):
    """Request body for PUT /api/skills/{id}."""

    name: str | None = Field(default=None, min_length=1, description="Skill name")
    category: SkillCategory | None = Field(default=None, description="Skill category")
    proficiency: SkillProficiency | None = Field(default=None, description="Proficiency level")
    evidence_source: str | None = Field(default=None, description="Evidence source")
    evidence_detail: str | None = Field(default=None, description="Evidence detail/quote")
    reason: str | None = Field(default=None, description="Reason for the change (for history)")


class IngestRequest(BaseModel):
    """Request body for POST /api/skills/ingest."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile to ingest skills for")
    sources: list[str] = Field(
        default_factory=lambda: ["cv", "assessments", "profile"],
        description="Sources to ingest: cv, assessments, profile",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SkillResponse(BaseModel):
    """Response schema for a single skill."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    name: str
    category: str
    proficiency: str
    evidence_source: str
    evidence_detail: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class SkillHistoryResponse(BaseModel):
    """Response schema for a skill history entry."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    skill_id: int = Field(..., ge=1, le=INT64_MAX)
    previous_proficiency: str | None = None
    new_proficiency: str
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_created_at_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class SkillListResponse(BaseModel):
    """Response schema for list of skills."""

    skills: list[SkillResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


class IngestResponse(BaseModel):
    """Response schema for ingestion results."""

    skills_created: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    skills_updated: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    sources_processed: list[str]
    errors: list[str] = []


class SkillsEmptyStateResponse(BaseModel):
    """Response when no skills exist — includes CTAs."""

    skills: list[SkillResponse] = []
    total: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    ctas: list[dict] = Field(
        default_factory=lambda: [
            {"label": "Import from CV", "action": "ingest_cv"},
            {"label": "Parse assessments", "action": "ingest_assessments"},
            {"label": "Add manually", "action": "add_manual"},
        ]
    )
