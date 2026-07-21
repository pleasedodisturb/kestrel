"""Tests for the in-package ESCO occupations fixture consumer (G-1351 Phase B).

Uses the real bundled fixture (no mocks) — this is the wheel-install path the
ticket exists to prove: a pip-installed user with no `scripts/` directory must
still be able to populate `esco_occupations` via `importlib.resources`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from career_os.services.occupation_taxonomy import (
    count_occupations,
    load_bundled_occupations,
    populate_occupations,
)

MIN_FIXTURE_ROWS = 2900


def test_load_bundled_occupations_returns_full_pillar() -> None:
    rows = load_bundled_occupations()
    assert len(rows) >= MIN_FIXTURE_ROWS
    first = rows[0]
    assert "concept_uri" in first
    assert "preferred_label" in first


def test_populate_occupations_inserts_full_fixture(db_session: Session) -> None:
    assert count_occupations(db_session) == 0

    result = populate_occupations(db_session)

    assert result["inserted"] >= MIN_FIXTURE_ROWS
    assert result["skipped"] == 0
    assert result["already_loaded"] is False
    assert count_occupations(db_session) == result["inserted"]


def test_populate_occupations_is_idempotent(db_session: Session) -> None:
    first = populate_occupations(db_session)
    count_after_first = count_occupations(db_session)

    second = populate_occupations(db_session)

    assert second["inserted"] == 0
    assert second["skipped"] == count_after_first
    assert second["already_loaded"] is True
    # No duplicates: row count unchanged.
    assert count_occupations(db_session) == first["inserted"]


def test_populate_occupations_force_does_not_duplicate(db_session: Session) -> None:
    first = populate_occupations(db_session)
    count_after_first = count_occupations(db_session)

    forced = populate_occupations(db_session, force=True)

    # force=True re-scans and finds nothing genuinely missing.
    assert forced["inserted"] == 0
    assert count_occupations(db_session) == count_after_first
    assert count_occupations(db_session) == first["inserted"]
