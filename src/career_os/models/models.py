"""SQLAlchemy ORM models for Career OS."""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from career_os.database import Base

FK_PROFILES_ID = "profiles.id"
FK_APPLICATIONS_ID = "applications.id"
CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class Profile(Base):
    """User profile supporting multi-user/multi-job-family."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dream_companies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    salary_range: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_market_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships — M1 tables
    applications: Mapped[list["Application"]] = relationship(
        back_populates="profile", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        back_populates="profile", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        back_populates="profile", cascade=CASCADE_ALL_DELETE_ORPHAN
    )

    # Relationships — M2 tables (Skills Intelligence)
    # These forward-reference models defined in career_os.models.skills
    skills: Mapped[list["Skill"]] = relationship(  # noqa: F821
        cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    goals: Mapped[list["Goal"]] = relationship(  # noqa: F821
        cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    coaching_suggestions: Mapped[list["CoachingSuggestion"]] = relationship(  # noqa: F821
        cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    # Note: skill_history cascades through Skill.history,
    # job_requirements cascade through Application.job_requirements,
    # learning_resources cascade through Profile (below) and also
    # via Skill/JobRequirement for FK ordering.
    learning_resources: Mapped[list["LearningResource"]] = relationship(  # noqa: F821
        cascade=CASCADE_ALL_DELETE_ORPHAN
    )

    # Onboarding state (one-to-one, optional — may not exist for pre-onboarding profiles)
    onboarding_state: Mapped["OnboardingState | None"] = relationship(  # noqa: F821
        "OnboardingState", back_populates="profile", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, name='{self.name}')>"


class Application(Base):
    """Job application record."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="discovered")
    salary_range: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_applied: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    profile: Mapped["Profile"] = relationship(back_populates="applications")
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        back_populates="application", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        back_populates="application", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    packages: Mapped[list["ApplicationPackage"]] = relationship(
        back_populates="application", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    # M2: job requirements parsed from this application's JD
    job_requirements: Mapped[list["JobRequirement"]] = relationship(  # noqa: F821
        cascade=CASCADE_ALL_DELETE_ORPHAN
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, company='{self.company}', role='{self.role}')>"


class ActivityLog(Base):
    """Chronological activity log entry — universal audit trail.

    Phase 1: application-scoped actions.
    Phase 2: any entity (contact, cv_package, submission) via entity_type/entity_id.
    """

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(FK_APPLICATIONS_ID), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Phase 2 — entity-generic audit fields
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)  # JSON blob

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    profile: Mapped["Profile"] = relationship(back_populates="activity_logs")
    application: Mapped["Application | None"] = relationship(back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, action='{self.action}')>"


class FollowUp(Base):
    """Follow-up reminder for an application."""

    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_APPLICATIONS_ID), nullable=False, index=True
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    follow_up_type: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    profile: Mapped["Profile"] = relationship(back_populates="follow_ups")
    application: Mapped["Application"] = relationship(back_populates="follow_ups")

    def __repr__(self) -> str:
        return f"<FollowUp(id={self.id}, type='{self.follow_up_type}')>"


class ApplicationPackage(Base):
    """Application materials package (CV, cover letter, etc.)."""

    __tablename__ = "application_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_APPLICATIONS_ID), nullable=False, index=True
    )
    package_dir: Mapped[str] = mapped_column(Text, nullable=False)
    cover_letter_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    profile: Mapped["Profile"] = relationship()
    application: Mapped["Application"] = relationship(back_populates="packages")

    def __repr__(self) -> str:
        return f"<ApplicationPackage(id={self.id}, dir='{self.package_dir}')>"
