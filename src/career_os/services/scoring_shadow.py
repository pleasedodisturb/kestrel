"""Scoring shadow-mode — log a candidate variant beside the live scorer.

Scoring Engine v2 (G-1336, finding I). When ``SCORING_SHADOW_VARIANT`` is set,
:func:`maybe_record_shadow_score` runs a *second*, candidate scoring pass on
each real production job and writes it to the ``shadow_scores`` table. The
shadow result is **never** surfaced to the user — it exists only so a candidate
rubric/model can be measured against the live scorer on production traffic
before promotion. This makes "measure on production, not a proxy" structurally
unskippable and mirrors the G-272 embedding-shadow pattern.

The comparator (:func:`compare_primary_vs_shadow`) scores prod-vs-shadow
agreement against a labeled reference (the golden set) using the shared
:mod:`career_os.services.scoring_eval` primitives.

Design notes:
* The hook is defensively wrapped — a shadow failure must never break the live
  scoring path (it is a diagnostic side-channel).
* By default the shadow reuses the active provider (a deterministic mock in
  tests, so the eval stays free). A caller may inject a variant provider to
  compare a different model/rubric; the variant label is recorded verbatim.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from career_os.ai.base import AIProvider
from career_os.ai.factory import get_ai_provider
from career_os.config import settings
from career_os.models.scoring import ShadowScore
from career_os.schemas.ai import ScoreResult
from career_os.schemas.scoring import classify_quadrant

logger = logging.getLogger(__name__)


async def record_shadow_score(
    db: Session,
    *,
    profile_id: int,
    variant: str,
    prompt: str,
    profile_data: dict,
    primary_fit_score: float | None,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    provider: AIProvider | None = None,
) -> ShadowScore | None:
    """Score a job with a candidate variant and persist it to ``shadow_scores``.

    Returns the persisted :class:`ShadowScore`, or ``None`` if the variant
    provider did not return a usable structured result. Raises nothing that the
    live path should care about — the caller wraps this defensively.
    """
    prov = provider if provider is not None else get_ai_provider()
    response = await prov.score(job_description=prompt, profile_data=profile_data)

    if not (response.structured and isinstance(response.structured, ScoreResult)):
        logger.warning("Shadow variant %s returned no structured score — skipping log", variant)
        return None

    candidate: ScoreResult = response.structured
    dims_json = (
        json.dumps(candidate.dimensional_scores.model_dump())
        if candidate.dimensional_scores is not None
        else None
    )
    quadrant = classify_quadrant(candidate.fit_score, candidate.desire_score)

    shadow = ShadowScore(
        profile_id=profile_id,
        scored_job_id=scored_job_id,
        discovered_job_id=discovered_job_id,
        variant=variant,
        fit_score=candidate.fit_score,
        desire_score=candidate.desire_score,
        quadrant=quadrant,
        primary_fit_score=primary_fit_score,
        dimensional_scores=dims_json,
        reasoning=candidate.reasoning,
    )
    db.add(shadow)
    db.commit()
    db.refresh(shadow)
    logger.info(
        "Shadow score logged (variant=%s): shadow=%.2f vs primary=%s",
        variant,
        candidate.fit_score,
        f"{primary_fit_score:.2f}" if primary_fit_score is not None else "n/a",
    )
    return shadow


async def maybe_record_shadow_score(
    db: Session,
    *,
    profile_id: int,
    prompt: str,
    profile_data: dict,
    primary_fit_score: float,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    provider: AIProvider | None = None,
) -> ShadowScore | None:
    """Log a shadow score iff ``SCORING_SHADOW_VARIANT`` is configured.

    Fully defensive: any failure is logged and swallowed so shadow-mode can
    never break live scoring. No-op (returns ``None``) when the setting is empty.
    """
    variant = settings.scoring_shadow_variant.strip()
    if not variant:
        return None
    try:
        return await record_shadow_score(
            db,
            profile_id=profile_id,
            variant=variant,
            prompt=prompt,
            profile_data=profile_data,
            primary_fit_score=primary_fit_score,
            scored_job_id=scored_job_id,
            discovered_job_id=discovered_job_id,
            provider=provider,
        )
    except Exception:
        db.rollback()
        logger.warning(
            "Shadow scoring failed (variant=%s) — live score unaffected", variant, exc_info=True
        )
        return None


def compare_primary_vs_shadow(
    primary_fit_scores: list[float],
    shadow_fit_scores: list[float],
    true_tiers: list[str],
) -> dict:
    """Compare live-vs-shadow scores against a labeled reference.

    Given aligned primary/shadow fit scores for the same jobs and the reference
    ``true_tiers`` (the golden-set labels), returns each variant's weighted κ
    (tier agreement) and NDCG@5 (ranking) plus the deltas, so a candidate can be
    judged *before* promotion.
    """
    from career_os.services.scoring_eval import (
        kappa_from_tiers,
        ndcg_at_k,
        tier_from_fit_score,
        tier_index,
    )

    if not (len(primary_fit_scores) == len(shadow_fit_scores) == len(true_tiers)):
        raise ValueError("primary, shadow, and label lists must be aligned and equal length")

    relevances = [float(tier_index(t)) for t in true_tiers]
    primary_tiers = [tier_from_fit_score(s) for s in primary_fit_scores]
    shadow_tiers = [tier_from_fit_score(s) for s in shadow_fit_scores]

    primary_kappa = kappa_from_tiers(true_tiers, primary_tiers)
    shadow_kappa = kappa_from_tiers(true_tiers, shadow_tiers)
    primary_ndcg = ndcg_at_k(relevances, primary_fit_scores, k=5)
    shadow_ndcg = ndcg_at_k(relevances, shadow_fit_scores, k=5)

    return {
        "n": len(true_tiers),
        "primary": {"kappa": primary_kappa, "ndcg@5": primary_ndcg},
        "shadow": {"kappa": shadow_kappa, "ndcg@5": shadow_ndcg},
        "delta": {
            "kappa": shadow_kappa - primary_kappa,
            "ndcg@5": shadow_ndcg - primary_ndcg,
        },
    }
