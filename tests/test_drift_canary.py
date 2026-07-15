"""Unit tests for the scoring drift canary (G-1336, finding J)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.config import settings
from career_os.database import Base
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob
from career_os.services import drift_canary
from career_os.services.drift_canary import (
    compute_score_psi,
    drift_canary_check,
    evaluate_drift,
    run_drift_canary,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    session.add(
        Profile(id=1, name="U", email="u@test.example.com", location="Remote", job_family="TPM")
    )
    session.commit()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# evaluate_drift — the joint-condition decision logic
# ---------------------------------------------------------------------------


def test_joint_condition_alerts():
    r = evaluate_drift(psi=0.35, kappa=0.40, ndcg=0.70, baseline_kappa=0.62, baseline_ndcg=0.75)
    assert r["alert"] is True
    assert r["distribution_drift"] and r["agreement_drop"]


def test_psi_only_does_not_alert():
    r = evaluate_drift(psi=0.35, kappa=0.62, ndcg=0.75, baseline_kappa=0.62, baseline_ndcg=0.75)
    assert r["alert"] is False
    assert r["distribution_drift"] is True
    assert "benign" in r["reason"]


def test_agreement_drop_only_does_not_alert():
    r = evaluate_drift(psi=0.05, kappa=0.30, ndcg=0.50, baseline_kappa=0.62, baseline_ndcg=0.75)
    assert r["alert"] is False
    assert r["agreement_drop"] is True


def test_stable_does_not_alert():
    r = evaluate_drift(psi=0.05, kappa=0.63, ndcg=0.76, baseline_kappa=0.62, baseline_ndcg=0.75)
    assert r["alert"] is False
    assert r["reason"] == "Stable"


def test_ndcg_drop_alone_can_trip_joint():
    # κ held, NDCG dropped past tolerance, PSI high → joint trip.
    r = evaluate_drift(psi=0.30, kappa=0.62, ndcg=0.60, baseline_kappa=0.62, baseline_ndcg=0.75)
    assert r["alert"] is True


# ---------------------------------------------------------------------------
# compute_score_psi
# ---------------------------------------------------------------------------


def _add_scores(db, values, created_at):
    for v in values:
        db.add(
            ScoredJob(
                profile_id=1,
                fit_score=v,
                reasoning="x",
                created_at=created_at,
            )
        )
    db.commit()


def test_compute_score_psi_insufficient_returns_none(db_session):
    now = datetime(2026, 7, 15, tzinfo=UTC)
    _add_scores(db_session, [5.0, 6.0], now - timedelta(hours=1))
    assert compute_score_psi(db_session, 1, min_samples=20, now=now) is None


def test_compute_score_psi_stable_is_low(db_session):
    now = datetime(2026, 7, 15, tzinfo=UTC)
    baseline_vals = [5.0] * 6 + [6.0] * 6
    recent_vals = [5.0] * 6 + [6.0] * 6
    _add_scores(db_session, baseline_vals, now - timedelta(days=10))
    _add_scores(db_session, recent_vals, now - timedelta(hours=2))
    psi = compute_score_psi(db_session, 1, min_samples=10, now=now)
    assert psi == pytest.approx(0.0, abs=1e-9)


def test_compute_score_psi_shift_is_positive(db_session):
    now = datetime(2026, 7, 15, tzinfo=UTC)
    _add_scores(db_session, [1.0] * 12, now - timedelta(days=10))  # baseline: all low
    _add_scores(db_session, [9.0] * 12, now - timedelta(hours=2))  # recent: all high
    psi = compute_score_psi(db_session, 1, min_samples=10, now=now)
    assert psi > 0.2


# ---------------------------------------------------------------------------
# run_drift_canary — orchestration
# ---------------------------------------------------------------------------


def test_run_canary_skips_without_psi(db_session):
    r = run_drift_canary(
        db_session, 1, kappa=0.3, ndcg=0.4, baseline_kappa=0.62, baseline_ndcg=0.75, psi=None
    )
    # psi=None and no stored history → PSI can't be computed → skipped, no alert.
    assert r["alert"] is False
    assert "Insufficient" in r["reason"]
    assert r["notified"] is False


def test_run_canary_alerts_and_notifies(db_session, monkeypatch):
    calls = {}

    def _fake_alert(db, **kwargs):
        calls.update(kwargs)
        return {"status": "sent"}

    monkeypatch.setattr(drift_canary, "run_drift_canary", run_drift_canary)  # ensure real fn
    monkeypatch.setattr("career_os.services.pushover.send_drift_alert", _fake_alert)

    r = run_drift_canary(
        db_session,
        1,
        kappa=0.30,
        ndcg=0.60,
        baseline_kappa=0.62,
        baseline_ndcg=0.75,
        psi=0.35,
    )
    assert r["alert"] is True
    assert r["notified"] is True
    assert calls["psi"] == 0.35


def test_run_canary_alert_without_notify(db_session):
    r = run_drift_canary(
        db_session,
        1,
        kappa=0.30,
        ndcg=0.60,
        baseline_kappa=0.62,
        baseline_ndcg=0.75,
        psi=0.35,
        notify=False,
    )
    assert r["alert"] is True
    assert r["notified"] is False


# ---------------------------------------------------------------------------
# drift_canary_check — the flag-gated entrypoint (DRIFT_CANARY_ENABLED)
# ---------------------------------------------------------------------------


def test_drift_canary_check_disabled_is_noop(db_session, monkeypatch):
    monkeypatch.setattr(settings, "drift_canary_enabled", False)
    called = []

    def _agreement():
        called.append(1)
        return (0.30, 0.60, 0.62, 0.75)

    result = drift_canary_check(db_session, 1, agreement_fn=_agreement, notify=False)
    assert result["status"] == "disabled"
    # The golden re-score (a potential paid op) must NOT run when disabled.
    assert called == []


def test_drift_canary_check_enabled_runs_and_alerts(db_session, monkeypatch):
    monkeypatch.setattr(settings, "drift_canary_enabled", True)

    now = datetime.now(UTC)
    _add_scores(db_session, [1.0] * 22, now - timedelta(days=10))  # baseline: low
    _add_scores(db_session, [9.0] * 22, now - timedelta(hours=2))  # recent: high → PSI high

    called = []

    def _agreement():
        called.append(1)
        return (0.30, 0.60, 0.62, 0.75)  # κ dropped vs baseline

    result = drift_canary_check(db_session, 1, agreement_fn=_agreement, notify=False)
    assert result["status"] == "ran"
    assert called == [1]
    assert result["alert"] is True
    assert result["notified"] is False


def test_drift_canary_check_enabled_stable_no_alert(db_session, monkeypatch):
    monkeypatch.setattr(settings, "drift_canary_enabled", True)

    now = datetime.now(UTC)
    _add_scores(db_session, [1.0] * 22, now - timedelta(days=10))
    _add_scores(db_session, [9.0] * 22, now - timedelta(hours=2))  # PSI high

    def _agreement():
        return (0.63, 0.76, 0.62, 0.75)  # agreement held → no joint trip

    result = drift_canary_check(db_session, 1, agreement_fn=_agreement, notify=False)
    assert result["status"] == "ran"
    assert result["alert"] is False
