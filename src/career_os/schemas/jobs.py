"""Pydantic schemas for Jobs Search & Filter API (Milestone 3)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _ensure_utc(v: Any) -> datetime | None:
    """Ensure a datetime value has UTC timezone info."""
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# ---------------------------------------------------------------------------
# Job Search / Filter Response
# ---------------------------------------------------------------------------


class JobSearchResult(BaseModel):
    """A single discovered job result with optional score data."""

    id: int
    profile_id: int
    title: str
    company: str
    location: str
    url: str | None = None
    description: str | None = None
    salary_range: str | None = None
    remote: bool = False
    posted_at: datetime | None = None
    sources: list[str] = []
    source_urls: list[str] = []
    fit_score: float | None = None
    readiness_score: float | None = None
    application_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("sources", "source_urls", mode="before")
    @classmethod
    def _parse_json_list(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("created_at", "updated_at", "posted_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class JobSearchResponse(BaseModel):
    """Paginated search results response."""

    jobs: list[JobSearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Saved Search CRUD
# ---------------------------------------------------------------------------


class SavedSearchConfig(BaseModel):
    """The configuration stored in a saved search."""

    q: str | None = None
    source: str | None = None
    remote: bool | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    score_min: float | None = None
    score_max: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    company: str | None = None
    location: str | None = None
    sort: str | None = None
    order: str | None = None


class SavedSearchCreate(BaseModel):
    """Request body for creating a saved search."""

    profile_id: int = Field(..., description="Profile ID")
    name: str = Field(..., min_length=1, max_length=255, description="Saved search name")
    config: SavedSearchConfig = Field(
        default_factory=SavedSearchConfig,
        description="Search/filter/sort configuration",
    )


class SavedSearchUpdate(BaseModel):
    """Request body for updating a saved search."""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Search name"
    )
    config: SavedSearchConfig | None = Field(
        default=None, description="Updated configuration"
    )


class SavedSearchResponse(BaseModel):
    """Response for a saved search record."""

    id: int
    profile_id: int
    name: str
    config: SavedSearchConfig
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("config", mode="before")
    @classmethod
    def _parse_json_config(cls, v: Any) -> dict:
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(v, dict):
            return v
        return {}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class SavedSearchListResponse(BaseModel):
    """Response for listing saved searches."""

    searches: list[SavedSearchResponse]
    total: int
