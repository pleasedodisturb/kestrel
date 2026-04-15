"""SQLAlchemy ORM model for WARN Act filing records (Epic 9 / G-277).

WARN Act (Worker Adjustment and Retraining Notification Act) requires employers to
give 60 days notice before mass layoffs. This data is public record, filed with state
governments. We scrape it via the warn-scraper library and use it as a red-flag signal.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class WARNFiling(Base):
    """A single WARN Act notice filed with a state government.

    Data sourced from warn-scraper (biglocalnews/warn-scraper). One row per
    unique (company_name, state, effective_date) combination; subsequent scrapes
    for the same notice update the existing row rather than inserting duplicates.
    """

    __tablename__ = "warn_filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Raw company name exactly as it appears in the state filing
    company_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # Lowercased, suffix-stripped version for fuzzy matching
    company_name_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)

    employees_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Effective date of the layoff (60 days after notice, per WARN Act)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Date the notice was filed with the state
    notice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<WARNFiling(id={self.id}, company='{self.company_name}', "
            f"state='{self.state}', notice_date={self.notice_date})>"
        )
