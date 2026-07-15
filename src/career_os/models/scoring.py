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

    # Rule-based red flags detected in JD (JSON array of {flag_type, severity, description})
    red_flags: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ATS keywords extracted by AI (JSON array of {keyword, category, matched})
    ats_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Desire score — measures "how much would the user want this job?" (0-10)
    desire_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    desire_score_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    desire_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Dimensional sub-scores (0-10, each may be null on legacy rows)
    dim_technical_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim_seniority_alignment: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim_compensation_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim_location_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim_career_trajectory: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim_company_fit: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Borderline 2-pass scoring (Epic 5 / G-273) — number of scoring passes used.
    # 1 = single pass (default), 2 = borderline zone triggered second pass.
    scoring_passes: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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


class ShadowScore(Base):
    """A candidate-variant score logged in parallel with the live scorer.

    Scoring Engine v2 (G-1336, finding I): when ``SCORING_SHADOW_VARIANT`` is
    set, every production scoring call ALSO scores the job with a candidate
    rubric/model and records the result here. Shadow scores are **never**
    surfaced to the user — they exist only to compare a candidate change against
    the live scorer on real production jobs before promotion. Mirrors the G-272
    embedding-shadow pattern ("measure on production, not a proxy").

    ``primary_fit_score`` snapshots the live score at the same instant so the
    prod-vs-shadow delta needs no join back to ``scored_jobs``.
    """

    __tablename__ = "shadow_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    # Nullable + ondelete SET NULL so pruning a live score never drops the
    # shadow audit trail, and so a shadow can be logged even when the primary
    # score is not persisted (e.g. offline comparator runs).
    scored_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scored_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    discovered_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("discovered_jobs.id"), nullable=True, index=True
    )

    # Free-form variant label (e.g. "0to5-scale", "mistral-large", "rubric-v2").
    variant: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Candidate-variant scores.
    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    desire_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quadrant: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Snapshot of the live score at logging time (for a join-free prod-vs-shadow diff).
    primary_fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full candidate breakdown + reasoning (JSON / text) for later inspection.
    dimensional_scores: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ShadowScore(id={self.id}, variant='{self.variant}', "
            f"fit_score={self.fit_score}, profile_id={self.profile_id})>"
        )


class ScoringFeedback(Base):
    """User feedback on an AI-generated score.

    Captures explicit corrections ("too high" / "too low") and implicit
    signals (promoted to application, reached interview stage).

    Referenced by Epic 11 (Bayesian Learning) to calibrate scoring behavior.
    """

    __tablename__ = "scoring_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scored_job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scored_jobs.id"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )

    # "too_high", "too_low", "correct", "implicit_positive",
    # "implicit_negative", "implicit_strong_positive"
    direction: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional: what the user thinks the score should be (0-10 scale)
    user_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Optional: free-text explanation from the user
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot of the AI-generated score at the time feedback was submitted
    original_fit_score: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ScoringFeedback(id={self.id}, scored_job_id={self.scored_job_id}, "
            f"direction='{self.direction}')>"
        )
