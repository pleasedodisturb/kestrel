"""Freeze the golden-set agreement baseline (G-1336, finding H).

Runs the real production scorer (MockProvider) over every golden fixture and
records the resulting κ / NDCG@5 into ``baseline_metrics.json``. The eval test
gates future runs on *deltas* vs this baseline (tolerance bands), so the check
tracks the production scoring pipeline's behavior rather than a brittle absolute
threshold — and mock nondeterminism never flaps it (the mock is deterministic).

Regenerate deliberately (and review the diff) whenever an intended scoring
change moves the metrics:

    python -m tests.eval.generate_baseline

NOTE: with the mock provider these numbers reflect the *plumbing*, not real
quality. They become quality signal once the labels are human and a real
reference model is run — see label_store.py.
"""

from __future__ import annotations

import asyncio
import glob
import json
from pathlib import Path

from tests.eval.harness import compute_agreement
from tests.eval.run_scoring import make_memory_session, score_fixture

BASELINE_PATH = Path(__file__).resolve().parent / "baseline_metrics.json"


async def _run() -> dict:
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    metrics: dict[str, dict] = {}
    for path in sorted(glob.glob(str(fixtures_dir / "scoring_golden_set*.json"))):
        fixture_name = Path(path).name
        db = make_memory_session()
        try:
            scored = await score_fixture(db, fixture_name)
        finally:
            db.close()
        agreement = compute_agreement(fixture_name, scored)
        spread = agreement["spread"]
        metrics[fixture_name] = {
            "n": agreement["n"],
            "kappa": round(agreement["kappa"], 4),
            "ndcg@5": round(agreement["ndcg@5"], 4),
            "spread": {
                "stddev": round(spread["stddev"], 4),
                "entropy": round(spread["entropy"], 4),
                "mode_share": round(spread["mode_share"], 4),
                "chosen_rejected_gap": round(spread["chosen_rejected_gap"], 4),
            },
        }
    return {
        "note": (
            "Baseline κ/NDCG@5 from the real score_job over the MockProvider. "
            "Deltas gate the eval; regenerate deliberately when scoring changes."
        ),
        "provider": "mock",
        "metrics": metrics,
    }


def regenerate() -> dict:
    doc = asyncio.run(_run())
    with open(BASELINE_PATH, "w") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    return doc


if __name__ == "__main__":
    doc = regenerate()
    for fixture, m in sorted(doc["metrics"].items()):
        print(f"{fixture}: κ={m['kappa']:.4f} NDCG@5={m['ndcg@5']:.4f} (n={m['n']})")
