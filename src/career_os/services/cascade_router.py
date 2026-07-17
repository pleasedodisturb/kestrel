"""Confidence-routed cascade (G-1338, finding K — Phase 4b, part 2).

A conservative, SHADOW-FIRST routing layer that decides which jobs even need the
expensive LLM scoring call, using three cheap, non-LLM signals. It **reframes the
blocked G-272 embedding pre-filter**: embeddings were never meant to be a gate on
their own (overlapping distributions mis-reject good jobs), so instead of a single
cosine threshold this router requires *unanimous* agreement across three
orthogonal signals before it will ever skip a job.

The rule (locked design):

* **Auto-REJECT only.** A job is routed to :attr:`CascadeAction.SKIP_REJECT` — the
  LLM is skipped — ONLY when ALL THREE signals **have data** and all three
  independently vote "clearly not a fit":

    1. **embedding similarity** below a conservative reject threshold (reuses the
       G-272 profile↔job cosine similarity),
    2. **lexical must-have overlap** at/below threshold (zero) — the JD's parsed
       must-have terms share no fuzzy/lexical overlap with the candidate, or (when
       no requirements are parsed) none of the candidate's skills appear in the JD
       text,
    3. **ESCO skills-overlap** at/below threshold (zero) — from the 4a
       :mod:`~career_os.services.esco_features` feature.

  One or two signals is NEVER enough. Crucially, a signal with **no data**
  (no embedding, no parsed requirements + empty JD text, no ESCO-grounded skills)
  ABSTAINS — and an abstaining signal blocks a skip. So a skip requires positive
  non-fit evidence from all three at once. This is the whole G-272 lesson.

* **NEVER auto-ACCEPT.** There is no "clear-strong skip". Everything that is not a
  unanimous reject is routed to :attr:`CascadeAction.SCORE` and hits the LLM
  exactly as it does today.

* **SHADOW-FIRST.** In shadow mode the LLM still scores everything; the routing
  decision is logged beside the eventual LLM score so the **false-skip rate**
  (jobs the router would have rejected that the LLM actually scored as a fit) can
  be measured BEFORE live skipping is ever trusted.

* **Live is a separate flag, off by default.** A live ``SKIP_REJECT`` bypasses the
  LLM and is persisted as a scored-but-rejected job (never dropped).

Everything here is **defensive**: a routing or logging failure is logged and
swallowed, and on any uncertainty the router falls back to ``SCORE`` — it never
skips a job on an error. The router itself makes **zero LLM calls**.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from career_os.config import settings
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application
from career_os.models.scoring import CascadeDecision as CascadeDecisionRow
from career_os.models.scoring import ScoredJob
from career_os.models.skills import JobRequirement, Skill
from career_os.schemas.scoring import classify_quadrant
from career_os.services.esco_features import compute_job_skills_overlap

logger = logging.getLogger(__name__)

# rapidfuzz WRatio floor (0–100) for a lexical token match. Matches the
# skill_normalizer's fuzzy threshold so "the same skill, spelled differently"
# still counts as overlap and does NOT push a job toward a wrongful skip.
_LEXICAL_FUZZ_THRESHOLD = 85.0

# Fit threshold (0–10) the false-skip comparator uses to decide the LLM "would
# have kept" a job. 5.0 is the quadrant boundary (a job the LLM scored >= 5.0 is
# at least not a reject) — a skip of such a job is a false skip.
DEFAULT_FIT_THRESHOLD = 5.0


class CascadeAction(StrEnum):
    """The routing decision for a single job."""

    SKIP_REJECT = "skip_reject"
    SCORE = "score"


@dataclass
class SignalVote:
    """One routing signal's verdict for a job.

    ``available`` is False when the signal had no data to judge on. An unavailable
    signal can never vote to reject (``votes_reject`` is forced False), so
    abstention structurally blocks a skip.
    """

    name: str
    available: bool
    value: float | None
    votes_reject: bool
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Hard invariant: an unavailable signal never votes to reject.
        if not self.available:
            self.votes_reject = False


@dataclass
class CascadeDecision:
    """The full routing decision plus the three signal votes."""

    action: CascadeAction
    embedding: SignalVote
    lexical: SignalVote
    esco: SignalVote

    @property
    def would_skip(self) -> bool:
        """True iff the router would skip the LLM for this job."""
        return self.action == CascadeAction.SKIP_REJECT

    @property
    def signals(self) -> tuple[SignalVote, SignalVote, SignalVote]:
        """The three signal votes in a stable order."""
        return (self.embedding, self.lexical, self.esco)

    def reject_reasons(self) -> list[str]:
        """Human-readable per-signal reasons (only meaningful on a skip)."""
        reasons: list[str] = []
        for s in self.signals:
            if s.available and s.votes_reject:
                val = f"{s.value:.3f}" if s.value is not None else "n/a"
                reasons.append(f"{s.name}={val}")
        return reasons


# ---------------------------------------------------------------------------
# The three signals (each pure / DB-read-only, individually defensive)
# ---------------------------------------------------------------------------


def embedding_signal(
    similarity: float | None,
    *,
    reject_threshold: float | None = None,
) -> SignalVote:
    """Vote from the G-272 profile↔job embedding cosine similarity.

    ``similarity`` is the already-computed cosine similarity (0–1), or ``None``
    when the job had no embedding (the signal then abstains). Votes to reject only
    when the similarity is strictly BELOW the conservative reject threshold.
    """
    threshold = (
        settings.cascade_embedding_reject_threshold
        if reject_threshold is None
        else reject_threshold
    )
    available = similarity is not None
    votes_reject = available and similarity < threshold  # type: ignore[operator]
    return SignalVote(
        name="embedding",
        available=available,
        value=similarity,
        votes_reject=votes_reject,
        detail={"threshold": threshold},
    )


def _normalize_term(term: str) -> str:
    """Lowercase + strip a skill/term for lexical comparison."""
    return term.strip().lower()


def _term_matches_any(term: str, candidates: list[str]) -> bool:
    """True if ``term`` fuzzily matches any candidate term (set overlap)."""
    t = _normalize_term(term)
    if not t:
        return False
    for cand in candidates:
        c = _normalize_term(cand)
        if not c:
            continue
        if t in c or c in t:
            return True
        if fuzz.WRatio(t, c) >= _LEXICAL_FUZZ_THRESHOLD:
            return True
    return False


def _term_in_text(term: str, text: str) -> bool:
    """True if ``term`` appears (substring, case-insensitive) in free JD text.

    Substring only — free-text fuzzy matching is too noisy for short skill tokens
    and could manufacture overlap that isn't there. Being strict here makes the
    lexical signal MORE likely to abstain-or-reject honestly, never to fabricate a
    match that wrongly rescues a job from a (correct) skip.
    """
    t = _normalize_term(term)
    if len(t) < 3:
        return False
    return t in text.lower()


def compute_lexical_overlap(
    musthave_terms: list[str],
    candidate_terms: list[str],
) -> dict:
    """Pure fuzzy overlap of the JD's must-have terms against candidate terms.

    Returns ``{overlap_score, matched, total, matched_terms, missing_terms}``.
    ``overlap_score`` is ``matched / total`` (0.0 when there are no must-have
    terms — the caller must check ``total`` to distinguish "no data" from "zero
    overlap", exactly like the ESCO feature).
    """
    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in musthave_terms:
        norm = _normalize_term(term)
        if norm and norm not in seen:
            seen.add(norm)
            unique_terms.append(term)

    matched_terms: list[str] = []
    missing_terms: list[str] = []
    for term in unique_terms:
        if _term_matches_any(term, candidate_terms):
            matched_terms.append(term)
        else:
            missing_terms.append(term)

    total = len(unique_terms)
    overlap_score = round(len(matched_terms) / total, 4) if total else 0.0
    return {
        "overlap_score": overlap_score,
        "matched": len(matched_terms),
        "total": total,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
    }


def _candidate_skill_names(db: Session, profile_id: int) -> list[str]:
    """Candidate profile skill names (the lexical 'have' side)."""
    rows = db.query(Skill.name).filter(Skill.profile_id == profile_id).all()
    return [name for (name,) in rows if name]


def _job_musthave_terms(db: Session, application_id: int, profile_id: int) -> list[str]:
    """The JD's must-have terms: critical parsed requirements, else all of them."""
    rows = (
        db.query(JobRequirement.skill_name, JobRequirement.severity)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )
    critical = [name for (name, sev) in rows if name and (sev or "").lower() == "critical"]
    if critical:
        return critical
    return [name for (name, _sev) in rows if name]


def lexical_signal(
    db: Session,
    *,
    profile_id: int,
    application_id: int | None,
    jd_text: str | None,
    reject_threshold: float | None = None,
) -> SignalVote:
    """Vote from lexical must-have overlap between the JD and the candidate.

    Primary path (when the job has parsed requirements): fuzzy-match the JD's
    must-have terms against the candidate's skill names. Fallback (no parsed
    requirements): count how many of the candidate's skills appear in the raw JD
    text. Abstains when neither has data. Votes to reject only when overlap is
    at/below the (zero) threshold — genuinely no lexical common ground.
    """
    threshold = (
        settings.cascade_lexical_reject_threshold if reject_threshold is None else reject_threshold
    )
    candidate = _candidate_skill_names(db, profile_id)

    musthaves = (
        _job_musthave_terms(db, application_id, profile_id) if application_id is not None else []
    )

    source: str
    if musthaves and candidate:
        result = compute_lexical_overlap(musthaves, candidate)
        source = "requirements"
    elif jd_text and candidate:
        # Fallback: are ANY of the candidate's skills lexically present in the JD?
        matched = [s for s in candidate if _term_in_text(s, jd_text)]
        total = len(candidate)
        result = {
            "overlap_score": round(len(matched) / total, 4) if total else 0.0,
            "matched": len(matched),
            "total": total,
            "matched_terms": matched,
            "missing_terms": [s for s in candidate if s not in matched],
        }
        source = "jd_text"
    else:
        # No must-have terms AND no usable JD-text/candidate pairing → abstain.
        return SignalVote(
            name="lexical",
            available=False,
            value=None,
            votes_reject=False,
            detail={"source": "none"},
        )

    available = result["total"] > 0
    overlap = result["overlap_score"]
    votes_reject = available and overlap <= threshold
    return SignalVote(
        name="lexical",
        available=available,
        value=overlap if available else None,
        votes_reject=votes_reject,
        detail={
            "source": source,
            "matched": result["matched"],
            "total": result["total"],
            "threshold": threshold,
        },
    )


def esco_signal(
    db: Session,
    *,
    profile_id: int,
    application_id: int | None,
    reject_threshold: float | None = None,
) -> SignalVote:
    """Vote from the 4a ESCO severity-weighted skills-overlap feature.

    Abstains when the job has no ESCO-grounded requirements (``total == 0`` — the
    esco_features docstring warns ``overlap_score == 0.0`` conflates "no data" and
    "zero coverage", so we key availability on ``total``). Votes to reject only
    when there IS data and the weighted coverage is at/below the (zero) threshold.
    """
    threshold = (
        settings.cascade_esco_reject_threshold if reject_threshold is None else reject_threshold
    )
    if application_id is None:
        return SignalVote(
            name="esco", available=False, value=None, votes_reject=False, detail={"total": 0}
        )
    overlap = compute_job_skills_overlap(db, application_id=application_id, profile_id=profile_id)
    total = overlap.get("total", 0)
    available = total > 0
    score = overlap.get("overlap_score", 0.0)
    votes_reject = available and score <= threshold
    return SignalVote(
        name="esco",
        available=available,
        value=score if available else None,
        votes_reject=votes_reject,
        detail={
            "matched": overlap.get("matched", 0),
            "total": total,
            "threshold": threshold,
        },
    )


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------


def route_job(
    db: Session,
    *,
    profile_id: int,
    application_id: int | None = None,
    discovered_job_id: int | None = None,
    embedding_similarity: float | None = None,
    jd_text: str | None = None,
    embedding_reject_threshold: float | None = None,
    lexical_reject_threshold: float | None = None,
    esco_reject_threshold: float | None = None,
) -> CascadeDecision:
    """Compute the routing decision for one job from the three signals.

    Returns :attr:`CascadeAction.SKIP_REJECT` **iff all three signals have data
    AND all three vote to reject** (unanimous, conservative). Any abstaining or
    non-reject signal yields :attr:`CascadeAction.SCORE`. Makes zero LLM calls.
    """
    emb = embedding_signal(embedding_similarity, reject_threshold=embedding_reject_threshold)
    lex = lexical_signal(
        db,
        profile_id=profile_id,
        application_id=application_id,
        jd_text=jd_text,
        reject_threshold=lexical_reject_threshold,
    )
    esc = esco_signal(
        db,
        profile_id=profile_id,
        application_id=application_id,
        reject_threshold=esco_reject_threshold,
    )

    unanimous_reject = all(s.available and s.votes_reject for s in (emb, lex, esc))
    action = CascadeAction.SKIP_REJECT if unanimous_reject else CascadeAction.SCORE
    return CascadeDecision(action=action, embedding=emb, lexical=lex, esco=esc)


def safe_route_job(
    db: Session,
    *,
    profile_id: int,
    application_id: int | None = None,
    discovered_job_id: int | None = None,
    embedding_similarity: float | None = None,
    jd_text: str | None = None,
) -> CascadeDecision | None:
    """Defensive wrapper around :func:`route_job` for the live scoring path.

    Returns ``None`` on ANY failure (rolling back a poisoned read transaction) so
    the caller falls through to normal LLM scoring — the router never skips a job
    because of its own error.
    """
    try:
        return route_job(
            db,
            profile_id=profile_id,
            application_id=application_id,
            discovered_job_id=discovered_job_id,
            embedding_similarity=embedding_similarity,
            jd_text=jd_text,
        )
    except Exception:
        logger.warning(
            "Cascade routing failed for profile=%s discovered_job=%s application=%s "
            "(swallowed — job will be scored normally)",
            profile_id,
            discovered_job_id,
            application_id,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            logger.debug("Cascade routing rollback also failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Persistence — nothing silently dropped
# ---------------------------------------------------------------------------


def persist_cascade_reject(
    db: Session,
    *,
    profile_id: int,
    decision: CascadeDecision,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
    reject_fit_score: float | None = None,
) -> ScoredJob:
    """Persist a LIVE cascade skip as a scored-but-rejected job.

    A skipped job is NEVER dropped — it is written to ``scored_jobs`` with a
    deterministic low ``fit_score`` and a reasoning string naming the cascade, and
    its cached ``fit_score`` is propagated to the linked DiscoveredJob/Application
    (mirroring ``_update_linked_scores``) so it renders as a normal (low) score in
    the UI. Commits and returns the persisted row.
    """
    score = settings.cascade_reject_fit_score if reject_fit_score is None else reject_fit_score
    reasons = ", ".join(decision.reject_reasons()) or "all three signals below threshold"
    scored = ScoredJob(
        profile_id=profile_id,
        discovered_job_id=discovered_job_id,
        application_id=application_id,
        fit_score=score,
        readiness_score=0.0,
        career_alignment=0.0,
        reasoning=(
            "Auto-rejected by the confidence-routed cascade without an LLM call: all "
            f"three cheap signals agreed this is not a fit ({reasons}). "
            "Enable full scoring to override."
        ),
        effort_flag="low",
        prep_level="unknown",
        is_stale=False,
    )
    db.add(scored)

    # Propagate to linked records (inlined to avoid a scoring<->cascade import cycle).
    if discovered_job_id is not None:
        dj = db.query(DiscoveredJob).filter(DiscoveredJob.id == discovered_job_id).first()
        if dj:
            dj.fit_score = score
    if application_id is not None:
        app_record = db.query(Application).filter(Application.id == application_id).first()
        if app_record:
            app_record.fit_score = score

    db.commit()
    db.refresh(scored)
    return scored


def record_cascade_decision(
    db: Session,
    *,
    profile_id: int,
    decision: CascadeDecision,
    mode: str,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
    llm_fit_score: float | None = None,
    llm_desire_score: float | None = None,
    reject_fit_score: float | None = None,
) -> CascadeDecisionRow | None:
    """Log a routing decision to ``cascade_decisions``. Defensive; never raises.

    Records the action, the three signal votes, and the outcome. In shadow mode
    ``llm_fit_score`` is the eventual live score (so the false-skip comparator can
    run); in a live skip it is ``None`` (no LLM call) and ``reject_fit_score`` is
    the deterministic score persisted instead. Any failure is logged and swallowed
    and the session rolled back — logging never affects the committed score.
    """
    try:
        quadrant = (
            classify_quadrant(llm_fit_score, llm_desire_score)
            if llm_fit_score is not None
            else None
        )
        emb, lex, esc = decision.embedding, decision.lexical, decision.esco
        row = CascadeDecisionRow(
            profile_id=profile_id,
            scored_job_id=scored_job_id,
            discovered_job_id=discovered_job_id,
            application_id=application_id,
            mode=mode,
            action=decision.action.value,
            would_skip=decision.would_skip,
            embedding_similarity=emb.value,
            embedding_available=emb.available,
            embedding_votes_reject=emb.votes_reject,
            lexical_overlap=lex.value,
            lexical_available=lex.available,
            lexical_votes_reject=lex.votes_reject,
            esco_overlap=esc.value,
            esco_available=esc.available,
            esco_votes_reject=esc.votes_reject,
            llm_fit_score=llm_fit_score,
            llm_quadrant=quadrant,
            reject_fit_score=reject_fit_score,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        logger.warning(
            "Cascade decision logging failed for scored_job=%s (swallowed — scoring unaffected)",
            scored_job_id,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            logger.debug("Cascade decision logging rollback also failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# False-skip comparator — the gate for enabling live routing
# ---------------------------------------------------------------------------


def false_skip_rate(
    samples: list[tuple[bool, float | None]],
    *,
    fit_threshold: float = DEFAULT_FIT_THRESHOLD,
) -> dict:
    """Compute the false-skip rate over ``(would_skip, llm_fit_score)`` samples.

    Pure. A **false skip** is a job the router would have skipped
    (``would_skip=True``) that the LLM actually scored at/above ``fit_threshold``
    (i.e. a fit the router would have wrongly rejected). Samples whose
    ``llm_fit_score`` is ``None`` (no LLM score to compare — e.g. a live-skipped
    job) are excluded from the denominator.

    Returns::

        {
            "n": int,                    # samples with a comparable LLM score
            "would_skip": int,           # of those, how many the router would skip
            "false_skips": int,          # would-skip AND llm_fit_score >= threshold
            "false_skip_rate": float,    # false_skips / would_skip (0.0 if none)
            "skip_rate": float,          # would_skip / n (0.0 if n == 0)
            "fit_threshold": float,
        }

    ``false_skip_rate`` is the number the owner reads to decide whether the router
    is safe to run live: it is the fraction of the router's *rejections* that were
    genuine fits. It should be driven near zero before ``CASCADE_ROUTING_ENABLED``
    is turned on.
    """
    comparable = [(ws, fit) for (ws, fit) in samples if fit is not None]
    n = len(comparable)
    would_skip = sum(1 for (ws, _fit) in comparable if ws)
    false_skips = sum(1 for (ws, fit) in comparable if ws and fit >= fit_threshold)  # type: ignore[operator]
    return {
        "n": n,
        "would_skip": would_skip,
        "false_skips": false_skips,
        "false_skip_rate": round(false_skips / would_skip, 4) if would_skip else 0.0,
        "skip_rate": round(would_skip / n, 4) if n else 0.0,
        "fit_threshold": fit_threshold,
    }


def run_false_skip_report(
    db: Session,
    *,
    profile_id: int | None = None,
    fit_threshold: float = DEFAULT_FIT_THRESHOLD,
) -> dict:
    """Run :func:`false_skip_rate` over logged SHADOW cascade decisions.

    Reads shadow-mode ``cascade_decisions`` rows that carry an ``llm_fit_score``
    (the ones with a real LLM score to compare against) and returns the false-skip
    report. Optionally scoped to one ``profile_id``. Read-only.
    """
    query = db.query(CascadeDecisionRow.would_skip, CascadeDecisionRow.llm_fit_score).filter(
        CascadeDecisionRow.mode == "shadow",
        CascadeDecisionRow.llm_fit_score.isnot(None),
    )
    if profile_id is not None:
        query = query.filter(CascadeDecisionRow.profile_id == profile_id)
    samples = [(bool(ws), fit) for (ws, fit) in query.all()]
    report = false_skip_rate(samples, fit_threshold=fit_threshold)
    report["profile_id"] = profile_id
    return report
