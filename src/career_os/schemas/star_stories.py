"""Pydantic schemas for STAR Stories API.

Covers:
- VAL-STAR-001: STAR story CRUD (create/list/view)
- VAL-STAR-002: Skill-to-company relevance mapping (recommended stories)
- VAL-STAR-003: Story gap identification
"""

from __future__ import annotations

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


class StarStoryCreate(BaseModel):
    """Create a new STAR story."""

    title: str = Field(..., min_length=1, max_length=500, description="Story title")
    situation: str = Field(..., min_length=1, description="STAR: Situation")
    task: str = Field(..., min_length=1, description="STAR: Task")
    action: str = Field(..., min_length=1, description="STAR: Action")
    result: str = Field(..., min_length=1, description="STAR: Result")
    skill_tags: list[str] = Field(
        default_factory=list,
        description="Skill tags for matching against requirements",
    )


class StarStoryUpdate(BaseModel):
    """Update an existing STAR story. All fields optional.

    When provided, string fields must be non-empty (same validation
    as StarStoryCreate).
    """

    title: str | None = Field(default=None, min_length=1, max_length=500)
    situation: str | None = Field(default=None, min_length=1)
    task: str | None = Field(default=None, min_length=1)
    action: str | None = Field(default=None, min_length=1)
    result: str | None = Field(default=None, min_length=1)
    skill_tags: list[str] | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StarStoryResponse(BaseModel):
    """A STAR story response."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    title: str
    situation: str
    task: str
    action: str
    result: str
    skill_tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class StarStoryListResponse(BaseModel):
    """List of STAR stories."""

    stories: list[StarStoryResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Recommended stories for an application
# ---------------------------------------------------------------------------


class RecommendedStory(BaseModel):
    """A STAR story recommended for an application based on skill tag match."""

    story: StarStoryResponse
    matching_skills: list[str] = Field(
        description="Skill tags that match the application requirements"
    )
    match_count: int = Field(
        ..., ge=INT64_MIN, le=INT64_MAX, description="Number of matching skill tags"
    )


class RecommendedStoriesResponse(BaseModel):
    """Recommended stories for an application."""

    application_id: int = Field(..., ge=1, le=INT64_MAX)
    company: str
    role: str
    recommended_stories: list[RecommendedStory]
    total_requirements: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    covered_skills: list[str] = Field(description="Skills covered by at least one story")


# ---------------------------------------------------------------------------
# Story gap identification
# ---------------------------------------------------------------------------


class StoryGap(BaseModel):
    """A skill that has no corresponding STAR story."""

    skill_name: str
    severity: str
    required_level: str
    has_story: bool = False
    create_prompt: str = Field(
        description="Prompt encouraging the user to create a story for this skill"
    )


class StoryGapsResponse(BaseModel):
    """Story gaps for an application."""

    application_id: int = Field(..., ge=1, le=INT64_MAX)
    company: str
    role: str
    story_gaps: list[StoryGap]
    total_requirements: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    covered_count: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    gap_count: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
