"""SQLAlchemy ORM models for Scoring Engine (Milestone 3)."""

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
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class ScoringWeights(Base):
    """Configurable scoring weights per profile.

    Weights are used by the scoring engine to compute a weighted fit_score.
    They persist across sessions (stored in DB) and can be modified via API.
    """

    __tablename__ = "scoring_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, unique=True, index=True
    )

    # Weight factors (all 0.0–1.0, should sum to ~1.0 for meaningful scoring)
    skills_match: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    career_alignment: Mapped[float] = mapped_column(Float, nullable=False, default=0.20)
    culture_fit: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    salary_match: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    location_match: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    growth_potential: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    remote_preference: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScoringWeights(id={self.id}, profile_id={self.profile_id})>"

    def to_dict(self) -> dict[str, float]:
        """Return weight factors as a dict."""
        return {
            "skills_match": self.skills_match,
            "career_alignment": self.career_alignment,
            "culture_fit": self.culture_fit,
            "salary_match": self.salary_match,
            "location_match": self.location_match,
            "growth_potential": self.growth_potential,
            "remote_preference": self.remote_preference,
        }


class ScoredJob(Base):
    """Score record for a discovered job or application.

    Stores full scoring breakdown. Linked to a discovered_job or application.
    Scores become stale when weights or profile change.
    """

    __tablename__ = "scored_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    discovered_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("discovered_jobs.id"), nullable=True, index=True
    )
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=True, index=True
    )

    # Core scores
    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    career_alignment: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Reasoning & details
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_salary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    effort_flag: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    prep_level: Mapped[str] = mapped_column(String(50), nullable=False, default="moderate")
    prep_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Score breakdown (JSON array of factor dicts)
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Staleness tracking
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Weights snapshot at scoring time (JSON)
    weights_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ScoredJob(id={self.id}, fit_score={self.fit_score}, profile_id={self.profile_id})>"
        )
