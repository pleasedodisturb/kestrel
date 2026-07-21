"""Occupation matcher: job_family <-> occupation, JD-title normalizer (G-1351 Phase B).

The crux of Phase B: give the scorer a real title-vs-occupation signal instead
of the 4a "inert axis" (see ``esco_features.py``'s module docstring for the
history — the caller only has a job-family *code* like "TPM"/"SWE", not a
title, and the old skills cache had no occupation concepts at all).

Two resolvers feed a pure classifier:

* ``map_family_to_occupation`` — job_family -> occupation ref, via a
  hand-checked overlay (exact, fixture-verified ``concept_uri`` pins for the
  families that have a genuine ESCO match, casefolded for case-insensitive
  lookup — G-1351 review F5) plus a conservative fuzzy fallback on
  ``preferred_label`` only.
* ``normalize_title_to_occupation`` — free-text JD title -> occupation ref,
  via conservative rapidfuzz n-gram matching over ``preferred_label`` +
  ``alt_labels`` (minus a curated denylist of ESCO alt-labels that collide
  with the wrong occupation for our domain — G-1351 review F2).

``match_occupation`` combines both into a tier: ``same_occupation``,
``same_isco_group``, ``no_match``, or ``unknown``. CRITICAL: ``unknown``
always carries ``score=None`` — never the fake ``0.0`` that made the old axis
inert and indistinguishable from a real "no match" (``no_match``, which IS
``0.0``). ``match_occupation`` is also self-sufficient (G-1351 review F1): if
``esco_occupations`` is empty (a normal server deployment that never ran
``kestrel occupations load``), it lazily populates the table from the bundled
fixture once, rather than returning ``unknown`` forever.

Naive fuzzy matching over short titles is unsafe (verified failures during
planning: "Senior Backend Engineer" -> "nurse assistant" via a loose scorer
picking up the substring "sen"; "data engineer" -> "data scientist" at 100
via a loose WRatio-style scorer). This module uses ``token_sort_ratio`` with a
high cutoff, case/punctuation-insensitive comparison, a length-guard that
rejects a short/generic candidate matching an unrelated label, a unigram
restriction that disallows single-word candidates on titles longer than 2
words (G-1351 review F4 — kills the "Representative" hijack of "Sales
Development Representative" while still resolving "Chef"), and a curated
alt-label denylist (G-1351 review F2) — an unresolved title returns ``None``
(-> ``unknown``) rather than a wrong tier.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process, utils
from sqlalchemy.orm import Session

from career_os.models.esco import ESCOOccupation
from career_os.services.occupation_taxonomy import count_occupations, populate_occupations

logger = logging.getLogger(__name__)

# T-n1d-01 mitigation (G-1351 review F3): cap n-gram generation to the first N
# words of a title. Real JD titles are a handful of words (well under 10); the
# original 500-word bound copied from cli/extract.py's full-text DoS guard was
# the wrong analog for a short title field and still allowed a ~20s/call CPU
# burn on a crafted 500-word "title". 20 is generous headroom over any real
# title while making the n-gram expansion trivially cheap.
MAX_WORDS_FOR_NGRAMS = 20

# G-1351 review F3: cap raw title length before any processing (splitting,
# n-gram generation, or the uncapped full-title candidate) so a crafted
# multi-KB "title" string can never reach the matching loop at all.
MAX_TITLE_CHARS = 300

# Conservative, high-confidence cutoffs. A generic WRatio/low-cutoff match is
# what caused the disaster cases above — token_sort_ratio + 90 is deliberately
# strict so an unresolved title/family returns None (unknown) rather than a
# wrong tier.
TITLE_MATCH_THRESHOLD = 90.0
FAMILY_FUZZY_THRESHOLD = 90.0

# Length-guard (T-n1d-02): a candidate shorter than this is a bare abbreviation
# ("sen", "ui") and is never trusted to match anything on its own.
MIN_CANDIDATE_LENGTH = 4
# ...and even at/above that length, a match is only trusted when the query and
# matched-label lengths are proportionate (kills a short/generic candidate
# tying with — or beating — a longer, correct candidate's own exact match).
LENGTH_GUARD_RATIO = 0.6

# G-1351 review F4: a bare single-word n-gram candidate (e.g. "Representative"
# out of "Sales Development Representative") is never trusted UNLESS the full
# title itself is that short — this keeps a genuinely one/two-word title like
# "Chef" working while killing the generic-unigram hijack of longer titles.
MAX_WORDS_FOR_UNIGRAM_CANDIDATES = 2

# ---------------------------------------------------------------------------
# Hand-checked family -> occupation overlay
# ---------------------------------------------------------------------------
# Each concept_uri below was grepped against the bundled fixture
# (career_os.fixtures/esco_occupations_en.json.gz) and confirmed to exist with
# the stated preferred_label before being pinned here. Families with no
# genuinely-correct ESCO occupation (e.g. Backend/Frontend/DevOps/SRE/Platform/
# ML/Data Engineer — verified during planning to have no exact preferred_label
# or alt_label match) are deliberately left OUT: they fall through to the
# conservative fuzzy fallback below, which will likely resolve to `unknown`.
# That is the correct, honest behavior — never invent a wrong pin.
FAMILY_OCCUPATION_OVERLAY: dict[str, str] = {
    # -- Technology --
    "SWE": "http://data.europa.eu/esco/occupation/f2b15a0e-e65a-438a-affb-29b9d50b77d1",  # software developer 2512.3
    # Natural-language alias of "SWE" (G-1351 review F5): job_family is free
    # text in some callers, not always the scoring-preset code, and the
    # abbreviation alone doesn't fuzzy-match "software developer" closely
    # enough (74.3 vs the 90 cutoff) to fall through correctly.
    "Software Engineer": "http://data.europa.eu/esco/occupation/f2b15a0e-e65a-438a-affb-29b9d50b77d1",  # software developer 2512.3
    "TPM": "http://data.europa.eu/esco/occupation/8b6388a4-4904-471b-9331-d3b1211f5525",  # ICT project manager 1330.7
    "QA Engineer": "http://data.europa.eu/esco/occupation/106f79e4-6264-45f1-9e7a-297435cd684b",  # software tester 2519.6
    "QA Automation Engineer": "http://data.europa.eu/esco/occupation/106f79e4-6264-45f1-9e7a-297435cd684b",  # software tester
    "SDET": "http://data.europa.eu/esco/occupation/106f79e4-6264-45f1-9e7a-297435cd684b",  # software tester
    "Data Scientist": "http://data.europa.eu/esco/occupation/258e46f9-0075-4a2e-adae-1ff0477e0f30",  # data scientist 2511.3
    "Data Analyst": "http://data.europa.eu/esco/occupation/d3edb8f8-3a06-47a0-8fb9-9b212c006aa2",  # data analyst 2511.2
    "Database Administrator": "http://data.europa.eu/esco/occupation/8c57af09-719c-42b3-be40-6ed4946236cc",  # database administrator 2521.1
    "Network Engineer": "http://data.europa.eu/esco/occupation/cf2b03cd-feb7-4f47-90f6-ff1ed6016d3d",  # ICT network engineer 2523.3
    "Systems Administrator": "http://data.europa.eu/esco/occupation/9e2e6e1e-363b-4e1b-a673-7bc0f7343300",  # ICT system administrator 2522.1
    "Product Manager": "http://data.europa.eu/esco/occupation/9f508305-80ce-4111-8722-f2c9b4a44890",  # product manager 1223.1
    "Business Analyst": "http://data.europa.eu/esco/occupation/60082a99-d8ef-4e84-9290-78902681b6ed",  # business analyst 2421.1
    "Sales Engineer": "http://data.europa.eu/esco/occupation/8529edc5-96ad-4cde-b34a-f86ad3753e4d",  # sales engineer 2433.4
    # -- Design --
    "Graphic Designer": "http://data.europa.eu/esco/occupation/69bcbb0a-8d80-4ecd-b0a4-9adea2a40de2",  # graphic designer 2166.10
    "Creative Director": "http://data.europa.eu/esco/occupation/d2db926b-8b14-4686-9c98-fb0dc3a38cbb",  # creative director 2431.7
    "Instructional Designer": "http://data.europa.eu/esco/occupation/a9c30651-ccbc-4a80-900c-7880615cdf6e",  # instructional designer 2359.8
    "Architect": "http://data.europa.eu/esco/occupation/8c3f536e-ba66-4321-ba40-363dc39f129b",  # architect 2161.1
    # -- Data / analytics --
    "Statistician": "http://data.europa.eu/esco/occupation/ac8b3cd1-a127-4e6a-8208-5cfcf7111955",  # statistician 2120.6
    "Market Research Analyst": "http://data.europa.eu/esco/occupation/66fb9704-0d56-4673-8e69-7823816b73e1",  # market research analyst 2431.11
    # -- Finance --
    "Financial Analyst": "http://data.europa.eu/esco/occupation/8d586ee9-0ab1-4155-a3b0-2ca786c8e48c",  # financial analyst 2413.1
    "Investment Analyst": "http://data.europa.eu/esco/occupation/b7f47c25-bdf3-42fa-a68e-ad32754b2dba",  # investment analyst 2413.1.3
    "Credit Analyst": "http://data.europa.eu/esco/occupation/075e4d25-74b3-46fb-9b6e-6b53cdb196e7",  # credit analyst 3312.2.1
    "Bookkeeper": "http://data.europa.eu/esco/occupation/c3aae59e-1441-4b3e-bdd1-6da50dc7cf42",  # bookkeeper 3313.2
    "Insurance Underwriter": "http://data.europa.eu/esco/occupation/e937449a-d9e0-4ab7-9ea5-4d3ac673be6d",  # insurance underwriter 3321.3
    "Loan Officer": "http://data.europa.eu/esco/occupation/8e185c49-704e-49c0-8584-a7e0b618f628",  # loan officer 3312.5
    # -- Legal / marketing / ops --
    "Corporate Lawyer": "http://data.europa.eu/esco/occupation/fdfce14e-992d-4ff4-9f9d-7a353c75654e",  # corporate lawyer 2611.1.1
    "Marketing Manager": "http://data.europa.eu/esco/occupation/6fcf4638-e7c7-4978-9302-9a7b63a3d57c",  # marketing manager 1221.3.2
    "Brand Manager": "http://data.europa.eu/esco/occupation/de80bbf0-447d-4a6a-845a-fdba4e0dc30c",  # brand manager 2431.4
    "Operations Manager": "http://data.europa.eu/esco/occupation/c6bd511a-d966-4df9-a48e-4f800354f268",  # operations manager 1321.1.3
    "Supply Chain Manager": "http://data.europa.eu/esco/occupation/aacc3918-b5d3-484b-9480-5d29aa550d74",  # supply chain manager 1324.3.4
}

# Casefolded overlay for case-insensitive lookup (G-1351 review F5): job_family
# is free text in some callers ("swe", "Software Engineer" as well as the
# canonical "SWE" scoring-preset code), matching scoring.py's
# _weights_for_job_family case-insensitivity.
_FAMILY_OCCUPATION_OVERLAY_CF: dict[str, str] = {
    key.casefold(): uri for key, uri in FAMILY_OCCUPATION_OVERLAY.items()
}

# ---------------------------------------------------------------------------
# Curated alt-label denylist (G-1351 review F2)
# ---------------------------------------------------------------------------
# Each entry below is an ESCO alt_label string (casefolded) that is a literal
# or near-exact collision with an occupation OUTSIDE our domain, verified
# against the real bundled fixture (see the F2 probe: every JOB_FAMILY_WEIGHTS
# key run through normalize_title_to_occupation). Filtered out entirely when
# building the title-matching surface — the affected occupations remain
# reachable via their own preferred_label; only the misleading alt is removed.
ALT_LABEL_DENYLIST: frozenset[str] = frozenset(
    {
        # Exact alt of "data scientist". "Data Engineer" has no genuine ESCO
        # pin (see FAMILY_OCCUPATION_OVERLAY comment) — without this entry a
        # "Data Engineer" JD title resolves same_occupation=1.0 against a
        # "Data Scientist" family, which is wrong.
        "data engineer",
        # Exact alt of BOTH "foundry manager" and "maintenance and repair
        # engineer" — neither is an engineering-management role in our
        # domain's sense.
        "engineering manager",
        # Exact alt of 4 unrelated occupations (metal production manager,
        # mine manager, financial markets back office administrator, business
        # manager). Worse than a fuzzy near-miss: this is a literal string
        # collision that non-deterministically shadowed the CORRECT
        # "operations manager" occupation's own preferred_label in the
        # candidate dict depending on DB row-insertion order — Operations
        # Manager is one of our 30 pinned overlay families, so this was a
        # same-title round-trip bug, not just a theoretical risk.
        "operations manager",
        # Plural alt of "bank account manager". ESCO has no generic "account
        # manager" occupation, only specialized variants (bank/ICT/sales); the
        # plural alt out-scores a plain "Account Manager" JD title via
        # token_sort_ratio (96.8) even though bank-specific is the wrong
        # domain for most of our job families.
        "account managers",
    }
)


@dataclass(frozen=True)
class _OccupationRef:
    """Immutable snapshot of the ESCOOccupation columns match_occupation needs.

    Deliberately NOT the live ORM row (G-1351 review F7): the match surface is
    cached at module scope across calls (and, in tests, across independently
    created/closed sessions with the same taxonomy row count). A cached live
    ORM instance would go detached/expired once its originating session
    closes; a plain-data snapshot has no such lifecycle to worry about.
    """

    concept_uri: str
    preferred_label: str
    isco_group: str | None


@dataclass
class _MatchSurface:
    """Pre-built matching surface for a given taxonomy row count (G-1351 F7)."""

    row_count: int
    family_labels: list[str] = field(default_factory=list)
    family_label_to_ref: dict[str, _OccupationRef] = field(default_factory=dict)
    title_candidates: list[str] = field(default_factory=list)
    title_candidate_to_ref: dict[str, _OccupationRef] = field(default_factory=dict)
    pin_uri_to_ref: dict[str, _OccupationRef] = field(default_factory=dict)


def _build_match_surface(db: Session, row_count: int) -> _MatchSurface:
    """Query the full taxonomy once and build both matching surfaces.

    Single full-table scan (previously duplicated per-call in both
    ``map_family_to_occupation`` and ``normalize_title_to_occupation`` —
    G-1351 review F7). Alt labels in ``ALT_LABEL_DENYLIST`` are dropped here
    (G-1351 review F2) so every caller of the cached surface benefits.
    """
    rows = db.query(ESCOOccupation).all()

    family_label_to_ref: dict[str, _OccupationRef] = {}
    title_candidate_to_ref: dict[str, _OccupationRef] = {}
    pin_uri_to_ref: dict[str, _OccupationRef] = {}

    for row in rows:
        ref = _OccupationRef(
            concept_uri=row.concept_uri,
            preferred_label=row.preferred_label,
            isco_group=row.isco_group,
        )
        pin_uri_to_ref[row.concept_uri] = ref
        # Family fuzzy fallback: preferred_label only (not alt_labels — those
        # are for title matching, where more variants are acceptable; a
        # family code should only fall back to a very close canonical
        # occupation name).
        family_label_to_ref.setdefault(row.preferred_label, ref)
        # Title matching: preferred_label + non-denylisted alt_labels.
        title_candidate_to_ref.setdefault(row.preferred_label, ref)
        for alt in row.alt_labels_list:
            if alt.casefold() in ALT_LABEL_DENYLIST:
                continue
            title_candidate_to_ref.setdefault(alt, ref)

    return _MatchSurface(
        row_count=row_count,
        family_labels=list(family_label_to_ref.keys()),
        family_label_to_ref=family_label_to_ref,
        title_candidates=list(title_candidate_to_ref.keys()),
        title_candidate_to_ref=title_candidate_to_ref,
        pin_uri_to_ref=pin_uri_to_ref,
    )


# Module-level cache of the built matching surface (G-1351 review F7),
# invalidated when the taxonomy row count changes. Identical data across DBs
# at the same row count is acceptable — the taxonomy is a single-source
# bundled fixture, so two DBs with the same count have the same content.
_surface_cache: _MatchSurface | None = None


def _get_match_surface(db: Session) -> _MatchSurface | None:
    """Return the cached match surface, rebuilding only if the row count changed.

    Returns ``None`` for an empty taxonomy (row_count == 0) so callers keep
    their existing "empty taxonomy -> None" behavior without a wasted build.
    """
    global _surface_cache
    row_count = count_occupations(db)
    if row_count == 0:
        return None
    if _surface_cache is None or _surface_cache.row_count != row_count:
        _surface_cache = _build_match_surface(db, row_count)
    return _surface_cache


# ---------------------------------------------------------------------------
# F1: lazy self-populate so match_occupation is never inert by default
# ---------------------------------------------------------------------------
# Set once a lazy populate attempt has failed, so a persistently-broken
# fixture/DB doesn't pay the populate-and-fail cost on every single
# match_occupation call. Intentionally module-level, not per-call: this is a
# "give up gracefully after one bad attempt" latch, not a per-request cache.
_POPULATE_ATTEMPT_FAILED = False


def _ensure_taxonomy_populated(db: Session) -> None:
    """Lazily populate esco_occupations if empty (G-1351 review F1).

    A normal server deployment never runs `kestrel occupations load`
    manually; without this, match_occupation was permanently inert (always
    `unknown`) in production — the exact 4a "honest but dead" failure shape
    this ticket exists to fix. `populate_occupations` is idempotent and takes
    ~1-2s for the bundled 2,942-row fixture, so calling it here is safe; the
    row-count check makes every call after the first a cheap no-op.

    Never raises: a populate failure degrades to `unknown` (via the empty
    surface downstream) and flips `_POPULATE_ATTEMPT_FAILED` so it is not
    retried on every subsequent call.
    """
    global _POPULATE_ATTEMPT_FAILED
    if _POPULATE_ATTEMPT_FAILED:
        return
    try:
        # Count AND populate on a SEPARATE session bound to the caller's
        # engine/connection: populate_occupations commits, and committing the
        # caller's borrowed session would persist the caller's own pending
        # score_job writes mid-transaction (the commit-flavored twin of the
        # F6 rollback hazard). Touching the caller's session here at all
        # would also autoflush its pending writes and take a write lock,
        # blocking the populate connection. On a connection-bound test
        # session this degrades gracefully to a savepoint (SQLAlchemy
        # conditional_savepoint join mode).
        with Session(bind=db.get_bind()) as populate_session:
            if count_occupations(populate_session) == 0:
                populate_occupations(populate_session)
    except Exception:
        logger.warning(
            "Lazy populate_occupations failed inside match_occupation; "
            "degrading to unknown until a successful populate (manual "
            "`kestrel occupations load` or a later process restart).",
            exc_info=True,
        )
        _POPULATE_ATTEMPT_FAILED = True


def _passes_length_guard(query: str, matched_label: str) -> bool:
    """Reject a match where query/label lengths are too disproportionate.

    Defense-in-depth alongside the high fuzzy cutoff: a bare abbreviation or a
    generic single word should never be trusted to match anything on its own.
    """
    if len(query) < MIN_CANDIDATE_LENGTH:
        return False
    shorter = min(len(query), len(matched_label))
    longer = max(len(query), len(matched_label))
    if longer == 0:
        return False
    return (shorter / longer) >= LENGTH_GUARD_RATIO


def map_family_to_occupation(db: Session, family: str | None) -> _OccupationRef | None:
    """Resolve a job_family code/label to an occupation ref.

    Overlay lookup first (casefolded exact family key -> pinned concept_uri —
    G-1351 review F5), then a conservative fuzzy fallback on ``preferred_label``
    only (high cutoff). Unknown/garbage family strings, or families with no
    confident match, return ``None`` rather than a wrong occupation. Does NOT
    lazily populate an empty taxonomy itself (that's `match_occupation`'s job
    — G-1351 review F1); called directly on an empty table this simply
    returns ``None``.
    """
    if not family or not family.strip():
        return None
    family_key = family.strip()

    surface = _get_match_surface(db)
    if surface is None:
        return None

    pinned_uri = _FAMILY_OCCUPATION_OVERLAY_CF.get(family_key.casefold())
    if pinned_uri:
        ref = surface.pin_uri_to_ref.get(pinned_uri)
        if ref is None:
            # G-1351 review F9: a pin whose concept_uri isn't in the table
            # would otherwise silently degrade to None — surface fixture/DB
            # drift instead of hiding it.
            logger.warning(
                "FAMILY_OCCUPATION_OVERLAY pin %r for family %r not found in "
                "esco_occupations — fixture/DB drift?",
                pinned_uri,
                family_key,
            )
        return ref

    # Conservative fuzzy fallback: preferred_label only (not alt_labels — those
    # are for title matching, where more variants are acceptable; a family
    # code should only fall back to a very close canonical occupation name).
    result = process.extractOne(
        family_key,
        surface.family_labels,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=FAMILY_FUZZY_THRESHOLD,
        processor=utils.default_process,
    )
    if not result:
        return None
    matched_label = result[0]
    return surface.family_label_to_ref.get(matched_label)


def normalize_title_to_occupation(db: Session, jd_title: str | None) -> _OccupationRef | None:
    """Resolve a free-text JD title to an occupation ref.

    Truncates to ``MAX_TITLE_CHARS`` before any processing (G-1351 review F3),
    then generates n-grams of the (truncated) title, capped at
    ``MAX_WORDS_FOR_NGRAMS``, and fuzzy-matches each against every
    occupation's preferred_label AND non-denylisted alt_labels (G-1351 review
    F2) via token_sort_ratio with a case/punctuation-insensitive processor and
    a high cutoff. Single-word candidates are only allowed when the full
    title itself is ``MAX_WORDS_FOR_UNIGRAM_CANDIDATES`` words or fewer
    (G-1351 review F4). A length-guard rejects a candidate/matched-label pair
    that is too disproportionate in length. Candidates are tried longest-first
    so a specific multi-word match (e.g. "nurse assistant") wins over a
    shorter, more generic single-word tie (e.g. "assistant"). Empty/whitespace
    title or an empty taxonomy -> ``None``.
    """
    if not jd_title or not jd_title.strip():
        return None

    title = jd_title.strip()[:MAX_TITLE_CHARS]

    surface = _get_match_surface(db)
    if surface is None:
        return None

    words = title.split()[:MAX_WORDS_FOR_NGRAMS]
    if not words:
        return None
    allow_unigrams = len(words) <= MAX_WORDS_FOR_UNIGRAM_CANDIDATES

    candidates: set[str] = {title}
    max_window = min(len(words), 5)
    for n in range(1, max_window + 1):
        if n == 1 and not allow_unigrams:
            continue
        for i in range(len(words) - n + 1):
            candidates.add(" ".join(words[i : i + n]))

    # Longest-first: on an equal-score tie, keep the more specific candidate
    # rather than letting a later, shorter generic word overwrite it.
    ordered_candidates = sorted(candidates, key=lambda c: (-len(c), c))

    best_ref: _OccupationRef | None = None
    best_score = -1.0
    for candidate in ordered_candidates:
        if len(candidate) < MIN_CANDIDATE_LENGTH:
            continue
        result = process.extractOne(
            candidate,
            surface.title_candidates,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=TITLE_MATCH_THRESHOLD,
            processor=utils.default_process,
        )
        if not result:
            continue
        matched_label, score, _ = result
        if not _passes_length_guard(candidate, matched_label):
            continue
        if score > best_score:
            best_score = score
            best_ref = surface.title_candidate_to_ref.get(matched_label)

    return best_ref


def _classify(
    family_occ: _OccupationRef | None, title_occ: _OccupationRef | None
) -> dict[str, str | float | None]:
    """Pure classifier: two resolved occupations (or None) -> a match tier.

    CRITICAL: unresolved input (either side is None) is ``unknown`` with
    ``score=None`` — never the fake ``0.0`` of the old inert axis. ``no_match``
    is the only tier that carries a real ``0.0``.
    """
    if family_occ is None or title_occ is None:
        return {"match": "unknown", "score": None}
    if family_occ.concept_uri == title_occ.concept_uri:
        return {"match": "same_occupation", "score": 1.0}
    if (
        family_occ.isco_group
        and title_occ.isco_group
        and family_occ.isco_group == title_occ.isco_group
    ):
        return {"match": "same_isco_group", "score": 0.5}
    return {"match": "no_match", "score": 0.0}


def match_occupation(db: Session, candidate_family: str | None, jd_title: str | None) -> dict:
    """Pure feature: job_family + JD title -> occupation-match tier + score.

    Returns a dict with ``match`` (same_occupation | same_isco_group |
    no_match | unknown), ``score`` (1.0 | 0.5 | 0.0 | None), and the resolved
    family/title URIs + labels for explainability. Self-sufficient (G-1351
    review F1): lazily populates ``esco_occupations`` from the bundled
    fixture on first use if the table is empty, so a normal server deployment
    that never runs `kestrel occupations load` still gets a real signal.

    Defensive: any unexpected failure degrades to the ``unknown`` result
    (never raises). CRITICAL (G-1351 review F6): unlike `esco_features.py`'s
    swallow-and-rollback pattern, this function NEVER calls `db.rollback()` on
    failure. It borrows the caller's session, and in the Phase C cascade will
    run mid `score_job` with the caller's own uncommitted rows already added
    to that session — rolling back here would silently discard those pending
    writes. The swallow path only logs and returns `unknown`; it never
    mutates transaction state. The F1 lazy populate likewise runs on its OWN
    session bound to the caller's engine — its commit can never persist the
    caller's pending writes.
    """
    try:
        _ensure_taxonomy_populated(db)
        family_occ = map_family_to_occupation(db, candidate_family)
        title_occ = normalize_title_to_occupation(db, jd_title)
        result = _classify(family_occ, title_occ)
        result["family_uri"] = family_occ.concept_uri if family_occ else None
        result["family_label"] = family_occ.preferred_label if family_occ else None
        result["title_uri"] = title_occ.concept_uri if title_occ else None
        result["title_label"] = title_occ.preferred_label if title_occ else None
        return result
    except Exception:
        logger.warning(
            "match_occupation failed for family=%r title=%r (swallowed, no "
            "rollback — see docstring, G-1351 review F6)",
            candidate_family,
            jd_title,
            exc_info=True,
        )
        return {
            "match": "unknown",
            "score": None,
            "family_uri": None,
            "family_label": None,
            "title_uri": None,
            "title_label": None,
        }
