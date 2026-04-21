"""Pydantic schemas for onboarding API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Canonical step names — must match OnboardingState column names (without _at suffix).
# Order defines next_step computation in the service layer (STEP_ORDER in services/onboarding.py).
VALID_STEPS: list[str] = [
    "profile_started",
    "profile_completed",
    "demo_seeded",
    "welcome_completed",
    "tour_completed",
    "feedback_prompted",
    "completed",
]


class OnboardingStepUpdate(BaseModel):
    """Request body for PATCH /api/onboarding/status (D-05).

    Marks a single step complete. The server sets the timestamp (D-05).
    Re-patching the same step is a no-op (D-06) — handled in service layer.
    Step ordering is NOT enforced (D-07).
    """

    step: str = Field(
        ...,
        description=(f"Step name to mark complete. Valid values: {', '.join(VALID_STEPS)}"),
    )
    via: Literal["cli", "web"] = Field(
        ...,
        description="Surface that completed this step ('cli' or 'web').",
    )


class OnboardingStatusResponse(BaseModel):
    """Response schema for GET and PATCH /api/onboarding/status (D-04).

    Computed fields (next_step, is_complete, progress_pct) are populated
    by the service layer — callers do not need to derive these.
    """

    profile_id: int
    current_step: str | None = None

    # Per-step completion timestamps (D-01) — None means not yet completed
    profile_started_at: datetime | None = None
    profile_completed_at: datetime | None = None
    demo_seeded_at: datetime | None = None
    welcome_completed_at: datetime | None = None
    tour_completed_at: datetime | None = None
    feedback_prompted_at: datetime | None = None
    completed_at: datetime | None = None

    # Per-step source surface (D-02) — None means not completed
    profile_started_via: str | None = None
    profile_completed_via: str | None = None
    demo_seeded_via: str | None = None
    welcome_completed_via: str | None = None
    tour_completed_via: str | None = None
    feedback_prompted_via: str | None = None
    completed_via: str | None = None

    # Computed fields populated by service layer (D-04)
    next_step: str | None = None
    is_complete: bool = False
    progress_pct: int = 0

    # Audit timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
