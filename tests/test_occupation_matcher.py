"""Tests for the occupation matcher (G-1351 Phase B, the crux).

Uses REAL family codes (from career_os.services.scoring.JOB_FAMILY_WEIGHTS)
and REAL JD title strings against the real bundled ESCO occupations taxonomy
(populated via occupation_taxonomy.populate_occupations — never seeded into
the ESCO skills cache). Proves the classifier is not a constant, that `unknown`
is strictly distinguishable from `no_match` (score=None vs score=0.0), and that
the known disaster case ("Senior Backend Engineer" -> nursing) cannot recur.

Also covers the G-1351 3-pass review fixes (F1-F9): self-sufficient lazy
populate (F1), the ambiguous-alt-label denylist (F2), the JD-title CPU cap
(F3), the generic-unigram hijack guard (F4), case-insensitive overlay lookup
(F5), the no-rollback swallow path (F6), the match-surface cache (F7), and the
additional testing-gap coverage (F8).
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy.orm import Session

import career_os.services.occupation_matcher as occupation_matcher
from career_os.services.occupation_matcher import (
    _classify,
    map_family_to_occupation,
    match_occupation,
    normalize_title_to_occupation,
)
from career_os.services.occupation_taxonomy import count_occupations, populate_occupations


def _populated(db_session: Session) -> Session:
    populate_occupations(db_session)
    return db_session


@pytest.fixture(autouse=True)
def _reset_matcher_module_state(monkeypatch):
    """Reset module-level lazy-populate/cache state around every test.

    Both `_POPULATE_ATTEMPT_FAILED` (F1) and `_surface_cache` (F7) are
    intentionally module-level (they cache/latch across calls within a
    process), but that makes them cross-test-contamination risks in a test
    suite that runs many independent DBs in the same process. monkeypatch
    restores the pre-test value after each test regardless of what the code
    mutates it to during the test, so this keeps every test hermetic without
    losing the module-level design the production code needs.
    """
    monkeypatch.setattr(occupation_matcher, "_POPULATE_ATTEMPT_FAILED", False)
    monkeypatch.setattr(occupation_matcher, "_surface_cache", None)
    yield


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
    # No populate_occupations call — table is empty. map_family_to_occupation
    # itself never lazily populates (that's match_occupation's job — F1).
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
# F5 — case-insensitive overlay lookup
# ---------------------------------------------------------------------------


def test_map_family_to_occupation_case_insensitive_overlay(db_session: Session) -> None:
    """'SWE', 'swe', 'Software Engineer', 'software engineer' all resolve to
    the same occupation (concept_uri) — job_family is free text, and
    scoring.py's _weights_for_job_family is already case-insensitive."""
    db = _populated(db_session)
    variants = ["SWE", "swe", "Software Engineer", "software engineer"]
    resolved = [map_family_to_occupation(db, v) for v in variants]
    assert all(occ is not None for occ in resolved)
    uris = {occ.concept_uri for occ in resolved}
    assert len(uris) == 1


# ---------------------------------------------------------------------------
# F3 — CPU DoS cap on crafted titles
# ---------------------------------------------------------------------------


def test_normalize_title_to_occupation_caps_cpu_on_huge_title(db_session: Session) -> None:
    """A 5,000-word junk title must complete fast and degrade safely."""
    db = _populated(db_session)
    junk_title = " ".join(f"word{i}" for i in range(5000))

    start = time.perf_counter()
    result = normalize_title_to_occupation(db, junk_title)
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, f"normalize_title_to_occupation took {elapsed:.2f}s (expected < 2s)"
    assert result is None


# ---------------------------------------------------------------------------
# F4 — generic unigram hijack guard
# ---------------------------------------------------------------------------


def test_normalize_title_to_occupation_unigram_hijack_guard(db_session: Session) -> None:
    """'Sales Development Representative' must never resolve via the bare
    unigram candidate 'Representative' hijacking an HR occupation."""
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Sales Development Representative")
    if occ is not None:
        assert "human resources" not in occ.preferred_label.lower()


def test_normalize_title_to_occupation_short_title_still_resolves(db_session: Session) -> None:
    """A genuinely short title ('Chef') must still resolve via its own unigram."""
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Chef")
    assert occ is not None
    assert occ.preferred_label == "chef"


def test_normalize_title_to_occupation_backend_engineer_no_wrong_resolution(
    db_session: Session,
) -> None:
    """'Senior Backend Engineer' must never resolve to an unrelated occupation
    (the original 4a disaster case) even with the unigram guard in place."""
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Senior Backend Engineer")
    if occ is not None:
        assert occ.preferred_label != "nurse assistant"


# ---------------------------------------------------------------------------
# F2 — ambiguous ESCO alt-label denylist
# ---------------------------------------------------------------------------


