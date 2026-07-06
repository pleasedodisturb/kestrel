#!/usr/bin/env python3
"""
Daily Job Search Pipeline — Automated orchestrator.

Chains: scrape → score → dedup against tracking → generate digest → notify.

Designed to run headlessly via:
  - GitHub Actions (recommended)
  - cron / launchd
  - n8n / Zapier webhook
  - Manual: .venv/bin/python tools/daily_pipeline.py

Environment variables:
  AI_PROVIDER             — Single provider name (e.g. ``mistral``); used when
                            no fallback chain is configured.
  AI_PROVIDER_FALLBACK    — Comma-separated ordered chain (e.g.
                            ``mistral,openai,together,anthropic``). When set,
                            scoring routes through ``FallbackProvider`` and
                            falls back across vendors on quota/timeout/HTTP
                            errors.
  <PROVIDER>_API_KEY      — Per-provider API key (MISTRAL_API_KEY,
                            OPENAI_API_KEY, TOGETHER_API_KEY, etc.). See
                            :mod:`career_os.ai.factory` for the full list.
  SCORING_MAX_FAILURE_RATE — Float in [0, 1]. If the post-run scoring
                            failure rate exceeds this, the pipeline raises
                            (default: 0.50). The exit-2 path turns into a
                            loud failure so silent degradation alerts.
  PIPELINE_MODE           — api-only | api-plus | all (default: api-only)
  PIPELINE_MIN_SCORE      — Minimum score to include in digest (default: 5)
  PIPELINE_HOURS_OLD      — Max posting age in hours (default: 24)
  PIPELINE_LOCATION       — Search location (default: Dublin)
  PIPELINE_DRY_RUN        — Set to "1" to skip CSV writes (default: 0)
  GITHUB_STEP_SUMMARY     — GitHub Actions summary file (auto-set in Actions)

Exit codes:
  0 — Success
  1 — Fatal error (missing deps, scoring failure-rate threshold exceeded)
  2 — Partial failure (some sources failed, digest still generated)
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logger = logging.getLogger("daily_pipeline")

# Default failure-rate threshold for the scoring loud-fail alarm. Configurable
# via SCORING_MAX_FAILURE_RATE env. Above this rate the pipeline raises so
# a misconfigured chain or mass provider outage produces an immediate alert
# rather than days of silent score=2 fallbacks.
DEFAULT_SCORING_MAX_FAILURE_RATE = 0.50


# --- Config ---


class PipelineConfig:
    def __init__(self):
        self.mode = os.getenv("PIPELINE_MODE", "api-only")
        self.min_score = int(os.getenv("PIPELINE_MIN_SCORE", "5"))
        self.hours_old = int(os.getenv("PIPELINE_HOURS_OLD", "24"))
        self.location = os.getenv("PIPELINE_LOCATION", "Dublin")
        self.dry_run = os.getenv("PIPELINE_DRY_RUN", "0") == "1"
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self.tracking_dir = PROJECT_ROOT / "tracking"
        self.digest_path = self.tracking_dir / f"daily-scan-{self.date}.md"
        self.raw_path = self.tracking_dir / f"scraped_raw_{self.date}.json"
        self.scored_path = self.tracking_dir / f"scraped_scored_{self.date}.json"
        self.csv_path = self.tracking_dir / "applications.csv"
        self.profile_path = PROJECT_ROOT / "profile" / "target-roles.md"


# --- Step 1: Scrape ---


def step_scrape(config: PipelineConfig) -> list[dict]:
    """Run the resilient scraper across all configured sources."""
    logger.info("=" * 60)
    logger.info("STEP 1: SCRAPE")
    logger.info("=" * 60)

    from dataclasses import asdict

    from scrape_resilient import scrape_all_sources

    jobs = scrape_all_sources(
        mode=config.mode,
        location=config.location,
        hours_old=config.hours_old,
    )

    results = [asdict(j) for j in jobs]
    logger.info(f"Scrape complete: {len(results)} jobs found")

    # Save raw results
    config.tracking_dir.mkdir(parents=True, exist_ok=True)
    config.raw_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    logger.info(f"Raw results saved to {config.raw_path}")

    return results


# --- Step 2: Score ---

# Budget-based scoring cap (ported from Eyas G-1119). Instead of a fixed job
# count, derive how many jobs to AI-score from a daily $ budget, clamped to a
# sane floor/ceiling. Combined with source-priority ordering (G-1114) below,
# the cap only ever trims the lowest-signal generic-board overflow.
DEFAULT_DAILY_BUDGET_USD = 5.0
EST_COST_PER_JOB_USD = 0.0015
SCORING_CAP_FLOOR = 500
SCORING_CAP_CEILING = 6000


def effective_scoring_cap() -> int:
    """Resolve the scoring cap: explicit PIPELINE_MAX_SCORE, else budget-derived."""
    override = os.getenv("PIPELINE_MAX_SCORE")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass
    try:
        budget = float(os.getenv("PIPELINE_DAILY_BUDGET_USD", DEFAULT_DAILY_BUDGET_USD))
    except ValueError:
        budget = DEFAULT_DAILY_BUDGET_USD
    return max(SCORING_CAP_FLOOR, min(SCORING_CAP_CEILING, int(budget / EST_COST_PER_JOB_USD)))


# When the scrape exceeds the cap, score the highest-signal sources FIRST so the
# cap never silently drops curated roles (ported from Eyas G-1114). The ATS
# board scrapers (greenhouse/ashby/lever/workable) carry the curated target
# companies and tend to be scraped last, so before this fix they were the first
# to be cap-skipped.
SOURCE_SCORING_PRIORITY: dict[str, int] = {
    "greenhouse": 0,
    "ashby": 0,
    "lever": 0,
    "workable": 0,
    "ai-jobs": 1,
    "germany_api": 2,
    "arbeitsagentur": 2,
    "arbeitnow": 2,
    "himalayas": 3,
}
_DEFAULT_SOURCE_PRIORITY = 5


def _source_priority(job: dict) -> int:
    return SOURCE_SCORING_PRIORITY.get(
        (job.get("source") or "").lower().strip(), _DEFAULT_SOURCE_PRIORITY
    )


def step_score(config: PipelineConfig, jobs: list[dict]) -> list[dict]:
    """Score each job against the profile via the AI provider stack.

    Routes through ``career_os.ai.factory.get_ai_provider``, which builds a
    ``FallbackProvider`` chain when ``AI_PROVIDER_FALLBACK`` is set. The chain
    transparently fails over on quota/timeout/HTTP errors. Sync wrapper around
    an internal async helper so the rest of the pipeline stays synchronous.

    Falls back to keyword-based scoring **only** when no AI provider can be
    constructed (e.g. running locally with no keys configured). When a provider
    chain is configured but every call fails, the pipeline raises so the
    workflow fails loudly instead of silently producing score=2 stubs — see
    ``SCORING_MAX_FAILURE_RATE``.
    """
    logger.info("=" * 60)
    logger.info("STEP 2: SCORE")
    logger.info("=" * 60)

    try:
        from career_os.ai.factory import get_ai_provider
    except ImportError as exc:
        logger.warning("career_os.ai unavailable (%s) — using keyword-based fallback scoring", exc)
        return _fallback_score(jobs)

    try:
        provider = get_ai_provider()
    except Exception as exc:  # missing keys, unsupported provider, etc.
        logger.warning("AI provider unavailable (%s) — using keyword-based fallback scoring", exc)
        return _fallback_score(jobs)

    return asyncio.run(_step_score_async(config, jobs, provider))


async def _step_score_async(
    config: PipelineConfig,
    jobs: list[dict],
    provider,  # AIProvider
) -> list[dict]:
    """Async scoring loop driving the provider stack one job at a time.

    Sequential by design — keeps memory + cost predictable for the daily
    cron, and the FallbackProvider already handles per-call resilience.
    Tracks failure count and raises when ``failures/scored_via_ai`` exceeds
    ``SCORING_MAX_FAILURE_RATE`` so silent degradation can't recur.
    """
    from job_scorer import PROFILE_CRITERIA, SCORING_SYSTEM_PROMPT_WITH_REVIEW, pre_filter_job

    from career_os.schemas.ai import AIFeature
    from career_os.services.batch_scoring import _sanitize_description

    profile_context = ""
    if config.profile_path.exists():
        profile_context = config.profile_path.read_text()[:3000]

    max_failure_rate = float(
        os.getenv("SCORING_MAX_FAILURE_RATE", str(DEFAULT_SCORING_MAX_FAILURE_RATE))
    )

    # Order by source priority BEFORE the budget cap so high-signal ATS sources
    # are scored first and never cap-skipped (G-1114). Stable sort preserves the
    # original within-source order.
    jobs = sorted(jobs, key=_source_priority)
    scoring_cap = effective_scoring_cap()

    scored: list[dict] = []
    skipped = 0
    cap_skipped = 0
    failures = 0
    ai_attempts = 0
    total = len(jobs)
    logger.info("Provider chain: %s (scoring cap: %d jobs)", provider.name, scoring_cap)

    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        location = job.get("location", "")
        remote = bool(job.get("remote", False))
        description = job.get("description", "")

        should_skip, filter_reason, score_cap = pre_filter_job(title, company, location, remote)
        if should_skip:
            job["fit_score"] = 0
            job["fit_reasoning"] = f"Pre-filtered: {filter_reason}"
            job["estimated_salary"] = "unknown"
            job["effort_flag"] = "unknown"
            job["prep_level"] = 0
            job["prep_notes"] = ""
            job["review_flag"] = False
            job["review_reason"] = ""
            scored.append(job)
            skipped += 1
            if (i + 1) % 10 == 0:
                logger.info("Scored %d/%d jobs (skipped %d)", i + 1, total, skipped)
            continue

        # Budget cap (G-1119): once effective_scoring_cap() jobs have gone to the
        # AI, stub the remainder. Jobs are pre-sorted by source priority, so the
        # overflow trimmed here is always the lowest-signal generic-board tail,
        # never a curated ATS role (G-1114).
        if ai_attempts >= scoring_cap:
            job["fit_score"] = 2
            job["fit_reasoning"] = "Skipped: scoring cap reached"
            job["estimated_salary"] = "unknown"
            job["effort_flag"] = "unknown"
            job["prep_level"] = 0
            job["prep_notes"] = ""
            job["review_flag"] = False
            job["review_reason"] = ""
            scored.append(job)
            cap_skipped += 1
            continue

        if not description or description == "nan":
            description = (
                f"Title: {title}\nCompany: {company}\nLocation: {location}\n"
                f"Tags: {', '.join(job.get('tags', []))}"
            )

        # Sanitize attacker-controlled job description before interpolating
        # into the prompt. Job postings come from public ATS boards — content
        # there is not trusted. Strips known prompt-injection patterns and
        # truncates to MAX_DESCRIPTION_LENGTH. Reuses the same defense as
        # batch scoring (career_os.services.batch_scoring._sanitize_description).
        description = _sanitize_description(description)

        # Inline system + user content into one prompt because we use
        # AIFeature.complete (no auto system message). Preserves the
        # CLI-specific scoring schema with review_flag / review_reason
        # consumed downstream by update_sheet.py and the digest "Review
        # Queue" section.
        prompt = (
            f"{SCORING_SYSTEM_PROMPT_WITH_REVIEW}\n\n"
            f"CANDIDATE PROFILE:\n{PROFILE_CRITERIA}\n\n"
            f"ADDITIONAL CONTEXT:\n{profile_context[:1000]}\n\n"
            f"JOB POSTING:\nTitle: {title}\nCompany: {company}\n"
            f"Description: {description[:3000]}"
        )

        ai_attempts += 1
        try:
            response = await provider.complete(prompt, feature=AIFeature.complete)
            raw = (response.content or "").strip()
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                # Strip common markdown fences before retry-parse
                stripped = raw
                for fence in ("```json", "```"):
                    stripped = stripped.replace(fence, "")
                try:
                    result = json.loads(stripped.strip().replace("'", '"'))
                except json.JSONDecodeError as parse_exc:
                    raise ValueError(f"unparseable JSON: {raw[:200]!r}") from parse_exc

            ai_score = int(result.get("score", result.get("fit_score", 2)))
            if score_cap is not None and ai_score > score_cap:
                result["reasoning"] = (
                    f"Capped from {ai_score} to {score_cap}: {result.get('reasoning', '')}"
                )
                ai_score = score_cap

            job["fit_score"] = ai_score
            job["fit_reasoning"] = result.get("reasoning", "")
            job["estimated_salary"] = result.get("estimated_salary", "unknown")
            job["effort_flag"] = result.get("effort_flag", "unknown")
            job["prep_level"] = int(result.get("prep_level", 0))
            job["prep_notes"] = result.get("prep_notes", "")
            job["review_flag"] = bool(result.get("review_flag", False))
            job["review_reason"] = result.get("review_reason", "")

        except Exception as exc:
            failures += 1
            logger.warning("Scoring failed for %s @ %s: %s", title, company, exc)
            job["fit_score"] = 2
            job["fit_reasoning"] = f"Scoring error: {exc}"
            job["estimated_salary"] = "unknown"
            job["effort_flag"] = "unknown"
            job["prep_level"] = 0
            job["prep_notes"] = ""
            job["review_flag"] = False
            job["review_reason"] = ""

        scored.append(job)
        if (i + 1) % 10 == 0:
            logger.info(
                "Scored %d/%d jobs (skipped %d, failures %d)",
                i + 1,
                total,
                skipped,
                failures,
            )

    logger.info(
        "Scoring complete: %d jobs (%d AI attempts, %d failures, "
        "%d pre-filter-skipped, %d cap-skipped)",
        len(scored),
        ai_attempts,
        failures,
        skipped,
        cap_skipped,
    )

    config.scored_path.write_text(json.dumps(scored, indent=2, ensure_ascii=False))

    # Loud-fail alarm: if too many AI calls failed, the chain is broken.
    # Raise so the workflow fails and existing Pushover failure path triggers,
    # rather than producing a digest full of score=2 stubs that look fine.
    if ai_attempts > 0:
        failure_rate = failures / ai_attempts
        if failure_rate > max_failure_rate:
            raise RuntimeError(
                f"Scoring failure rate {failure_rate:.0%} ({failures}/{ai_attempts}) "
                f"exceeds threshold {max_failure_rate:.0%}. "
                f"Provider chain '{provider.name}' is unhealthy — check API keys, "
                f"quotas, and provider status pages."
            )

    return scored


def _fallback_score(jobs: list[dict]) -> list[dict]:
    """Simple keyword-based scoring when OpenAI is unavailable."""
    from job_scorer import pre_filter_job

    positive_signals = [
        "ai",
        "ml",
        "machine learning",
        "product manager",
        "program manager",
        "technical program",
        "innovation",
        "platform",
        "builder",
        "remote",
        "startup",
        "founding",
        "devrel",
        "developer relations",
        "developer advocate",
    ]
    negative_signals = [
        "pmbok",
        "pmo",
        "coordinator",
        "administrator",
        "sachbearbeiter",
        "accountant",
        "sales rep",
        "nurse",
        "driver",
        "warehouse",
        "customer support",
        "hr specialist",
        "recruiter",
        "legal",
    ]

    config = PipelineConfig()
    for job in jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        location = job.get("location", "")
        remote = bool(job.get("remote", False))

        # Apply pre-filter first
        should_skip, filter_reason, score_cap = pre_filter_job(title, company, location, remote)
        if should_skip:
            job["fit_score"] = 0
            job["fit_reasoning"] = f"Pre-filtered: {filter_reason}"
            job["estimated_salary"] = "unknown"
            job["effort_flag"] = "unknown"
            job["prep_level"] = 0
            job["prep_notes"] = ""
            continue

        text = f"{title} {company} {job.get('description', '')}".lower()
        pos = sum(1 for s in positive_signals if s in text)
        neg = sum(1 for s in negative_signals if s in text)
        score = min(10, max(1, 3 + pos - neg * 2))  # Start at 3 not 5

        if score_cap is not None and score > score_cap:
            score = score_cap

        job["fit_score"] = score
        job["fit_reasoning"] = f"Keyword scoring: {pos} positive, {neg} negative signals"
        job["estimated_salary"] = "unknown"
        job["effort_flag"] = "unknown"
        job["prep_level"] = 0
        job["prep_notes"] = ""

    # Save scored results (same as OpenAI path)
    config.scored_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    return jobs


# --- Step 3: Deduplicate against tracking ---


def step_dedup_against_tracking(config: PipelineConfig, jobs: list[dict]) -> list[dict]:
    """Remove jobs that are already tracked in the Kestrel DB."""
    logger.info("=" * 60)
    logger.info("STEP 3: DEDUP AGAINST TRACKING")
    logger.info("=" * 60)

    # Canonical dedup key (G-1122): normalize company/title so trivial drift
    # ("Hugging Face" vs slug-derived "Huggingface", "Acme GmbH" vs "Acme",
    # "Senior PM" vs "Senior PM (m/f/d)") doesn't let the same role re-surface.
    from normalize import job_key

    tracked_keys: set[tuple[str, str]] = set()

    # Check Kestrel DB (primary)
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from career_os.database import SessionLocal
        from career_os.models.models import Application

        db = SessionLocal()
        apps = db.query(Application).filter(Application.archived_at.is_(None)).all()
        for app in apps:
            tracked_keys.add(job_key(app.company, app.role))
        db.close()
        logger.info(f"Loaded {len(tracked_keys)} tracked jobs from Kestrel DB")
    except Exception as e:
        logger.warning(f"Could not read Kestrel DB: {e}")

        # Fallback to CSV
        if config.csv_path.exists():
            try:
                with open(config.csv_path) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        company = (row.get("company") or "").strip()
                        role = (row.get("role") or "").strip()
                        if company and role:
                            tracked_keys.add(job_key(company, role))
                logger.info(f"Fallback: loaded {len(tracked_keys)} tracked jobs from CSV")
            except Exception as e2:
                logger.warning(f"Could not read tracking CSV either: {e2}")

    new_jobs = []
    already_tracked = 0
    for job in jobs:
        key = job_key(job.get("company"), job.get("title"))
        if key in tracked_keys:
            already_tracked += 1
        else:
            new_jobs.append(job)

    logger.info(f"Dedup: {len(jobs)} → {len(new_jobs)} new ({already_tracked} already tracked)")
    return new_jobs


# --- Step 4: Filter by score ---


def step_filter(config: PipelineConfig, jobs: list[dict]) -> list[dict]:
    """Filter jobs by minimum score threshold."""
    logger.info("=" * 60)
    logger.info(f"STEP 4: FILTER (min_score={config.min_score})")
    logger.info("=" * 60)

    filtered = [j for j in jobs if j.get("fit_score", 0) >= config.min_score]
    filtered.sort(key=lambda j: j.get("fit_score", 0), reverse=True)

    logger.info(f"Filter: {len(jobs)} → {len(filtered)} jobs (score >= {config.min_score})")
    return filtered


# --- Step 5: Generate digest ---


def step_generate_digest(
    config: PipelineConfig,
    all_scraped: list[dict],
    scored: list[dict],
    filtered: list[dict],
) -> str:
    """Generate the daily digest markdown report."""
    logger.info("=" * 60)
    logger.info("STEP 5: GENERATE DIGEST")
    logger.info("=" * 60)

    lines = [
        f"# Daily Job Scan — {config.date}",
        "",
        f"**Pipeline mode:** {config.mode} | **Min score:** {config.min_score} | **Hours old:** {config.hours_old}h",
        "",
    ]

    # Stats section
    score_dist = {}
    for j in scored:
        s = j.get("fit_score", 0)
        score_dist[s] = score_dist.get(s, 0) + 1

    lines.extend(
        [
            "## Stats",
            "",
            f"- **Total scraped:** {len(all_scraped)}",
            f"- **After dedup + scoring:** {len(scored)}",
            f"- **Score >= {config.min_score} (new):** {len(filtered)}",
            f"- **Score distribution:** {' | '.join(f'{s}/10: {c}' for s, c in sorted(score_dist.items(), reverse=True))}",
            "",
        ]
    )

    # Main results table
    if filtered:
        lines.extend(
            [
                "## New Roles Found",
                "",
                "| Score | Company | Role | Location | Salary | Effort | Source | URL |",
                "|-------|---------|------|----------|--------|--------|--------|-----|",
            ]
        )
        for j in filtered:
            score = j.get("fit_score", "?")
            company = j.get("company", "?")[:30]
            title = j.get("title", "?")[:40]
            loc = j.get("location", "?")[:20]
            salary = j.get("estimated_salary", "?")
            effort = j.get("effort_flag", "?")
            source = j.get("source", "?")
            url = j.get("url", "")
            url_display = f"[Link]({url})" if url else "—"
            lines.append(
                f"| {score}/10 | {company} | {title} | {loc} | {salary} | {effort} | {source} | {url_display} |"
            )

        lines.append("")

        # Top 5 quick adds
        top5 = filtered[:5]
        lines.extend(
            [
                "## Quick adds (top 5 for /job-intake)",
                "",
            ]
        )
        for j in top5:
            url = j.get("url", "N/A")
            lines.append(
                f"- [{j.get('fit_score', '?')}/10] {j.get('company', '?')} — {j.get('title', '?')}: {url}"
            )
        lines.append("")

        # Reasoning details
        lines.extend(
            [
                "## Scoring Details",
                "",
            ]
        )
        for j in filtered[:15]:
            lines.append(
                f"**[{j.get('fit_score', '?')}/10] {j.get('company', '?')} — {j.get('title', '?')}**"
            )
            lines.append(f"  - {j.get('fit_reasoning', 'No reasoning')}")
            if j.get("prep_notes"):
                lines.append(f"  - Prep ({j.get('prep_level', '?')}/5): {j.get('prep_notes', '')}")
            lines.append("")
    else:
        lines.extend(
            [
                "## No new roles found above threshold",
                "",
                "Try lowering `PIPELINE_MIN_SCORE` or expanding search keywords.",
                "",
            ]
        )

    # Review Queue - wildcards, edge cases, ambiguous fits
    review_jobs = [j for j in scored if j.get("review_flag")]
    if review_jobs:
        lines.extend(
            [
                "## Review Queue (wildcards + edge cases)",
                "",
                "These roles scored low but were flagged for manual review - unusual angles, "
                "exceptional companies, or potential wildcard career moves.",
                "",
                "| Score | Company | Role | Review Reason |",
                "|-------|---------|------|---------------|",
            ]
        )
        for j in review_jobs:
            score = j.get("fit_score", "?")
            company = j.get("company", "?")[:30]
            title = j.get("title", "?")[:40]
            reason = j.get("review_reason", "")[:80]
            url = j.get("url", "")
            lines.append(f"| {score}/10 | {company} | {title} | {reason} |")
        lines.append("")

    lines.extend(
        [
            "---",
            f"*Generated by daily_pipeline.py at {config.timestamp}*",
        ]
    )

    digest = "\n".join(lines)

    # Write digest file
    config.tracking_dir.mkdir(parents=True, exist_ok=True)
    config.digest_path.write_text(digest)
    logger.info(f"Digest saved to {config.digest_path}")

    # Also write to GitHub Actions summary if available
    # CodeQL: digest contains public job data (titles, companies, scores), not secrets.
    # GH Actions summaries are only visible to repo collaborators.
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(digest)
        logger.info("Digest written to GitHub Actions summary")

    return digest


# --- Main pipeline ---


def run_pipeline() -> int:
    """Execute the full daily pipeline. Returns exit code."""
    config = PipelineConfig()

    logger.info(f"Daily Pipeline starting: {config.timestamp}")
    logger.info(f"Mode: {config.mode} | Min score: {config.min_score} | Hours: {config.hours_old}")
    logger.info(f"Location: {config.location} | Dry run: {config.dry_run}")

    exit_code = 0

    # Step 1: Scrape
    try:
        all_scraped = step_scrape(config)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        all_scraped = []
        exit_code = 2

    if not all_scraped:
        logger.warning("No jobs scraped — generating empty digest")
        step_generate_digest(config, [], [], [])
        return exit_code or 2

    # Step 2: Score
    # The failure-rate alarm raises RuntimeError when too many AI calls fail
    # (chain misconfigured / mass provider outage). We let that propagate as
    # exit 1 so the workflow fails loudly and existing Pushover failure path
    # triggers. Other scoring exceptions still get the soft exit-2 treatment.
    try:
        scored = step_score(config, all_scraped)
    except RuntimeError:
        # Loud-fail alarm — re-raise so main() exits non-zero.
        raise
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        scored = all_scraped
        exit_code = 2

    # Step 3: Dedup against tracking
    new_jobs = step_dedup_against_tracking(config, scored)

    # Step 4: Filter
    filtered = step_filter(config, new_jobs)

    # Step 5: Generate digest
    digest = step_generate_digest(config, all_scraped, scored, filtered)

    # Print summary to stdout
    print("\n" + "=" * 60)
    print(f"DAILY PIPELINE COMPLETE — {config.date}")
    print(
        f"Scraped: {len(all_scraped)} | Scored: {len(scored)} | New: {len(new_jobs)} | Above threshold: {len(filtered)}"
    )
    print(f"Digest: {config.digest_path}")
    print("=" * 60)

    if filtered:
        print("\nTop matches:")
        for j in filtered[:5]:
            print(
                f"  [{j.get('fit_score', '?')}/10] {j.get('company', '?')} — {j.get('title', '?')}"
            )

    return exit_code


def main():
    # Ensure logs directory exists before FileHandler tries to open it
    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                PROJECT_ROOT / "logs" / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                mode="w",
            ),
        ],
    )

    exit_code = run_pipeline()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
