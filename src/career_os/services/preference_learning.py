"""Bayesian Preference Learning — Epic 11 (G-279).

Maintains per-dimension Beta distributions updated from user feedback,
generates weight adjustment suggestions, and selects active queries
for borderline scores.

The preference model is computed on-the-fly from existing ScoringFeedback
and ScoredJob records — no new tables required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from career_os.models.scoring import ScoredJob, ScoringFeedback, ScoringWeights
from career_os.services.scoring import get_or_create_weights

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum feedback records before suggestions are generated.
SUGGESTION_MIN_FEEDBACK = 15

#: Minimum confidence to include a suggestion in results.
SUGGESTION_MIN_CONFIDENCE = 0.6

#: Minimum absolute weight delta to consider a suggestion meaningful.
SUGGESTION_MIN_DELTA = 0.03

#: Learning rate for Bayesian updates (controls how much each feedback record
#: shifts the posterior).  Smaller = slower adaptation, more stability.
LEARNING_RATE = 0.5

#: Fit-score band considered "borderline" for active query selection.
BORDERLINE_LOW = 4.5
BORDERLINE_HIGH = 5.5

#: Uncertainty threshold (variance of Beta distribution) above which a
#: dimension is considered "uncertain enough" to benefit from a query.
UNCERTAINTY_THRESHOLD = 0.02

# ---------------------------------------------------------------------------
# Dimension ↔ Weight mapping
# ---------------------------------------------------------------------------

#: Maps ScoringWeights attribute names to ScoredJob dimensional column names.
WEIGHT_TO_DIMENSION: dict[str, str | None] = {
    "skills_match": "dim_technical_fit",
    "career_alignment": "dim_career_trajectory",
    "culture_fit": "dim_company_fit",
    "salary_match": "dim_compensation_fit",
    "location_match": "dim_location_fit",
    "growth_potential": "dim_seniority_alignment",
    "remote_preference": None,  # no direct dimensional score
}

#: Reverse mapping for convenience.
DIMENSION_TO_WEIGHT: dict[str, str] = {
    v: k for k, v in WEIGHT_TO_DIMENSION.items() if v is not None
}


# ---------------------------------------------------------------------------
# Beta distribution helpers
# ---------------------------------------------------------------------------


@dataclass
class BetaDistribution:
    """Parameterisation of a Beta(α, β) distribution."""

    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        """Expected value of the distribution."""
        total = self.alpha + self.beta
        if total == 0:
            return 0.5
        return self.alpha / total

    @property
    def variance(self) -> float:
        """Variance of the distribution."""
        a, b = self.alpha, self.beta
        total = a + b
        if total == 0 or total + 1 == 0:
            return 0.0
        return (a * b) / (total * total * (total + 1))

    def update_too_high(self, dim_score_normalised: float) -> None:
        """User says overall score was too high — dimension may be overvalued.

        If the dimension scored high for this job, increase β (evidence that
        the dimension contributed to an inflated score).
        """
        self.beta += LEARNING_RATE * dim_score_normalised

    def update_too_low(self, dim_score_normalised: float) -> None:
        """User says overall score was too low — dimension may be undervalued.

        If the dimension scored high for this job but the user thought the
        overall score should be higher, increase α (evidence that the
        dimension is more important than the weight suggests).
        """
        self.alpha += LEARNING_RATE * dim_score_normalised

    def update_correct(self) -> None:
        """User confirms the score was correct — reinforce both α and β slightly."""
        self.alpha += LEARNING_RATE * 0.1
        self.beta += LEARNING_RATE * 0.1


@dataclass
class PreferenceModel:
    """Per-profile Bayesian preference model.

    Each dimension has its own Beta distribution whose prior is derived
    from the user's configured weight.
    """

    distributions: dict[str, BetaDistribution] = field(default_factory=dict)

    @classmethod
    def from_weights(cls, weights: ScoringWeights) -> PreferenceModel:
        """Initialise priors from the user's configured scoring weights.

        Higher configured weight → stronger prior (α₀ = β₀ = weight × 10).
        """
        model = cls()
        for weight_name, dim_col in WEIGHT_TO_DIMENSION.items():
            if dim_col is None:
                continue  # skip remote_preference — no dimensional score
            weight_val = getattr(weights, weight_name)
            # Prior strength proportional to weight (minimum 1.0 to avoid
            # degenerate distributions).
            prior = max(weight_val * 10, 1.0)
            model.distributions[weight_name] = BetaDistribution(alpha=prior, beta=prior)
        return model

    def update_from_feedback(
        self,
        direction: str,
        scored_job: ScoredJob,
    ) -> None:
        """Update posteriors based on a single feedback record."""
        for weight_name, dist in self.distributions.items():
            dim_col = WEIGHT_TO_DIMENSION.get(weight_name)
            if dim_col is None:
                continue
            raw_dim = getattr(scored_job, dim_col, None)
            if raw_dim is None:
                continue
            # Normalise 0-10 to 0-1
            dim_normalised = raw_dim / 10.0

            if direction == "too_high":
                dist.update_too_high(dim_normalised)
            elif direction == "too_low":
                dist.update_too_low(dim_normalised)
            elif direction == "correct" or direction in (
                "implicit_positive",
                "implicit_strong_positive",
            ):
                dist.update_correct()
            elif direction == "implicit_negative":
                dist.update_too_high(dim_normalised)


# ---------------------------------------------------------------------------
# Suggestion data class
# ---------------------------------------------------------------------------


@dataclass
class WeightSuggestion:
    """A single weight adjustment suggestion."""

    dimension: str
    current_weight: float
    suggested_weight: float
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "current_weight": round(self.current_weight, 4),
            "suggested_weight": round(self.suggested_weight, 4),
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Core service functions
# ---------------------------------------------------------------------------


def build_preference_model(db: Session, profile_id: int) -> PreferenceModel:
    """Build the full posterior preference model for a profile.

    Starts from the user's configured weights as prior, then replays
    all feedback records in chronological order to produce the posterior.
    """
    weights = get_or_create_weights(db, profile_id)
    model = PreferenceModel.from_weights(weights)

    # Load feedback with their scored jobs (need dimensional scores)
    feedback_records = (
        db.query(ScoringFeedback)
        .filter(ScoringFeedback.profile_id == profile_id)
        .order_by(ScoringFeedback.created_at.asc())
        .all()
    )

    # Pre-load scored jobs to avoid N+1
    scored_job_ids = {fb.scored_job_id for fb in feedback_records}
    if scored_job_ids:
        scored_jobs = db.query(ScoredJob).filter(ScoredJob.id.in_(scored_job_ids)).all()
        scored_job_map = {sj.id: sj for sj in scored_jobs}
    else:
        scored_job_map = {}

    for fb in feedback_records:
        sj = scored_job_map.get(fb.scored_job_id)
        if sj is None:
            continue
        model.update_from_feedback(fb.direction, sj)

    return model


def generate_suggestions(
    db: Session,
    profile_id: int,
) -> list[WeightSuggestion]:
    """Generate weight adjustment suggestions based on accumulated feedback.

    Returns an empty list if fewer than SUGGESTION_MIN_FEEDBACK records exist.
    """
    feedback_count = (
        db.query(ScoringFeedback).filter(ScoringFeedback.profile_id == profile_id).count()
    )
    if feedback_count < SUGGESTION_MIN_FEEDBACK:
        return []

    weights = get_or_create_weights(db, profile_id)
    model = build_preference_model(db, profile_id)

    suggestions: list[WeightSuggestion] = []

    for weight_name, dist in model.distributions.items():
        current_weight = getattr(weights, weight_name)
        # The Beta mean represents the learned preference for this dimension.
        # Map it back to a weight suggestion by scaling relative to the prior mean (0.5).
        posterior_mean = dist.mean

        # Confidence is inversely related to variance — lower variance = higher confidence.
        # Use 1 - normalised_variance, where we cap variance contribution.
        confidence = 1.0 - min(dist.variance / 0.05, 1.0)

        # If posterior mean > 0.5, the user values this dimension more than the prior;
        # if < 0.5, they value it less.
        # Scale the delta proportionally to the current weight.
        shift = (posterior_mean - 0.5) * 2.0  # range: -1 to +1
        suggested_weight = current_weight + shift * current_weight * 0.5
        # Clamp to valid range
        suggested_weight = max(0.01, min(1.0, suggested_weight))

        delta = abs(suggested_weight - current_weight)

        if confidence < SUGGESTION_MIN_CONFIDENCE:
            continue
        if delta < SUGGESTION_MIN_DELTA:
            continue

        # Build human-readable reason
        if suggested_weight > current_weight:
            reason = (
                f"You consistently rate jobs higher than the AI when "
                f"{_human_name(weight_name)} is strong — consider increasing this weight"
            )
        else:
            reason = (
                f"You tend to dismiss jobs the AI scored highly on "
                f"{_human_name(weight_name)} — consider decreasing this weight"
            )

        suggestions.append(
            WeightSuggestion(
                dimension=weight_name,
                current_weight=current_weight,
                suggested_weight=round(suggested_weight, 4),
                confidence=round(confidence, 4),
                reason=reason,
            )
        )

    # Sort by confidence descending
    suggestions.sort(key=lambda s: s.confidence, reverse=True)
    return suggestions


def should_active_query(
    fit_score: float,
    model: PreferenceModel,
) -> bool:
    """Determine whether an active query should be presented to the user.

    Conditions (all must be true):
    1. fit_score is in the borderline band (4.5–5.5)
    2. At least one dimension has high uncertainty (variance > threshold)

    This function does NOT check the feature flag — the caller is responsible
    for gating on ACTIVE_QUERY_ENABLED.
    """
    if not (BORDERLINE_LOW <= fit_score <= BORDERLINE_HIGH):
        return False

    return any(dist.variance > UNCERTAINTY_THRESHOLD for dist in model.distributions.values())


def get_active_query_dimensions(model: PreferenceModel) -> list[str]:
    """Return the dimension names with the highest uncertainty.

    Useful for telling the user which aspects of the job to focus feedback on.
    """
    uncertain = [
        (name, dist.variance)
        for name, dist in model.distributions.items()
        if dist.variance > UNCERTAINTY_THRESHOLD
    ]
    uncertain.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in uncertain]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_HUMAN_NAMES: dict[str, str] = {
    "skills_match": "technical fit",
    "career_alignment": "career trajectory",
    "culture_fit": "company/culture fit",
    "salary_match": "compensation fit",
    "location_match": "location fit",
    "growth_potential": "seniority/growth alignment",
    "remote_preference": "remote preference",
}


def _human_name(weight_name: str) -> str:
    """Return a human-readable label for a weight dimension."""
    return _HUMAN_NAMES.get(weight_name, weight_name.replace("_", " "))
