"""Tests for rule-based red flag detection (#73)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from career_os.services.red_flags import detect_red_flags

# A generic description used when a rule doesn't need real content.
_FILLER = "This is a normal software engineering role. " * 10


# ---------------------------------------------------------------------------
# Guard clauses
# ---------------------------------------------------------------------------


def test_empty_description_returns_no_flags() -> None:
    assert detect_red_flags("") == []
    assert detect_red_flags(None) == []


# ---------------------------------------------------------------------------
# stale_posting
# ---------------------------------------------------------------------------


def test_stale_posting_old_post_flags() -> None:
    old = datetime.now(UTC) - timedelta(days=90)
    flags = detect_red_flags(_FILLER, posted_at=old)
    types = [f["flag_type"] for f in flags]
    assert "stale_posting" in types


def test_stale_posting_recent_post_does_not_flag() -> None:
    recent = datetime.now(UTC) - timedelta(days=7)
    flags = detect_red_flags(_FILLER, posted_at=recent)
    types = [f["flag_type"] for f in flags]
    assert "stale_posting" not in types


def test_stale_posting_naive_datetime_is_normalized() -> None:
    naive = (datetime.now(UTC) - timedelta(days=90)).replace(tzinfo=None)
    flags = detect_red_flags(_FILLER, posted_at=naive)
    types = [f["flag_type"] for f in flags]
    assert "stale_posting" in types


# ---------------------------------------------------------------------------
# unrealistic_requirements
# ---------------------------------------------------------------------------


def test_unrealistic_requirements_10_years_plus_junior_title() -> None:
    desc = "Looking for a candidate with 10+ years of Python experience. " + _FILLER
    flags = detect_red_flags(desc, title="Junior Software Engineer")
    types = [f["flag_type"] for f in flags]
    assert "unrealistic_requirements" in types


def test_unrealistic_requirements_senior_title_ok() -> None:
    desc = "Looking for a candidate with 10+ years of Python experience. " + _FILLER
    flags = detect_red_flags(desc, title="Senior Principal Engineer")
    types = [f["flag_type"] for f in flags]
    # Senior title shouldn't match the junior+10yr rule; excessive skill
    # token rule may still pass since only one skill mentioned.
    assert "unrealistic_requirements" not in types


# ---------------------------------------------------------------------------
# turnover_language
# ---------------------------------------------------------------------------


def test_turnover_language_triggers_on_multiple_signals() -> None:
    desc = (
        "We are a fast-paced environment where you will wear many hats. "
        "We need someone who can hit the ground running and be a rockstar. "
    ) * 3
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "turnover_language" in types


def test_turnover_language_suppressed_when_work_life_mentioned() -> None:
    desc = (
        "We are a fast-paced environment where you will wear many hats. "
        "We prioritize work-life balance and offer flexible hours. "
    ) * 3
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "turnover_language" not in types


# ---------------------------------------------------------------------------
# missing_salary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("location", ["Boulder, CO", "San Francisco, CA", "Seattle, WA"])
def test_missing_salary_in_mandate_state(location: str) -> None:
    flags = detect_red_flags(_FILLER, salary_range=None, location=location)
    types = [f["flag_type"] for f in flags]
    assert "missing_salary" in types


def test_missing_salary_with_salary_present_not_flagged() -> None:
    flags = detect_red_flags(_FILLER, salary_range="$120k-$150k", location="Boulder, CO")
    types = [f["flag_type"] for f in flags]
    assert "missing_salary" not in types


def test_missing_salary_outside_mandate_states_not_flagged() -> None:
    flags = detect_red_flags(_FILLER, salary_range=None, location="Austin, TX")
    types = [f["flag_type"] for f in flags]
    assert "missing_salary" not in types


# ---------------------------------------------------------------------------
# staffing_agency
# ---------------------------------------------------------------------------


def test_staffing_agency_keyword_triggers() -> None:
    desc = "We are a staffing agency hiring on behalf of our client. " + _FILLER
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "staffing_agency" in types


def test_staffing_agency_contract_to_hire_triggers() -> None:
    desc = "This is a contract-to-hire position. " + _FILLER
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "staffing_agency" in types


def test_staffing_agency_regular_direct_hire_not_flagged() -> None:
    desc = "Full-time direct hire at a product company. " + _FILLER
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "staffing_agency" not in types


# ---------------------------------------------------------------------------
# vague_responsibilities
# ---------------------------------------------------------------------------


def test_vague_responsibilities_short_description() -> None:
    desc = "Looking for a candidate."
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "vague_responsibilities" in types


def test_vague_responsibilities_150_chars_triggers() -> None:
    """A 150-char description is well below the 400-char threshold and should trigger."""
    desc = "We need a developer to work on stuff. " * 4  # ~148 chars
    assert len(desc.strip()) < 400
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "vague_responsibilities" in types


def test_vague_responsibilities_250_chars_triggers() -> None:
    """250 chars is below the new 400-char threshold, so it triggers."""
    desc = "We are looking for a software engineer to join our team. " * 5  # ~285 chars
    assert 200 < len(desc.strip()) < 400
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "vague_responsibilities" in types


def test_vague_responsibilities_350_chars_triggers() -> None:
    """350 chars is still below the 400-char threshold, so it triggers."""
    desc = (
        "Join our engineering team to build scalable backend services. "
        "You will design APIs, write tests, and collaborate with product managers. "
        "We use Python, FastAPI, and PostgreSQL in our technology stack. "
        "Strong communication skills are a must for this hybrid role based in Berlin. "
        "We offer competitive pay, equity packages, and comprehensive benefits globally. "
    )
    assert 300 < len(desc) < 400
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "vague_responsibilities" in types


def test_vague_responsibilities_bullet_ratio_triggers_on_long_desc() -> None:
    """A 450+ char description with >50% vague bullets should trigger via bullet-ratio path."""
    vague_lines = [
        "- Other duties as assigned",
        "- Various tasks as needed",
        "- Support the team as needed",
        "- Help with daily operations",
        "- Assist with ongoing projects",
    ]
    specific_lines = [
        "- Build REST APIs using Python and FastAPI",
        "- Write unit tests with pytest",
    ]
    desc = (
        "We are hiring a software engineer for our platform team. "
        "This is a full-time position based in our Berlin office.\n"
        + "\n".join(vague_lines + specific_lines)
        + "\nApply today to join our growing company and make an impact on millions of users."
    )
    assert len(desc) > 400
    flags = detect_red_flags(desc)
    types = [f["flag_type"] for f in flags]
    assert "vague_responsibilities" in types


def test_vague_responsibilities_normal_length_not_flagged() -> None:
    flags = detect_red_flags(_FILLER)
    types = [f["flag_type"] for f in flags]
    assert "vague_responsibilities" not in types


# ---------------------------------------------------------------------------
# excessive_requirements
# ---------------------------------------------------------------------------


def test_excessive_requirements_many_skills() -> None:
    desc = (
        "Must know: Python, Java, JavaScript, TypeScript, Go, Rust, React, Angular, "
        "Vue, Django, FastAPI, PostgreSQL, MongoDB, Redis, Kafka, Docker, Kubernetes, "
        "AWS, GCP, Terraform. " + _FILLER
    )
    flags = detect_red_flags(desc, title="Senior Engineer")
    types = [f["flag_type"] for f in flags]
    # Either excessive_requirements or the combined unrealistic_requirements
    # rule should fire on this description.
    assert "excessive_requirements" in types or "unrealistic_requirements" in types


def test_excessive_requirements_few_skills_ok() -> None:
    desc = "Looking for a Python developer with Django experience. " + _FILLER
    flags = detect_red_flags(desc, title="Senior Python Engineer")
    types = [f["flag_type"] for f in flags]
    assert "excessive_requirements" not in types


# ---------------------------------------------------------------------------
# Combined — multiple rules fire together
# ---------------------------------------------------------------------------


def test_multiple_flags_combine() -> None:
    old = datetime.now(UTC) - timedelta(days=120)
    desc = (
        "Contract-to-hire staffing agency role. "
        "Must have 10+ years experience in everything. "
        "This is a fast-paced environment where you wear many hats. "
        "Rockstar ninja needed. " + _FILLER
    )
    flags = detect_red_flags(
        desc,
        posted_at=old,
        title="Junior Developer",
        salary_range=None,
        location="Denver, CO",
    )
    types = {f["flag_type"] for f in flags}
    expected = {
        "stale_posting",
        "staffing_agency",
        "missing_salary",
        "unrealistic_requirements",
        "turnover_language",
    }
    assert expected.issubset(types), f"missing flags: {expected - types}"


def test_all_flags_have_required_fields() -> None:
    old = datetime.now(UTC) - timedelta(days=120)
    flags = detect_red_flags(
        "Contract-to-hire. " + _FILLER,
        posted_at=old,
        title="Developer",
        salary_range=None,
        location="Los Angeles, CA",
    )
    assert len(flags) >= 1
    for f in flags:
        assert set(f.keys()) == {"flag_type", "severity", "description"}
        assert f["severity"] in {"info", "caution", "warning", "dealbreaker"}
