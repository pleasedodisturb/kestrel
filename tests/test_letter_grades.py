"""Tests for the letter-grade helper and ScoreResponse integration (#71)."""

from __future__ import annotations

import pytest

from career_os.schemas.ai import ScoreBreakdownFactor
from career_os.schemas.scoring import ScoreResponse, score_to_letter_grade


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "F"),
        (2.9, "F"),
        (3.0, "D"),
        (3.9, "D"),
        (4.0, "C"),
        (4.9, "C"),
        (5.0, "C+"),
        (5.9, "C+"),
        (6.0, "B"),
        (6.9, "B"),
        (7.0, "B+"),
        (7.9, "B+"),
        (8.0, "A-"),
        (8.9, "A-"),
        (9.0, "A"),
        (10.0, "A"),
    ],
)
def test_score_to_letter_grade_boundaries(score: float, expected: str) -> None:
    assert score_to_letter_grade(score) == expected


def test_score_to_letter_grade_none() -> None:
    assert score_to_letter_grade(None) is None


def test_score_response_populates_letter_grade_after_validation() -> None:
    """ScoreResponse should auto-populate letter_grade from fit_score."""
    breakdown = [
        ScoreBreakdownFactor(factor="skills", contribution=2.5, description="Strong match"),
        ScoreBreakdownFactor(factor="culture", contribution=1.5, description="Good culture"),
        ScoreBreakdownFactor(factor="location", contribution=1.0, description="Remote friendly"),
    ]
    response = ScoreResponse(
        profile_id=1,
        fit_score=8.5,
        readiness_score=75.0,
        career_alignment=8.0,
        score_breakdown=breakdown,
        reasoning="a" * 120,
        estimated_salary="$120k-$140k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Brush up on system design.",
    )
    assert response.letter_grade == "A-"


def test_score_response_letter_grade_for_low_score() -> None:
    """Make sure a below-3 fit_score maps to F."""
    breakdown = [
        ScoreBreakdownFactor(factor="skills", contribution=-1.0, description="Big gap"),
        ScoreBreakdownFactor(factor="culture", contribution=-0.5, description="Mismatch"),
        ScoreBreakdownFactor(factor="location", contribution=-0.5, description="Far"),
    ]
    response = ScoreResponse(
        profile_id=1,
        fit_score=2.0,
        readiness_score=30.0,
        career_alignment=2.0,
        score_breakdown=breakdown,
        reasoning="a" * 120,
        estimated_salary="$60k-$70k",
        effort_flag="high",
        prep_level="intensive",
        prep_notes="Lots of prep needed.",
    )
    assert response.letter_grade == "F"


def test_score_response_respects_explicit_letter_grade() -> None:
    """Callers can override letter_grade; validator should not clobber it."""
    breakdown = [
        ScoreBreakdownFactor(factor="skills", contribution=2.0, description="Good"),
        ScoreBreakdownFactor(factor="culture", contribution=1.0, description="Ok"),
        ScoreBreakdownFactor(factor="location", contribution=1.0, description="Ok"),
    ]
    response = ScoreResponse(
        profile_id=1,
        fit_score=8.5,
        readiness_score=70.0,
        career_alignment=7.0,
        letter_grade="OVERRIDE",
        score_breakdown=breakdown,
        reasoning="a" * 120,
        estimated_salary="$100k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Notes.",
    )
    assert response.letter_grade == "OVERRIDE"
