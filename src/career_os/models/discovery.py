"""SQLAlchemy ORM models for Job Discovery (Milestone 3)."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base
from career_os.models.models import FK_PROFILES_ID


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class DiscoveredJob(Base):
    """A job discovered through automated scraping.

    Deduplication key: (title_normalized, company_normalized, location_normalized).
    Multiple sources may contribute data to the same record; the richest
    description, earliest posted date, and a JSON list of source URLs are kept.
    """

    __tablename__ = "discovered_jobs"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "title_normalized",
            "company_normalized",
            "location_normalized",
            name="uq_discovered_job_dedup",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )

    # Raw fields from scraping
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Dedup-normalized keys (lowercase, stripped)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    company_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Source tracking — JSON array of source names, e.g. ["arbeitsagentur", "arbeitnow"]
    sources: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # JSON array of all URLs from different sources
    source_urls: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Scoring (populated later by M3 scoring engine)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Embedding cosine similarity to profile (Epic 4 / G-272).
    # Populated during batch scoring pre-filter; NULL until first embedding run.
    embedding_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Pipeline linkage — set when auto-fed into pipeline
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<DiscoveredJob(id={self.id}, title='{self.title}', company='{self.company}')>"


class SearchProfile(Base):
    """Saved search profile for recurring discovery sweeps."""

    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    locations: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    remote_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    # Additional filter config as JSON
    filters: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Schedule fields
    cadence: Mapped[str | None] = mapped_column(String(50), nullable=True)  # weekly | daily | None
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<SearchProfile(id={self.id}, name='{self.name}')>"


class DiscoveryRun(Base):
    """Log of each discovery sweep execution."""

    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    search_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_profiles.id", ondelete="SET NULL"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual | scheduled | cli
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="running"
    )  # running | completed | failed
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<DiscoveryRun(id={self.id}, trigger='{self.trigger}', status='{self.status}')>"


class SavedSearch(Base):
    """User-saved search/filter combination for the discovery search UI.

    Stores a named set of search query, filters, and sort preferences
    so the user can quickly re-execute favorite search configurations.
    """

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # All filter state stored as JSON for flexibility
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<SavedSearch(id={self.id}, name='{self.name}')>"
