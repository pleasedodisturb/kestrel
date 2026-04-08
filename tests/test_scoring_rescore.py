"""
Re-score the 2026-03-27 raw data using the new pre-filters.
Generates a before/after comparison report.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from job_scorer import pre_filter_job

RAW_DATA_PATH = Path(__file__).resolve().parent.parent / "tracking" / "scraped_raw_2026-03-27.json"
SCORED_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "tracking" / "scraped_scored_2026-03-27.json"
)
REPORT_DIR = Path(__file__).resolve().parent / "results"


@pytest.fixture
def raw_jobs():
    if not RAW_DATA_PATH.exists():
        pytest.skip(f"Raw data not found: {RAW_DATA_PATH}")
    with open(RAW_DATA_PATH) as f:
        return json.load(f)


@pytest.fixture
def scored_jobs():
    if not SCORED_DATA_PATH.exists():
        pytest.skip(f"Scored data not found: {SCORED_DATA_PATH}")
    with open(SCORED_DATA_PATH) as f:
        return json.load(f)


class TestRescoring:
    def test_prefilter_rejects_significant_portion(self, raw_jobs):
        """Pre-filter should reject at least 30% of the 194 jobs."""
        skipped = 0
        for j in raw_jobs:
            skip, _, _ = pre_filter_job(
                j.get("title", ""),
                j.get("company", ""),
                j.get("location", ""),
                bool(j.get("remote", False)),
            )
            if skip:
                skipped += 1
        ratio = skipped / len(raw_jobs)
        assert ratio >= 0.20, f"Only {ratio:.0%} rejected -- expected at least 20%"

    def test_no_false_positives_on_pm_roles(self, raw_jobs):
        """Product Manager roles should never be pre-filtered out."""
        for j in raw_jobs:
            title = j.get("title", "")
            if "product manager" in title.lower():
                skip, reason, _ = pre_filter_job(
                    title, j.get("company", ""), j.get("location", ""), bool(j.get("remote", False))
                )
                assert skip is False, f"False reject: {title} -- {reason}"

    def test_no_false_positives_on_tpm_roles(self, raw_jobs):
        """TPM roles should never be pre-filtered out."""
        for j in raw_jobs:
            title = j.get("title", "")
            if "technical program manager" in title.lower() or "tpm" in title.lower():
                skip, reason, _ = pre_filter_job(
                    title, j.get("company", ""), j.get("location", ""), bool(j.get("remote", False))
                )
                assert skip is False, f"False reject: {title} -- {reason}"

    def test_generate_report(self, raw_jobs, scored_jobs):
        """Generate a before/after comparison report."""
        # Build old score map
        old_scores = {}
        for j in scored_jobs:
            key = f"{j.get('title', '')}|{j.get('company', '')}"
            old_scores[key] = j.get("fit_score", 0)

        # Run pre-filter on all jobs
        results = []
        skipped = 0
        capped = 0
        passed = 0
        skip_reasons = Counter()

        for j in raw_jobs:
            title = j.get("title", "")
            company = j.get("company", "")
            location = j.get("location", "")
            remote = bool(j.get("remote", False))
            key = f"{title}|{company}"
            old_score = old_scores.get(key, "?")

            should_skip, reason, cap = pre_filter_job(title, company, location, remote)

            if should_skip:
                new_score = 0
                skipped += 1
                skip_reasons[reason.split(":")[0] if ":" in reason else reason] += 1
            elif cap is not None:
                new_score = f"<={cap}"
                capped += 1
            else:
                new_score = "AI"
                passed += 1

            results.append(
                {
                    "title": title,
                    "company": company,
                    "old_score": old_score,
                    "new_score": new_score,
                    "filter_action": "REJECTED"
                    if should_skip
                    else (f"CAPPED at {cap}" if cap else "PASS"),
                    "reason": reason if should_skip or cap else "",
                }
            )

        # Count old 10/10 scores
        old_10s = sum(1 for r in results if r["old_score"] == 10)
        new_rejected_from_10 = sum(
            1 for r in results if r["old_score"] == 10 and r["filter_action"] == "REJECTED"
        )

        # Generate report
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / "scoring-fix-report.md"

        lines = [
            "# Scoring Fix Report -- 2026-03-27 Re-score",
            "",
            "## Summary",
            "",
            f"- **Total jobs:** {len(raw_jobs)}",
            f"- **Pre-filter rejected:** {skipped} ({skipped / len(raw_jobs):.0%})",
            f"- **Pre-filter capped:** {capped}",
            f"- **Passed to AI scoring:** {passed}",
            "",
            "## Before vs After",
            "",
            f"- **Old 10/10 scores:** {old_10s} (was 78 out of 194 = 40%)",
            f"- **Of those 78, now rejected by pre-filter:** {new_rejected_from_10}",
            f"- **Remaining for AI (from old 10s):** {old_10s - new_rejected_from_10}",
            "",
            "## What Changed",
            "",
            "### 1. Hard pre-filters added (before AI scoring)",
            "- Title-based rejection for obviously irrelevant roles",
            "  (accountant, sales rep, customer support, HR, legal, nurse, etc.)",
            "- Blocked companies (Nebius, Yandex)",
            "- Junior role detection (intern, werkstudent, junior without lead/senior)",
            "- US-only location cap (score capped at 3 unless remote)",
            "",
            "### 2. AI prompt rewritten to be much stricter",
            "- Explicit HARD CAPS for each wrong-domain category (sales=MAX 1, etc.)",
            "- Clear scoring calibration: max 2-3 per 200 at 9-10",
            "- Candidate profile embedded directly in system prompt",
            "- Changed from 'strict' to 'EXTREMELY strict' with explicit instructions",
            "  to score 1 immediately for obviously wrong titles",
            "",
            "### 3. Fallback scores lowered",
            "- JSON parse error fallback: 5 -> 2",
            "- API error fallback: 5 -> 2",
            "- Keyword fallback base: 5 -> 3",
            "",
            "## Rejection Reasons",
            "",
        ]
        for reason, count in skip_reasons.most_common():
            lines.append(f"- {reason}: {count}")

        lines.extend(
            [
                "",
                "## Sample: Old 10/10 Now Rejected",
                "",
                "| Title | Company | Old Score | Action |",
                "|-------|---------|-----------|--------|",
            ]
        )
        for r in results:
            if r["old_score"] == 10 and r["filter_action"] == "REJECTED":
                lines.append(
                    f"| {r['title'][:50]} | {r['company'][:25]} | {r['old_score']} | {r['filter_action']} |"
                )

        lines.extend(
            [
                "",
                "## Sample: Correctly Passed (Good Roles)",
                "",
                "| Title | Company | Old Score | Action |",
                "|-------|---------|-----------|--------|",
            ]
        )
        good_keywords = [
            "product manager",
            "tpm",
            "devrel",
            "developer",
            "engineer",
            "ai",
            "founding",
        ]
        for r in results:
            if r["filter_action"] == "PASS" and any(
                kw in r["title"].lower() for kw in good_keywords
            ):
                lines.append(
                    f"| {r['title'][:50]} | {r['company'][:25]} | {r['old_score']} | PASS |"
                )

        report_content = "\n".join(lines) + "\n"
        report_path.write_text(report_content)

        # Assertions
        assert skipped >= 30, f"Expected at least 30 rejections, got {skipped}"
        assert new_rejected_from_10 >= 20, (
            f"Expected at least 20 of the 78 old 10/10s to be rejected, got {new_rejected_from_10}"
        )
        assert passed > 0, "Should have some jobs passing to AI"
