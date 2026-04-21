"""Pydantic schemas for Market Intelligence API (Milestone 3)."""

from __future__ import annotations

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
# VAL-MARKET-001: Salary Trends
# ---------------------------------------------------------------------------


class SalaryTrendItem(BaseModel):
    """A single salary trend entry for a role/location/period combination."""

    role: str = Field(..., description="Role type (normalized title)")
    location: str = Field(default="", description="Location filter applied")
    period: str = Field(default="", description="Time period (YYYY-MM)")
    median: float = Field(..., description="Median salary (EUR)")
    p25: float = Field(..., description="25th percentile salary")
    p75: float = Field(..., description="75th percentile salary")
    sample_size: int = Field(
        ..., ge=0, le=INT64_MAX, description="Number of postings with salary data"
    )


class SalaryTrendsResponse(BaseModel):
    """Response for GET /api/market/salary-trends."""

    trends: list[SalaryTrendItem] = Field(default_factory=list)
    last_refreshed_at: datetime | None = None

    @field_validator("last_refreshed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---------------------------------------------------------------------------
# VAL-MARKET-002: Skill Demand Trends
# ---------------------------------------------------------------------------


class SkillTrendItem(BaseModel):
    """A single skill demand trend entry."""

    skill_name: str = Field(..., description="Skill name")
    mention_count: int = Field(
        ..., ge=0, le=INT64_MAX, description="Times mentioned across postings"
    )
    trend_direction: str = Field(..., description="Trend: up, down, or stable")
    percentage_of_postings: float = Field(
        ..., ge=0, le=100, description="% of postings mentioning this skill"
    )


class SkillTrendsResponse(BaseModel):
    """Response for GET /api/market/skill-trends."""

    skills: list[SkillTrendItem] = Field(default_factory=list)
    total_postings_analyzed: int = Field(
        default=0, ge=INT64_MIN, le=INT64_MAX, description="Total postings analyzed"
    )
    last_refreshed_at: datetime | None = None

    @field_validator("last_refreshed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---------------------------------------------------------------------------
# VAL-MARKET-003: Company Hiring Patterns
# ---------------------------------------------------------------------------


class HiringPatternItem(BaseModel):
    """Hiring pattern for a single company."""

    company: str = Field(..., description="Company name")
    active_postings_count: int = Field(
        ..., ge=0, le=INT64_MAX, description="Number of active postings"
    )
    posting_velocity: float = Field(..., description="Postings per week (recent velocity)")
    roles_trending: list[str] = Field(
        default_factory=list, description="Role titles being hired for"
    )


class HiringPatternsResponse(BaseModel):
    """Response for GET /api/market/hiring-patterns."""

    companies: list[HiringPatternItem] = Field(default_factory=list)
    last_refreshed_at: datetime | None = None

    @field_validator("last_refreshed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---------------------------------------------------------------------------
# VAL-MARKET-004: Market Positioning
# ---------------------------------------------------------------------------


class PositionItem(BaseModel):
    """Market positioning for a single role type."""

    role_type: str = Field(..., description="Role type (e.g., 'Senior TPM')")
    match_percentage: float = Field(
        ..., ge=0, le=100, description="Profile match % for this role type"
    )
    total_roles_analyzed: int = Field(
        ..., ge=0, le=INT64_MAX, description="Number of roles analyzed for this type"
    )


class PositioningResponse(BaseModel):
    """Response for GET /api/market/positioning."""

    positions: list[PositionItem] = Field(default_factory=list)
    last_refreshed_at: datetime | None = None

    @field_validator("last_refreshed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---------------------------------------------------------------------------
# VAL-MARKET-005: Dream Company Opportunity Radar
# ---------------------------------------------------------------------------


class OpportunityItem(BaseModel):
    """A flagged dream company opportunity."""

    id: int = Field(..., ge=1, le=INT64_MAX, description="Discovered job ID")
    title: str
    company: str
    location: str
    url: str | None = None
    fit_score: float | None = None
    salary_range: str | None = None
    priority: str = Field(default="dream", description="Always 'dream' for radar results")
    alert: bool = Field(default=True, description="Always True for radar results")
    posted_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("posted_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class OpportunityRadarResponse(BaseModel):
    """Response for GET /api/market/opportunity-radar."""

    opportunities: list[OpportunityItem] = Field(default_factory=list)
    dream_companies: list[str] = Field(
        default_factory=list, description="Dream companies searched for"
    )
    last_refreshed_at: datetime | None = None

    @field_validator("last_refreshed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class MarketRefreshRequest(BaseModel):
    """Request body for POST /api/market/refresh."""

    profile_id: int = Field(
        ..., ge=1, le=INT64_MAX, description="Profile ID to refresh market data for"
    )


class MarketRefreshResponse(BaseModel):
    """Response for POST /api/market/refresh."""

    last_refreshed_at: datetime
    salary_trends_count: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    skill_trends_count: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    companies_analyzed: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)

    @field_validator("last_refreshed_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)
