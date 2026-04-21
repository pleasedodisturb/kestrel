"""Pydantic schemas for Networking CRM (M6) — contacts, interactions, linking."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RelationshipType(StrEnum):
    referral = "referral"
    recruiter = "recruiter"
    hiring_manager = "hiring_manager"
    peer = "peer"
    mentor = "mentor"
    other = "other"


class ReferralStatus(StrEnum):
    none = "none"
    contacted = "contacted"
    cv_sent = "cv_sent"
    submitted = "submitted"
    feedback_received = "feedback_received"


class Warmth(StrEnum):
    cold = "cold"
    warm = "warm"
    hot = "hot"


class InteractionType(StrEnum):
    email = "email"
    call = "call"
    coffee = "coffee"
    linkedin_message = "linkedin_message"
    intro = "intro"
    referral_submission = "referral_submission"


class Direction(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class ContactRole(StrEnum):
    """Role a contact plays for a specific application."""

    referrer = "referrer"
    recruiter = "recruiter"
    hiring_manager = "hiring_manager"
    interviewer = "interviewer"
    insider = "insider"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_utc(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# ---------------------------------------------------------------------------
# Contact schemas
# ---------------------------------------------------------------------------


class ContactCreate(BaseModel):
    """Request body for POST /api/contacts."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile this contact belongs to")
    name: str = Field(..., min_length=1, max_length=255, description="Contact name")
    company: str | None = Field(default=None, max_length=255, description="Company")
    role: str | None = Field(default=None, max_length=255, description="Their role/title")
    email: str | None = Field(default=None, max_length=255, description="Email address")
    linkedin_url: str | None = Field(default=None, max_length=500, description="LinkedIn URL")
    phone: str | None = Field(default=None, max_length=50, description="Phone number")
    relationship_type: str = Field(default="other", description="Relationship type")
    referral_status: str | None = Field(default=None, description="Referral status")
    warmth: str = Field(default="cold", description="Connection strength")
    notes: str | None = Field(default=None, description="Free-text notes")
    tags: list[str] | None = Field(default=None, description="Tags as list")
    source: str | None = Field(default=None, max_length=100, description="How you met")
    next_follow_up: datetime | None = Field(default=None, description="Next follow-up date (UTC)")

    @field_validator("relationship_type", mode="before")
    @classmethod
    def _validate_relationship_type(cls, v: Any) -> str:
        if v is not None:
            v = str(v).strip().lower()
            if v not in RelationshipType.__members__:
                raise ValueError(
                    f"Invalid relationship_type '{v}'. "
                    f"Must be one of: {', '.join(RelationshipType.__members__)}"
                )
        return v

    @field_validator("referral_status", mode="before")
    @classmethod
    def _validate_referral_status(cls, v: Any) -> str | None:
        if v is None:
            return v
        v = str(v).strip().lower()
        if v not in ReferralStatus.__members__:
            raise ValueError(
                f"Invalid referral_status '{v}'. "
                f"Must be one of: {', '.join(ReferralStatus.__members__)}"
            )
        return v

    @field_validator("warmth", mode="before")
    @classmethod
    def _validate_warmth(cls, v: Any) -> str:
        if v is not None:
            v = str(v).strip().lower()
            if v not in Warmth.__members__:
                raise ValueError(
                    f"Invalid warmth '{v}'. Must be one of: {', '.join(Warmth.__members__)}"
                )
        return v


