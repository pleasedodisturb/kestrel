"""Skill normalizer service: maps free-text skills to ESCO canonical entries.

Normalization pipeline (three passes):
  1. Exact match   — preferred_label or alt_labels, case-insensitive (~60% coverage)
  2. Fuzzy match   — Levenshtein via rapidfuzz, threshold 85% (~25% more coverage)
  3. Embedding     — reserved for future; placeholder logs a warning and returns None

Results are cached in the skill_mappings table to avoid re-computation.

Usage::

    from career_os.services.skill_normalizer import normalize_skill, NormalizationResult

    result = normalize_skill(db, "React.js")
    if result:
        print(result.esco_uri, result.preferred_label, result.confidence)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from career_os.models.esco import ESCOSkill, SkillMapping

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Fuzzy match threshold (0–100 scale used by rapidfuzz)
FUZZY_THRESHOLD = 85.0


@dataclass
class NormalizationResult:
    """Result of normalizing a raw skill string."""

    raw_text: str
    esco_uri: str
    preferred_label: str
    match_method: str  # "exact" | "fuzzy" | "embedding"
    confidence: float  # 0.0 – 1.0


def normalize_skill(db: Session, raw_skill: str) -> NormalizationResult | None:
    """Map a free-text skill string to an ESCO canonical entry.

    Args:
        db: SQLAlchemy session (synchronous).
        raw_skill: Raw skill text, e.g. "React.js", "Kubernets", "Python".

    Returns:
        NormalizationResult if a match was found, else None.
        Results are cached in the skill_mappings table.
    """
    if not raw_skill or not raw_skill.strip():
        return None

    normalized_input = raw_skill.strip()

    # --- Cache lookup ---
    cached = db.query(SkillMapping).filter(SkillMapping.raw_text == normalized_input).first()
    if cached is not None:
        if cached.esco_uri is None:
            return None  # confirmed no-match, cached
        return NormalizationResult(
            raw_text=cached.raw_text,
            esco_uri=cached.esco_uri,
            preferred_label=cached.preferred_label or "",
            match_method=cached.match_method or "exact",
            confidence=cached.confidence or 1.0,
        )

    # --- Pass 1: Exact match ---
    result = _exact_match(db, normalized_input)

    # --- Pass 2: Fuzzy match ---
    if result is None:
        result = _fuzzy_match(db, normalized_input)

    # --- Pass 3: Embedding (future) ---
    if result is None:
        result = _embedding_match(db, normalized_input)

    # --- Persist to cache ---
    _cache_result(db, normalized_input, result)

    return result


def _exact_match(db: Session, raw: str) -> NormalizationResult | None:
    """Case-insensitive exact match against preferred_label and alt_labels."""
    raw_lower = raw.lower()

    # Try preferred_label first (fastest path)
    skill = db.query(ESCOSkill).filter(ESCOSkill.preferred_label.ilike(raw_lower)).first()
    if skill:
        return NormalizationResult(
            raw_text=raw,
            esco_uri=skill.concept_uri,
            preferred_label=skill.preferred_label,
            match_method="exact",
            confidence=1.0,
        )

    # Scan alt_labels for all skills (SQLite: no JSON array support, we use LIKE)
    # We search for the raw text surrounded by newlines or at string boundaries.
    # The alt_labels field stores synonyms separated by "\n".
    skills_with_alts = (
        db.query(ESCOSkill)
        .filter(ESCOSkill.alt_labels.isnot(None))
        .filter(ESCOSkill.alt_labels.ilike(f"%{raw_lower}%"))
        .all()
    )
    for skill in skills_with_alts:
        for alt in skill.alt_labels_list:
            if alt.lower() == raw_lower:
                return NormalizationResult(
                    raw_text=raw,
                    esco_uri=skill.concept_uri,
                    preferred_label=skill.preferred_label,
                    match_method="exact",
                    confidence=1.0,
                )

    return None


def _fuzzy_match(db: Session, raw: str) -> NormalizationResult | None:
    """Levenshtein fuzzy match via rapidfuzz against all preferred labels.

    Loads all preferred labels into memory once per call (acceptable for ~14K entries;
    future optimisation: build in-memory index on first call and reuse).
    """
    all_skills = db.query(ESCOSkill.concept_uri, ESCOSkill.preferred_label).all()
    if not all_skills:
        return None

    # Build label list for rapidfuzz
    labels = [s.preferred_label for s in all_skills]
    match = process.extractOne(
        raw,
        labels,
        scorer=fuzz.WRatio,
        score_cutoff=FUZZY_THRESHOLD,
    )
    if match is None:
        return None

    matched_label, score, idx = match
    skill_row = all_skills[idx]
    confidence = round(score / 100.0, 4)

    return NormalizationResult(
        raw_text=raw,
        esco_uri=skill_row.concept_uri,
        preferred_label=matched_label,
        match_method="fuzzy",
        confidence=confidence,
    )


def _embedding_match(db: Session, raw: str) -> NormalizationResult | None:
    """Embedding similarity fallback (future implementation).

    Placeholder: logs a debug message and returns None.
    Full implementation would use a sentence-transformer model to embed *raw*
    and compare against pre-computed ESCO skill embeddings stored in a vector column.
    """
    logger.debug(
        "Embedding fallback not yet implemented for skill '%s'. "
        "Install a sentence-transformers model and populate esco_skill_embeddings "
        "to enable this pass.",
        raw,
    )
    return None


def _cache_result(db: Session, raw_text: str, result: NormalizationResult | None) -> None:
    """Persist a normalization result (or confirmed no-match) to skill_mappings cache."""
    mapping = SkillMapping(
        raw_text=raw_text,
        esco_uri=result.esco_uri if result else None,
        preferred_label=result.preferred_label if result else None,
        match_method=result.match_method if result else "none",
        confidence=result.confidence if result else None,
    )
    try:
        db.add(mapping)
        db.commit()
    except Exception:
        db.rollback()
        logger.debug(
            "Cache write failed for '%s' (likely duplicate key — already cached)", raw_text
        )


# ---------------------------------------------------------------------------
# Profile skill enrichment
# ---------------------------------------------------------------------------


def enrich_profile_skill(db: Session, skill_id: int) -> NormalizationResult | None:
    """Normalize a profile skill and persist its esco_uri.

    Args:
        db: SQLAlchemy session.
        skill_id: ID of the Skill record to enrich.

    Returns:
        NormalizationResult if matched, else None.
    """
    from career_os.models.skills import Skill

    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        logger.warning("enrich_profile_skill: skill %d not found", skill_id)
        return None

    result = normalize_skill(db, skill.name)
    if result:
        skill.esco_uri = result.esco_uri
        db.commit()
        logger.debug(
            "Enriched skill '%s' → %s (method=%s, confidence=%.2f)",
            skill.name,
            result.esco_uri,
            result.match_method,
            result.confidence,
        )
    else:
        logger.debug("No ESCO match for skill '%s'", skill.name)

    return result


def enrich_job_requirement(db: Session, job_requirement_id: int) -> NormalizationResult | None:
    """Normalize a job requirement keyword and persist its esco_uri.

    Args:
        db: SQLAlchemy session.
        job_requirement_id: ID of the JobRequirement record.

    Returns:
        NormalizationResult if matched, else None.
    """
    from career_os.models.skills import JobRequirement

    req = db.query(JobRequirement).filter(JobRequirement.id == job_requirement_id).first()
    if not req:
        logger.warning("enrich_job_requirement: job_requirement %d not found", job_requirement_id)
        return None

    result = normalize_skill(db, req.skill_name)
    if result:
        req.esco_uri = result.esco_uri
        db.commit()
        logger.debug(
            "Enriched job_requirement '%s' → %s (method=%s)",
            req.skill_name,
            result.esco_uri,
            result.match_method,
        )
    else:
        logger.debug("No ESCO match for job_requirement '%s'", req.skill_name)

    return result


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------


def enrich_all_profile_skills(db: Session, profile_id: int) -> dict[str, int]:
    """Normalize all un-enriched skills for a profile.

    Args:
        db: SQLAlchemy session.
        profile_id: Profile whose skills to enrich.

    Returns:
        Dict with counts: {"enriched": N, "no_match": M, "already_set": K}
    """
    from career_os.models.skills import Skill

    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    counts: dict[str, int] = {"enriched": 0, "no_match": 0, "already_set": 0}

    for skill in skills:
        if skill.esco_uri:
            counts["already_set"] += 1
            continue
        result = enrich_profile_skill(db, skill.id)
        if result:
            counts["enriched"] += 1
        else:
            counts["no_match"] += 1

    logger.info("enrich_all_profile_skills(profile=%d): %s", profile_id, counts)
    return counts
