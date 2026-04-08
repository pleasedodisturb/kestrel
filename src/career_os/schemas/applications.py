"""Pydantic schemas for Application CRUD API."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ApplicationStatus(StrEnum):
    """Valid application statuses for the pipeline."""

    discovered = "discovered"
    interested = "interested"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    accepted = "accepted"
    rejected = "rejected"
    ghosted = "ghosted"


# Valid transitions: from_status → set of allowed to_statuses
# Forward: discovered→interested→applied→interviewing→offer→accepted/rejected
# Backward: allowed so users can move apps back (e.g., company reschedules)
# any non-terminal → ghosted
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.discovered: {
        ApplicationStatus.interested,
        ApplicationStatus.ghosted,
    },
    ApplicationStatus.interested: {
        ApplicationStatus.discovered,
        ApplicationStatus.applied,
        ApplicationStatus.ghosted,
    },
    ApplicationStatus.applied: {
        ApplicationStatus.interested,
        ApplicationStatus.discovered,
        ApplicationStatus.interviewing,
        ApplicationStatus.ghosted,
    },
    ApplicationStatus.interviewing: {
        ApplicationStatus.applied,
        ApplicationStatus.interested,
        ApplicationStatus.discovered,
        ApplicationStatus.offer,
        ApplicationStatus.ghosted,
    },
    ApplicationStatus.offer: {
        ApplicationStatus.interviewing,
        ApplicationStatus.accepted,
        ApplicationStatus.rejected,
        ApplicationStatus.ghosted,
    },
    # Terminal statuses — can be reopened to discovered
    ApplicationStatus.accepted: {ApplicationStatus.discovered},
    ApplicationStatus.rejected: {ApplicationStatus.discovered},
    ApplicationStatus.ghosted: {ApplicationStatus.discovered},
}


def normalize_status(raw: str) -> str:
    """Normalize a status string to its canonical lowercase form.

    Handles title-cased, upper-cased, and mixed-case variants that may
    arrive from the Kanban DnD UI or external callers.  Returns the
    canonical ``ApplicationStatus`` value (always lowercase).

    Raises ``ValueError`` if *raw* does not map to a known status.
    """
    cleaned = raw.strip().lower()
    # Validate against the enum – raises ValueError for unknown values
    return ApplicationStatus(cleaned).value


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Check if a status transition is allowed.

    Both statuses are normalized before comparison, so title-cased or
    mixed-case values coming from the frontend work correctly.
    """
    try:
        from_s = ApplicationStatus(from_status.strip().lower())
        to_s = ApplicationStatus(to_status.strip().lower())
    except ValueError:
        return False
    return to_s in VALID_TRANSITIONS.get(from_s, set())


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ApplicationCreate(BaseModel):
    """Request body for POST /api/applications."""

    profile_id: int = Field(..., description="Profile this application belongs to")
    company: str = Field(..., min_length=1, description="Company name")
    role: str = Field(..., min_length=1, description="Role / job title")
    url: str | None = Field(default=None, description="Job posting URL")
    source: str | None = Field(default=None, description="How the job was found")
    salary_range: str | None = Field(default=None, description="Salary range")
    contact: str | None = Field(default=None, description="Contact person")
    next_step: str | None = Field(default=None, description="Next action to take")
    notes: str | None = Field(default=None, description="Free-form notes")
    fit_score: float | None = Field(
        default=None, ge=0, le=10, description="Fit score 0-10"
    )


class ApplicationUpdate(BaseModel):
    """Request body for PATCH /api/applications/{id}."""

    company: str | None = Field(default=None, min_length=1, description="Company name")
    role: str | None = Field(default=None, min_length=1, description="Role / job title")
    url: str | None = Field(default=None, description="Job posting URL")
    source: str | None = Field(default=None, description="How the job was found")
    status: str | None = Field(default=None, description="New status (validated transition)")
    salary_range: str | None = Field(default=None, description="Salary range")
    contact: str | None = Field(default=None, description="Contact person")
    next_step: str | None = Field(default=None, description="Next action to take")
    notes: str | None = Field(default=None, description="Free-form notes")
    fit_score: float | None = Field(default=None, ge=0, le=10, description="Fit score 0-10")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: Any) -> str | None:
        """Normalize status to canonical lowercase form.

        This handles title-cased values sent by Kanban drag-and-drop,
        e.g. ``"Applied"`` → ``"applied"``.
        """
        if v is None:
            return v
        try:
            return normalize_status(v)
        except ValueError:
            return v  # let transition validation handle invalid values


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


def _ensure_utc(v: Any) -> datetime | None:
    """Ensure a datetime value has UTC timezone info.

    SQLite stores datetimes without timezone, so we assume UTC and attach it.
    """
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


class ActivityLogResponse(BaseModel):
    """Response schema for an activity log entry."""

    id: int
    action: str
    details: str | None = None
    source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_created_at_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class ApplicationResponse(BaseModel):
    """Response schema for a single application."""

    id: int
    profile_id: int
    company: str
    role: str
    url: str | None = None
    source: str | None = None
    status: str
    salary_range: str | None = None
    contact: str | None = None
    next_step: str | None = None
    notes: str | None = None
    fit_score: float | None = None
    readiness_score: float | None = None
    date_applied: datetime | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    is_ghost: bool = False

    model_config = {"from_attributes": True}

    @field_validator("status", mode="before")
    @classmethod
    def _ensure_status_lowercase(cls, v: Any) -> str:
        """Always emit lowercase status in API responses."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("created_at", "updated_at", "date_applied", "archived_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class FollowUpSummaryResponse(BaseModel):
    """Minimal follow-up info embedded in application detail."""

    id: int
    due_date: datetime
    follow_up_type: str
    notes: str | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("due_date", "completed_at", "created_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class ApplicationPackageSummaryResponse(BaseModel):
    """Minimal application-package info embedded in application detail."""

    id: int
    package_name: str
    file_path: str
    package_type: str

    model_config = {"from_attributes": True}


class ApplicationDetailResponse(ApplicationResponse):
    """Response schema for application detail including activity log, follow-ups, and packages."""

    activity_log: list[ActivityLogResponse] = []
    follow_ups: list[FollowUpSummaryResponse] = []
    packages: list[ApplicationPackageSummaryResponse] = []


class ApplicationListResponse(BaseModel):
    """Response schema for list of applications."""

    applications: list[ApplicationResponse]
    total: int
