#!/usr/bin/env python3
"""G-286: Scoring evolution benchmark — before/after validation.

Scores the golden set (20 jobs × 3 runs) without and with the rubric,
then compares variance, accuracy, red flags, dual-score, and full pipeline.

Requires:
    AI_PROVIDER=openrouter  OPENROUTER_API_KEY=...
    (or set in .env / environment before running)

Usage:
    .venv/bin/python scripts/benchmark_scoring.py
    .venv/bin/python scripts/benchmark_scoring.py \\
        --golden-set tests/fixtures/scoring_golden_set_finance.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Env vars must be set BEFORE importing career_os (Settings validates on load)
# ---------------------------------------------------------------------------
os.environ.setdefault("AI_PROVIDER", "openrouter")
# Accept key from env or fall back to rbw lookup later

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

GOLDEN_SET_PATH = PROJECT_ROOT / "tests" / "fixtures" / "scoring_golden_set.json"
PRIVATE_DIR = PROJECT_ROOT / "private"
PRIVATE_DIR.mkdir(exist_ok=True)
BASELINE_PATH = PRIVATE_DIR / "benchmark-baseline-no-rubric.json"
RUBRIC_PATH = PRIVATE_DIR / "benchmark-with-rubric.json"

RUNS_PER_JOB = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("benchmark")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> tuple[dict, list[dict]]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        # Legacy format (bare array)
        return {}, data
    return data.get("profile", {}), data["jobs"]


def create_benchmark_profile(db, profile_data: dict | None = None):
    """Create a benchmark profile with skills & goals for scoring context.

    When *profile_data* is provided (from the golden set's ``profile`` section),
    its ``job_family``, ``location``, and ``key_skills`` override the defaults.
    """
    from career_os.models.models import Profile
    from career_os.models.skills import Goal, Skill

    job_family = (profile_data or {}).get("job_family", "TPM")
    location = (profile_data or {}).get("location", "Berlin, Germany")
    key_skills = (profile_data or {}).get("key_skills")

    profile = Profile(
        name=f"Benchmark {job_family}",
        email="benchmark@test.local",
        location=location,
        job_family=job_family,
    )
    db.add(profile)
    db.flush()

    def _skill(name, cat, prof):
        return Skill(
            profile_id=profile.id,
            name=name,
            category=cat,
            proficiency=prof,
            evidence_source="benchmark",
        )

    if key_skills:
        skills = [_skill(s, "technical", "expert") for s in key_skills]
    else:
        skills = [
            _skill("Python", "technical", "expert"),
            _skill("Program Management", "management", "expert"),
            _skill("AI/ML", "technical", "advanced"),
            _skill("Cross-functional Leadership", "management", "expert"),
            _skill("Cloud Infrastructure", "technical", "intermediate"),
            _skill("Stakeholder Management", "management", "expert"),
            _skill("Agile/Scrum", "process", "expert"),
            _skill("Technical Architecture", "technical", "advanced"),
            _skill("Data Analysis", "technical", "advanced"),
            _skill("Risk Management", "process", "advanced"),
        ]
    db.add_all(skills)

    goals = [
        Goal(
            profile_id=profile.id,
            title="Lead AI program at a top-tier tech company",
            goal_type="career",
            description="TPM/Program Lead role at an AI-native company (Anthropic, DeepMind, Mistral, etc.)",
            status="active",
        ),
        Goal(
            profile_id=profile.id,
            title="Remote-first or hybrid in Frankfurt area",
            goal_type="location",
            description="Prefer remote EU roles; on-site only acceptable for dream companies",
            status="active",
        ),
    ]
    db.add_all(goals)
    db.commit()
    db.refresh(profile)

    log.info("Created benchmark profile id=%d (%s, %s)", profile.id, job_family, location)
    return profile


async def score_one(db, profile_id: int, job: dict) -> dict:
    """Score a single golden-set job and return raw result dict."""
    from career_os.services.scoring import score_job

    t0 = time.monotonic()
    scored = await score_job(
        db,
        profile_id,
        job["description"],
        job_title=job["title"],
        job_company=job["company"],
    )
    elapsed = round(time.monotonic() - t0, 2)

    dim_scores = {}
    for dim in [
        "dim_technical_fit",
        "dim_seniority_alignment",
        "dim_compensation_fit",
        "dim_location_fit",
        "dim_career_trajectory",
        "dim_company_fit",
    ]:
        dim_scores[dim] = getattr(scored, dim, None)

    return {
        "golden_id": job["id"],
        "category": job["category"],
        "expected_band": job["expected_band"],
        "title": job["title"],
        "company": job["company"],
        "fit_score": scored.fit_score,
        "readiness_score": scored.readiness_score,
        "career_alignment": scored.career_alignment,
        "reasoning": scored.reasoning,
        "dimensional_scores": dim_scores,
        "desire_score": scored.desire_score,
        "desire_score_method": scored.desire_score_method,
        "desire_reasoning": scored.desire_reasoning,
        "red_flags": json.loads(scored.red_flags) if scored.red_flags else [],
        "ats_keywords": json.loads(scored.ats_keywords) if scored.ats_keywords else [],
        "score_breakdown": json.loads(scored.score_breakdown) if scored.score_breakdown else [],
        "effort_flag": scored.effort_flag,
        "elapsed_seconds": elapsed,
    }


async def run_scoring_pass(db, profile_id: int, golden_set: list[dict], label: str) -> list[dict]:
    """Score all golden-set jobs RUNS_PER_JOB times. Returns flat list of results."""
    results = []
    total = len(golden_set) * RUNS_PER_JOB
    done = 0

    for job in golden_set:
        for run in range(1, RUNS_PER_JOB + 1):
            done += 1
            log.info(
                "[%s] %d/%d — %s @ %s (run %d)",
                label,
                done,
                total,
                job["title"],
                job["company"],
                run,
            )
            try:
                result = await score_one(db, profile_id, job)
                result["run"] = run
                results.append(result)
                log.info(
                    "  → fit=%.1f desire=%s elapsed=%.1fs",
                    result["fit_score"],
                    result.get("desire_score"),
                    result["elapsed_seconds"],
                )
            except Exception as e:
                log.error("  ✗ FAILED: %s", e)
                results.append(
                    {
                        "golden_id": job["id"],
                        "category": job["category"],
                        "expected_band": job["expected_band"],
                        "title": job["title"],
                        "company": job["company"],
                        "run": run,
                        "error": str(e),
                    }
                )

    return results


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze_pass(results: list[dict], label: str) -> dict:
    """Compute per-job and overall statistics for a scoring pass."""
    # Group by golden_id
    by_job: dict[str, list[dict]] = {}
    for r in results:
        if "error" in r:
            continue
        by_job.setdefault(r["golden_id"], []).append(r)

    job_stats = []
    for gid, runs in sorted(by_job.items()):
        scores = [r["fit_score"] for r in runs]
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        in_band = sum(
            1 for r in runs if r["expected_band"][0] <= r["fit_score"] <= r["expected_band"][1]
        )
        job_stats.append(
            {
                "golden_id": gid,
                "category": runs[0]["category"],
                "expected_band": runs[0]["expected_band"],
                "title": runs[0]["title"],
                "company": runs[0]["company"],
                "scores": scores,
                "mean": round(mean, 2),
                "std": round(std, 3),
                "in_band_count": in_band,
                "in_band_pct": round(in_band / len(runs) * 100, 1),
            }
        )

    # Overall stats
    all_stds = [j["std"] for j in job_stats if j["std"] > 0]
    mean_std = round(statistics.mean(all_stds), 3) if all_stds else 0.0

    # Category stats
    cat_stats = {}
    for cat in ["reject", "mediocre", "strong", "dream"]:
        cat_jobs = [j for j in job_stats if j["category"] == cat]
        if cat_jobs:
            cat_scores = [s for j in cat_jobs for s in j["scores"]]
            in_band = sum(j["in_band_count"] for j in cat_jobs)
            total_runs = sum(len(j["scores"]) for j in cat_jobs)
            cat_stats[cat] = {
                "mean": round(statistics.mean(cat_scores), 2),
                "std": round(statistics.stdev(cat_scores), 3) if len(cat_scores) > 1 else 0.0,
                "min": min(cat_scores),
                "max": max(cat_scores),
                "in_band_pct": round(in_band / total_runs * 100, 1) if total_runs else 0,
                "n_jobs": len(cat_jobs),
                "n_runs": total_runs,
            }

    # Dimensional consistency
    dim_names = [
        "dim_technical_fit",
        "dim_seniority_alignment",
        "dim_compensation_fit",
        "dim_location_fit",
        "dim_career_trajectory",
        "dim_company_fit",
    ]
    dim_consistency = {}
    for dim in dim_names:
        dim_stds = []
        for gid, runs in by_job.items():
            vals = [
                r["dimensional_scores"].get(dim)
                for r in runs
                if r["dimensional_scores"].get(dim) is not None
            ]
            if len(vals) > 1:
                dim_stds.append(statistics.stdev(vals))
        dim_consistency[dim] = round(statistics.mean(dim_stds), 3) if dim_stds else None

    return {
        "label": label,
        "total_runs": len([r for r in results if "error" not in r]),
        "errors": len([r for r in results if "error" in r]),
        "mean_std_across_jobs": mean_std,
        "category_stats": cat_stats,
        "dimensional_consistency": dim_consistency,
        "per_job": job_stats,
    }


def compare_passes(baseline: dict, rubric: dict) -> dict:
    """Compare baseline vs rubric results."""
    b_std = baseline["mean_std_across_jobs"]
    r_std = rubric["mean_std_across_jobs"]
    variance_reduction = round((1 - r_std / b_std) * 100, 1) if b_std > 0 else None

    # Per-category accuracy comparison
    accuracy_comparison = {}
    for cat in ["reject", "mediocre", "strong", "dream"]:
        b_cat = baseline["category_stats"].get(cat, {})
        r_cat = rubric["category_stats"].get(cat, {})
        accuracy_comparison[cat] = {
            "baseline_in_band_pct": b_cat.get("in_band_pct", 0),
            "rubric_in_band_pct": r_cat.get("in_band_pct", 0),
            "baseline_mean": b_cat.get("mean", 0),
            "rubric_mean": r_cat.get("mean", 0),
        }

    # Category separation: do categories have distinct, non-overlapping ranges?
    separation = {}
    for label, analysis in [("baseline", baseline), ("rubric", rubric)]:
        ranges = {}
        for cat in ["reject", "mediocre", "strong", "dream"]:
            cs = analysis["category_stats"].get(cat, {})
            ranges[cat] = (cs.get("min", 0), cs.get("max", 0))
        separation[label] = ranges

    return {
        "variance_reduction_pct": variance_reduction,
        "baseline_mean_std": b_std,
        "rubric_mean_std": r_std,
        "accuracy_comparison": accuracy_comparison,
        "category_separation": separation,
        "dimensional_consistency_comparison": {
            "baseline": baseline["dimensional_consistency"],
            "rubric": rubric["dimensional_consistency"],
        },
    }


# ---------------------------------------------------------------------------
# Red flags validation
# ---------------------------------------------------------------------------


def validate_red_flags(rubric_results: list[dict]) -> dict:
    """Analyze red flag detection across golden set."""

    flag_counts: dict[str, int] = {}
    false_positives = []  # flags on dream/strong jobs
    per_job = []

    for r in rubric_results:
        if "error" in r or r["run"] != 1:  # only check first run
            continue
        flags = r.get("red_flags", [])
        for f in flags:
            flag_counts[f["flag_type"]] = flag_counts.get(f["flag_type"], 0) + 1
            if r["category"] in ("strong", "dream"):
                false_positives.append(
                    {
                        "job": f"{r['title']} @ {r['company']}",
                        "category": r["category"],
                        "flag": f["flag_type"],
                        "severity": f["severity"],
                        "description": f["description"],
                    }
                )
        per_job.append(
            {
                "golden_id": r["golden_id"],
                "category": r["category"],
                "title": r["title"],
                "n_flags": len(flags),
                "flag_types": [f["flag_type"] for f in flags],
            }
        )

    return {
        "total_flags_triggered": sum(flag_counts.values()),
        "flag_type_counts": flag_counts,
        "false_positives_on_strong_dream": false_positives,
        "per_job": per_job,
    }


# ---------------------------------------------------------------------------
# Dual-score spot check
# ---------------------------------------------------------------------------


def validate_dual_score(rubric_results: list[dict]) -> list[dict]:
    """Spot-check desire_score quadrant classifications."""
    checks = []
    for r in rubric_results:
        if "error" in r or r["run"] != 1:
            continue

        fit = r["fit_score"]
        desire = r.get("desire_score")
        if desire is None:
            quadrant = "no_desire_score"
        elif fit >= 7 and desire >= 7:
            quadrant = "Dream Job"
        elif fit >= 7 and desire < 7:
            quadrant = "Safe Bet"
        elif fit < 7 and desire >= 7:
            quadrant = "Reach"
        else:
            quadrant = "Skip"

        checks.append(
            {
                "golden_id": r["golden_id"],
                "category": r["category"],
                "title": r["title"],
                "company": r["company"],
                "fit_score": fit,
                "desire_score": desire,
                "desire_method": r.get("desire_score_method"),
                "quadrant": quadrant,
            }
        )

    return checks


# ---------------------------------------------------------------------------
# Embedding analysis (optional — requires Ollama)
# ---------------------------------------------------------------------------


async def embedding_analysis(golden_set: list[dict], rubric_analysis: dict) -> dict | None:
    """Generate embeddings and compare cosine similarity vs fit_score."""
    try:
        import httpx
    except ImportError:
        log.warning("httpx not available, skipping embedding analysis")
        return None

    OLLAMA_URL = "http://localhost:11434"
    MODEL = "nomic-embed-text"

    # Check Ollama availability
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            if MODEL not in models and f"{MODEL}:latest" not in models:
                log.warning("Embedding model '%s' not found in Ollama (have: %s)", MODEL, models)
                return None
    except Exception as e:
        log.warning("Ollama not available: %s", e)
        return None

    async def get_embedding(text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": MODEL, "input": text},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]

    def cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    # Synthetic profile embedding
    profile_text = (
        "Technical Program Manager with expertise in AI/ML, Python, "
        "cross-functional leadership, cloud infrastructure, and stakeholder management. "
        "Based in Berlin, Germany. Seeking AI program lead role at a top-tier tech company."
    )
    log.info("Generating profile embedding...")
    profile_emb = await get_embedding(profile_text)

    # Job embeddings + similarity
    results = []
    for job in golden_set:
        log.info("Embedding: %s @ %s", job["title"], job["company"])
        job_emb = await get_embedding(f"{job['title']} at {job['company']}. {job['description']}")
        sim = cosine_sim(profile_emb, job_emb)

        # Find mean fit_score from rubric pass
        job_stats = [j for j in rubric_analysis["per_job"] if j["golden_id"] == job["id"]]
        mean_fit = job_stats[0]["mean"] if job_stats else None

        results.append(
            {
                "golden_id": job["id"],
                "category": job["category"],
                "title": job["title"],
                "company": job["company"],
                "cosine_similarity": round(sim, 4),
                "mean_fit_score": mean_fit,
            }
        )

    # Sort by similarity
    results.sort(key=lambda x: x["cosine_similarity"], reverse=True)

    # Find threshold that filters all rejects without losing strong/dream
    reject_sims = [r["cosine_similarity"] for r in results if r["category"] == "reject"]
    strong_dream_sims = [
        r["cosine_similarity"] for r in results if r["category"] in ("strong", "dream")
    ]

    max_reject_sim = max(reject_sims) if reject_sims else 0
    min_sd_sim = min(strong_dream_sims) if strong_dream_sims else 1

    threshold_analysis = {
        "max_reject_similarity": max_reject_sim,
        "min_strong_dream_similarity": min_sd_sim,
        "clean_threshold_exists": max_reject_sim < min_sd_sim,
    }

    if max_reject_sim < min_sd_sim:
        suggested_threshold = round((max_reject_sim + min_sd_sim) / 2, 4)
        # Count what this threshold would filter
        filtered = sum(1 for r in results if r["cosine_similarity"] < suggested_threshold)
        false_negatives = sum(
            1
            for r in results
            if r["cosine_similarity"] < suggested_threshold and r["category"] in ("strong", "dream")
        )
        threshold_analysis["suggested_threshold"] = suggested_threshold
        threshold_analysis["would_filter_pct"] = round(filtered / len(results) * 100, 1)
        threshold_analysis["false_negative_rate"] = round(false_negatives / len(results) * 100, 1)

    return {
        "model": MODEL,
        "per_job": results,
        "threshold_analysis": threshold_analysis,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    import career_os.services.scoring as scoring_mod
    from career_os.database import SessionLocal

    parser = argparse.ArgumentParser(description="Scoring benchmark")
    parser.add_argument(
        "--golden-set", default=str(GOLDEN_SET_PATH), help="Path to golden set JSON"
    )
    args = parser.parse_args()
    golden_set_path = Path(args.golden_set)

    profile_data, golden_set = load_golden_set(golden_set_path)
    log.info("Loaded %d golden-set jobs from %s", len(golden_set), golden_set_path)

    db = SessionLocal()
    try:
        profile = create_benchmark_profile(db, profile_data)
        profile_id = profile.id

        # ── Phase 1: Baseline (no rubric) ──────────────────────────
        log.info("═" * 60)
        log.info("PHASE 1: BASELINE SCORING (no rubric)")
        log.info("═" * 60)

        # Monkey-patch: disable rubric
        original_rubric = scoring_mod.SCORING_RUBRIC
        scoring_mod.SCORING_RUBRIC = ""
        log.info("Rubric disabled (monkey-patched to empty string)")

        baseline_results = await run_scoring_pass(db, profile_id, golden_set, "BASELINE")

        with open(BASELINE_PATH, "w") as f:
            json.dump(baseline_results, f, indent=2, default=str)
        log.info("Baseline results saved to %s", BASELINE_PATH)

        # ── Phase 2: With rubric ──────────────────────────────────
        log.info("═" * 60)
        log.info("PHASE 2: RUBRIC SCORING")
        log.info("═" * 60)

        # Restore rubric
        scoring_mod.SCORING_RUBRIC = original_rubric
        log.info("Rubric re-enabled")

        rubric_results = await run_scoring_pass(db, profile_id, golden_set, "RUBRIC")

        with open(RUBRIC_PATH, "w") as f:
            json.dump(rubric_results, f, indent=2, default=str)
        log.info("Rubric results saved to %s", RUBRIC_PATH)

        # ── Phase 3: Analysis ─────────────────────────────────────
        log.info("═" * 60)
        log.info("PHASE 3: ANALYSIS")
        log.info("═" * 60)

        baseline_analysis = analyze_pass(baseline_results, "baseline")
        rubric_analysis = analyze_pass(rubric_results, "rubric")
        comparison = compare_passes(baseline_analysis, rubric_analysis)

        # Red flags
        red_flag_report = validate_red_flags(rubric_results)

        # Dual-score
        dual_score_report = validate_dual_score(rubric_results)

        # Embedding analysis
        embedding_report = await embedding_analysis(golden_set, rubric_analysis)

        # ── Save full analysis ────────────────────────────────────
        full_report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": {
                "runs_per_job": RUNS_PER_JOB,
                "n_jobs": len(golden_set),
                "ai_provider": os.environ.get("AI_PROVIDER"),
                "model": os.environ.get("OPENROUTER_MODEL", "default"),
            },
            "baseline_analysis": baseline_analysis,
            "rubric_analysis": rubric_analysis,
            "comparison": comparison,
            "red_flags": red_flag_report,
            "dual_score": dual_score_report,
            "embedding_analysis": embedding_report,
        }

        analysis_path = PRIVATE_DIR / "benchmark-analysis.json"
        with open(analysis_path, "w") as f:
            json.dump(full_report, f, indent=2, default=str)
        log.info("Full analysis saved to %s", analysis_path)

        # ── Print summary ─────────────────────────────────────────
        print("\n" + "═" * 60)
        print("BENCHMARK SUMMARY")
        print("═" * 60)

        vr = comparison["variance_reduction_pct"]
        print(f"\nVariance reduction: {vr}%" if vr is not None else "\nVariance reduction: N/A")
        print(f"  Baseline mean σ: {comparison['baseline_mean_std']}")
        print(f"  Rubric mean σ:   {comparison['rubric_mean_std']}")

        print("\nCategory accuracy (% scores in expected band):")
        for cat, data in comparison["accuracy_comparison"].items():
            print(
                f"  {cat:10s} — baseline: {data['baseline_in_band_pct']:5.1f}%  rubric: {data['rubric_in_band_pct']:5.1f}%"
            )

        print(
            f"\nRed flags: {red_flag_report['total_flags_triggered']} total, "
            f"{len(red_flag_report['false_positives_on_strong_dream'])} false positives on strong/dream"
        )

        print("\nDual-score quadrants:")
        quadrant_counts: dict[str, int] = {}
        for ds in dual_score_report:
            q = ds["quadrant"]
            quadrant_counts[q] = quadrant_counts.get(q, 0) + 1
        for q, n in sorted(quadrant_counts.items()):
            print(f"  {q}: {n}")

        if embedding_report:
            ta = embedding_report["threshold_analysis"]
            print("\nEmbedding pre-filter:")
            print(f"  Clean threshold exists: {ta['clean_threshold_exists']}")
            if ta.get("suggested_threshold"):
                print(f"  Suggested threshold: {ta['suggested_threshold']}")
                print(f"  Would filter: {ta['would_filter_pct']}%")
                print(f"  False negative rate: {ta['false_negative_rate']}%")

        print(f"\nFull analysis: {analysis_path}")
        print("═" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
