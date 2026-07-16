"""ESCO quantitative scoring features (G-1338, finding L).

Upgrades the G-276 ESCO integration from *normalization* (mapping free-text
skills to canonical URIs) to *quantitative signals* the scorer and the future
confidence-routed cascade (Phase 4b / finding K) can consume:

1. **Skills-overlap score** — weighted coverage of the JD's required ESCO skills
   that are present in the candidate profile. Severity-weighted so a missing
   *critical* skill hurts more than a missing *bonus* one. Gives free, non-LLM
   explainability ("6/8 required skills matched").
2. **Title→occupation axis** — normalizes the JD title and the candidate's target
   role to ESCO/ISCO occupations *separately from content*, so a wrong-role
   dream-company job scores low on this axis even when its JD body overlaps the
   candidate's skills. Directly complements the G-1335 role-fit gate.

Everything here is a **pure, additive computation** — it does NOT change existing
ESCO normalization, the scoring prompt, or what is sent to the LLM. The numbers
are surfaced as structured signals (e.g. into the distillation log, finding M)
and are the routing features Phase 4b's cascade will gate on.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from career_os.models.esco import ESCOSkill
from career_os.models.skills import JobRequirement, Skill
from career_os.services.skill_normalizer import normalize_skill

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

# Title→occupation match scores.
_TITLE_EXACT_MATCH = 1.0  # same ESCO occupation/skill URI
_TITLE_ISCO_MATCH = 0.7  # same ISCO-08 group (adjacent occupation)
_TITLE_NO_MATCH = 0.0


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
    (nothing to cover), keeping the signal well-defined and JSON-safe.
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


def _esco_occupation_for_title(db: Session, title: str | None) -> dict | None:
    """Normalize a job/role title to an ESCO entry with its ISCO group.

    Returns ``{"esco_uri", "label", "isco_group"}`` or ``None`` when the title is
    empty or has no ESCO match. Reuses the existing (cached) ``normalize_skill``
    pipeline — this is the "compute separately from content" title axis.
    """
    if not title or not title.strip():
        return None
    match = normalize_skill(db, title.strip())
    if match is None:
        return None
    esco = db.query(ESCOSkill).filter(ESCOSkill.concept_uri == match.esco_uri).first()
    return {
        "esco_uri": match.esco_uri,
        "label": match.preferred_label or (esco.preferred_label if esco else None),
        "isco_group": esco.isco_group if esco else None,
    }


def title_occupation_axis(db: Session, jd_title: str | None, candidate_role: str | None) -> dict:
    """Occupation-level match between a JD title and the candidate's target role.

    Computed from the *titles only* (not JD content), so it is an independent
    axis from the skills-overlap and dimensional scores. Match scale:

    * ``1.0`` — same ESCO occupation URI
    * ``0.7`` — same ISCO-08 group (adjacent occupation)
    * ``0.0`` — different / unresolved

    Returns a dict with the resolved occupations, ISCO groups, the numeric
    ``match_score`` and the ``same_occupation`` / ``same_isco_group`` booleans.
    """
    jd = _esco_occupation_for_title(db, jd_title)
    cand = _esco_occupation_for_title(db, candidate_role)

    same_occupation = bool(jd and cand and jd["esco_uri"] == cand["esco_uri"])
    same_isco_group = bool(
        jd and cand and jd["isco_group"] is not None and jd["isco_group"] == cand["isco_group"]
    )

    if same_occupation:
        match_score = _TITLE_EXACT_MATCH
    elif same_isco_group:
        match_score = _TITLE_ISCO_MATCH
    else:
        match_score = _TITLE_NO_MATCH

    return {
        "match_score": match_score,
        "same_occupation": same_occupation,
        "same_isco_group": same_isco_group,
        "jd_occupation": jd,
        "candidate_occupation": cand,
    }


def compute_esco_features(
    db: Session,
    *,
    profile_id: int,
    application_id: int | None = None,
    jd_title: str | None = None,
    candidate_role: str | None = None,
) -> dict | None:
    """Compute both ESCO features as one structured-signals bundle.

    Convenience entry point for the distillation log (finding M) and Phase 4b's
    cascade router. Fully defensive: returns ``None`` on any failure so a caller
    can treat ESCO features as best-effort. Skills-overlap is only computed when
    an ``application_id`` (which owns the parsed JobRequirements) is supplied.
    """
    try:
        features: dict = {}
        if application_id is not None:
            features["skills_overlap"] = compute_job_skills_overlap(
                db, application_id=application_id, profile_id=profile_id
            )
        features["title_occupation"] = title_occupation_axis(db, jd_title, candidate_role)
        return features
    except Exception:
        logger.warning(
            "compute_esco_features failed for profile=%s application=%s (swallowed)",
            profile_id,
            application_id,
            exc_info=True,
        )
        return None
