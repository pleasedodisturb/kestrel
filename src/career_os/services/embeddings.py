"""Embedding service — manages embedding generation, caching, and similarity (G-272).

Builds text representations of profiles and job descriptions, generates
embedding vectors via the configured AI provider, and stores them in the
``embeddings`` table.  Cosine similarity is computed in Python (no sqlite-vec
dependency).

Key design decisions:
- Vectors are stored as raw float32 bytes in a BLOB column.
- Cosine similarity is computed in Python using struct/math (no numpy dep).
- Profile embeddings are invalidated when skills/goals/job_family change.
- Graceful degradation: if the provider can't embed, callers get None.
"""

from __future__ import annotations

import logging
import math
import struct
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from career_os.config import settings
from career_os.models.embeddings import Embedding
from career_os.models.models import Profile
from career_os.models.skills import Goal, Skill

if TYPE_CHECKING:
    from career_os.ai.base import AIProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vector serialization helpers
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 768  # nomic-embed-text default


def vector_to_bytes(vec: list[float]) -> bytes:
    """Serialize a float list to raw little-endian float32 bytes."""
    return struct.pack(f"<{len(vec)}f", *vec)


def bytes_to_vector(data: bytes) -> list[float]:
    """Deserialize raw float32 bytes back to a float list."""
    count = len(data) // 4
    return list(struct.unpack(f"<{count}f", data))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns 0.0 if either vector has zero magnitude.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------

_MAX_JD_CHARS = 32_000  # ~8K tokens at ~4 chars/token


def build_profile_text(db: Session, profile_id: int) -> str | None:
    """Build a structured text representation of a profile for embedding.

    Returns None if the profile doesn't exist or has no useful content.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        return None

    parts: list[str] = []

    if profile.job_family:
        parts.append(f"Job Family: {profile.job_family}")

    # Skills with proficiency
    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    if skills:
        skill_strs = []
        for s in skills[:30]:  # Cap to avoid huge text
            level = f" ({s.proficiency})" if s.proficiency else ""
            skill_strs.append(f"{s.name}{level}")
        parts.append(f"Skills: {', '.join(skill_strs)}")

    # Goals
    goals = db.query(Goal).filter(Goal.profile_id == profile_id).all()
    if goals:
        goal_strs = [g.description for g in goals[:10] if g.description]
        if goal_strs:
            parts.append(f"Goals: {', '.join(goal_strs)}")

    if profile.location:
        parts.append(f"Location: {profile.location}")

    if not parts:
        return None

    return "\n".join(parts)


def build_job_text(description: str | None, title: str = "", company: str = "") -> str:
    """Build text for embedding a job posting.

    Uses title + company as prefix, then the description (truncated).
    """
    parts: list[str] = []
    if title:
        parts.append(f"Title: {title}")
    if company:
        parts.append(f"Company: {company}")
    if description:
        parts.append(description[:_MAX_JD_CHARS])
    return "\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Embedding CRUD
# ---------------------------------------------------------------------------


def get_embedding(
    db: Session,
    entity_type: str,
    entity_id: int,
    model_name: str | None = None,
) -> list[float] | None:
    """Retrieve a cached embedding vector, or None if not found."""
    model = model_name or settings.embedding_model
    row = (
        db.query(Embedding)
        .filter(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == entity_id,
            Embedding.model_name == model,
        )
        .first()
    )
    if row is None:
        return None
    return bytes_to_vector(row.vector)


def store_embedding(
    db: Session,
    entity_type: str,
    entity_id: int,
    vector: list[float],
    model_name: str | None = None,
) -> Embedding:
    """Store (or update) an embedding vector."""
    model = model_name or settings.embedding_model
    blob = vector_to_bytes(vector)

    existing = (
        db.query(Embedding)
        .filter(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == entity_id,
            Embedding.model_name == model,
        )
        .first()
    )
    if existing:
        existing.vector = blob
        db.flush()
        return existing

    emb = Embedding(
        entity_type=entity_type,
        entity_id=entity_id,
        model_name=model,
        vector=blob,
    )
    db.add(emb)
    db.flush()
    return emb


def delete_embedding(
    db: Session,
    entity_type: str,
    entity_id: int,
    model_name: str | None = None,
) -> int:
    """Delete cached embedding(s) for an entity. Returns count deleted."""
    model = model_name or settings.embedding_model
    count = (
        db.query(Embedding)
        .filter(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == entity_id,
            Embedding.model_name == model,
        )
        .delete()
    )
    db.flush()
    return count


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------


async def generate_profile_embedding(
    db: Session,
    profile_id: int,
    provider: AIProvider,
) -> list[float] | None:
    """Generate and cache a profile embedding.

    Returns the embedding vector, or None if the profile has no useful text
    or the provider doesn't support embeddings.
    """
    text = build_profile_text(db, profile_id)
    if not text:
        logger.debug("Profile %d has no useful text for embedding", profile_id)
        return None

    try:
        vector = await provider.embed(text)
    except NotImplementedError:
        logger.debug("Provider %s does not support embeddings", provider.name)
        return None
    except Exception:
        logger.warning("Failed to generate embedding for profile %d", profile_id, exc_info=True)
        return None

    store_embedding(db, "profile", profile_id, vector)
    db.commit()
    return vector


async def generate_job_embedding(
    db: Session,
    job_id: int,
    description: str | None,
    title: str = "",
    company: str = "",
    provider: AIProvider | None = None,
) -> list[float] | None:
    """Generate and cache a job embedding.

    Returns the vector, or None on failure/unsupported.
    """
    text = build_job_text(description, title, company)
    if not text:
        return None

    if provider is None:
        from career_os.ai.factory import get_ai_provider

        provider = get_ai_provider()

    try:
        vector = await provider.embed(text)
    except NotImplementedError:
        logger.debug("Provider %s does not support embeddings", provider.name)
        return None
    except Exception:
        logger.warning("Failed to generate embedding for job %d", job_id, exc_info=True)
        return None

    store_embedding(db, "discovered_job", job_id, vector)
    db.flush()
    return vector


def invalidate_profile_embedding(db: Session, profile_id: int) -> int:
    """Delete cached profile embedding so it gets regenerated on next scoring.

    Call this when skills, goals, or job_family change.
    Returns the number of embeddings deleted.
    """
    count = delete_embedding(db, "profile", profile_id)
    if count:
        logger.info("Invalidated %d profile embedding(s) for profile %d", count, profile_id)
    return count


async def compute_job_similarities(
    db: Session,
    profile_id: int,
    jobs: list,
    provider: AIProvider,
) -> dict[int, float]:
    """Compute cosine similarity between profile and each job.

    Returns a dict of {job_id: similarity_score}.
    Jobs without descriptions or that fail embedding are omitted.
    """
    # Ensure profile embedding exists
    profile_vec = get_embedding(db, "profile", profile_id)
    if profile_vec is None:
        profile_vec = await generate_profile_embedding(db, profile_id, provider)
    if profile_vec is None:
        logger.info("Cannot compute similarities: no profile embedding for %d", profile_id)
        return {}

    similarities: dict[int, float] = {}

    for job in jobs:
        # Try cached embedding first
        job_vec = get_embedding(db, "discovered_job", job.id)
        if job_vec is None:
            job_vec = await generate_job_embedding(
                db,
                job.id,
                job.description,
                title=job.title,
                company=job.company,
                provider=provider,
            )
        if job_vec is None:
            continue

        sim = cosine_similarity(profile_vec, job_vec)
        similarities[job.id] = round(sim, 4)

        # Store similarity on the DiscoveredJob row
        job.embedding_similarity = sim

    db.flush()
    return similarities
