"""CLI commands for scoring diagnostics (G-1336).

Usage:
    DRIFT_CANARY_ENABLED=true kestrel scoring drift-canary
    DRIFT_CANARY_ENABLED=true kestrel scoring drift-canary --notify

The drift canary re-scores the frozen golden set through the real production
scorer and compares agreement (κ/NDCG) + score-distribution PSI against a stored
baseline, alerting via Pushover only on the joint condition. It is gated behind
``DRIFT_CANARY_ENABLED`` (off by default) and, by default, re-scores with the
configured ``AI_PROVIDER`` — keep it ``mock`` (the default) for a free,
deterministic check; point it at a real provider only when you deliberately want
a live-model canary (a small paid op).

Requires the golden eval harness under ``tests/eval`` (i.e. run from a repo
checkout, as the nightly job does).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

from career_os.database import SessionLocal

console = Console()

scoring_app = typer.Typer(
    name="scoring",
    help="Scoring diagnostics — drift canary and related checks.",
    no_args_is_help=True,
)


@scoring_app.callback()
def _scoring_main() -> None:
    """Scoring diagnostics — drift canary and related checks."""
    # Presence of a callback keeps this a subcommand GROUP (so `drift-canary` is
    # a named subcommand) even while it has a single command today.


def _golden_agreement() -> tuple[float, float, float, float]:
    """Re-score the golden set (real ``score_job``) and return mean agreement.

    Returns ``(kappa, ndcg, baseline_kappa, baseline_ndcg)`` averaged across the
    golden families. Imports the eval harness lazily so the rest of the CLI does
    not depend on ``tests/`` — raises ``ImportError`` when unavailable.
    """
    import tests.eval as eval_pkg
    from tests.eval.harness import compute_agreement
    from tests.eval.run_scoring import make_memory_session, score_fixture

    baseline = json.loads((Path(eval_pkg.__file__).parent / "baseline_metrics.json").read_text())
    metrics: dict = baseline["metrics"]

    async def _measure() -> tuple[list[float], list[float]]:
        kappas: list[float] = []
        ndcgs: list[float] = []
        for fixture_name in sorted(metrics):
            db = make_memory_session()
            try:
                scored = await score_fixture(db, fixture_name)
            finally:
                db.close()
            agreement = compute_agreement(fixture_name, scored)
            kappas.append(agreement["kappa"])
            ndcgs.append(agreement["ndcg@5"])
        return kappas, ndcgs

    kappas, ndcgs = asyncio.run(_measure())
    baseline_kappas = [metrics[f]["kappa"] for f in sorted(metrics)]
    baseline_ndcgs = [metrics[f]["ndcg@5"] for f in sorted(metrics)]

    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return _mean(kappas), _mean(ndcgs), _mean(baseline_kappas), _mean(baseline_ndcgs)


@scoring_app.command("drift-canary")
def drift_canary(
    profile_id: int = typer.Option(1, "--profile-id", help="Profile to check PSI for."),
    notify: bool = typer.Option(
        False, "--notify", help="Send a Pushover alert on a joint drift trip."
    ),
) -> None:
    """Run the scoring drift canary (gated by DRIFT_CANARY_ENABLED).

    No-ops with a message when the flag is unset, so a scheduled invocation is
    safe to leave wired. Never runs a live paid re-score unless AI_PROVIDER is
    deliberately pointed at a real provider.
    """
    from career_os.config import settings
    from career_os.services.drift_canary import drift_canary_check

    if not settings.drift_canary_enabled:
        console.print("[yellow]Drift canary disabled[/] — set DRIFT_CANARY_ENABLED=true to run it.")
        raise typer.Exit(0)

    try:
        agreement_fn = _golden_agreement
        # Resolve the harness eagerly so a missing checkout fails before scoring.
        import tests.eval  # noqa: F401
    except ImportError:
        console.print(
            "[red]Golden eval harness unavailable[/] — run the drift canary from a repo "
            "checkout (tests/eval must be importable)."
        )
        raise typer.Exit(1) from None

    db = SessionLocal()
    try:
        result = drift_canary_check(db, profile_id, agreement_fn=agreement_fn, notify=notify)
    finally:
        db.close()

    psi = result.get("psi")
    console.print(
        f"[bold]Drift canary[/]: status={result['status']} "
        f"alert={result.get('alert')} notified={result.get('notified')}"
    )
    console.print(
        f"  PSI={psi if psi is None else f'{psi:.3f}'} "
        f"κ={result.get('kappa'):.3f} NDCG@5={result.get('ndcg'):.3f}"
        if result.get("status") == "ran"
        else f"  {result.get('reason', '')}"
    )
    if result.get("alert"):
        console.print(f"[red]⚠️  {result['reason']}[/]")
