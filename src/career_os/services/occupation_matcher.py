"""Occupation matcher: job_family <-> occupation, JD-title normalizer (G-1351 Phase B).

The crux of Phase B: give the scorer a real title-vs-occupation signal instead
of the 4a "inert axis" (see ``esco_features.py``'s module docstring for the
history — the caller only has a job-family *code* like "TPM"/"SWE", not a
title, and the old skills cache had no occupation concepts at all).

Two resolvers feed a pure classifier:

* ``map_family_to_occupation`` — job_family -> ``ESCOOccupation``, via a
  hand-checked overlay (exact, fixture-verified ``concept_uri`` pins for the
  families that have a genuine ESCO match) plus a conservative fuzzy fallback
  on ``preferred_label`` only.
* ``normalize_title_to_occupation`` — free-text JD title -> ``ESCOOccupation``,
  via conservative rapidfuzz n-gram matching over ``preferred_label`` +
  ``alt_labels``.

``match_occupation`` combines both into a tier: ``same_occupation``,
``same_isco_group``, ``no_match``, or ``unknown``. CRITICAL: ``unknown``
always carries ``score=None`` — never the fake ``0.0`` that made the old axis
inert and indistinguishable from a real "no match" (``no_match``, which IS
``0.0``).

Naive fuzzy matching over short titles is unsafe (verified failures during
planning: "Senior Backend Engineer" -> "nurse assistant" via a loose scorer
picking up the substring "sen"; "data engineer" -> "data scientist" at 100
via a loose WRatio-style scorer). This module uses ``token_sort_ratio`` with a
high cutoff, case/punctuation-insensitive comparison, and a length-guard that
rejects a short/generic candidate matching an unrelated label — an unresolved
title returns ``None`` (-> ``unknown``) rather than a wrong tier.
"""

from __future__ import annotations

import logging

from rapidfuzz import fuzz, process, utils
from sqlalchemy.orm import Session

from career_os.models.esco import ESCOOccupation

logger = logging.getLogger(__name__)

# T-n1d-01 mitigation: cap n-gram generation to the first N words of a title,
# mirroring cli/extract.py's MAX_WORDS_FOR_NGRAMS (T-02-02) DoS bound. Real JD
# titles are a handful of words; this only guards against a maliciously huge
# "title" string blowing up n-gram expansion.
MAX_WORDS_FOR_NGRAMS = 500

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


def _passes_length_guard(query: str, matched_label: str) -> bool:
    """Reject a match where query/label lengths are too disproportionate.

    Defense-in-depth alongside the high fuzzy cutoff: a bare abbreviation or a
    generic single word should never be trusted to resolve a title, even if it
    happens to clear the score threshold against some unrelated label.
    """
    if len(query) < MIN_CANDIDATE_LENGTH:
        return False
    shorter = min(len(query), len(matched_label))
    longer = max(len(query), len(matched_label))
    if longer == 0:
        return False
    return (shorter / longer) >= LENGTH_GUARD_RATIO


def map_family_to_occupation(db: Session, family: str | None) -> ESCOOccupation | None:
    """Resolve a job_family code/label to an ``ESCOOccupation``.

    Overlay lookup first (exact family key -> pinned concept_uri), then a
    conservative fuzzy fallback on ``preferred_label`` only (high cutoff).
    Unknown/garbage family strings, or families with no confident match,
    return ``None`` rather than a wrong occupation.
    """
    if not family or not family.strip():
        return None
    family_key = family.strip()

    pinned_uri = FAMILY_OCCUPATION_OVERLAY.get(family_key)
    if pinned_uri:
        return db.query(ESCOOccupation).filter(ESCOOccupation.concept_uri == pinned_uri).first()

    # Conservative fuzzy fallback: preferred_label only (not alt_labels — those
    # are for title matching, where more variants are acceptable; a family
    # code should only fall back to a very close canonical occupation name).
    rows = db.query(ESCOOccupation).all()
    if not rows:
        return None
    label_to_row = {row.preferred_label: row for row in rows}
    labels = list(label_to_row.keys())
    result = process.extractOne(
        family_key,
        labels,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=FAMILY_FUZZY_THRESHOLD,
        processor=utils.default_process,
    )
    if not result:
        return None
    matched_label = result[0]
    return label_to_row.get(matched_label)


def normalize_title_to_occupation(db: Session, jd_title: str | None) -> ESCOOccupation | None:
    """Resolve a free-text JD title to an ``ESCOOccupation``.

    Generates n-grams of the title (capped at MAX_WORDS_FOR_NGRAMS — T-n1d-01)
    and fuzzy-matches each against every occupation's preferred_label AND
    alt_labels via token_sort_ratio with a case/punctuation-insensitive
    processor and a high cutoff. A length-guard rejects a candidate/matched-
    label pair that is too disproportionate in length. Candidates are tried
    longest-first so a specific multi-word match (e.g. "nurse assistant")
    wins over a shorter, more generic single-word tie (e.g. "assistant").
    Empty/whitespace title or an empty taxonomy -> ``None``.
    """
    if not jd_title or not jd_title.strip():
        return None

    rows = db.query(ESCOOccupation).all()
    if not rows:
        return None

    candidate_to_row: dict[str, ESCOOccupation] = {}
    for row in rows:
        candidate_to_row.setdefault(row.preferred_label, row)
        for alt in row.alt_labels_list:
            candidate_to_row.setdefault(alt, row)
    labels = list(candidate_to_row.keys())
    if not labels:
        return None

    words = jd_title.split()[:MAX_WORDS_FOR_NGRAMS]
    candidates: set[str] = {jd_title.strip()}
    max_window = min(len(words), 5)
    for n in range(1, max_window + 1):
        for i in range(len(words) - n + 1):
            candidates.add(" ".join(words[i : i + n]))

    # Longest-first: on an equal-score tie, keep the more specific candidate
    # rather than letting a later, shorter generic word overwrite it.
    ordered_candidates = sorted(candidates, key=lambda c: (-len(c), c))

    best_row: ESCOOccupation | None = None
    best_score = -1.0
    for candidate in ordered_candidates:
        if len(candidate) < MIN_CANDIDATE_LENGTH:
            continue
        result = process.extractOne(
            candidate,
            labels,
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
            best_row = candidate_to_row.get(matched_label)

    return best_row


def _classify(
    family_occ: ESCOOccupation | None, title_occ: ESCOOccupation | None
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
    family/title URIs + labels for explainability. Defensive: any unexpected
    failure degrades to the ``unknown`` result (never raises), mirroring
    ``esco_features.py``'s swallow-and-rollback pattern.
    """
    try:
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
            "match_occupation failed for family=%r title=%r (swallowed)",
            candidate_family,
            jd_title,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            logger.debug("match_occupation rollback also failed", exc_info=True)
        return {
            "match": "unknown",
            "score": None,
            "family_uri": None,
            "family_label": None,
            "title_uri": None,
            "title_label": None,
        }
