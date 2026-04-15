"""Tests for Epic 11 — Bayesian Preference Learning (G-279).

Covers:
- Beta distribution prior initialisation from weights
- Posterior updates for too_high, too_low, correct feedback
- No suggestions below SUGGESTION_MIN_FEEDBACK records
- Suggestions generated with sufficient feedback
- Suggestion confidence & delta thresholds
- Active query detection (borderline + high uncertainty)
- Active query disabled by default (feature flag)
- Weight ↔ dimension mapping correctness
- Integration test: profile + weights + 20 feedback records → suggestions API
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob, ScoringFeedback, ScoringWeights
from career_os.services.preference_learning import (
    BORDERLINE_HIGH,
    BORDERLINE_LOW,
    SUGGESTION_MIN_FEEDBACK,
    UNCERTAINTY_THRESHOLD,
    WEIGHT_TO_DIMENSION,
    BetaDistribution,
    PreferenceModel,
    build_preference_model,
    generate_suggestions,
    get_active_query_dimensions,
    should_active_query,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _record):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    Session_ = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = Session_()

    profile = Profile(
        id=1, name="Test User", email="test@example.com", location="Berlin", job_family="SWE"
    )
    session.add(profile)
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_weights(db: Session, *, profile_id: int = 1, **overrides) -> ScoringWeights:
    """Insert ScoringWeights and return it."""
    defaults = {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    }
    defaults.update(overrides)
    w = ScoringWeights(profile_id=profile_id, **defaults)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def _make_scored_job(
    db: Session,
    *,
    profile_id: int = 1,
    fit_score: float = 7.5,
    dim_technical_fit: float | None = 8.0,
    dim_seniority_alignment: float | None = 6.0,
    dim_compensation_fit: float | None = 7.0,
    dim_location_fit: float | None = 5.0,
    dim_career_trajectory: float | None = 7.5,
    dim_company_fit: float | None = 6.5,
) -> ScoredJob:
    """Insert a ScoredJob with dimensional scores."""
    sj = ScoredJob(
        profile_id=profile_id,
        fit_score=fit_score,
        readiness_score=60.0,
        career_alignment=7.0,
        reasoning="Test reasoning " * 10,
        estimated_salary="$120k–$150k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Prep notes here.",
        dim_technical_fit=dim_technical_fit,
        dim_seniority_alignment=dim_seniority_alignment,
        dim_compensation_fit=dim_compensation_fit,
        dim_location_fit=dim_location_fit,
        dim_career_trajectory=dim_career_trajectory,
        dim_company_fit=dim_company_fit,
    )
    db.add(sj)
    db.commit()
    db.refresh(sj)
    return sj


def _make_feedback(
    db: Session,
    scored_job_id: int,
    *,
    profile_id: int = 1,
    direction: str = "too_high",
    user_score: float | None = None,
) -> ScoringFeedback:
    """Insert a ScoringFeedback record."""
    sj = db.query(ScoredJob).filter(ScoredJob.id == scored_job_id).one()
    fb = ScoringFeedback(
        scored_job_id=scored_job_id,
        profile_id=profile_id,
        direction=direction,
        user_score=user_score,
        original_fit_score=sj.fit_score,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


# ---------------------------------------------------------------------------
# 1. Beta distribution prior initialisation
# ---------------------------------------------------------------------------


class TestBetaDistributionPrior:
    """Verify prior initialisation from configured weights."""

    def test_prior_from_default_weights(self, db_session):
        """Default weights produce symmetric priors (α = β) scaled by weight × 10."""
        weights = _make_weights(db_session)
        model = PreferenceModel.from_weights(weights)

        # skills_match = 0.25 → prior = 2.5
        dist = model.distributions["skills_match"]
        assert dist.alpha == pytest.approx(2.5)
        assert dist.beta == pytest.approx(2.5)

        # growth_potential = 0.10 → prior = max(1.0, 1.0) = 1.0
        dist_gp = model.distributions["growth_potential"]
        assert dist_gp.alpha == pytest.approx(1.0)
        assert dist_gp.beta == pytest.approx(1.0)

    def test_prior_mean_is_half(self, db_session):
        """All priors should have mean ≈ 0.5 (symmetric)."""
        weights = _make_weights(db_session)
        model = PreferenceModel.from_weights(weights)

        for name, dist in model.distributions.items():
            assert dist.mean == pytest.approx(0.5), f"{name} mean is not 0.5"

    def test_remote_preference_excluded(self, db_session):
        """remote_preference has no dimensional score — should not be in model."""
        weights = _make_weights(db_session)
        model = PreferenceModel.from_weights(weights)
        assert "remote_preference" not in model.distributions

    def test_minimum_prior_strength(self, db_session):
        """Even a very small weight (0.01) gets prior ≥ 1.0."""
        weights = _make_weights(db_session, skills_match=0.01)
        model = PreferenceModel.from_weights(weights)
        dist = model.distributions["skills_match"]
        assert dist.alpha >= 1.0
        assert dist.beta >= 1.0


# ---------------------------------------------------------------------------
# 2. Posterior update — too_high
# ---------------------------------------------------------------------------


class TestPosteriorTooHigh:
    """Feedback direction 'too_high' should increase β for high-scoring dims."""

    def test_beta_increases_on_too_high(self):
        """When a dimension scored high and user says too_high, β increases."""
        dist = BetaDistribution(alpha=2.5, beta=2.5)
        original_beta = dist.beta
        # Simulate high dim score (8.0 / 10 = 0.8)
        dist.update_too_high(0.8)
        assert dist.beta > original_beta
        assert dist.alpha == pytest.approx(2.5)  # α unchanged

    def test_mean_decreases_on_too_high(self):
        """Repeated too_high feedback should push the mean below 0.5."""
        dist = BetaDistribution(alpha=2.5, beta=2.5)
        for _ in range(10):
            dist.update_too_high(0.8)
        assert dist.mean < 0.5


# ---------------------------------------------------------------------------
# 3. Posterior update — too_low
# ---------------------------------------------------------------------------


class TestPosteriorTooLow:
    """Feedback direction 'too_low' should increase α for high-scoring dims."""

    def test_alpha_increases_on_too_low(self):
        """When user says too_low, α increases."""
        dist = BetaDistribution(alpha=2.5, beta=2.5)
        original_alpha = dist.alpha
        dist.update_too_low(0.8)
        assert dist.alpha > original_alpha
        assert dist.beta == pytest.approx(2.5)  # β unchanged

    def test_mean_increases_on_too_low(self):
        """Repeated too_low feedback should push the mean above 0.5."""
        dist = BetaDistribution(alpha=2.5, beta=2.5)
        for _ in range(10):
            dist.update_too_low(0.8)
        assert dist.mean > 0.5


# ---------------------------------------------------------------------------
# 4. Posterior update — correct
# ---------------------------------------------------------------------------


class TestPosteriorCorrect:
    """Feedback direction 'correct' reinforces both α and β slightly."""

    def test_both_increase_on_correct(self):
        dist = BetaDistribution(alpha=2.5, beta=2.5)
        orig_a, orig_b = dist.alpha, dist.beta
        dist.update_correct()
        assert dist.alpha > orig_a
        assert dist.beta > orig_b

    def test_mean_stays_near_half_on_correct(self):
        """Correct feedback shouldn't shift the mean significantly."""
        dist = BetaDistribution(alpha=2.5, beta=2.5)
        for _ in range(20):
            dist.update_correct()
        assert dist.mean == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# 5. No suggestions below threshold
