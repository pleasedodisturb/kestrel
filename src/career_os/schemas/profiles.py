"""Pydantic schemas for Profile API."""

import json as json_mod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


class ProfileCreate(BaseModel):
    """Request body for POST /api/profiles."""

    name: str = Field(..., min_length=1, description="Profile name")
    email: str | None = Field(default=None, description="Email address")
    location: str | None = Field(default=None, description="Location")
    job_family: str | None = Field(default=None, description="Target job family")
    dream_companies: list[str] | None = Field(default=None, description="List of dream companies")


class ProfileUpdate(BaseModel):
    """Request body for PATCH /api/profiles/{id}."""

    name: str | None = Field(default=None, min_length=1, description="Profile name")
    email: str | None = Field(default=None, description="Email address")
    location: str | None = Field(default=None, description="Location")
    job_family: str | None = Field(default=None, description="Target job family")
    dream_companies: list[str] | None = Field(default=None, description="List of dream companies")


class ProfileResponse(BaseModel):
    """Response schema for a profile."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    name: str
    email: str | None = None
    location: str | None = None
    job_family: str | None = None
    dream_companies: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("dream_companies", mode="before")
    @classmethod
    def _parse_dream_companies(cls, v: Any) -> list[str] | None:
        """Parse dream_companies from JSON string if it comes from DB."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                parsed = json_mod.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (json_mod.JSONDecodeError, TypeError):
                return None
        return v


class ProfileListResponse(BaseModel):
    """Response schema for list of profiles."""

    profiles: list[ProfileResponse]
    count: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
