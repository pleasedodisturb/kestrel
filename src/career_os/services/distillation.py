"""Distillation-label logging — record scoring training tuples (G-1338, finding M).

The audit's cheapest, highest-urgency item: we already generate thousands of
labeled LLM scores daily, so we should **start logging them now** as a distillation
dataset for a future small local feature model ("every unlogged day is training
data lost"). This module records, per scored job, the tuple

    (structured signals, LLM score, user correction)

into the ``distillation_samples`` table. It makes **no LLM calls** — it only
records what already happened during scoring.

Two invariants the scoring path relies on:

* **Off by default.** Gated on ``settings.distillation_logging_enabled``. When the
  flag is off, :func:`log_distillation_sample` is a pure no-op (returns ``None``).
* **Never breaks scoring.** Every write is wrapped defensively: any exception is
  logged and swallowed, and the session is rolled back so the caller's already
  committed score is untouched.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from career_os.config import settings
from career_os.models.scoring import DistillationSample
from career_os.schemas.ai import ScoreResult, role_fit_gate_failed
from career_os.schemas.scoring import classify_quadrant

logger = logging.getLogger(__name__)


def build_distillation_signals(
    score_result: ScoreResult,
    profile_data: dict | None,
    *,
    extra: dict | None = None,
) -> dict:
    """Assemble the JSON feature vector recorded alongside the LLM label.

    Pure and deterministic (given ``extra``): captures the structured signals the
    scorer produced or consumed — dimensional sub-scores, the role-fit gate
    verdict + disqualifiers, readiness/career-alignment, effort, the weights
    snapshot, and job family. ``extra`` merges in caller-supplied signals (e.g.
    the ESCO skills-overlap / title-occupation features from finding L, or a
    red-flag count). No PII beyond what already lives in ``profile_data`` is
    recorded — only the ``job_family`` string and weights are pulled from it.
    """
    profile_data = profile_data or {}

    dims = None
    if score_result.dimensional_scores is not None:
        dims = score_result.dimensional_scores.model_dump()

    role_match = None
    if score_result.role_match is not None:
        role_match = {
            "is_same_role_family": score_result.role_match.is_same_role_family,
            "evidence": score_result.role_match.evidence,
        }

    signals: dict = {
        "dimensional_scores": dims,
        "role_match": role_match,
        "role_fit_gate_failed": role_fit_gate_failed(score_result),
        "disqualifiers": list(score_result.disqualifiers),
        "readiness_score": score_result.readiness_score,
        "career_alignment": score_result.career_alignment,
        "effort_flag": score_result.effort_flag,
        "ats_keyword_count": len(score_result.ats_keywords),
        "job_family": profile_data.get("job_family"),
        "weights": profile_data.get("weights"),
    }
    if extra:
        signals.update(extra)
    return signals


def log_distillation_sample(
    db: Session,
    *,
    profile_id: int,
    score_result: ScoreResult,
    profile_data: dict | None,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    rubric_version: str | None = None,
    extra_signals: dict | None = None,
) -> DistillationSample | None:
    """Persist one training tuple. No-op unless the flag is on. Never raises.

    Called opportunistically from the scoring path *after* the live score has
    been committed. Uses the caller's session but is fully defensive: on any
    failure it rolls back the (uncommitted) sample and returns ``None`` — the
    already-committed :class:`ScoredJob` is never affected.
    """
    if not settings.distillation_logging_enabled:
        return None

    try:
        signals = build_distillation_signals(score_result, profile_data, extra=extra_signals)
        quadrant = classify_quadrant(score_result.fit_score, score_result.desire_score)
        sample = DistillationSample(
            profile_id=profile_id,
            scored_job_id=scored_job_id,
            discovered_job_id=discovered_job_id,
            fit_score=score_result.fit_score,
            desire_score=score_result.desire_score,
            quadrant=quadrant,
            signals=json.dumps(signals),
            rubric_version=rubric_version,
        )
        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample
    except Exception:
        logger.warning(
            "Distillation logging failed for scored_job=%s (swallowed — scoring unaffected)",
            scored_job_id,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            logger.debug("Distillation rollback also failed", exc_info=True)
        return None


def record_distillation_feedback(
    db: Session,
    *,
    scored_job_id: int,
    direction: str,
    user_score: float | None = None,
) -> int:
    """Backfill a user correction onto this scored job's distillation sample(s).

    Called opportunistically after a user submits (explicit or implicit)
    feedback, so the training tuple gains its label correction. No-op unless the
    flag is on. Returns the number of samples updated (0 on no-op or failure).
    Never raises.
    """
    if not settings.distillation_logging_enabled:
        return 0

    try:
        samples = (
            db.query(DistillationSample)
            .filter(DistillationSample.scored_job_id == scored_job_id)
            .all()
        )
        if not samples:
            return 0
        for sample in samples:
            sample.feedback_direction = direction
            sample.feedback_user_score = user_score
        db.commit()
        return len(samples)
    except Exception:
        logger.warning(
            "Distillation feedback backfill failed for scored_job=%s (swallowed)",
            scored_job_id,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            logger.debug("Distillation feedback rollback also failed", exc_info=True)
        return 0


def get_distillation_samples(
    db: Session, profile_id: int, *, limit: int = 1000
) -> list[DistillationSample]:
    """Return recorded distillation samples for a profile, newest first.

    A read helper for future distillation training runs / inspection. Not used
    by the live product.
    """
    return (
        db.query(DistillationSample)
        .filter(DistillationSample.profile_id == profile_id)
        .order_by(DistillationSample.created_at.desc())
        .limit(limit)
        .all()
    )