class ContactUpdate(BaseModel):
    """Request body for PATCH /api/contacts/{id}."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    relationship_type: str | None = Field(default=None)
    referral_status: str | None = Field(default=None)
    warmth: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    source: str | None = Field(default=None, max_length=100)
    next_follow_up: datetime | None = Field(default=None)

    @field_validator("relationship_type", mode="before")
    @classmethod
    def _validate_relationship_type(cls, v: Any) -> str | None:
        if v is None:
            return v
        v = str(v).strip().lower()
        if v not in RelationshipType.__members__:
            raise ValueError(
                f"Invalid relationship_type '{v}'. "
                f"Must be one of: {', '.join(RelationshipType.__members__)}"
            )
        return v

    @field_validator("referral_status", mode="before")
    @classmethod
    def _validate_referral_status(cls, v: Any) -> str | None:
        if v is None:
            return v
        v = str(v).strip().lower()
        if v not in ReferralStatus.__members__:
            raise ValueError(
                f"Invalid referral_status '{v}'. "
                f"Must be one of: {', '.join(ReferralStatus.__members__)}"
            )
        return v

    @field_validator("warmth", mode="before")
    @classmethod
    def _validate_warmth(cls, v: Any) -> str | None:
        if v is None:
            return v
        v = str(v).strip().lower()
        if v not in Warmth.__members__:
            raise ValueError(
                f"Invalid warmth '{v}'. Must be one of: {', '.join(Warmth.__members__)}"
            )
        return v


class ContactResponse(BaseModel):
    """Response schema for a single contact."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    name: str
    company: str | None = None
    role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    relationship_type: str
    referral_status: str | None = None
    warmth: str
    notes: str | None = None
    tags: list[str] | None = None
    source: str | None = None
    last_contacted_at: datetime | None = None
    next_follow_up: datetime | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator(
        "created_at",
        "updated_at",
        "archived_at",
        "last_contacted_at",
        "next_follow_up",
        mode="before",
    )
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)

    @field_validator("tags", mode="before")
    @classmethod
    def _parse_tags(cls, v: Any) -> list[str] | None:
        """Deserialize JSON string from DB into list."""
        if v is None:
            return None
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ContactListResponse(BaseModel):
    """Response schema for list of contacts."""

    contacts: list[ContactResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Interaction schemas
# ---------------------------------------------------------------------------


class InteractionCreate(BaseModel):
    """Request body for POST /api/contacts/{id}/interactions."""

    interaction_type: str = Field(..., description="Type of interaction")
    direction: str = Field(..., description="inbound or outbound")
    subject: str | None = Field(default=None, max_length=500, description="Subject line")
    notes: str | None = Field(default=None, description="Interaction notes")
    occurred_at: datetime | None = Field(default=None, description="When it happened (UTC)")

    @field_validator("interaction_type", mode="before")
    @classmethod
    def _validate_interaction_type(cls, v: Any) -> str:
        v = str(v).strip().lower()
        if v not in InteractionType.__members__:
            raise ValueError(
                f"Invalid interaction_type '{v}'. "
                f"Must be one of: {', '.join(InteractionType.__members__)}"
            )
        return v

    @field_validator("direction", mode="before")
    @classmethod
    def _validate_direction(cls, v: Any) -> str:
        v = str(v).strip().lower()
        if v not in Direction.__members__:
            raise ValueError(
                f"Invalid direction '{v}'. Must be one of: {', '.join(Direction.__members__)}"
            )
        return v


class InteractionResponse(BaseModel):
    """Response schema for a single interaction."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    contact_id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    interaction_type: str
    direction: str
    subject: str | None = None
    notes: str | None = None
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("occurred_at", "created_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class InteractionListResponse(BaseModel):
    """Response schema for list of interactions."""

    interactions: list[InteractionResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Contact-Application link schemas
# ---------------------------------------------------------------------------


class ContactApplicationCreate(BaseModel):
    """Request body for POST /api/contacts/{id}/applications."""

    application_id: int = Field(..., ge=1, le=INT64_MAX, description="Application to link")
    role: str = Field(..., description="Contact's role for this application")
    notes: str | None = Field(default=None, description="Notes about the link")

    @field_validator("role", mode="before")
    @classmethod
    def _validate_role(cls, v: Any) -> str:
        v = str(v).strip().lower()
        if v not in ContactRole.__members__:
            raise ValueError(
                f"Invalid role '{v}'. Must be one of: {', '.join(ContactRole.__members__)}"
            )
        return v


class ContactApplicationResponse(BaseModel):
    """Response schema for a contact-application link."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    contact_id: int = Field(..., ge=1, le=INT64_MAX)
    application_id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    role: str
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class ContactDetailResponse(ContactResponse):
    """Response schema for contact detail with related data."""

    interactions: list[InteractionResponse] = []
    linked_applications: list[ContactApplicationResponse] = []
