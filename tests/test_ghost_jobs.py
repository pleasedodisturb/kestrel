"""Tests for ghost job detection rules (G-270).

Covers normalization helpers, occurrence counting, threshold logic, multi-city
blast detection, and integration with score_job via detect_data_driven_red_flags.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.services.red_flags import (
    _count_company_title_occurrences,
    _detect_ghost_job_signals,
    _detect_multi_city_blast,
    detect_data_driven_red_flags,
    normalize_company_name,
    normalize_job_title,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FILLER_DESC = "This is a normal software engineering role with clear responsibilities. " * 5

# Counter used to make each inserted job's location unique so the dedup
# constraint (profile_id, title_normalized, company_normalized, location_normalized)
# is never violated when inserting multiple rows for the same company+title.
_location_counter = itertools.count(1)


def _make_job(
    db: Session,
    profile_id: int,
    *,
    title: str = "Software Engineer",
    company: str = "Acme",
    location: str | None = None,
    description: str = _FILLER_DESC,
    days_ago: int = 1,
) -> DiscoveredJob:
    """Insert a DiscoveredJob row and return it.

    ``location`` defaults to a unique city name so that multiple inserts for
    the same company+title don't collide with the dedup unique constraint.
    """
    if location is None:
        location = f"City {next(_location_counter)}, Germany"
    created = datetime.now(UTC) - timedelta(days=days_ago)
    job = DiscoveredJob(
        profile_id=profile_id,
        title=title,
        company=company,
        location=location,
        description=description,
        title_normalized=normalize_job_title(title),
        company_normalized=normalize_company_name(company),
        location_normalized=location.lower().strip(),
        created_at=created,
        updated_at=created,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# normalize_company_name
# ---------------------------------------------------------------------------


def test_normalize_company_name_strips_llc() -> None:
    assert normalize_company_name("Google LLC") == "google"


def test_normalize_company_name_strips_inc_with_period() -> None:
    assert normalize_company_name("Alphabet Inc.") == "alphabet"


def test_normalize_company_name_strips_corp() -> None:
    assert normalize_company_name("ACME Corp") == "acme"


def test_normalize_company_name_strips_gmbh() -> None:
    assert normalize_company_name("Startup GmbH") == "startup"


def test_normalize_company_name_no_suffix_unchanged() -> None:
    assert normalize_company_name("OpenAI") == "openai"


def test_normalize_company_name_multiple_words() -> None:
    assert normalize_company_name("Big Corp AG") == "big"


# ---------------------------------------------------------------------------
# normalize_job_title
# ---------------------------------------------------------------------------


def test_normalize_job_title_strips_senior() -> None:
    assert normalize_job_title("Senior Software Engineer") == "software engineer"


def test_normalize_job_title_strips_sr_abbreviation() -> None:
    assert normalize_job_title("Sr. Software Engineer") == "software engineer"


def test_normalize_job_title_strips_junior() -> None:
    assert normalize_job_title("Junior Backend Developer") == "backend developer"


def test_normalize_job_title_strips_lead() -> None:
    assert normalize_job_title("Lead Platform Engineer") == "platform engineer"


def test_normalize_job_title_strips_parenthesized_qualifier() -> None:
    result = normalize_job_title("Software Engineer (Senior)")
    assert "senior" not in result
    assert "software engineer" in result


def test_normalize_job_title_lowercases() -> None:
    assert normalize_job_title("Data Scientist") == "data scientist"


# ---------------------------------------------------------------------------
# _count_company_title_occurrences
# ---------------------------------------------------------------------------


def test_count_occurrences_zero_when_no_jobs(db_session: Session, profile: Profile) -> None:
    count = _count_company_title_occurrences(db_session, "Acme", "Software Engineer", profile.id)
    assert count == 0


def test_count_occurrences_matches_normalized_titles(db_session: Session, profile: Profile) -> None:
    # Insert one job with a "Senior" prefix — should normalize to same key
    _make_job(db_session, profile.id, title="Senior Software Engineer", company="Acme LLC")
    count = _count_company_title_occurrences(
        db_session, "Acme LLC", "Software Engineer", profile.id
    )
    assert count == 1


def test_count_occurrences_ignores_different_profile(db_session: Session, profile: Profile) -> None:
    # Insert a second profile and a job under it
    p2 = Profile(
        id=2, name="Other User", email="other@example.com", location="London", job_family="SWE"
    )
    db_session.add(p2)
    db_session.commit()
    _make_job(db_session, p2.id, title="Software Engineer", company="Acme")
    count = _count_company_title_occurrences(db_session, "Acme", "Software Engineer", profile.id)
    assert count == 0


def test_count_occurrences_respects_days_window(db_session: Session, profile: Profile) -> None:
    # Insert 3 jobs older than 90 days — each in a unique location to avoid dedup constraint
    for _ in range(3):
        _make_job(db_session, profile.id, title="Software Engineer", company="Acme", days_ago=100)
    count = _count_company_title_occurrences(
        db_session, "Acme", "Software Engineer", profile.id, days=90
    )
    assert count == 0


# ---------------------------------------------------------------------------
# _detect_ghost_job_signals — threshold logic
# ---------------------------------------------------------------------------


def test_ghost_detection_below_threshold(db_session: Session, profile: Profile) -> None:
    """2 occurrences in 90 days -> no flag."""
    for _ in range(2):
        _make_job(db_session, profile.id, title="Software Engineer", company="Acme")
    result = _detect_ghost_job_signals(db_session, "Acme", "Software Engineer", profile.id)
    assert result is None


def test_ghost_detection_caution_threshold(db_session: Session, profile: Profile) -> None:
    """3 occurrences in 90 days -> caution."""
    for _ in range(3):
        _make_job(db_session, profile.id, title="Software Engineer", company="Acme")
    result = _detect_ghost_job_signals(db_session, "Acme", "Software Engineer", profile.id)
    assert result is not None
    assert result["flag_type"] == "ghost_job"
    assert result["severity"] == "caution"


def test_ghost_detection_warning_threshold(db_session: Session, profile: Profile) -> None:
    """5 occurrences in 90 days -> warning."""
    for _ in range(5):
        _make_job(db_session, profile.id, title="Software Engineer", company="Acme")
    result = _detect_ghost_job_signals(db_session, "Acme", "Software Engineer", profile.id)
    assert result is not None
    assert result["flag_type"] == "ghost_job"
    assert result["severity"] == "warning"


def test_ghost_detection_outside_window(db_session: Session, profile: Profile) -> None:
    """5 occurrences but all >90 days ago -> no flag."""
    for _ in range(5):
        _make_job(db_session, profile.id, title="Software Engineer", company="Acme", days_ago=95)
    result = _detect_ghost_job_signals(db_session, "Acme", "Software Engineer", profile.id)
    assert result is None


def test_ghost_detection_normalizes_title_variants(db_session: Session, profile: Profile) -> None:
    """Sr. and Senior should both match the same base title."""
    titles = [
        "Software Engineer",
        "Senior Software Engineer",
        "Sr. Software Engineer",
    ]
    for t in titles:
        _make_job(db_session, profile.id, title=t, company="Acme")
    result = _detect_ghost_job_signals(db_session, "Acme", "Software Engineer", profile.id)
    assert result is not None
    assert result["flag_type"] == "ghost_job"


def test_ghost_detection_flag_has_required_fields(db_session: Session, profile: Profile) -> None:
    for _ in range(3):
        _make_job(db_session, profile.id, title="Product Manager", company="ACME Inc")
    result = _detect_ghost_job_signals(db_session, "ACME Inc", "Product Manager", profile.id)
    assert result is not None
    assert set(result.keys()) == {"flag_type", "severity", "description"}
    assert result["severity"] in {"info", "caution", "warning", "dealbreaker"}


# ---------------------------------------------------------------------------
# _detect_multi_city_blast
# ---------------------------------------------------------------------------

_BLAST_DESC = "A" * 250  # description longer than _DESC_PREFIX_LEN


def test_multi_city_blast_detection(db_session: Session, profile: Profile) -> None:
    """Same company, same description, 3+ locations -> info flag."""
    locations = ["Berlin, Germany", "Munich, Germany", "Hamburg, Germany"]
    for loc in locations:
        _make_job(db_session, profile.id, company="BigCo", location=loc, description=_BLAST_DESC)
    result = _detect_multi_city_blast(db_session, "BigCo", _BLAST_DESC, profile.id)
    assert result is not None
    assert result["flag_type"] == "multi_city_blast"
    assert result["severity"] == "info"


def test_multi_city_blast_different_descriptions(db_session: Session, profile: Profile) -> None:
    """Same company, different descriptions, 3+ locations -> no flag."""
    locations = ["Berlin, Germany", "Munich, Germany", "Hamburg, Germany"]
    for i, loc in enumerate(locations):
        _make_job(
            db_session,
            profile.id,
            company="BigCo",
            location=loc,
            description=f"Unique description number {i} " * 20,
        )
    result = _detect_multi_city_blast(db_session, "BigCo", "Different desc " * 20, profile.id)
    assert result is None


def test_multi_city_blast_below_threshold(db_session: Session, profile: Profile) -> None:
    """Same company, same description, only 2 locations -> no flag."""
    locations = ["Berlin, Germany", "Munich, Germany"]
    for loc in locations:
        _make_job(db_session, profile.id, company="BigCo", location=loc, description=_BLAST_DESC)
    result = _detect_multi_city_blast(db_session, "BigCo", _BLAST_DESC, profile.id)
    assert result is None


def test_multi_city_blast_empty_description(db_session: Session, profile: Profile) -> None:
    """Empty description -> no flag (cannot fingerprint)."""
    result = _detect_multi_city_blast(db_session, "BigCo", "", profile.id)
    assert result is None


def test_multi_city_blast_normalizes_company_name(db_session: Session, profile: Profile) -> None:
    """Company name variants should resolve to same normalized key."""
    locations = ["Berlin, Germany", "Munich, Germany", "Hamburg, Germany"]
    for loc in locations:
        # Insert under "BigCo GmbH" but query under "BigCo"
        _make_job(
            db_session, profile.id, company="BigCo GmbH", location=loc, description=_BLAST_DESC
        )
    result = _detect_multi_city_blast(db_session, "BigCo", _BLAST_DESC, profile.id)
    assert result is not None
    assert result["flag_type"] == "multi_city_blast"


# ---------------------------------------------------------------------------
# detect_data_driven_red_flags — public API
# ---------------------------------------------------------------------------


def test_detect_data_driven_no_flags_clean_job(db_session: Session, profile: Profile) -> None:
    """A single occurrence produces no flags."""
    _make_job(db_session, profile.id, title="Product Manager", company="CleanCo")
    flags = detect_data_driven_red_flags(
        db_session,
        company="CleanCo",
        title="Product Manager",
        description=_FILLER_DESC,
        profile_id=profile.id,
    )
    assert flags == []


def test_detect_data_driven_ghost_flag_appears(db_session: Session, profile: Profile) -> None:
    """3+ occurrences -> ghost_job flag in returned list."""
    for _ in range(3):
        _make_job(db_session, profile.id, title="Backend Engineer", company="GhostCo")
    flags = detect_data_driven_red_flags(
        db_session,
        company="GhostCo",
        title="Backend Engineer",
        description=_FILLER_DESC,
        profile_id=profile.id,
    )
    flag_types = [f["flag_type"] for f in flags]
    assert "ghost_job" in flag_types


def test_detect_data_driven_returns_list_of_dicts(db_session: Session, profile: Profile) -> None:
    """Return value is always a list; each item has the standard shape."""
    flags = detect_data_driven_red_flags(
        db_session,
        company="NoCo",
        title="Engineer",
        description=_FILLER_DESC,
        profile_id=profile.id,
    )
    assert isinstance(flags, list)
    for f in flags:
        assert set(f.keys()) == {"flag_type", "severity", "description"}


def test_ghost_flags_appear_in_scored_job(db_session: Session, profile: Profile) -> None:
    """Integration: ghost flags from detect_data_driven_red_flags merge correctly."""
    # Insert 3+ ghost job rows
    for _ in range(3):
        _make_job(db_session, profile.id, title="Product Manager", company="GhostCorp")

    ghost_flags = detect_data_driven_red_flags(
        db_session,
        company="GhostCorp",
        title="Product Manager",
        description=_FILLER_DESC,
        profile_id=profile.id,
    )

    # Simulate what score_job does: merge stateless + data-driven flags
    from career_os.services.red_flags import detect_red_flags

    stateless_flags = detect_red_flags(_FILLER_DESC)
    all_flags = stateless_flags + ghost_flags

    flag_types = {f["flag_type"] for f in all_flags}
    assert "ghost_job" in flag_types
