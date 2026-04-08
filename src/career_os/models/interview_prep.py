"""SQLAlchemy ORM models for Interview Preparation (Milestone 4).

Covers:
- InterviewPrepSession: per-application prep with AI-generated topics/questions
- InterviewPrepItem: checklist items with completion tracking (progress persistence)
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class InterviewPrepSession(Base):
    """Interview preparation session for an application.

    Stores AI-generated topics and questions as JSON text.
    Each application has at most one session per profile.
    """

    __tablename__ = "interview_prep_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    questions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    total_prep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_researched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    items: Mapped[list["InterviewPrepItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<InterviewPrepSession(id={self.id}, application_id={self.application_id})>"


class InterviewPrepItem(Base):
    """A single checklist item in an interview prep session.

    Tracks completion state for progress persistence across sessions.
    """

    __tablename__ = "interview_prep_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interview_prep_sessions.id"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    item: Mapped[str] = mapped_column(Text, nullable=False)
    time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    session: Mapped["InterviewPrepSession"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<InterviewPrepItem(id={self.id}, item='{self.item[:40]}...', "
            f"completed={self.completed})>"
        )
