"""Golden-set agreement harness (G-1336, finding H).

Turns a set of production ``fit_score`` outputs plus the interim tier/rank labels
into the two agreement metrics we actually care about for a *ranking* problem:

* weighted Cohen's κ on the ordinal tier (categorical agreement), and
* NDCG@5 on the ranking (does the scorer put the best jobs on top).

The scores MUST come from the real ``career_os.services.scoring.score_job``
(driven by the deterministic mock provider) — never a reimplementation. This
module only does the label alignment + metric aggregation; the async scoring
loop lives in the test/conftest so the harness stays pure and unit-testable.
"""

from __future__ import annotations

from career_os.services.scoring_eval import (
    kappa_from_tiers,
    ndcg_at_k,
    spread_metrics,
    tier_from_fit_score,
    tier_index,
)

# A changed fixture invalidates its label; the harness reports these so a human
# knows to re-label rather than trusting a stale reference.
from tests.eval.label_store import input_hash, load_fixture, load_labels


def check_label_freshness(fixture_name: str) -> list[str]:
    """Return job IDs whose fixture text no longer matches its stored label hash."""
    fixture = load_fixture(fixture_name)
    labels = load_labels(fixture_name)["labels"]
    stale: list[str] = []
    for job in fixture["jobs"]:
        jid = job["id"]
        if jid not in labels:
            stale.append(jid)
            continue
        if labels[jid].get("input_hash") != input_hash(job):
            stale.append(jid)
    return stale


def compute_agreement(fixture_name: str, scored: dict[str, float]) -> dict:
    """Compute κ / NDCG@5 for a fixture given ``{job_id: production_fit_score}``.

    Aligns to the label file, projects scores into ordinal tiers, and returns the
    metric bundle. Raises ``ValueError`` if a labeled job is missing a score.
    """
    labels = load_labels(fixture_name)["labels"]
    job_ids = list(labels.keys())

    missing = [jid for jid in job_ids if jid not in scored]
    if missing:
        raise ValueError(f"{fixture_name}: missing production scores for {missing}")

    true_tiers = [labels[jid]["tier"] for jid in job_ids]
    relevances = [float(labels[jid]["relevance"]) for jid in job_ids]
    fit_scores = [scored[jid] for jid in job_ids]
    pred_tiers = [tier_from_fit_score(s) for s in fit_scores]

    kappa = kappa_from_tiers(true_tiers, pred_tiers)
    ndcg = ndcg_at_k(relevances, fit_scores, k=5)
    # Spread (finding F): does the judge still discriminate? The gap uses the
    # *true* tiers so it measures whether labeled-good jobs outscore labeled-bad.
    spread = spread_metrics(fit_scores, tiers=true_tiers)

    return {
        "fixture": fixture_name,
        "n": len(job_ids),
        "kappa": kappa,
        "ndcg@5": ndcg,
        "spread": spread,
    }


def relevances_from_labels(fixture_name: str, job_ids: list[str]) -> list[float]:
    """Relevance grades (from labels) for the given job IDs, in order."""
    labels = load_labels(fixture_name)["labels"]
    return [float(tier_index(labels[jid]["tier"])) for jid in job_ids]
