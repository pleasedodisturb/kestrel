"""SQLAlchemy ORM model for embedding vectors (Epic 4 / G-272).

Stores embedding vectors as BLOBs for profile and job text representations.
Cosine similarity is computed in Python (numpy or manual) rather than via
sqlite-vec, which requires a C extension not available in all environments.

TODO: When deployed on a system with sqlite-vec available, add a sqlite-vec
virtual table index for faster nearest-neighbor queries at scale.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from career_os.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class Embedding(Base):
    """Cached embedding vector for a profile or discovered job.

    entity_type: "profile" or "discovered_job"
    entity_id:   the PK of the corresponding Profile or DiscoveredJob row
    model_name:  embedding model used (e.g. "nomic-embed-text")
    vector:      raw float32 bytes (768 * 4 = 3072 bytes for nomic-embed-text)
    """

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "model_name", name="uq_embedding_entity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Embedding(id={self.id}, entity_type='{self.entity_type}', "
            f"entity_id={self.entity_id}, model='{self.model_name}')>"
        )
