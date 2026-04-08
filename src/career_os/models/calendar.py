"""SQLAlchemy ORM model for calendar events."""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class CalendarEvent(Base):
    """A calendar event created by the Career OS platform.

    Covers: interviews, follow-ups, prep reminders.
    """

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=True, index=True
    )
    follow_up_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    parent_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Event details
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # interview | follow_up | prep_reminder
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)  # Physical or video link
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Interview-specific fields
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(500), nullable=True)
    interview_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # phone_screen | technical | behavioral | system_design | panel | other
    meeting_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Prep reminder config
    reminder_minutes_before: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=1440
    )  # Default 24h = 1440 min

    # Tracking
    uid: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )  # iCal UID for dedup
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent(id={self.id}, type='{self.event_type}', title='{self.title}')>"
