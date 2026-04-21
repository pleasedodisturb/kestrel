#!/usr/bin/env python3
"""Spike: Batch scoring quality A/B comparison (G-453).

Compares batch-10 scoring vs individual scoring to validate that the batch
pipeline doesn't degrade scoring quality.  Uses MockProvider so no real API
calls are made — the comparison is structural (schema compliance, result
count, dimensional score correlation).

Usage:
    .venv/bin/python tools/spike_batch_quality.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from pathlib import Path

# ── Bootstrap project imports ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from career_os.ai.mock_provider import MockProvider  # noqa: E402
from career_os.schemas.ai import ScoreResult  # noqa: E402
from career_os.services.batch_scoring import batch_score_jobs  # noqa: E402

GOLDEN_SET = PROJECT_ROOT / "tests" / "fixtures" / "scoring_golden_set.json"
BATCH_SIZE = 10


def load_golden_set() -> tuple[list[dict], dict]:
    """Load golden set jobs and profile from fixture file."""
    data = json.loads(GOLDEN_SET.read_text())
    return data["jobs"], data["profile"]


async def score_individually(
    provider: MockProvider,
    jobs: list[dict],
    profile_data: dict,
) -> dict[str, ScoreResult]:
    """Score each job individually via provider.score()."""
    results: dict[str, ScoreResult] = {}
    for job in jobs:
        response = await provider.score(
            job_description=job.get("description", ""),
            profile_data=profile_data,
        )
        if response.structured and isinstance(response.structured, ScoreResult):
            results[str(job["id"])] = response.structured
    return results


async def score_in_batches(
    provider: MockProvider,
    jobs: list[dict],
    profile_data: dict,
) -> dict[str, ScoreResult]:
    """Score jobs in batches via batch_score_jobs()."""
    return await batch_score_jobs(
        provider=provider,
        jobs=jobs,
        profile_data=profile_data,
        batch_size=BATCH_SIZE,
    )


def compare_results(
    individual: dict[str, ScoreResult],
    batch: dict[str, ScoreResult],
    jobs: list[dict],
) -> dict:
    """Compare individual vs batch scoring results and return a report dict."""
    report: dict = {
        "total_jobs": len(jobs),
        "individual_count": len(individual),
        "batch_count": len(batch),
        "count_match": len(individual) == len(batch),
        "schema_compliance": {"individual": 0, "batch": 0},
        "missing_in_batch": [],
        "fit_score_deltas": [],
        "dimensional_correlation": [],
    }

    # Schema compliance: count how many results are valid ScoreResult instances
    for results, key in [(individual, "individual"), (batch, "batch")]:
        valid = 0
        for sr in results.values():
            try:
                ScoreResult.model_validate(sr.model_dump())
                valid += 1
            except Exception:
                pass
        report["schema_compliance"][key] = valid

    # Jobs present in individual but missing from batch
    for job_id in individual:
        if job_id not in batch:
            report["missing_in_batch"].append(job_id)

    # Fit score deltas (only for jobs in both)
    common_ids = set(individual.keys()) & set(batch.keys())
    for job_id in sorted(common_ids):
        ind_score = individual[job_id].fit_score
        bat_score = batch[job_id].fit_score
        report["fit_score_deltas"].append(
            {
                "job_id": job_id,
                "individual": ind_score,
                "batch": bat_score,
                "delta": round(abs(ind_score - bat_score), 2),
            }
        )

    # Dimensional score correlation (for jobs in both that have dimensional scores)
    for job_id in sorted(common_ids):
        ind_dim = individual[job_id].dimensional_scores
        bat_dim = batch[job_id].dimensional_scores
        if ind_dim and bat_dim:
            ind_vals = [
                ind_dim.technical_fit,
                ind_dim.seniority_alignment,
                ind_dim.compensation_fit,
                ind_dim.location_fit,
                ind_dim.career_trajectory,
                ind_dim.company_fit,
            ]
            bat_vals = [
                bat_dim.technical_fit,
                bat_dim.seniority_alignment,
                bat_dim.compensation_fit,
                bat_dim.location_fit,
                bat_dim.career_trajectory,
                bat_dim.company_fit,
            ]
            deltas = [round(abs(a - b), 2) for a, b in zip(ind_vals, bat_vals, strict=True)]
            report["dimensional_correlation"].append(
                {
                    "job_id": job_id,
                    "mean_delta": round(statistics.mean(deltas), 2),
                    "max_delta": max(deltas),
                }
            )

    return report


def print_report(report: dict) -> None:
    """Pretty-print the comparison report."""
    print("=" * 70)
    print("  Batch Scoring Quality A/B Test — Spike Results (G-453)")
    print("=" * 70)

    print(f"\nTotal jobs in golden set:    {report['total_jobs']}")
    print(f"Individual results returned:  {report['individual_count']}")
    print(f"Batch results returned:       {report['batch_count']}")
    print(f"Count match:                  {'PASS' if report['count_match'] else 'FAIL'}")

    print(
        f"\nSchema compliance (individual): {report['schema_compliance']['individual']}"
        f"/{report['individual_count']}"
    )
    print(
        f"Schema compliance (batch):      {report['schema_compliance']['batch']}"
        f"/{report['batch_count']}"
    )

    if report["missing_in_batch"]:
        print(f"\nMissing in batch: {report['missing_in_batch']}")
    else:
        print("\nAll individual job IDs present in batch: PASS")

    # Fit score deltas
    deltas = [d["delta"] for d in report["fit_score_deltas"]]
    if deltas:
        print("\nFit score deltas (individual vs batch):")
        print(f"  Mean delta:  {statistics.mean(deltas):.2f}")
        print(f"  Max delta:   {max(deltas):.2f}")
        print(f"  Zero deltas: {sum(1 for d in deltas if d == 0.0)}/{len(deltas)}")

    # Dimensional correlation
    dim_deltas = [d["mean_delta"] for d in report["dimensional_correlation"]]
    if dim_deltas:
        print("\nDimensional score mean deltas:")
        print(f"  Mean of means: {statistics.mean(dim_deltas):.2f}")
        print(f"  Max of means:  {max(dim_deltas):.2f}")

    # Summary
    print("\n" + "=" * 70)
    batch_has_all = report["count_match"] and not report["missing_in_batch"]
    schema_ok = (
        report["schema_compliance"]["batch"] == report["batch_count"]
        and report["schema_compliance"]["individual"] == report["individual_count"]
    )

    if batch_has_all and schema_ok:
        print("  OVERALL: Pipeline structurally sound. Batch returns same count,")
        print("  all results schema-valid. Score deltas expected with MockProvider")
        print("  (different prompts produce different deterministic seeds).")
    else:
        issues = []
        if not batch_has_all:
            issues.append("batch count mismatch or missing IDs")
        if not schema_ok:
            issues.append("schema validation failures")
        print(f"  OVERALL: Issues detected: {', '.join(issues)}")
    print("=" * 70)

    return report


async def main() -> dict:
    """Run the full A/B comparison."""
    jobs, profile = load_golden_set()
    provider = MockProvider()

    print(f"Loaded {len(jobs)} jobs from golden set")
    print("Scoring individually...")
    individual = await score_individually(provider, jobs, profile)
    print(f"  -> {len(individual)} results")

    print(f"Scoring in batches of {BATCH_SIZE}...")
    batch = await score_in_batches(provider, jobs, profile)
    print(f"  -> {len(batch)} results\n")

    report = compare_results(individual, batch, jobs)
    print_report(report)
    return report


if __name__ == "__main__":
    asyncio.run(main())
