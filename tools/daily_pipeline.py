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
  OPENAI_API_KEY       — Required for AI scoring (GPT-4o-mini)
  PIPELINE_MODE        — api-only | api-plus | all (default: api-only)
  PIPELINE_MIN_SCORE   — Minimum score to include in digest (default: 5)
  PIPELINE_HOURS_OLD   — Max posting age in hours (default: 24)
  PIPELINE_LOCATION    — Search location (default: Berlin)
  PIPELINE_DRY_RUN     — Set to "1" to skip CSV writes (default: 0)
  GITHUB_STEP_SUMMARY  — GitHub Actions summary file (auto-set in Actions)

Exit codes:
  0 — Success
  1 — Fatal error (missing deps, no API key)
  2 — Partial failure (some sources failed, digest still generated)
"""

from __future__ import annotations

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

logger = logging.getLogger("daily_pipeline")


# --- Config ---


class PipelineConfig:
    def __init__(self):
        self.mode = os.getenv("PIPELINE_MODE", "api-only")
        self.min_score = int(os.getenv("PIPELINE_MIN_SCORE", "5"))
        self.hours_old = int(os.getenv("PIPELINE_HOURS_OLD", "24"))
        self.location = os.getenv("PIPELINE_LOCATION", "Berlin")
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


def step_score(config: PipelineConfig, jobs: list[dict]) -> list[dict]:
    """Score each job against the profile using OpenAI."""
    logger.info("=" * 60)
    logger.info("STEP 2: SCORE")
    logger.info("=" * 60)

    if not config.openai_key:
        logger.warning("No OPENAI_API_KEY — using keyword-based fallback scoring")
        return _fallback_score(jobs)

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed — using fallback scoring")
        return _fallback_score(jobs)

    # Support OpenRouter keys (sk-or-*) by auto-detecting base_url
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url and config.openai_key.startswith("sk-or-"):
        base_url = "https://openrouter.ai/api/v1"
    client = OpenAI(api_key=config.openai_key, base_url=base_url)

    # Load profile for context
    profile_context = ""
    if config.profile_path.exists():
        profile_context = config.profile_path.read_text()[:3000]

    from job_scorer import (
        PROFILE_CRITERIA,
        SCORING_SYSTEM_PROMPT_WITH_REVIEW,
        apply_hard_caps,
        pre_filter_job,
    )

    scored = []
    skipped = 0
    total = len(jobs)
    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        location = job.get("location", "")
        remote = bool(job.get("remote", False))
        description = job.get("description", "")

        # --- Pre-filter: skip obviously irrelevant jobs before AI scoring ---
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
                logger.info(f"Scored {i + 1}/{total} jobs (skipped {skipped})")
            continue

        if not description or description == "nan":
            # Use title + company + tags as description proxy
            description = f"Title: {title}\nCompany: {company}\nLocation: {location}\nTags: {', '.join(job.get('tags', []))}"

        desc_truncated = description[:3000]

        try:
            response = client.chat.completions.create(
                model="anthropic/claude-sonnet-4.6",
                messages=[
                    {"role": "system", "content": SCORING_SYSTEM_PROMPT_WITH_REVIEW},
                    {
                        "role": "user",
                        "content": f"CANDIDATE PROFILE:\n{PROFILE_CRITERIA}\n\nADDITIONAL CONTEXT:\n{profile_context[:1000]}\n\nJOB POSTING:\nTitle: {title}\nCompany: {company}\nDescription: {desc_truncated}",
                    },
                ],
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                # Handle single quotes from some models
                result = json.loads(raw.replace("'", '"'))

            ai_score = int(result.get("score", 2))

            # Apply score cap from pre-filter (e.g. US-only location)
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

        except Exception as e:
            status_code = getattr(e, "status_code", None)
            error_str = str(e)

            if status_code in (402, 429) or "insufficient_quota" in error_str.lower():
                logger.error(
                    f"AI credits exhausted after scoring {len(scored)}/{total} jobs — stopping. "
                    "Add credits at https://openrouter.ai"
                )
                job["fit_score"] = 0
                job["fit_reasoning"] = "Not scored: AI credits exhausted"
                job["estimated_salary"] = "unknown"
                job["effort_flag"] = "unknown"
                job["prep_level"] = 0
                job["prep_notes"] = ""
                scored.append(job)
                for remaining_job in jobs[i + 1 :]:
                    remaining_job["fit_score"] = 0
                    remaining_job["fit_reasoning"] = "Not scored: AI credits exhausted"
                    remaining_job["estimated_salary"] = "unknown"
                    remaining_job["effort_flag"] = "unknown"
                    remaining_job["prep_level"] = 0
                    remaining_job["prep_notes"] = ""
                    scored.append(remaining_job)
                break

            logger.warning(f"Scoring failed for {title} @ {company}: {e}")
            job["fit_score"] = 2  # Default to 2, not 5 -- unknown jobs shouldn't pass
            job["fit_reasoning"] = f"Scoring error: {e}"
            job["estimated_salary"] = "unknown"
            job["effort_flag"] = "unknown"
            job["prep_level"] = 0
            job["prep_notes"] = ""

        scored.append(job)

        if (i + 1) % 10 == 0:
            logger.info(f"Scored {i + 1}/{total} jobs (skipped {skipped})")

    logger.info(f"Scoring complete: {len(scored)} jobs scored")

    # Apply hard caps -- enforce score ceilings for poor-fit categories
    scored = apply_hard_caps(scored)
    capped = sum(1 for j in scored if j.get("cap_applied"))
    if capped:
        logger.info(f"Hard caps applied: {capped} jobs capped")

    # Save scored results
    config.scored_path.write_text(json.dumps(scored, indent=2, ensure_ascii=False))

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

    # Apply hard caps -- enforce score ceilings for poor-fit categories
    from job_scorer import apply_hard_caps as _apply_hard_caps

    jobs = _apply_hard_caps(jobs)

    # Save scored results (same as OpenAI path)
    config.scored_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    return jobs


# --- Step 3: Deduplicate against tracking ---


def step_dedup_against_tracking(config: PipelineConfig, jobs: list[dict]) -> list[dict]:
    """Remove jobs that are already tracked in CareerOS DB."""
    logger.info("=" * 60)
    logger.info("STEP 3: DEDUP AGAINST TRACKING")
    logger.info("=" * 60)

    tracked_keys: set[tuple[str, str]] = set()

    # Check CareerOS DB (primary)
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from career_os.database import SessionLocal
        from career_os.models.models import Application

        db = SessionLocal()
        apps = db.query(Application).filter(Application.archived_at.is_(None)).all()
        for app in apps:
            tracked_keys.add((app.company.lower().strip(), app.role.lower().strip()))
        db.close()
        logger.info(f"Loaded {len(tracked_keys)} tracked jobs from CareerOS DB")
    except Exception as e:
        logger.warning(f"Could not read CareerOS DB: {e}")

        # Fallback to CSV
        if config.csv_path.exists():
            try:
                with open(config.csv_path) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        company = row.get("company", "").lower().strip()
                        role = row.get("role", "").lower().strip()
                        if company and role:
                            tracked_keys.add((company, role))
                logger.info(f"Fallback: loaded {len(tracked_keys)} tracked jobs from CSV")
            except Exception as e2:
                logger.warning(f"Could not read tracking CSV either: {e2}")

    new_jobs = []
    already_tracked = 0
    for job in jobs:
        key = (job.get("company", "").lower().strip(), job.get("title", "").lower().strip())
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
    try:
        scored = step_score(config, all_scraped)
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
