#!/usr/bin/env python3
"""
Enhanced local job scorer — no API calls needed.

Applies the same scoring rubric as job_scorer.py but using deterministic
keyword/pattern matching. Designed to run fast on 1000+ jobs locally.

Usage:
    .venv/bin/python tools/local_scorer.py tracking/scraped_raw_2026-04-02.json
    .venv/bin/python tools/local_scorer.py tracking/scraped_raw_2026-04-02.json --min-score 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from job_scorer import pre_filter_job

# --- Dream companies (AI-native, target list) ---
DREAM_COMPANIES = {
    "anthropic",
    "mistral",
    "cohere",
    "deepl",
    "aleph alpha",
    "scale ai",
    "hugging face",
    "huggingface",
    "lovable",
    "databricks",
    "openai",
    "n8n",
    "jetbrains",
    "qdrant",
    "weaviate",
    "langchain",
    "vercel",
    "supabase",
    "hashicorp",
    "grafana",
    "elastic",
    "datadog",
    "cloudflare",
    "netlify",
    "deno",
    "bun",
    "replit",
    "cursor",
    "codeium",
    "tabnine",
    "sourcegraph",
    "linear",
    "raycast",
}

STRONG_COMPANIES = {
    "nvidia",
    "shopware",
    "revolut",
    "stripe",
    "klarna",
    "wise",
    "zalando",
    "delivery hero",
    "sumup",
    "personio",
    "celonis",
    "contentful",
    "agora",
    "ashby",
    "attio",
    "plain",
    "notion",
    "figma",
    "miro",
    "canva",
    "airtable",
    "retool",
    "postman",
    "snyk",
    "sentry",
    "pagerduty",
    "clickhouse",
    "cockroachdb",
    "planetscale",
    "neon",
    "timescale",
    "airbyte",
    "dbt",
    "sword health",
    "pandadoc",
    "unity",
    "photoroom",
    "gladia",
    "synthflow",
    "omnora",
    "cognite",
    "cresta",
}

# --- Title patterns with scores ---
# (pattern, base_score_boost) — matched case-insensitively
DREAM_TITLE_PATTERNS = [
    (r"technical program manager.*ai", 4),
    (r"tpm.*ai", 4),
    (r"head of developer relations", 4),
    (r"developer advocate.*ai", 4),
    (r"devrel.*ai", 4),
    (r"founding.*engineer", 3),
    (r"founding.*product", 3),
    (r"ai.native.*tpm", 4),
    (r"ai.native.*program", 4),
    (r"product engineer.*ai", 3),
    (r"senior product engineer", 3),
    (r"staff.*product.*engineer", 3),
    (r"ai program lead", 4),
    (r"innovation lead.*ai", 3),
    (r"head of product.*ai", 3),
    (r"director.*ai.*initiative", 3),
    (r"vp.*engineering", 3),
    (r"head of engineering", 3),
]

STRONG_TITLE_PATTERNS = [
    (r"technical program manager", 3),
    (r"senior.*product manager", 2),
    (r"staff.*product manager", 3),
    (r"principal.*product manager", 3),
    (r"product manager.*ai", 3),
    (r"ai product manager", 3),
    (r"technical product manager", 3),
    (r"developer relations", 2),
    (r"developer advocate", 2),
    (r"product engineer", 2),
    (r"ai engineer", 2),
    (r"ml engineer", 2),
    (r"innovation.*manager", 2),
    (r"engineering manager.*ai", 2),
    (r"engineering manager.*product", 2),
    (r"forward deployed engineer", 2),
    (r"solutions engineer.*ai", 2),
    (r"director.*product", 2),
    (r"head of new products", 2),
    (r"ki.*produktmanager", 2),
    (r"ki.*ingenieur", 2),
    (r"innovationsmanager", 2),
    (r"programmmanager", 1),
    (r"projektleiter", 1),
]

# --- Description signals ---
STRONG_POSITIVE_KEYWORDS = [
    "llm",
    "large language model",
    "agentic",
    "mcp",
    "ai-native",
    "generative ai",
    "genai",
    "gpt",
    "claude",
    "foundational model",
    "ml pipeline",
    "model training",
    "rag",
    "retrieval augmented",
    "transformer",
    "embedding",
    "vector database",
    "ai product",
    "ai strategy",
    "ai transformation",
]

POSITIVE_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "natural language processing",
    "nlp",
    "computer vision",
    "product-led",
    "developer experience",
    "developer tools",
    "open source",
    "api platform",
    "platform engineering",
    "cross-functional",
    "autonomous",
    "innovation mandate",
    "startup",
    "scale-up",
    "equity",
    "rsu",
    "stock options",
    "remote-first",
    "async",
    "4-day week",
    "work-life",
    "sustainable pace",
    "founding team",
    "series a",
    "series b",
    "series c",
    "product engineer",
    "full-stack",
]

NEGATIVE_KEYWORDS = [
    "pmbok",
    "pmo",
    "coordinate meetings",
    "status reporting",
    "waterfall",
    "prince2",
    "itil",
    "itsm",
    "heavy process",
    "documentation-heavy",
    "must have 10+ years",
    "must have 15+ years",
    "rigid hierarchy",
    "matrix organization",
    "on-call rotation",
    "24/7 support",
]

RED_FLAG_KEYWORDS = [
    "staffing agency",
    "personalvermittlung",
    "zeitarbeit",
    "wordpress developer",
    "php developer",
    "sap consultant",
    "sap basis",
    "abap",
    "mainframe",
    "cobol",
    "rpg developer",
]

# --- Location scoring ---
FRANKFURT_BONUS = ["frankfurt", "offenbach", "wiesbaden", "mainz", "darmstadt"]
GERMANY_CITIES = [
    "berlin",
    "munich",
    "münchen",
    "hamburg",
    "cologne",
    "köln",
    "stuttgart",
    "düsseldorf",
    "dusseldorf",
    "mannheim",
    "leipzig",
]


def score_job_local(job: dict) -> dict:
    """Score a single job using deterministic rules."""
    title = (job.get("title") or "").lower().strip()
    company = (job.get("company") or "").lower().strip()
    location = (job.get("location") or "").lower().strip()
    description = (job.get("description") or "").lower()
    remote = bool(job.get("remote", False))
    tags = [t.lower() for t in job.get("tags", [])]
    text = f"{title} {company} {description} {' '.join(tags)}"

    # Pre-filter
    should_skip, reason, score_cap = pre_filter_job(
        job.get("title", ""), job.get("company", ""), job.get("location", ""), remote
    )
    if should_skip:
        job["fit_score"] = 0
        job["fit_reasoning"] = f"Pre-filtered: {reason}"
        job["estimated_salary"] = "unknown"
        job["effort_flag"] = "unknown"
        job["prep_level"] = 0
        job["prep_notes"] = ""
        job["review_flag"] = False
        return job

    score = 1  # Base score
    reasons = []

    # --- Company tier ---
    company_clean = re.sub(r"\b(gmbh|ag|se|inc|ltd|co|kg|ohg|e\.v\.)\b", "", company).strip()
    for dc in DREAM_COMPANIES:
        if dc in company_clean:
            score += 3
            reasons.append(f"dream company: {dc}")
            break
    else:
        for sc in STRONG_COMPANIES:
            if sc in company_clean:
                score += 2
                reasons.append(f"strong company: {sc}")
                break

    # --- Title patterns ---
    best_title_boost = 0
    best_title_match = ""
    for pattern, boost in DREAM_TITLE_PATTERNS:
        if re.search(pattern, title):
            if boost > best_title_boost:
                best_title_boost = boost
                best_title_match = pattern
    for pattern, boost in STRONG_TITLE_PATTERNS:
        if re.search(pattern, title):
            if boost > best_title_boost:
                best_title_boost = boost
                best_title_match = pattern
    if best_title_boost > 0:
        score += best_title_boost
        reasons.append(f"title match: {best_title_match}")

    # --- Description signals ---
    strong_pos = sum(1 for kw in STRONG_POSITIVE_KEYWORDS if kw in text)
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    red = sum(1 for kw in RED_FLAG_KEYWORDS if kw in text)

    score += min(strong_pos * 1, 3)  # Up to +3 from strong AI signals
    score += min(pos, 2)  # Up to +2 from positive signals
    score -= neg  # Each negative signal subtracts 1
    score -= red * 2  # Red flags subtract 2 each

    if strong_pos > 0:
        reasons.append(f"{strong_pos} strong AI signals")
    if pos > 0:
        reasons.append(f"{pos} positive signals")
    if neg > 0:
        reasons.append(f"{neg} negative signals")
    if red > 0:
        reasons.append(f"{red} red flags")

    # --- Location scoring ---
    if any(loc in location for loc in FRANKFURT_BONUS):
        score += 1
        reasons.append("Frankfurt area")
    elif remote or "remote" in location or "remote" in " ".join(tags):
        score += 1
        reasons.append("remote")
    elif any(loc in location for loc in GERMANY_CITIES):
        pass  # No bonus, no penalty
    else:
        score -= 1
        reasons.append("non-ideal location")

    # --- No description penalty ---
    if not description.strip():
        score = min(score, 4)
        reasons.append("no description")

    # Clamp and apply cap
    score = max(1, min(10, score))
    if score_cap is not None and score > score_cap:
        reasons.append(f"capped from {score} to {score_cap}")
        score = score_cap

    # Effort flag heuristic
    effort = "unknown"
    if any(kw in text for kw in ["founding", "0-1", "greenfield", "build from scratch"]):
        effort = "high-intensity"
    elif any(kw in text for kw in ["sustainable", "work-life", "async", "4-day"]):
        effort = "sweet-spot"
    elif any(kw in text for kw in ["hypergrowth", "fast-paced", "high-growth"]):
        effort = "moderate"

    # Salary estimation heuristic
    salary = "unknown"
    if "founding" in title or "founding" in description[:200]:
        salary = "90-120k EUR + equity"
    elif any(kw in title for kw in ["head of", "director", "vp "]):
        salary = "120-160k EUR"
    elif any(kw in title for kw in ["staff", "principal", "lead"]):
        salary = "100-140k EUR"
    elif any(kw in title for kw in ["senior"]):
        salary = "80-120k EUR"
    else:
        salary = "70-100k EUR"

    job["fit_score"] = score
    job["fit_reasoning"] = "; ".join(reasons) if reasons else "baseline score"
    job["estimated_salary"] = salary
    job["effort_flag"] = effort
    job["prep_level"] = 0
    job["prep_notes"] = ""
    job["review_flag"] = 4 <= score <= 6
    job["review_reason"] = "borderline — manual review recommended" if 4 <= score <= 6 else ""

    return job


def main():
    parser = argparse.ArgumentParser(description="Local job scorer (no API calls)")
    parser.add_argument("json_path", help="Path to scraped_raw JSON")
    parser.add_argument(
        "--min-score", type=int, default=0, help="Only show jobs at or above this score"
    )
    parser.add_argument(
        "--output", help="Output path (default: tracking/scraped_scored_<date>.json)"
    )
    args = parser.parse_args()

    data = json.loads(Path(args.json_path).read_text())
    print(f"Scoring {len(data)} jobs locally...")

    scored = [score_job_local(j) for j in data]

    # Sort by score descending
    scored.sort(key=lambda j: j.get("fit_score", 0), reverse=True)

    # Output path
    input_name = Path(args.json_path).stem.replace("scraped_raw", "scraped_scored")
    output_path = (
        Path(args.output) if args.output else Path(args.json_path).parent / f"{input_name}.json"
    )
    output_path.write_text(json.dumps(scored, indent=2, ensure_ascii=False))

    # Stats
    from collections import Counter

    dist = Counter(j["fit_score"] for j in scored)
    print("\nScore distribution:")
    for score in sorted(dist.keys(), reverse=True):
        count = dist[score]
        bar = "█" * min(count, 50)
        print(f"  {score:2d}: {count:4d} {bar}")

    # Show top results
    top = [j for j in scored if j["fit_score"] >= (args.min_score or 5)]
    print(f"\n{'=' * 80}")
    print(f"Top {len(top)} jobs (score >= {args.min_score or 5}):")
    print(f"{'=' * 80}")
    for j in top:
        s = j["fit_score"]
        title = j.get("title", "?")
        company = j.get("company", "?")
        loc = j.get("location", "?")
        sal = j.get("estimated_salary", "?")
        effort = j.get("effort_flag", "?")
        reason = j.get("fit_reasoning", "")
        url = j.get("url", "")
        print(f"\n  [{s:2d}/10] {title}")
        print(f"         @ {company} | {loc} | {effort}")
        print(f"         {reason}")

    print(f"\nSaved {len(scored)} scored jobs to {output_path}")


if __name__ == "__main__":
    main()
