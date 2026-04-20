"""Pydantic schemas for Discovery API (Milestone 3)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN

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
# Discovery Request / Response
# ---------------------------------------------------------------------------


class DiscoverRequest(BaseModel):
    """Request body for POST /api/discover — triggers a discovery sweep."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile to discover jobs for")
    keywords: list[str] = Field(default_factory=list, description="Search keywords")
    locations: list[str] = Field(default_factory=list, description="Locations to search")
    remote_only: bool = Field(default=False, description="Only remote jobs")
    sources: list[str] = Field(
        default_factory=list,
        description="Sources to search (empty = all available)",
    )
    search_profile_id: int | None = Field(
        default=None,
        ge=1,
        le=INT64_MAX,
        description="Use saved search profile parameters instead of inline ones",
    )
    limit_per_source: int = Field(default=25, ge=1, le=100, description="Max per source")


class DiscoveredJobResponse(BaseModel):
    """Response schema for a single discovered job."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
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
    application_id: int | None = Field(default=None, ge=1, le=INT64_MAX)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("sources", "source_urls", mode="before")
    @classmethod
    def _parse_json_list(cls, v: Any) -> list[str]:
        """Parse JSON string to list if needed."""
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


class DiscoveryWarning(BaseModel):
    """Warning from a single source that failed during discovery."""

    source: str
    error: str


class DiscoverResponse(BaseModel):
    """Response for POST /api/discover — sweep results."""

    run_id: int = Field(..., ge=1, le=INT64_MAX)
    total_found: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    new_jobs: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    duplicates: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    jobs: list[DiscoveredJobResponse]
    warnings: list[DiscoveryWarning] = []
    sources_queried: list[str] = []


# ---------------------------------------------------------------------------
# Search Profile CRUD
# ---------------------------------------------------------------------------


class SearchProfileCreate(BaseModel):
    """Request body for POST /api/search-profiles."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile this search belongs to")
    name: str = Field(..., min_length=1, description="Search profile name")
    keywords: list[str] = Field(default_factory=list, description="Keywords")
    locations: list[str] = Field(default_factory=list, description="Locations")
    remote_only: bool = Field(default=False, description="Remote only filter")
    sources: list[str] = Field(default_factory=list, description="Sources to query")
    filters: dict[str, Any] | None = Field(default=None, description="Additional filters")


class SearchProfileUpdate(BaseModel):
    """Request body for PUT /api/search-profiles/{id}."""

    name: str | None = Field(default=None, min_length=1, description="Search profile name")
    keywords: list[str] | None = Field(default=None, description="Keywords")
    locations: list[str] | None = Field(default=None, description="Locations")
    remote_only: bool | None = Field(default=None, description="Remote only filter")
    sources: list[str] | None = Field(default=None, description="Sources to query")
    filters: dict[str, Any] | None = Field(default=None, description="Additional filters")
    is_active: bool | None = Field(default=None, description="Active status")


class SearchProfileResponse(BaseModel):
    """Response schema for a saved search profile."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    name: str
    keywords: list[str] = []
    locations: list[str] = []
    remote_only: bool = False
    sources: list[str] = []
    filters: dict[str, Any] | None = None
    is_active: bool = True
    cadence: str | None = Field(default=None, description="Schedule cadence: daily | weekly | None")
    next_run: datetime | None = Field(default=None, description="Next scheduled run time (UTC)")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("keywords", "locations", "sources", mode="before")
    @classmethod
    def _parse_json_list(cls, v: Any) -> list[str]:
        """Parse JSON string to list if needed."""
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("filters", mode="before")
    @classmethod
    def _parse_json_dict(cls, v: Any) -> dict[str, Any] | None:
        """Parse JSON string to dict if needed."""
        if v is None:
            return None
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(v, dict):
            return v
        return None

    @field_validator("created_at", "updated_at", "next_run", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class SearchProfileListResponse(BaseModel):
    """Response for listing search profiles."""

    profiles: list[SearchProfileResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Discovery Run Log
# ---------------------------------------------------------------------------


class DiscoveryRunResponse(BaseModel):
    """Response schema for a discovery run log entry."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    search_profile_id: int | None = Field(default=None, ge=1, le=INT64_MAX)
    trigger: str
    status: str
    total_found: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    new_jobs: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    duplicates: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    errors: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    warnings: list[DiscoveryWarning] = []
    started_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("warnings", mode="before")
    @classmethod
    def _parse_warnings(cls, v: Any) -> list[dict]:
        """Parse JSON string to list if needed."""
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)
