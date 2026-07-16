"""Per-provider post-hoc score calibration (G-1337, finding G).

Cheap models score on their own idiosyncratic scale — DeepSeek/Mistral cluster
low, Qwen saturates high — so a raw ``fit_score`` is only comparable *within* one
model/run. This module fits a monotonic **raw → calibrated** map per provider from
already-labeled data (stored user corrections in ``ScoringFeedback`` or the golden
set), so cheap-model scores line up with the human/reference scale and stay
comparable across runs and providers.

Design:

* **Isotonic regression (PAV)** — a non-parametric, order-preserving fit. Pure
  Python (``math`` only in the hot path); no numpy/sklearn at runtime. scikit-learn
  is a dev-only test oracle (``tests/test_scoring_calibration.py`` cross-checks the
  fit against ``sklearn.isotonic.IsotonicRegression``). Isotonic is preferred over
  Platt here because the map must be **monotonic but not sigmoid-shaped** — a higher
  raw score must never calibrate lower, but we don't want to assume a logistic form.
* **Off by default.** Gated behind ``SCORING_CALIBRATION_ENABLED`` (default False),
  mirroring the opt-in convention of the existing feedback/preference infra
  (``FEEDBACK_CALIBRATION_ENABLED``, ``preference_learning``). Even when the flag is
  on, an unregistered provider calibrates to identity — so enabling the flag with no
  fitted map is a strict no-op.
* **No paid ops to fit.** Calibrators are fit from stored labels
  (``ScoringFeedback.original_fit_score`` → ``user_score``) or golden-set labels,
  never from live LLM calls.

The registry is process-local and starts empty; a caller (CLI / opt-in job) fits a
calibrator and registers it. ``apply_provider_calibration`` is the single hook the
scoring service calls.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Storage/display axis bounds — calibrated output is always clamped into range.
SCORE_MIN = 0.0
SCORE_MAX = 10.0

#: Minimum labeled pairs before a calibrator is fit. Below this the map would
#: overfit noise; the fitter returns None so the caller falls back to identity.
MIN_CALIBRATION_SAMPLES = 8


# ---------------------------------------------------------------------------
# Isotonic (PAV) calibrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IsotonicCalibrator:
    """A fitted monotonic raw → calibrated map (piecewise-linear interpolation).

    ``knot_x`` is non-decreasing and ``knot_y`` is non-decreasing (the isotonic
    constraint). :meth:`predict` linearly interpolates between knots, clips
    beyond the fitted range (flat extrapolation), and clamps to ``[0, 10]``.
    """

    knot_x: tuple[float, ...]
    knot_y: tuple[float, ...]

    def predict(self, raw_score: float) -> float:
        """Map a raw score to its calibrated value, clamped to ``[0, 10]``."""
        xs, ys = self.knot_x, self.knot_y
        if not xs:
            return _clamp(raw_score)
        if raw_score <= xs[0]:
            return _clamp(ys[0])
        if raw_score >= xs[-1]:
            return _clamp(ys[-1])
        # Binary-free linear scan is fine — knot sets are tiny (≤ label count).
        for i in range(1, len(xs)):
            if raw_score <= xs[i]:
                x0, x1 = xs[i - 1], xs[i]
                y0, y1 = ys[i - 1], ys[i]
                if x1 == x0:
                    return _clamp(y1)
                frac = (raw_score - x0) / (x1 - x0)
                return _clamp(y0 + frac * (y1 - y0))
        return _clamp(ys[-1])


def _clamp(value: float) -> float:
    """Clamp a score into the ``[SCORE_MIN, SCORE_MAX]`` display axis.

    A ``NaN`` input (unreachable via the current fit paths, but hardened here)
    collapses to :data:`SCORE_MIN` rather than silently passing through the
    ``max``/``min`` ordering as 10.0.
    """
    if math.isnan(value):
        return SCORE_MIN
    return max(SCORE_MIN, min(SCORE_MAX, value))


def fit_isotonic(raw: list[float], target: list[float]) -> IsotonicCalibrator | None:
    """Fit a non-decreasing isotonic map ``raw → target`` via pool-adjacent-violators.

    Ties in ``raw`` are averaged first (weighted), then PAV enforces monotonicity.
    Returns ``None`` when there are fewer than :data:`MIN_CALIBRATION_SAMPLES`
    pairs (too little signal to calibrate). Matches
    ``sklearn.isotonic.IsotonicRegression(out_of_bounds="clip")`` on the fitted knots.

    Raises ``ValueError`` on length mismatch.
    """
    if len(raw) != len(target):
        raise ValueError("raw and target must have equal length")
    if len(raw) < MIN_CALIBRATION_SAMPLES:
        return None

    # Sort by raw, aggregate ties (equal raw → mean target, accumulated weight).
    pairs = sorted(zip(raw, target, strict=True))
    xs: list[float] = []
    ys: list[float] = []
    ws: list[float] = []
    for x, y in pairs:
        if xs and xs[-1] == x:
            tot = ws[-1] + 1.0
            ys[-1] = (ys[-1] * ws[-1] + y) / tot
            ws[-1] = tot
        else:
            xs.append(x)
            ys.append(y)
            ws.append(1.0)

    # Pool-adjacent-violators: merge while the previous block mean violates the
    # non-decreasing constraint. Each block remembers its member x-positions so
    # the fitted value can be expanded per unique x for interpolation knots.
    blocks: list[dict] = []
    for x, y, w in zip(xs, ys, ws, strict=True):
        block = {"mean": y, "weight": w, "xs": [x]}
        while blocks and blocks[-1]["mean"] >= block["mean"]:
            prev = blocks.pop()
            tot = prev["weight"] + block["weight"]
            block = {
                "mean": (prev["mean"] * prev["weight"] + block["mean"] * block["weight"]) / tot,
                "weight": tot,
                "xs": prev["xs"] + block["xs"],
            }
        blocks.append(block)

    knot_x: list[float] = []
    knot_y: list[float] = []
    for block in blocks:
        for x in block["xs"]:
            knot_x.append(x)
            knot_y.append(block["mean"])

    return IsotonicCalibrator(knot_x=tuple(knot_x), knot_y=tuple(knot_y))


# ---------------------------------------------------------------------------
# Process-local registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, IsotonicCalibrator] = {}


def register_calibrator(provider_name: str, calibrator: IsotonicCalibrator) -> None:
    """Register a fitted calibrator for a provider (overwrites any existing)."""
    _REGISTRY[provider_name] = calibrator


def get_calibrator(provider_name: str) -> IsotonicCalibrator | None:
    """Return the registered calibrator for a provider, or None."""
    return _REGISTRY.get(provider_name)


def clear_calibrators() -> None:
    """Drop all registered calibrators (used by tests and re-fitting)."""
    _REGISTRY.clear()


def apply_provider_calibration(
    provider_name: str,
    raw_score: float,
    *,
    enabled: bool,
) -> float:
    """Return the calibrated ``fit_score`` for a provider, or ``raw_score`` unchanged.

    Identity (returns ``raw_score``) when ``enabled`` is False OR no calibrator is
    registered for ``provider_name`` — so enabling the flag without a fitted map is
    a strict no-op. This is the single hook the scoring service calls post-parse.
    """
    if not enabled:
        return raw_score
    calibrator = _REGISTRY.get(provider_name)
    if calibrator is None:
        return raw_score
    return calibrator.predict(raw_score)


# ---------------------------------------------------------------------------
# Fitting from stored labels (no paid ops) — reuses the feedback infra
# ---------------------------------------------------------------------------


def fit_from_feedback(db: Session, profile_id: int) -> IsotonicCalibrator | None:
    """Fit a calibrator from stored user corrections (``ScoringFeedback``).

    Reuses the existing feedback infra: pairs each ``original_fit_score`` (the raw
    AI score) with the user's ``user_score`` (the human target) for every explicit
    correction that carries a ``user_score``. Zero LLM calls — purely stored labels.
    Returns ``None`` when there are too few labeled corrections.
    """
    from career_os.models.scoring import ScoringFeedback

    rows = (
        db.query(ScoringFeedback.original_fit_score, ScoringFeedback.user_score)
        .filter(
            ScoringFeedback.profile_id == profile_id,
            ScoringFeedback.user_score.isnot(None),
        )
        .all()
    )
    if len(rows) < MIN_CALIBRATION_SAMPLES:
        return None
    raw = [float(r[0]) for r in rows]
    target = [float(r[1]) for r in rows]
    return fit_isotonic(raw, target)