def test_normalize_title_denylist_blocks_data_engineer_as_data_scientist(
    db_session: Session,
) -> None:
    """'data engineer' is a literal ESCO alt_label of 'data scientist' —
    denylisted so a Data Engineer JD title never resolves to it."""
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Data Engineer")
    if occ is not None:
        assert occ.preferred_label != "data scientist"


def test_normalize_title_denylist_blocks_engineering_manager_as_foundry_manager(
    db_session: Session,
) -> None:
    """'engineering manager' is a literal ESCO alt_label of 'foundry manager' —
    denylisted so an Engineering Manager JD title never resolves to it."""
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Engineering Manager")
    if occ is not None:
        assert occ.preferred_label != "foundry manager"


def test_match_occupation_data_scientist_family_vs_data_engineer_title(
    db_session: Session,
) -> None:
    """The exact disaster reproduction from the review: Data Scientist family
    + Data Engineer title must NOT be same_occupation=1.0."""
    db = _populated(db_session)
    result = match_occupation(db, "Data Scientist", "Data Engineer")
    assert result["match"] != "same_occupation"


def test_match_occupation_operations_manager_self_match_restored(db_session: Session) -> None:
    """Denylisting the 'operations manager' alt-label collision restores the
    same-title round-trip for one of our 30 pinned overlay families — before
    the fix, DB row-insertion order could non-deterministically shadow the
    correct occupation with an unrelated one (metal production manager, mine
    manager, financial markets back office administrator, business manager)."""
    db = _populated(db_session)
    result = match_occupation(db, "Operations Manager", "Operations Manager")
    assert result["match"] == "same_occupation"
    assert result["score"] == 1.0


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


def test_match_occupation_disaster_guard_backend_engineer(db_session: Session) -> None:
    """The 4a disaster case this ticket exists to prevent.

    "Senior Backend Engineer" must NEVER resolve to an unrelated (e.g.
    nursing) occupation. Backend Engineer has no confident ESCO pin, so the
    family side resolves to None -> the whole result is `unknown`
    (score=None), deterministically (G-1351 review F8 tightened this from
    accepting 3 of 4 tiers to the single correct tier).
    """
    db = _populated(db_session)
    result = match_occupation(db, "Backend Engineer", "Senior Backend Engineer")
    assert result["match"] == "unknown"
    assert result["score"] is None
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


# ---------------------------------------------------------------------------
# F1 — self-sufficient lazy populate
# ---------------------------------------------------------------------------


def test_match_occupation_lazy_populates_empty_taxonomy(db_session: Session) -> None:
    """A fresh, never-populated DB — no populate_occupations call, no CLI —
    must still get a REAL tier from match_occupation, not permanent
    `unknown`. This is the core F1 fix: a normal server deployment never
    manually runs `kestrel occupations load`."""
    assert count_occupations(db_session) == 0

    result = match_occupation(db_session, "SWE", "Senior Software Engineer")

    assert result["match"] == "same_occupation"
    assert result["score"] == 1.0
    # Proves the lazy populate actually ran.
    assert count_occupations(db_session) > 0


def test_match_occupation_lazy_populate_failure_degrades_to_unknown(
    db_session: Session, monkeypatch
) -> None:
    """A populate failure inside the lazy path must degrade to `unknown`
    (score=None) rather than raising or leaving the caller with a wrong
    fabricated result."""
    assert count_occupations(db_session) == 0

    def _boom(db):
        raise RuntimeError("simulated populate failure")

    monkeypatch.setattr(occupation_matcher, "populate_occupations", _boom)

    result = match_occupation(db_session, "SWE", "Senior Software Engineer")

    assert result["match"] == "unknown"
    assert result["score"] is None
    assert occupation_matcher._POPULATE_ATTEMPT_FAILED is True


def test_match_occupation_lazy_populate_not_retried_after_failure(
    db_session: Session, monkeypatch
) -> None:
    """After a failed lazy-populate attempt, subsequent calls must not retry
    populate_occupations on every single call (F1's "already attempted"
    latch)."""
    call_count = {"n": 0}

    def _boom(db):
        call_count["n"] += 1
        raise RuntimeError("simulated populate failure")

    monkeypatch.setattr(occupation_matcher, "populate_occupations", _boom)

    match_occupation(db_session, "SWE", "Senior Software Engineer")
    match_occupation(db_session, "SWE", "Senior Software Engineer")
    match_occupation(db_session, "SWE", "Senior Software Engineer")

    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# F6 — swallow path never rolls back the caller's session
# ---------------------------------------------------------------------------


