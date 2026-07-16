"""Tests for the 0-5 → 0-10 dimensional-scale bridge (G-1337, finding E).

Covers the pure scaler (`scale_dimensions_to_display`), the ScoreResult wrapper
(`scale_score_result_dimensions`), the real single-scorer parse boundary
(`_try_parse_structured`), and the batch parse path (`parse_batch_response`) —
plus the invariants that (a) top-level fit_score/desire_score/career_alignment are
never touched, and (b) a single out-of-range dimension does not flip the whole set
to half-scale (WARNING 3 robustness).
"""

from __future__ import annotations

import json

import pytest

from career_os.schemas.ai import (
    DIMENSION_LEGACY_TEN_SCALE_MIN_SIGNALS,
    DIMENSION_SCALE_FACTOR,
    AIFeature,
    DimensionalScores,
    ScoreResult,
    scale_dimensions_to_display,
    scale_score_result_dimensions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dims(**overrides: float) -> DimensionalScores:
    base = dict(
        technical_fit=3.0,
        seniority_alignment=2.5,
        compensation_fit=4.0,
        location_fit=5.0,
        career_trajectory=1.0,
        company_fit=0.0,
    )
    base.update(overrides)
    return DimensionalScores(**base)


def _score_json(dims: dict, *, fit_score: float = 7.5, desire_score: float = 6.0) -> str:
    return json.dumps(
        {
            "fit_score": fit_score,
            "reasoning": "x" * 120,
            "estimated_salary": "120k EUR",
            "effort_flag": "medium",
            "prep_level": "moderate",
            "prep_notes": "Study X.",
            "readiness_score": 72.0,
            "career_alignment": 8.0,
            "score_breakdown": [
                {"factor": "a", "contribution": 2.0, "description": "d"},
                {"factor": "b", "contribution": 1.5, "description": "d"},
                {"factor": "c", "contribution": -0.5, "description": "d"},
            ],
            "dimensional_scores": dims,
            "desire_score": desire_score,
            "desire_reasoning": "y",
        }
    )


# ---------------------------------------------------------------------------
# scale_dimensions_to_display — the pure scaler
# ---------------------------------------------------------------------------


def test_scale_factor_is_two():
    assert DIMENSION_SCALE_FACTOR == 2.0


def test_all_zero_to_five_scaled_by_two():
    out = scale_dimensions_to_display(_dims())
    assert out.technical_fit == pytest.approx(6.0)  # 3 → 6
    assert out.seniority_alignment == pytest.approx(5.0)  # 2.5 → 5
    assert out.compensation_fit == pytest.approx(8.0)  # 4 → 8
    assert out.location_fit == pytest.approx(10.0)  # 5 → 10 (boundary)
    assert out.career_trajectory == pytest.approx(2.0)  # 1 → 2
    assert out.company_fit == pytest.approx(0.0)  # 0 → 0


def test_boundary_five_maps_to_ten():
    out = scale_dimensions_to_display(_dims(technical_fit=5.0))
    assert out.technical_fit == pytest.approx(10.0)


def test_single_outlier_does_not_flip_to_legacy():
    """One dim slightly over 5 → still scaled (clamped to 5 first), others ×2."""
    out = scale_dimensions_to_display(_dims(technical_fit=6.0, seniority_alignment=2.0))
    # The outlier is clamped to 5 then scaled → 10, NOT left at 6.
    assert out.technical_fit == pytest.approx(10.0)
    # The other dims are still scaled ×2 (NOT halved by a legacy flip).
    assert out.seniority_alignment == pytest.approx(4.0)
    assert out.compensation_fit == pytest.approx(8.0)


def test_two_signals_flip_to_legacy_clamp_not_scale():
    """≥2 dims over 5 → treated as legacy 0-10; clamp into range, do NOT scale."""
    assert DIMENSION_LEGACY_TEN_SCALE_MIN_SIGNALS == 2
    out = scale_dimensions_to_display(_dims(technical_fit=8.0, seniority_alignment=6.0))
    assert out.technical_fit == pytest.approx(8.0)  # unchanged
    assert out.seniority_alignment == pytest.approx(6.0)  # unchanged
    assert out.location_fit == pytest.approx(5.0)  # unchanged (was 5, not scaled)


def test_schema_bounds_inputs_so_scaler_never_sees_out_of_range():
    """DimensionalScores enforces [0, 10], so the scaler's clamp is belt-and-braces.

    This documents why negative / >10 inputs are unreachable: Pydantic rejects
    them before they can reach scale_dimensions_to_display.
    """
    with pytest.raises(ValueError):
        _dims(technical_fit=12.0)
    with pytest.raises(ValueError):
        _dims(company_fit=-1.0)


def test_output_always_within_display_axis():
    """Every valid input produces output inside [0, 10]."""
    for tf in (0.0, 2.5, 5.0, 7.0, 9.9, 10.0):
        out = scale_dimensions_to_display(_dims(technical_fit=tf))
        assert 0.0 <= out.technical_fit <= 10.0


def test_scaler_is_pure_no_mutation():
    original = _dims()
    snapshot = original.model_copy(deep=True)
    scale_dimensions_to_display(original)
    assert original == snapshot


# ---------------------------------------------------------------------------
# scale_score_result_dimensions — the ScoreResult wrapper
# ---------------------------------------------------------------------------


def _score_result(dims: DimensionalScores | None) -> ScoreResult:
    return ScoreResult(
        fit_score=7.5,
        reasoning="x" * 120,
        estimated_salary="1",
        effort_flag="low",
        prep_level="a",
        prep_notes="b",
        readiness_score=50.0,
        career_alignment=8.0,
        score_breakdown=[
            {"factor": "a", "contribution": 1.0, "description": "d"},
            {"factor": "b", "contribution": 1.0, "description": "d"},
            {"factor": "c", "contribution": 1.0, "description": "d"},
        ],
        dimensional_scores=dims,
        desire_score=6.0,
        desire_reasoning="y",
    )


def test_wrapper_none_dims_is_noop():
    r = _score_result(None)
    out = scale_score_result_dimensions(r)
    assert out.dimensional_scores is None
    assert out is r  # unchanged reference


def test_wrapper_scales_dims():
    out = scale_score_result_dimensions(_score_result(_dims(technical_fit=3.0)))
    assert out.dimensional_scores.technical_fit == pytest.approx(6.0)


def test_wrapper_never_touches_top_level_scores():
    """fit_score / desire_score / career_alignment must be invariant under scaling."""
    r = _score_result(_dims())
    out = scale_score_result_dimensions(r)
    assert out.fit_score == pytest.approx(7.5)
    assert out.desire_score == pytest.approx(6.0)
    assert out.career_alignment == pytest.approx(8.0)
    assert out.readiness_score == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Real single-scorer parse boundary — _try_parse_structured
# ---------------------------------------------------------------------------


def test_parse_boundary_scales_zero_to_five_dims():
    from career_os.ai.openrouter_provider import _try_parse_structured

    dims = {
        "technical_fit": 3.0,
        "seniority_alignment": 2.0,
        "compensation_fit": 4.0,
        "location_fit": 5.0,
        "career_trajectory": 1.0,
        "company_fit": 2.5,
    }
    result = _try_parse_structured(_score_json(dims), AIFeature.score)
    assert isinstance(result, ScoreResult)
    # Dims scaled ×2.
    assert result.dimensional_scores.technical_fit == pytest.approx(6.0)
    assert result.dimensional_scores.location_fit == pytest.approx(10.0)
    assert result.dimensional_scores.company_fit == pytest.approx(5.0)
    # Top-level axes untouched.
    assert result.fit_score == pytest.approx(7.5)
    assert result.desire_score == pytest.approx(6.0)


def test_parse_boundary_legacy_detection():
    from career_os.ai.openrouter_provider import _try_parse_structured

    dims = {
        "technical_fit": 9.0,
        "seniority_alignment": 8.0,  # 2 signals >5 → legacy
        "compensation_fit": 4.0,
        "location_fit": 3.0,
        "career_trajectory": 2.0,
        "company_fit": 1.0,
    }
    result = _try_parse_structured(_score_json(dims), AIFeature.score)
    assert result.dimensional_scores.technical_fit == pytest.approx(9.0)  # not scaled
    assert result.dimensional_scores.compensation_fit == pytest.approx(4.0)  # not scaled


def test_parse_boundary_no_dims_is_noop():
    from career_os.ai.openrouter_provider import _try_parse_structured

    payload = json.loads(_score_json({"technical_fit": 3.0} | _dims().model_dump()))
    del payload["dimensional_scores"]
    result = _try_parse_structured(json.dumps(payload), AIFeature.score)
    assert result.dimensional_scores is None
    assert result.fit_score == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# Batch parse path — parse_batch_response (unified to 0-5, WARNING 4)
# ---------------------------------------------------------------------------


def test_batch_parse_scales_dims():
    from career_os.services.batch_scoring import parse_batch_response

    item = json.loads(
        _score_json(
            {
                "technical_fit": 3.0,
                "seniority_alignment": 2.0,
                "compensation_fit": 4.0,
                "location_fit": 5.0,
                "career_trajectory": 1.0,
                "company_fit": 2.5,
            }
        )
    )
    item["job_id"] = "job-1"
    content = json.dumps([item])
    results = parse_batch_response(content, ["job-1"])
    assert "job-1" in results
    dims = results["job-1"].dimensional_scores
    assert dims.technical_fit == pytest.approx(6.0)  # 3 → 6
    assert dims.location_fit == pytest.approx(10.0)  # 5 → 10
    # Top-level axis untouched.
    assert results["job-1"].fit_score == pytest.approx(7.5)
