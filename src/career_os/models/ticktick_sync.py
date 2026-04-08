"""SQLAlchemy ORM model for TickTick sync task mappings."""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class TickTickSyncTask(Base):
    """Maps a Career OS entity (follow-up, learning goal, pipeline action) to a TickTick task.

    Tracks bidirectional sync state between Career OS and TickTick.
    """

    __tablename__ = "ticktick_sync_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Career OS side
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # follow_up | learning_goal | pipeline_action
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # TickTick side
    ticktick_task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ticktick_project_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Sync metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="synced"
    )  # synced | completed | error
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<TickTickSyncTask(id={self.id}, entity_type='{self.entity_type}', "
            f"entity_id={self.entity_id}, ticktick_task_id='{self.ticktick_task_id}')>"
        )