# ---------------------------------------------------------------------------


def test_no_suggestions_below_threshold(db_session):
    """Returns empty list when fewer than SUGGESTION_MIN_FEEDBACK records exist."""
    _make_weights(db_session)
    sj = _make_scored_job(db_session)

    # Create feedback records below threshold
    for _ in range(SUGGESTION_MIN_FEEDBACK - 1):
        _make_feedback(db_session, sj.id, direction="too_high")

    suggestions = generate_suggestions(db_session, profile_id=1)
    assert suggestions == []


# ---------------------------------------------------------------------------
# 6. Suggestions generated with sufficient feedback
# ---------------------------------------------------------------------------


def test_suggestions_generated_with_enough_feedback(db_session):
    """With ≥15 consistent feedback records, suggestions are generated."""
    _make_weights(db_session)

    # Create jobs with high technical_fit but overall too_high feedback
    # This should suggest decreasing skills_match weight
    for _ in range(20):
        sj = _make_scored_job(
            db_session,
            fit_score=8.0,
            dim_technical_fit=9.0,  # high
            dim_seniority_alignment=3.0,  # low
            dim_compensation_fit=4.0,
            dim_location_fit=5.0,
            dim_career_trajectory=4.0,
            dim_company_fit=4.0,
        )
        _make_feedback(db_session, sj.id, direction="too_high")

    suggestions = generate_suggestions(db_session, profile_id=1)
    # Should have at least one suggestion
    assert len(suggestions) >= 1
    # All suggestions should have valid fields
    for s in suggestions:
        assert 0 <= s.current_weight <= 1
        assert 0 <= s.suggested_weight <= 1
        assert 0 <= s.confidence <= 1
        assert len(s.reason) > 0


