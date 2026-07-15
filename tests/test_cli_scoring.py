"""CLI tests for the scoring drift-canary command (G-1336, finding J)."""

from __future__ import annotations

from typer.testing import CliRunner

from career_os.cli.scoring import scoring_app
from career_os.config import settings

runner = CliRunner()


def test_drift_canary_cli_disabled_noops(monkeypatch):
    """With DRIFT_CANARY_ENABLED off, the command no-ops cleanly (exit 0)."""
    monkeypatch.setattr(settings, "drift_canary_enabled", False)
    result = runner.invoke(scoring_app, ["drift-canary"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout.lower()


def test_drift_canary_cli_enabled_invokes_check(monkeypatch):
    """With the flag on, the command runs the check via the golden-agreement fn."""
    monkeypatch.setattr(settings, "drift_canary_enabled", True)

    called = {}

    def _fake_check(db, profile_id, *, agreement_fn, notify):
        called["ran"] = True
        called["notify"] = notify
        return {
            "status": "ran",
            "alert": False,
            "notified": False,
            "psi": None,
            "kappa": 0.6,
            "ndcg": 0.7,
            "reason": "Stable",
        }

    # Avoid the real golden re-score + DB; assert the flag gate lets execution through.
    monkeypatch.setattr("career_os.services.drift_canary.drift_canary_check", _fake_check)
    result = runner.invoke(scoring_app, ["drift-canary"])
    assert result.exit_code == 0
    assert called.get("ran") is True
