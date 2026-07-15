"""Scoring drift canary — guard against silent score rot.

Scoring Engine v2 (G-1336, finding J). A provider can swap the model behind an
OpenRouter slug with zero code change on our side and quietly rot every score.
The canary catches that by watching two independent signals and paging **only
when both move together** (so a benign shift in the day's job mix never wakes
anyone):

1. **PSI** — Population Stability Index of the recent ``fit_score`` distribution
   vs a rolling baseline window (pure-Python, :mod:`career_os.services.scoring_eval`).
2. **Agreement** — weighted Cohen's κ and NDCG@5 of a re-score of the frozen
   golden set vs its labels, compared to a stored baseline.

The alert fires on the JOINT condition: ``PSI > threshold`` **and** a κ/NDCG
drop beyond tolerance. Alerts reuse the existing Pushover integration.

This module is opt-in (``DRIFT_CANARY_ENABLED``) and is invoked by a nightly job
or CLI, not an always-on loop — re-scoring the golden set with the live provider
is a small but real paid op, so it is never triggered implicitly.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from career_os.models.scoring import ScoredJob
from career_os.services.scoring_eval import (
    DEFAULT_SCORE_BINS,
    PSI_SIGNIFICANT_SHIFT,
    psi_from_scores,
)

logger = logging.getLogger(__name__)

# Default agreement-drop tolerances (absolute, vs the stored baseline). A drop
# larger than this — together with PSI drift — trips the canary.
DEFAULT_KAPPA_DROP_TOLERANCE = 0.10
DEFAULT_NDCG_DROP_TOLERANCE = 0.05


def evaluate_drift(
    *,
    psi: float,
    kappa: float,
    ndcg: float,
    baseline_kappa: float,
    baseline_ndcg: float,
    psi_threshold: float = PSI_SIGNIFICANT_SHIFT,
    kappa_drop_tolerance: float = DEFAULT_KAPPA_DROP_TOLERANCE,
    ndcg_drop_tolerance: float = DEFAULT_NDCG_DROP_TOLERANCE,
) -> dict:
    """Decide whether the drift canary should alert (pure decision logic).

    Alerts only on the JOINT condition: a significant distribution shift AND a
    meaningful agreement drop. Returns a structured verdict dict.
    """
    distribution_drift = psi > psi_threshold
    kappa_drop = kappa < baseline_kappa - kappa_drop_tolerance
    ndcg_drop = ndcg < baseline_ndcg - ndcg_drop_tolerance
    agreement_drop = kappa_drop or ndcg_drop

    alert = distribution_drift and agreement_drop

    reasons: list[str] = []
    if distribution_drift:
        reasons.append(f"PSI {psi:.3f} > {psi_threshold}")
    if kappa_drop:
        reasons.append(f"κ {kappa:.3f} < baseline {baseline_kappa:.3f} − {kappa_drop_tolerance}")
    if ndcg_drop:
        reasons.append(f"NDCG@5 {ndcg:.3f} < baseline {baseline_ndcg:.3f} − {ndcg_drop_tolerance}")

    if alert:
        reason = "JOINT drift+agreement drop: " + "; ".join(reasons)
    elif distribution_drift:
        reason = "Distribution shifted but agreement held — not alerting (benign job-mix change)"
    elif agreement_drop:
        reason = "Agreement dropped but distribution stable — not alerting (needs joint signal)"
    else:
        reason = "Stable"

    return {
        "psi": psi,
        "kappa": kappa,
        "ndcg": ndcg,
        "distribution_drift": distribution_drift,
        "agreement_drop": agreement_drop,
        "alert": alert,
        "reason": reason,
    }


def compute_score_psi(
    db: Session,
    profile_id: int,
    *,
    baseline_days: int = 30,
    recent_days: int = 1,
    min_samples: int = 20,
    edges: tuple[float, ...] = DEFAULT_SCORE_BINS,
    now: datetime | None = None,
) -> float | None:
    """PSI of the recent ``fit_score`` distribution vs a rolling baseline window.

    ``recent`` = scores created in the last ``recent_days``; ``baseline`` = scores
    from the preceding ``baseline_days``. Returns ``None`` when either window has
    fewer than ``min_samples`` scores (not enough signal to judge drift).
    """
    ref_now = now or datetime.now(UTC)
    recent_start = ref_now - timedelta(days=recent_days)
    baseline_start = recent_start - timedelta(days=baseline_days)

    def _scores(lo: datetime, hi: datetime) -> list[float]:
        rows = (
            db.query(ScoredJob.fit_score)
            .filter(
                ScoredJob.profile_id == profile_id,
                ScoredJob.created_at >= lo,
                ScoredJob.created_at < hi,
            )
            .all()
        )
        return [r[0] for r in rows]

    recent = _scores(recent_start, ref_now)
    baseline = _scores(baseline_start, recent_start)

    if len(recent) < min_samples or len(baseline) < min_samples:
        logger.info(
            "Drift canary: insufficient samples (baseline=%d, recent=%d, need %d) — skipping PSI",
            len(baseline),
            len(recent),
            min_samples,
        )
        return None

    return psi_from_scores(baseline, recent, edges=edges)


def run_drift_canary(
    db: Session,
    profile_id: int,
    *,
    kappa: float,
    ndcg: float,
    baseline_kappa: float,
    baseline_ndcg: float,
    psi: float | None = None,
    notify: bool = True,
    psi_threshold: float = PSI_SIGNIFICANT_SHIFT,
    kappa_drop_tolerance: float = DEFAULT_KAPPA_DROP_TOLERANCE,
    ndcg_drop_tolerance: float = DEFAULT_NDCG_DROP_TOLERANCE,
) -> dict:
    """Run the drift canary and (optionally) send a Pushover alert on a joint trip.

    ``kappa``/``ndcg`` are the freshly-measured golden-set agreement metrics (the
    caller re-scores the frozen golden set through the real production path). If
    ``psi`` is not supplied it is computed from stored scores via
    :func:`compute_score_psi`; when there is not enough data to compute PSI, the
    canary reports ``skipped`` and never alerts (the joint condition needs it).
    """
    if psi is None:
        psi = compute_score_psi(db, profile_id)

    if psi is None:
        result = {
            "psi": None,
            "kappa": kappa,
            "ndcg": ndcg,
            "distribution_drift": False,
            "agreement_drop": False,
            "alert": False,
            "reason": "Insufficient score history to compute PSI — skipped",
            "notified": False,
        }
        return result

    result = evaluate_drift(
        psi=psi,
        kappa=kappa,
        ndcg=ndcg,
        baseline_kappa=baseline_kappa,
        baseline_ndcg=baseline_ndcg,
        psi_threshold=psi_threshold,
        kappa_drop_tolerance=kappa_drop_tolerance,
        ndcg_drop_tolerance=ndcg_drop_tolerance,
    )

    notified = False
    if result["alert"] and notify:
        from career_os.services.pushover import send_drift_alert

        send_result = send_drift_alert(
            db,
            profile_id=profile_id,
            psi=psi,
            kappa=kappa,
            ndcg=ndcg,
            reason=result["reason"],
        )
        notified = send_result.get("status") == "sent"
        logger.warning("Drift canary ALERT for profile %d: %s", profile_id, result["reason"])

    result["notified"] = notified
    return result
