"""SQLAlchemy ORM models for ESCO skill taxonomy cache and skill mappings."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class ESCOSkill(Base):
    """Cached ESCO skill taxonomy entry.

    Populated by the load_esco_data script from the ESCO v1.2 CSV dataset.
    ~14K rows covering 13,939 canonical skills across 28 languages.
    """

    __tablename__ = "esco_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_uri: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    preferred_label: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    alt_labels: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # newline-separated synonyms
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # skill/competence, knowledge, attitude
    isco_group: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ISCO-08 group code
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ESCOSkill(uri='{self.concept_uri}', label='{self.preferred_label}')>"

    @property
    def alt_labels_list(self) -> list[str]:
        """Return alt_labels as a Python list."""
        if not self.alt_labels:
            return []
        return [lbl.strip() for lbl in self.alt_labels.split("\n") if lbl.strip()]


class SkillMapping(Base):
    """Cache table mapping raw skill text → ESCO concept URI.

    Avoids re-running expensive normalization for the same skill name.
    Stores the match method used and confidence score for diagnostics.
    """

    __tablename__ = "skill_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_text: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    esco_uri: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # None = confirmed no match
    preferred_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    match_method: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # exact, fuzzy, embedding, none
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 – 1.0
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("raw_text", name="uq_skill_mappings_raw_text"),)

    def __repr__(self) -> str:
        return (
            f"<SkillMapping(raw='{self.raw_text}', uri='{self.esco_uri}', "
            f"method='{self.match_method}')>"
        )
