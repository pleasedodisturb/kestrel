"""SQLAlchemy ORM models for STAR Stories (Milestone 4).

Covers:
- StarStory: STAR story with Situation, Task, Action, Result + title + skill tags
"""

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


class StarStory(Base):
    """A STAR story with Situation, Task, Action, Result, title, and skill tags.

    Skill tags are stored as a comma-separated string for simplicity.
    """

    __tablename__ = "star_stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    skill_tags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def get_skill_tags_list(self) -> list[str]:
        """Return skill_tags as a list of strings."""
        if not self.skill_tags:
            return []
        return [t.strip() for t in self.skill_tags.split(",") if t.strip()]

    def __repr__(self) -> str:
        return f"<StarStory(id={self.id}, title='{self.title}')>"