# ---------------------------------------------------------------------------
# 7. Suggestion confidence threshold
# ---------------------------------------------------------------------------


def test_suggestion_confidence_threshold(db_session):
    """Low-confidence suggestions are filtered out."""
    _make_weights(db_session)

    # Mixed feedback — some too_high, some too_low — should produce lower
    # confidence and potentially no suggestions
    for i in range(SUGGESTION_MIN_FEEDBACK + 5):
        sj = _make_scored_job(db_session, fit_score=7.0)
        direction = "too_high" if i % 2 == 0 else "too_low"
        _make_feedback(db_session, sj.id, direction=direction)

    suggestions = generate_suggestions(db_session, profile_id=1)
    # All returned suggestions must meet the confidence threshold
    for s in suggestions:
        assert s.confidence >= 0.6, (
            f"Suggestion for {s.dimension} has low confidence {s.confidence}"
        )


# ---------------------------------------------------------------------------
# 8. Active query detection
# ---------------------------------------------------------------------------


class TestActiveQuery:
    """Active query should trigger only for borderline scores with uncertain dims."""

    def test_borderline_with_high_uncertainty(self):
        """Borderline score + uncertain dimension → should query."""
        model = PreferenceModel()
        # Create a distribution with high uncertainty
        model.distributions["skills_match"] = BetaDistribution(alpha=1.0, beta=1.0)
        assert model.distributions["skills_match"].variance > UNCERTAINTY_THRESHOLD

        assert should_active_query(5.0, model) is True

    def test_non_borderline_no_query(self):
        """Non-borderline score → no query even with uncertainty."""
        model = PreferenceModel()
        model.distributions["skills_match"] = BetaDistribution(alpha=1.0, beta=1.0)

        assert should_active_query(8.0, model) is False
        assert should_active_query(2.0, model) is False

    def test_borderline_low_uncertainty_no_query(self):
        """Borderline score but low uncertainty → no query."""
        model = PreferenceModel()
        # High α and β → low variance
        model.distributions["skills_match"] = BetaDistribution(alpha=100.0, beta=100.0)
        assert model.distributions["skills_match"].variance < UNCERTAINTY_THRESHOLD

        assert should_active_query(5.0, model) is False

    def test_borderline_edges(self):
        """Exact boundary values (4.5 and 5.5) are within the borderline band."""
        model = PreferenceModel()
        model.distributions["skills_match"] = BetaDistribution(alpha=1.0, beta=1.0)

        assert should_active_query(BORDERLINE_LOW, model) is True
        assert should_active_query(BORDERLINE_HIGH, model) is True

    def test_get_uncertain_dimensions(self):
        """get_active_query_dimensions returns only uncertain dimensions, sorted."""
        model = PreferenceModel()
        model.distributions["skills_match"] = BetaDistribution(alpha=1.0, beta=1.0)  # uncertain
        model.distributions["salary_match"] = BetaDistribution(alpha=100.0, beta=100.0)  # certain

        dims = get_active_query_dimensions(model)
        assert "skills_match" in dims
        assert "salary_match" not in dims


