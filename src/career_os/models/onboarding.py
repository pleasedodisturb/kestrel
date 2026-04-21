"""SQLAlchemy ORM model for onboarding state."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from career_os.database import Base
from career_os.models.models import FK_PROFILES_ID, _utcnow


class OnboardingState(Base):
    """Tracks per-profile onboarding progress with per-step timestamps.

    Created on first PATCH call (D-13) — not on profile creation.
    One-to-one with Profile (D-11): profile_id is unique and non-nullable.
    """

    __tablename__ = "onboarding_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, unique=True, index=True
    )

    # Resume-from-last-step (D-03)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Per-step completion timestamps (D-01) — None means step not yet completed
    profile_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    demo_seeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    welcome_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tour_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    feedback_prompted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Per-step source surface tracking (D-02) — 'cli' or 'web', None means step not completed
    profile_started_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    profile_completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    demo_seeded_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    welcome_completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tour_completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    feedback_prompted_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Audit timestamps (follow existing model convention)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationship back to Profile (Python-side convenience, no migration needed per D-12 note)
    profile: Mapped["Profile"] = relationship(  # noqa: F821
        "Profile", back_populates="onboarding_state"
    )
