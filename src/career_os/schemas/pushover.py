"""Pydantic schemas for Pushover notification integration."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from career_os.schemas.constraints import INT64_MAX, INT64_MIN

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class NotificationCategory(StrEnum):
    """Categories of notifications that can be toggled."""

    follow_up = "follow_up"
    ghost = "ghost"
    discovery = "discovery"
    interview = "interview"


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


class NotificationPreferenceUpdate(BaseModel):
    """Request body for updating notification preferences."""

    follow_up_reminders: bool | None = None
    ghost_alerts: bool | None = None
    discovery_alerts: bool | None = None
    interview_reminders: bool | None = None
    quiet_hours_start: int | None = Field(
        default=None, ge=0, le=23, description="Quiet hours start (0-23)"
    )
    quiet_hours_end: int | None = Field(
        default=None, ge=0, le=23, description="Quiet hours end (0-23)"
    )
    interview_lead_time_minutes: int | None = Field(
        default=None, ge=0, le=10080, description="Interview reminder lead time in minutes"
    )
    discovery_score_threshold: float | None = Field(
        default=None, ge=0, le=10, description="Min score to trigger discovery notification"
    )


class NotificationPreferenceResponse(BaseModel):
    """Response schema for notification preferences."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    follow_up_reminders: bool
    ghost_alerts: bool
    discovery_alerts: bool
    interview_reminders: bool
    quiet_hours_start: int | None = Field(default=None, ge=INT64_MIN, le=INT64_MAX)
    quiet_hours_end: int | None = Field(default=None, ge=INT64_MIN, le=INT64_MAX)
    interview_lead_time_minutes: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    discovery_score_threshold: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Send notification request
# ---------------------------------------------------------------------------


class SendNotificationRequest(BaseModel):
    """Request body for manually sending a test notification."""

    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    category: NotificationCategory
    title: str = Field(..., min_length=1, max_length=250)
    message: str = Field(..., min_length=1, max_length=1024)
    application_id: int | None = Field(default=None, ge=1, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Notification log
# ---------------------------------------------------------------------------


class NotificationLogResponse(BaseModel):
    """Response schema for a single notification log entry."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    profile_id: int = Field(..., ge=1, le=INT64_MAX)
    category: str
    title: str
    message: str
    application_id: int | None = Field(default=None, ge=1, le=INT64_MAX)
    status: str
    error_message: str | None = None
    sent_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogListResponse(BaseModel):
    """Response schema for listing notification logs."""

    notifications: list[NotificationLogResponse]
    total: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


# ---------------------------------------------------------------------------
# Trigger responses
# ---------------------------------------------------------------------------


class NotificationTriggerResponse(BaseModel):
    """Response from triggering notifications (e.g., follow-up check)."""

    triggered: int = Field(..., ge=INT64_MIN, le=INT64_MAX, description="Number of notifications sent")
    skipped: int = Field(..., ge=INT64_MIN, le=INT64_MAX, description="Number skipped (disabled, quiet hours, etc.)")
    failed: int = Field(..., ge=INT64_MIN, le=INT64_MAX, description="Number that failed to send")
    details: list[dict] = Field(default_factory=list)
