"""Scoring shadow-mode — log a candidate variant beside the live scorer.

Scoring Engine v2 (G-1336, finding I). When ``SCORING_SHADOW_VARIANT`` is set,
`score_job` *schedules* a second, candidate scoring pass on the same production
job and writes it to the ``shadow_scores`` table. The shadow result is **never**
surfaced to the user — it exists only so a candidate model/rubric can be measured
against the live scorer on production traffic before promotion. Mirrors the G-272
embedding-shadow pattern ("measure on production, not a proxy").

Two properties the review demanded and this module guarantees:

* **A real, distinct variant.** ``SCORING_SHADOW_VARIANT`` selects an actual
  provider (``"mistral"``) or provider+model (``"mistral:mistral-large-latest"``)
  via the AI factory. If it resolves to the *same* provider+model as the live
  scorer (a self-comparison) or cannot be built, it **no-ops cleanly** — it never
  compares the live model to itself.
* **Zero added live latency.** The shadow runs **fire-and-forget** on its own
  asyncio task with its own DB session, so enabling it never slows the live
  score. It DOES cost an extra (background) LLM call per sampled job — bound the
  spend with ``SCORING_SHADOW_SAMPLE`` (fraction 0–1). Off by default.

Every entry point is fully defensive: a shadow failure is logged and swallowed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random

from sqlalchemy.orm import Session

from career_os.ai.base import AIProvider
from career_os.ai.factory import get_ai_provider
from career_os.config import settings
from career_os.database import SessionLocal
from career_os.models.scoring import ShadowScore
from career_os.schemas.ai import ScoreResult, apply_role_fit_gate
from career_os.schemas.scoring import classify_quadrant

logger = logging.getLogger(__name__)


def build_shadow_provider(
    variant: str,
    *,
    live_provider_name: str | None = None,
) -> AIProvider | None:
    """Resolve ``SCORING_SHADOW_VARIANT`` to a REAL, distinct provider.

    ``variant`` is ``"<provider>"`` or ``"<provider>:<model>"`` (e.g.
    ``"mistral"``, ``"anthropic:claude-opus-4"``). Returns the built provider, or
    ``None`` when the variant is empty, names an unknown provider, fails to build
    (e.g. missing API key), or would merely compare the live scorer to itself
    (same provider name + no model override). ``None`` means "no shadow" — the
    caller no-ops.
    """
    variant = (variant or "").strip()
    if not variant:
        return None

    name, _, model = variant.partition(":")
    name = name.strip().lower()
    model = model.strip() or None

    # Self-comparison guard: same provider and no model override → nothing to learn.
    if live_provider_name and name == live_provider_name.strip().lower() and model is None:
        logger.info(
            "Shadow variant %r matches the live provider with no model override — skipping "
            "(it would compare the model to itself)",
            variant,
        )
        return None

    try:
        provider = get_ai_provider(name)
    except Exception:
        logger.warning("Shadow variant %r could not be resolved to a provider — skipping", variant)
        return None

    # Providers store the chat model as the private ``_model`` attribute (a
    # shared convention across all provider classes); fall back to a public
    # ``model`` for any that expose one.
    if model is not None:
        if hasattr(provider, "_model"):
            provider._model = model
        elif hasattr(provider, "model"):
            provider.model = model  # type: ignore[attr-defined]

    return provider


async def record_shadow_score(
    db: Session,
    *,
    profile_id: int,
    variant: str,
    prompt: str,
    profile_data: dict,
    primary_fit_score: float | None,
    provider: AIProvider,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
) -> ShadowScore | None:
    """Score a job with a candidate ``provider`` and persist it to ``shadow_scores``.

    Returns the persisted :class:`ShadowScore`, or ``None`` if the variant
    provider did not return a usable structured result.
    """
    response = await provider.score(job_description=prompt, profile_data=profile_data)

    if not (response.structured and isinstance(response.structured, ScoreResult)):
        logger.warning("Shadow variant %s returned no structured score — skipping log", variant)
        return None

    # Apply the SAME role-fit hard gate (G-1335) the live scorer applies to its
    # primary fit_score, BEFORE persisting/comparing. ``primary_fit_score`` here is
    # already post-gate (it comes from ``score_job`` after the gate), so gating the
    # candidate too keeps the comparison apples-to-apples: for a role-mismatched job
    # (live capped ≤3) the candidate is capped ≤3 as well, instead of leaving it at
    # an un-gated 8 and making a good candidate model look worse on exactly the jobs
    # the gate exists to fix (κ/NDCG in ``compare_primary_vs_shadow``).
    candidate: ScoreResult = apply_role_fit_gate(response.structured)
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


async def run_shadow_score(
    *,
    profile_id: int,
    variant: str,
    prompt: str,
    profile_data: dict,
    primary_fit_score: float | None,
    provider: AIProvider,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    session_factory=SessionLocal,
) -> ShadowScore | None:
    """Background body: score + log a shadow on a fresh, independent DB session.

    Runs off the live request path (its own session), so it never touches the
    caller's transaction. Fully defensive — any failure is logged and swallowed.
    """
    db = session_factory()
    try:
        return await record_shadow_score(
            db,
            profile_id=profile_id,
            variant=variant,
            prompt=prompt,
            profile_data=profile_data,
            primary_fit_score=primary_fit_score,
            provider=provider,
            scored_job_id=scored_job_id,
            discovered_job_id=discovered_job_id,
        )
    except Exception:
        with contextlib.suppress(Exception):
            db.rollback()
        logger.warning("Background shadow scoring failed (variant=%s)", variant, exc_info=True)
        return None
    finally:
        db.close()


def schedule_shadow_score(
    *,
    profile_id: int,
    prompt: str,
    profile_data: dict,
    primary_fit_score: float,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    live_provider_name: str | None = None,
    session_factory=SessionLocal,
) -> asyncio.Task | None:
    """Fire-and-forget a shadow score iff configured. Adds NO latency to the caller.

    Gates on ``SCORING_SHADOW_VARIANT`` (must resolve to a distinct provider) and
    ``SCORING_SHADOW_SAMPLE`` (fraction of jobs to shadow), then spawns an
    asyncio task and returns immediately. Returns the scheduled task, or ``None``
    when shadow-mode is off, this job is not sampled, the variant can't resolve,
    or there is no running event loop.
    """
    variant = settings.scoring_shadow_variant.strip()
    if not variant:
        return None

    sample = settings.scoring_shadow_sample
    if sample < 1.0 and random.random() >= max(sample, 0.0):
        return None

    provider = build_shadow_provider(variant, live_provider_name=live_provider_name)
    if provider is None:
        return None

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("No running event loop — skipping shadow score for variant %s", variant)
        return None

    return loop.create_task(
        run_shadow_score(
            profile_id=profile_id,
            variant=variant,
            prompt=prompt,
            profile_data=profile_data,
            primary_fit_score=primary_fit_score,
            provider=provider,
            scored_job_id=scored_job_id,
            discovered_job_id=discovered_job_id,
            session_factory=session_factory,
        )
    )


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