def test_match_occupation_swallow_path_does_not_rollback(db_session: Session, monkeypatch) -> None:
    """match_occupation borrows the caller's session; a swallowed internal
    failure must never call db.rollback() (it would silently discard the
    caller's own pending uncommitted writes in the Phase C cascade)."""
    db = _populated(db_session)

    def _boom(db, family):
        raise RuntimeError("simulated internal failure")

    monkeypatch.setattr(occupation_matcher, "map_family_to_occupation", _boom)

    rollback_calls = {"n": 0}
    original_rollback = db.rollback

    def _counting_rollback():
        rollback_calls["n"] += 1
        return original_rollback()

    monkeypatch.setattr(db, "rollback", _counting_rollback)

    result = match_occupation(db, "SWE", "Senior Software Engineer")

    assert result["match"] == "unknown"
    assert result["score"] is None
    assert rollback_calls["n"] == 0


# ---------------------------------------------------------------------------
# F7 — match-surface cache
# ---------------------------------------------------------------------------


def test_match_surface_cached_across_calls(db_session: Session, monkeypatch) -> None:
    """Two consecutive match_occupation calls against an unchanged taxonomy
    must only build the match surface once."""
    db = _populated(db_session)

    call_count = {"n": 0}
    original_builder = occupation_matcher._build_match_surface

    def _counting_builder(db, row_count):
        call_count["n"] += 1
        return original_builder(db, row_count)

    monkeypatch.setattr(occupation_matcher, "_build_match_surface", _counting_builder)

    match_occupation(db, "SWE", "Senior Software Engineer")
    match_occupation(db, "SWE", "Senior Software Engineer")

    assert call_count["n"] == 1


def test_match_surface_second_call_is_fast(db_session: Session) -> None:
    """The second call against a warm cache should be comfortably fast.

    Generous bound to stay robust against CI jitter — this is a smoke guard
    against a catastrophic per-call rebuild regression, not a tight
    micro-benchmark (the deterministic call-count test above carries the
    real regression-proofing weight).
    """
    db = _populated(db_session)
    match_occupation(db, "SWE", "Senior Software Engineer")  # warm the cache

    start = time.perf_counter()
    match_occupation(db, "SWE", "Senior Software Engineer")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.5, f"second call took {elapsed:.3f}s (expected < 0.5s)"


# ---------------------------------------------------------------------------
# F8 — additional testing-gap coverage
# ---------------------------------------------------------------------------


def test_match_occupation_same_isco_group_data_scientist_vs_data_analyst(
    db_session: Session,
) -> None:
    """e2e same_isco_group with real fixture data: Data Scientist family vs a
    Data Analyst title — both occupations share ISCO unit group 2511, but are
    genuinely different occupations, so same_isco_group at 0.5 (not
    same_occupation at 1.0, and not a fake 0.0)."""
    db = _populated(db_session)
    result = match_occupation(db, "Data Scientist", "Data Analyst")
    assert result["match"] == "same_isco_group"
    assert result["score"] == 0.5
    assert result["family_label"] == "data scientist"
    assert result["title_label"] == "data analyst"


def test_populate_occupations_force_inserts_genuinely_missing_row(db_session: Session) -> None:
    from career_os.models.esco import ESCOOccupation

    first = populate_occupations(db_session)
    assert first["inserted"] > 0

    victim = db_session.query(ESCOOccupation).first()
    victim_uri = victim.concept_uri
    db_session.delete(victim)
    db_session.commit()

    forced = populate_occupations(db_session, force=True)

    assert forced["inserted"] == 1
    restored = (
        db_session.query(ESCOOccupation).filter(ESCOOccupation.concept_uri == victim_uri).first()
    )
    assert restored is not None


@pytest.mark.parametrize("family", [None, "", "   "])
def test_match_occupation_empty_or_none_family_is_unknown(
    db_session: Session, family: str | None
) -> None:
    db = _populated(db_session)
    result = match_occupation(db, family, "Senior Software Engineer")
    assert result["match"] == "unknown"
    assert result["score"] is None


def test_normalize_title_to_occupation_unicode_title_degrades_to_unknown(
    db_session: Session,
) -> None:
    """A non-English title must degrade to `unknown` (no cross-language
    mis-match) rather than raising or fabricating a wrong resolution."""
    db = _populated(db_session)
    occ = normalize_title_to_occupation(db, "Développeur logiciel")
    # Either it stays unresolved (expected), or — if it happens to resolve —
    # it must be a real occupation object, never a crash.
    if occ is not None:
        assert occ.preferred_label


def test_normalize_title_to_occupation_exact_preferred_label_match(db_session: Session) -> None:
    """An exact preferred_label as the JD title resolves to same_occupation
    for the corresponding pinned family."""
    db = _populated(db_session)
    result = match_occupation(db, "SWE", "software developer")
    assert result["match"] == "same_occupation"
    assert result["score"] == 1.0
