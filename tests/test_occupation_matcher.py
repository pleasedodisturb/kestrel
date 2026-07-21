"""Tests for the occupation matcher (G-1351 Phase B, the crux).

Uses REAL family codes (from career_os.services.scoring.JOB_FAMILY_WEIGHTS)
and REAL JD title strings against the real bundled ESCO occupations taxonomy
(populated via occupation_taxonomy.populate_occupations — never seeded into
the ESCO skills cache). Proves the classifier is not a constant, that `unknown`
is strictly distinguishable from `no_match` (score=None vs score=0.0), and that
the known disaster case ("Senior Backend Engineer" -> nursing) cannot recur.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from career_os.services.occupation_matcher import (
    _classify,
    map_family_to_occupation,
    match_occupation,
    normalize_title_to_occupation,
)
from career_os.services.occupation_taxonomy import populate_occupations


def _populated(db_session: Session) -> Session:
    populate_occupations(db_session)
    return db_session


# ---------------------------------------------------------------------------
# Pure _classify unit tests — no DB needed
# ---------------------------------------------------------------------------


class _FakeOccupation:
    def __init__(self, concept_uri: str, preferred_label: str, isco_group: str | None) -> None:
        self.concept_uri = concept_uri
        self.preferred_label = preferred_label
        self.isco_group = isco_group


def test_classify_same_occupation() -> None:
    occ = _FakeOccupation("uri-1", "software developer", "2512")
    result = _classify(occ, occ)
    assert result == {"match": "same_occupation", "score": 1.0}


def test_classify_same_isco_group() -> None:
    a = _FakeOccupation("uri-1", "software developer", "2512")
    b = _FakeOccupation("uri-2", "software architect", "2512")
    result = _classify(a, b)
    assert result == {"match": "same_isco_group", "score": 0.5}


def test_classify_no_match() -> None:
    a = _FakeOccupation("uri-1", "software developer", "2512")
    b = _FakeOccupation("uri-2", "software tester", "2519")
    result = _classify(a, b)
    assert result == {"match": "no_match", "score": 0.0}


def test_classify_unknown_family_none() -> None:
    b = _FakeOccupation("uri-2", "software tester", "2519")
    result = _classify(None, b)
    assert result["match"] == "unknown"
    assert result["score"] is None


def test_classify_unknown_title_none() -> None:
    a = _FakeOccupation("uri-1", "software developer", "2512")
    result = _classify(a, None)
    assert result["match"] == "unknown"
    assert result["score"] is None


def test_classify_unknown_both_none() -> None:
    result = _classify(None, None)
    assert result == {"match": "unknown", "score": None}


# ---------------------------------------------------------------------------
# map_family_to_occupation / normalize_title_to_occupation
# ---------------------------------------------------------------------------


def test_map_family_to_occupation_resolves_overlay_pin(db_session: Session) -> None:
    db = _populated(db_session)
    occ = map_family_to_occupation(db, "SWE")
    assert occ is not None
    assert occ.preferred_label == "software developer"


def test_map_family_to_occupation_unmapped_family_returns_none(db_session: Session) -> None:
    db = _populated(db_session)
    # "Actuary" is a real JOB_FAMILY_WEIGHTS key with no overlay pin and no
    # close-enough fuzzy match (verified during planning).
    occ = map_family_to_occupation(db, "Actuary")
    assert occ is None


def test_map_family_to_occupation_empty_taxonomy_returns_none(db_session: Session) -> None:
    # No populate_occupations call — table is empty.
    occ = map_family_to_occupation(db_session, "SWE")
    assert occ is None


def test_normalize_title_to_occupation_resolves_real_title(db_session: Session) -> None:
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Senior Software Engineer")
    assert occ is not None
    assert occ.preferred_label == "software developer"


def test_normalize_title_to_occupation_empty_title_returns_none(db_session: Session) -> None:
    db = _populated(db_session)
    assert normalize_title_to_occupation(db, "") is None
    assert normalize_title_to_occupation(db, "   ") is None
    assert normalize_title_to_occupation(db, None) is None


# ---------------------------------------------------------------------------
# match_occupation — the pure feature
# ---------------------------------------------------------------------------


def test_match_occupation_same_occupation(db_session: Session) -> None:
    db = _populated(db_session)
    result = match_occupation(db, "SWE", "Senior Software Engineer")
    assert result["match"] == "same_occupation"
    assert result["score"] == 1.0


def test_match_occupation_no_match(db_session: Session) -> None:
    db = _populated(db_session)
    # Data Scientist family vs a Software Tester title: different, non-empty
    # ISCO groups (2511 vs 2519) -> a genuine no_match, score 0.0.
    result = match_occupation(db, "Data Scientist", "Software Tester")
    assert result["match"] == "no_match"
    assert result["score"] == 0.0


def test_match_occupation_unknown_unmapped_family(db_session: Session) -> None:
    db = _populated(db_session)
    result = match_occupation(db, "Actuary", "Insurance Actuary")
    assert result["match"] == "unknown"
    assert result["score"] is None


def test_match_occupation_unknown_empty_taxonomy(db_session: Session) -> None:
    # Empty esco_occupations table — no populate call.
    result = match_occupation(db_session, "SWE", "Senior Software Engineer")
    assert result["match"] == "unknown"
    assert result["score"] is None


def test_match_occupation_disaster_guard_backend_engineer(db_session: Session) -> None:
    """The 4a disaster case this ticket exists to prevent.

    "Senior Backend Engineer" must NEVER resolve to an unrelated (e.g.
    nursing) occupation. Backend Engineer has no confident ESCO pin, so the
    family side resolves to None -> the whole result is `unknown`
    (score=None) — never a fabricated wrong tier.
    """
    db = _populated(db_session)
    result = match_occupation(db, "Backend Engineer", "Senior Backend Engineer")
    assert result["match"] in ("same_occupation", "same_isco_group", "unknown")
    if result["match"] == "unknown":
        assert result["score"] is None
    else:
        assert result["score"] in (1.0, 0.5)
    # The specific disaster: never resolve through to a nursing occupation.
    assert result["title_label"] != "nurse assistant"


def test_match_occupation_non_constancy(db_session: Session) -> None:
    """Across distinct (family, title) pairs, the signal must vary.

    This is the exact 4a failure mode: a matcher that always returns the
    same tier (or always 0.0) carries no signal. At least 2 distinct tiers
    must appear, including "unknown".
    """
    db = _populated(db_session)
    pairs = [
        ("SWE", "Senior Software Engineer"),  # same_occupation
        ("Data Scientist", "Software Tester"),  # no_match
        ("Actuary", "Insurance Actuary"),  # unknown (unmapped family)
        ("Backend Engineer", "Senior Backend Engineer"),  # unknown (no pin)
        ("TPM", "ICT Project Manager"),  # same_occupation
    ]
    tiers = {match_occupation(db, family, title)["match"] for family, title in pairs}
    assert len(tiers) >= 2
    assert "unknown" in tiers


def test_match_occupation_no_occupation_rows_in_skills_table(db_session: Session) -> None:
    """Guard: this test module must never seed occupation rows into the ESCO skills cache."""
    from career_os.models.esco import ESCOSkill

    _populated(db_session)
    assert db_session.query(ESCOSkill).count() == 0