# ---------------------------------------------------------------------------
# 9. Active query disabled by default (feature flag)
# ---------------------------------------------------------------------------


def test_active_query_feature_flag_default():
    """ACTIVE_QUERY_ENABLED defaults to False."""
    from career_os.config import settings

    assert settings.active_query_enabled is False


# ---------------------------------------------------------------------------
# 10. Weight ↔ dimension mapping correctness
# ---------------------------------------------------------------------------


class TestWeightDimensionMapping:
    """Verify the mapping between weight names and dimensional score columns."""

    def test_all_weights_mapped(self):
        """All 7 weight dimensions are present in the mapping."""
        expected_weights = {
            "skills_match",
            "career_alignment",
            "culture_fit",
            "salary_match",
            "location_match",
            "growth_potential",
            "remote_preference",
        }
        assert set(WEIGHT_TO_DIMENSION.keys()) == expected_weights

    def test_six_dimensions_mapped(self):
        """6 of 7 weights map to dimensional score columns (remote_preference → None)."""
        mapped = {k: v for k, v in WEIGHT_TO_DIMENSION.items() if v is not None}
        assert len(mapped) == 6
        assert WEIGHT_TO_DIMENSION["remote_preference"] is None

    def test_dimension_columns_exist_on_scored_job(self):
        """All mapped dimension column names exist as attributes on ScoredJob."""
        for dim_col in WEIGHT_TO_DIMENSION.values():
            if dim_col is None:
                continue
            assert hasattr(ScoredJob, dim_col), f"ScoredJob missing column {dim_col}"

    def test_specific_mappings(self):
        """Verify the exact weight → dimension mappings."""
        assert WEIGHT_TO_DIMENSION["skills_match"] == "dim_technical_fit"
        assert WEIGHT_TO_DIMENSION["career_alignment"] == "dim_career_trajectory"
        assert WEIGHT_TO_DIMENSION["culture_fit"] == "dim_company_fit"
        assert WEIGHT_TO_DIMENSION["salary_match"] == "dim_compensation_fit"
        assert WEIGHT_TO_DIMENSION["location_match"] == "dim_location_fit"
        assert WEIGHT_TO_DIMENSION["growth_potential"] == "dim_seniority_alignment"


# ---------------------------------------------------------------------------
# 11. Build preference model end-to-end
# ---------------------------------------------------------------------------


def test_build_preference_model_no_feedback(db_session):
    """With no feedback, model stays at prior."""
    _make_weights(db_session)
    model = build_preference_model(db_session, profile_id=1)

    for name, dist in model.distributions.items():
        assert dist.mean == pytest.approx(0.5), f"{name} drifted from prior without feedback"


def test_build_preference_model_with_feedback(db_session):
    """Feedback shifts the model away from prior."""
    _make_weights(db_session)

    # Create 10 too_high feedback records with high technical fit
    for _ in range(10):
        sj = _make_scored_job(db_session, dim_technical_fit=9.0)
        _make_feedback(db_session, sj.id, direction="too_high")

    model = build_preference_model(db_session, profile_id=1)
    # skills_match (mapped to dim_technical_fit) should have mean < 0.5
    assert model.distributions["skills_match"].mean < 0.5


# ---------------------------------------------------------------------------
# 12. Integration test: full flow via API
# ---------------------------------------------------------------------------


