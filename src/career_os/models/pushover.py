"""SQLAlchemy ORM models for Pushover notification integration."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
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


class NotificationPreference(Base):
    """Per-profile notification preferences: category toggles + quiet hours."""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )

    # Per-category toggles (default True = enabled)
    follow_up_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ghost_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    discovery_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    interview_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Quiet hours (24h format, e.g., 22 = 10 PM, 8 = 8 AM)
    quiet_hours_start: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Hour (0-23), e.g., 22
    quiet_hours_end: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Hour (0-23), e.g., 8

    # Interview reminder lead time (minutes before interview)
    interview_lead_time_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1440,  # 24h default
    )

    # Discovery score threshold (only notify for scores >= this)
    discovery_score_threshold: Mapped[float] = mapped_column(Integer, nullable=False, default=7)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(id={self.id}, profile_id={self.profile_id})>"


class NotificationLog(Base):
    """Log of sent notifications for dedup and audit."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # follow_up | ghost | discovery | interview
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="sent"
    )  # sent | failed | queued (quiet hours)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id}, category='{self.category}', status='{self.status}')>"
        )
