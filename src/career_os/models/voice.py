"""SQLAlchemy models for voice discussion sessions."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from career_os.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class VoiceSession(Base):
    """A voice/text discussion session.

    Supports three modes:
    - cover_letter: brainstorm a cover letter referencing profile + application
    - coaching: coaching dialogue with role-relevant questions + feedback
    - job_evaluation: scored evaluation of a job with pros/cons
    """

    __tablename__ = "voice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # cover_letter | coaching | job_evaluation
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )  # active | completed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    messages: Mapped[list["VoiceMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="VoiceMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<VoiceSession(id={self.id}, mode='{self.mode}')>"


class VoiceMessage(Base):
    """A single message in a voice discussion session."""

    __tablename__ = "voice_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("voice_sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    session: Mapped["VoiceSession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<VoiceMessage(id={self.id}, role='{self.role}')>"
