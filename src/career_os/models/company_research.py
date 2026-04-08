"""SQLAlchemy ORM model for persisted Company Research Reports.

Stores the result of company research so that the interview prep
research gate can verify whether actual research has been performed
for a given company (not just a non-empty company name).
"""

from datetime import UTC, datetime

from sqlalchemy import (
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


class CompanyResearchReportModel(Base):
    """Persisted company research report.

    Created when company research is successfully completed.
    Used by interview prep to check if actual research data exists.
    """

    __tablename__ = "company_research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    company_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    values_alignment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    industry_segment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CompanyResearchReportModel(id={self.id}, company_name='{self.company_name}')>"
