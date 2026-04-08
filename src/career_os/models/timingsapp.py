"""SQLAlchemy ORM model for TimingsApp tracked sessions."""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class TimeSession(Base):
    """A tracked time session for job-search activities.

    Each row represents a single timed session (start/stop) with a category
    and optional link to a TimingsApp time entry.
    """

    __tablename__ = "time_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Session details
    activity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # applying | researching | prepping | networking | learning
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # TimingsApp integration
    timingsapp_entry_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # External ID from TimingsApp
    timingsapp_project: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # TimingsApp project used

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<TimeSession(id={self.id}, activity='{self.activity_name}', "
            f"category='{self.category}')>"
        )