def test_integration_suggestions_api(client, db_session):
    """Full flow: create profile + weights + 20 feedback records → GET suggestions."""
    _make_weights(db_session)

    # Create 20 consistent too_high feedback records
    for _ in range(20):
        sj = _make_scored_job(
            db_session,
            fit_score=8.0,
            dim_technical_fit=9.0,
            dim_seniority_alignment=3.0,
            dim_compensation_fit=4.0,
            dim_location_fit=5.0,
            dim_career_trajectory=4.0,
            dim_company_fit=4.0,
        )
        _make_feedback(db_session, sj.id, direction="too_high")

    resp = client.get("/api/score/suggestions", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()

    assert data["ready"] is True
    assert data["feedback_count"] == 20
    assert data["min_feedback_required"] == SUGGESTION_MIN_FEEDBACK
    assert len(data["suggestions"]) >= 1

    # Verify suggestion structure
    for s in data["suggestions"]:
        assert "dimension" in s
        assert "current_weight" in s
        assert "suggested_weight" in s
        assert "confidence" in s
        assert "reason" in s
        assert 0 <= s["confidence"] <= 1
        assert 0 <= s["suggested_weight"] <= 1


def test_integration_suggestions_not_ready(client, db_session):
    """Suggestions API returns ready=False when below threshold."""
    _make_weights(db_session)

    # Only 5 feedback records
    for _ in range(5):
        sj = _make_scored_job(db_session)
        _make_feedback(db_session, sj.id, direction="too_high")

    resp = client.get("/api/score/suggestions", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()

    assert data["ready"] is False
    assert data["feedback_count"] == 5
    assert data["suggestions"] == []


def test_integration_suggestions_correct_feedback(client, db_session):
    """Suggestions from mostly 'correct' feedback should produce few/no suggestions."""
    _make_weights(db_session)

    # 20 "correct" feedback records — should not shift preferences much
    for _ in range(20):
        sj = _make_scored_job(db_session)
        _make_feedback(db_session, sj.id, direction="correct")

    resp = client.get("/api/score/suggestions", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()

    assert data["ready"] is True
    # Correct feedback shouldn't produce large suggestions
    for s in data["suggestions"]:
        delta = abs(s["suggested_weight"] - s["current_weight"])
        assert delta < 0.1, f"Unexpected large suggestion for {s['dimension']}: delta={delta}"


# ---------------------------------------------------------------------------
# 13. Edge cases
# ---------------------------------------------------------------------------


def test_scored_job_missing_dimensions(db_session):
    """Feedback for scored jobs with None dimensions is handled gracefully."""
    _make_weights(db_session)

    for _ in range(SUGGESTION_MIN_FEEDBACK + 5):
        sj = _make_scored_job(
            db_session,
            dim_technical_fit=None,
            dim_seniority_alignment=None,
            dim_compensation_fit=None,
            dim_location_fit=None,
            dim_career_trajectory=None,
            dim_company_fit=None,
        )
        _make_feedback(db_session, sj.id, direction="too_high")

    # Should not raise, just no meaningful suggestions
    suggestions = generate_suggestions(db_session, profile_id=1)
    assert isinstance(suggestions, list)


def test_beta_distribution_edge_zero(self=None):
    """BetaDistribution handles zero alpha/beta gracefully."""
    dist = BetaDistribution(alpha=0.0, beta=0.0)
    assert dist.mean == 0.5  # safe default
    assert dist.variance == 0.0  # no variance when no data


def test_implicit_feedback_shifts_model(db_session):
    """Implicit feedback (positive/negative) also shifts the model."""
    _make_weights(db_session)

    # Create implicit_negative feedback (treated like too_high)
    for _ in range(SUGGESTION_MIN_FEEDBACK + 5):
        sj = _make_scored_job(db_session, dim_technical_fit=9.0)
        _make_feedback(db_session, sj.id, direction="implicit_negative")

    model = build_preference_model(db_session, profile_id=1)
    # implicit_negative is treated as too_high → skills_match mean < 0.5
    assert model.distributions["skills_match"].mean < 0.5
