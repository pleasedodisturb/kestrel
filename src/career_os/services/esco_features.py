"""ESCO quantitative scoring features (G-1338, finding L — part 1).

Upgrades the G-276 ESCO integration from *normalization* (mapping free-text
skills to canonical URIs) to a *quantitative signal* the scorer and the future
confidence-routed cascade (Phase 4b / finding K) can consume:

**Skills-overlap score** — severity-weighted coverage of the JD's required ESCO
skills that are present in the candidate profile. A missing *critical* skill
hurts more than a missing *bonus* one. Gives free, non-LLM explainability
("6/8 required skills matched").

This is a **pure, additive computation** — it does NOT change existing ESCO
normalization, the scoring prompt, or what is sent to the LLM. The number is
surfaced as a structured signal (into the distillation log, finding M) and is a
routing feature Phase 4b's cascade will gate on.

**Scoped out of this PR:** the "title→occupation axis" from finding L's second
half. It requires a real ESCO/ISCO or O*NET **occupations** taxonomy, which this
repo does not have (the `esco_skills` cache is a ~14K-row *skills/competence*
table, not occupations) — and the production caller only knows a job-family
*code* ("TPM"/"SWE"), not a JD title/role string to normalize. Shipping it here
would be an inert, always-0.0 signal. Tracked as a follow-up (needs an
occupations taxonomy first); Phase 4b's cascade can consume it once that lands.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from career_os.models.skills import JobRequirement, Skill

logger = logging.getLogger(__name__)

# Severity → weight for skills-overlap coverage. A missing critical skill costs
# 4× a missing bonus skill. Unknown severities fall back to the nice-to-have
# weight so an unlabeled requirement still counts.
SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 1.0,
    "nice-to-have": 0.5,
    "bonus": 0.25,
}
_DEFAULT_SEVERITY_WEIGHT = 0.5


def _severity_weight(severity: str | None) -> float:
    """Map a requirement severity to its coverage weight."""
    if not severity:
        return _DEFAULT_SEVERITY_WEIGHT
    return SEVERITY_WEIGHTS.get(severity.strip().lower(), _DEFAULT_SEVERITY_WEIGHT)


def compute_skills_overlap(
    required: list[tuple[str | None, str | None]],
    candidate_uris: set[str],
) -> dict:
    """Weighted coverage of required ESCO skills present in the candidate profile.

    Pure — no DB. ``required`` is a list of ``(esco_uri, severity)`` for the JD's
    required skills; ``candidate_uris`` is the set of ESCO URIs the candidate has.
    Requirements with no ``esco_uri`` (un-normalized) are ignored — coverage is
    only defined over ESCO-grounded requirements.

    Returns a dict::

        {
            "overlap_score": 0.0-1.0,   # weighted coverage (matched_w / total_w)
            "matched": int,             # count of matched required skills
            "total": int,               # count of ESCO-grounded required skills
            "matched_weight": float,
            "total_weight": float,
            "matched_uris": [...],
            "missing_uris": [...],
        }

    ``overlap_score`` is ``0.0`` when there are no ESCO-grounded requirements
    (nothing to cover), keeping the signal well-defined and JSON-safe. NOTE this
    means ``overlap_score == 0.0`` conflates two cases — *no ESCO data at all* and
    *matched nothing*; a consumer must inspect ``total`` to disambiguate
    (``total == 0`` → no data, ``total > 0`` → genuinely zero coverage).
    """
    matched_uris: list[str] = []
    missing_uris: list[str] = []
    matched_weight = 0.0
    total_weight = 0.0

    for esco_uri, severity in required:
        if not esco_uri:
            continue
        weight = _severity_weight(severity)
        total_weight += weight
        if esco_uri in candidate_uris:
            matched_uris.append(esco_uri)
            matched_weight += weight
        else:
            missing_uris.append(esco_uri)

    total = len(matched_uris) + len(missing_uris)
    overlap_score = round(matched_weight / total_weight, 4) if total_weight > 0 else 0.0

    return {
        "overlap_score": overlap_score,
        "matched": len(matched_uris),
        "total": total,
        "matched_weight": round(matched_weight, 4),
        "total_weight": round(total_weight, 4),
        "matched_uris": matched_uris,
        "missing_uris": missing_uris,
    }


def get_candidate_skill_uris(db: Session, profile_id: int) -> set[str]:
    """Return the set of ESCO URIs the candidate's profile skills map to."""
    rows = (
        db.query(Skill.esco_uri)
        .filter(Skill.profile_id == profile_id, Skill.esco_uri.isnot(None))
        .all()
    )
    return {uri for (uri,) in rows if uri}


def get_job_required_esco(
    db: Session, application_id: int, profile_id: int
) -> list[tuple[str | None, str | None]]:
    """Return ``(esco_uri, severity)`` for a job's parsed requirements."""
    rows = (
        db.query(JobRequirement.esco_uri, JobRequirement.severity)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )
    return [(uri, sev) for (uri, sev) in rows]


def compute_job_skills_overlap(db: Session, *, application_id: int, profile_id: int) -> dict:
    """DB wrapper: weighted ESCO skills-overlap for one application vs one profile."""
    required = get_job_required_esco(db, application_id, profile_id)
    candidate = get_candidate_skill_uris(db, profile_id)
    return compute_skills_overlap(required, candidate)


def compute_esco_features(
    db: Session,
    *,
    profile_id: int,
    application_id: int | None = None,
) -> dict | None:
    """Compute the ESCO skills-overlap feature as a structured-signals bundle.

    Convenience entry point for the distillation log (finding M) and Phase 4b's
    cascade router. Skills-overlap is only defined against a job's parsed
    ``JobRequirement`` rows, so this returns ``None`` when no ``application_id``
    is supplied (nothing to compute). Fully defensive: returns ``None`` and rolls
    the session back on any failure, so a caller can treat ESCO features as
    best-effort without inheriting a poisoned transaction.
    """
    if application_id is None:
        return None
    try:
        return {
            "skills_overlap": compute_job_skills_overlap(
                db, application_id=application_id, profile_id=profile_id
            )
        }
    except Exception:
        logger.warning(
            "compute_esco_features failed for profile=%s application=%s (swallowed)",
            profile_id,
            application_id,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            logger.debug("compute_esco_features rollback also failed", exc_info=True)
        return None
