"""Pydantic schemas for Calendar Integration API."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CalendarEventType(StrEnum):
    """Types of calendar events."""

    interview = "interview"
    follow_up = "follow_up"
    prep_reminder = "prep_reminder"


class CalendarProvider(StrEnum):
    """Supported calendar providers."""

    ical = "ical"
    google = "google"
    fantastical = "fantastical"


class CalendarEventCreate(BaseModel):
    """Request body for creating a calendar event."""

    profile_id: int
    application_id: int | None = None
    follow_up_id: int | None = None

    event_type: CalendarEventType
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime

    # Interview-specific
    company: str | None = None
    role: str | None = None
    interview_type: str | None = None
    meeting_link: str | None = None
    prep_notes: str | None = None

    # Reminder config
    reminder_minutes_before: int = Field(
        default=1440, ge=0, le=10080,
        description="Minutes before event for prep reminder (default 24h)",
    )


class CalendarEventUpdate(BaseModel):
    """Request body for updating a calendar event."""

    title: str | None = None
    description: str | None = None
    location: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    interview_type: str | None = None
    meeting_link: str | None = None
    prep_notes: str | None = None
    reminder_minutes_before: int | None = Field(
        default=None, ge=0, le=10080
    )


class CalendarEventResponse(BaseModel):
    """Response schema for a calendar event."""

    id: int
    profile_id: int
    application_id: int | None = None
    follow_up_id: int | None = None
    parent_event_id: int | None = None

    event_type: str
    title: str
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime

    company: str | None = None
    role: str | None = None
    interview_type: str | None = None
    meeting_link: str | None = None
    prep_notes: str | None = None

    reminder_minutes_before: int | None = None
    uid: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarEventListResponse(BaseModel):
    """Response for listing calendar events."""

    events: list[CalendarEventResponse]
    total: int


class CalendarExportResponse(BaseModel):
    """Response with iCal data."""

    ical_data: str
    filename: str
    content_type: str = "text/calendar"


class GoogleCalendarUrlResponse(BaseModel):
    """Response with a Google Calendar URL to add event."""

    url: str
    event_id: int


class FantasticalUrlResponse(BaseModel):
    """Response with a Fantastical URL scheme to add event."""

    url: str
    event_id: int


class CalendarProviderConfigResponse(BaseModel):
    """Response with provider-specific export data for an event."""

    event_id: int
    providers: dict[str, str]  # provider_name -> url_or_data
