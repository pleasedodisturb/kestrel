"""
New German/EMEA job market scrapers.

Covers sources not in the original pipeline:
- Himalayas (free JSON API, remote jobs, no auth)
- Greenhouse Job Board API (public, per-company, no auth)
- Lever Postings API (public, per-company, no auth)
- Ashby Job Board API (public, per-company, no auth)
- startup.jobs (Algolia-backed search)
- TheHub.io (Berlin/Nordic startup ecosystem, HTML scraping)

All scrapers return list[ScrapedJob] and gracefully return [] on failure.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from scrape_resilient import (
    MAX_DESCRIPTION_LENGTH,
    ScrapedJob,
    _get_user_agent,
    _random_delay,
    _retry_with_backoff,
)

logger = logging.getLogger("scrape_new_sources")


# ---------------------------------------------------------------------------
# Target company lists for ATS board scrapers (Greenhouse, Lever, Ashby)
# These are REDACTED
# REDACTED.
# ---------------------------------------------------------------------------

# Greenhouse companies: slug is from their careers URL
# e.g. https://boards.greenhouse.io/{slug}
GREENHOUSE_COMPANIES: list[str] = [
    "mistral",  # Mistral AI
    "huggingface",  # Hugging Face
    "cohere",  # Cohere
    "anthropic",  # Anthropic
    "deepmind",  # Google DeepMind
    "figma",  # Figma
    "linear",  # Linear
    "vercel",  # Vercel
    "notion",  # Notion
    "airtable",  # Airtable
    "hashicorp",  # HashiCorp
    "grafana",  # Grafana Labs
    "postman",  # Postman
    "snyk",  # Snyk
    "miro",  # Miro
    "contentful",  # Contentful (Berlin)
    "datadog",  # Datadog
    "sourcegraph",  # Sourcegraph
    "gitlabinc",  # GitLab
    "anyscale",  # Anyscale (Ray)
    "replit",  # Replit
    "together",  # Together AI
    "modal",  # Modal
    "weights-and-biases",  # Weights & Biases
    "deepl",  # DeepL (Cologne)
    "celonis",  # Celonis (Munich)
    "personio",  # Personio (Munich)
    "scalableai",  # Scalable Capital
    "tldraw",  # tldraw
    "sentry",  # Sentry
    "supabase",  # Supabase
]

# Lever companies: slug from https://jobs.lever.co/{slug}
LEVER_COMPANIES: list[str] = [
    "proton",  # Proton (privacy, Switzerland)
    "tuta",  # Tuta (Tutanota, Germany)
    "lovable",  # Lovable (AI coding)
    "oxide",  # Oxide Computer
    "fly",  # Fly.io
    "railway",  # Railway
    "retool",  # Retool
    "render",  # Render
    "webflow",  # Webflow
    "cal-com",  # Cal.com
    "descript",  # Descript
    "livekit",  # LiveKit
    "langchain",  # LangChain
    "prefect",  # Prefect
    "zed-industries",  # Zed
    "netlify",  # Netlify
    "prisma",  # Prisma (Berlin)
    "commercetools",  # commercetools (Munich)
]

# Ashby companies: slug from their job board URL
ASHBY_COMPANIES: list[str] = [
    "linear",  # Linear
    "vercel",  # Vercel
    "resend",  # Resend
    "clerk",  # Clerk
    "deno",  # Deno
    "neon",  # Neon (serverless Postgres)
    "turso",  # Turso
    "unkey",  # Unkey
    "inngest",  # Inngest
    "val-town",  # Val Town
]


# ---------------------------------------------------------------------------
# Himalayas API (free, no auth, remote-focused)
# ---------------------------------------------------------------------------

HIMALAYAS_API = "https://himalayas.app/jobs/api"


def scrape_himalayas(
    keywords: list[str] | None = None,
    limit: int = 20,
) -> list[ScrapedJob]:
    """
    Scrape Himalayas free JSON API. No auth needed.
    Max 20 results per request (API limit as of 2025).
    Supports keyword search and geo filtering.
    https://himalayas.app/docs/remote-jobs-api
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    search_terms = keywords or [
        "product manager",
        "program manager",
        "AI engineer",
        "developer relations",
    ]

    for term in search_terms:

        def _fetch(search=term):
            with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.get(
                    "https://himalayas.app/jobs/api",
                    params={"limit": min(limit, 20), "q": search},
                )
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        for j in data.get("jobs", []):
            location = j.get("location", "")
            jobs.append(
                ScrapedJob(
                    title=j.get("title", ""),
                    company=j.get("companyName", j.get("company_name", "")),
                    location=location,
                    url=j.get("applicationUrl", j.get("url", "")),
                    source="himalayas",
                    description=str(j.get("description", ""))[:MAX_DESCRIPTION_LENGTH],
                    posted=j.get("pubDate", j.get("published_at", "")),
                    remote=True,
                    salary=j.get("salary", ""),
                    tags=j.get("categories", []) if isinstance(j.get("categories"), list) else [],
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"Himalayas: {len(jobs)} jobs")
    return jobs


# ---------------------------------------------------------------------------
# Greenhouse Job Board API (public, per-company, no auth)
# https://developers.greenhouse.io/job-board.html
# ---------------------------------------------------------------------------

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def scrape_greenhouse(
    companies: list[str] | None = None,
    keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """
    Scrape Greenhouse public job board API for specific companies.
    No auth needed. Returns all open positions per company.
    Keyword filter applied client-side on title.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    companies = companies or GREENHOUSE_COMPANIES
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for slug in companies:
        url = GREENHOUSE_API.format(slug=slug)

        def _fetch(u=url):
            with httpx.Client(timeout=20, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.get(u, params={"content": "true"})
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        for j in data.get("jobs", []):
            title = j.get("title", "")
            # Apply keyword filter if provided
            if kw_lower and not any(k in title.lower() for k in kw_lower):
                continue

            loc_obj = j.get("location", {})
            location = loc_obj.get("name", "") if isinstance(loc_obj, dict) else str(loc_obj)

            # Extract department
            departments = j.get("departments", [])
            dept_names = [d.get("name", "") for d in departments if isinstance(d, dict)]

            content = j.get("content", "")
            # Strip HTML tags from content for description
            desc = re.sub(r"<[^>]+>", " ", unescape(content))[:MAX_DESCRIPTION_LENGTH]

            job_url = j.get("absolute_url", "")

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=slug.replace("-", " ").title(),
                    location=location,
                    url=job_url,
                    source="greenhouse",
                    description=desc,
                    posted=j.get("updated_at", ""),
                    remote="remote" in location.lower(),
                    tags=dept_names,
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"Greenhouse: {len(jobs)} jobs from {len(companies)} companies")
    return jobs


# ---------------------------------------------------------------------------
# Lever Postings API (public, per-company, no auth)
# https://github.com/lever/postings-api
# ---------------------------------------------------------------------------

LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def scrape_lever(
    companies: list[str] | None = None,
    keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """
    Scrape Lever public postings API for specific companies.
    No auth needed. Returns all open positions per company.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    companies = companies or LEVER_COMPANIES
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for slug in companies:
        url = LEVER_API.format(slug=slug)

        def _fetch(u=url):
            with httpx.Client(timeout=20, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.get(u)
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data or not isinstance(data, list):
            continue

        for j in data:
            title = j.get("text", "")
            if kw_lower and not any(k in title.lower() for k in kw_lower):
                continue

            categories = j.get("categories", {})
            location = categories.get("location", "")
            team = categories.get("team", "")
            commitment = categories.get("commitment", "")

            desc_parts = []
            lists_data = j.get("lists", [])
            for lst in lists_data:
                desc_parts.append(lst.get("text", ""))
                desc_parts.append(lst.get("content", ""))
            desc = " ".join(filter(None, desc_parts))
            desc = re.sub(r"<[^>]+>", " ", unescape(desc))[:MAX_DESCRIPTION_LENGTH]

            tags = [t for t in [team, commitment] if t]

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=slug.replace("-", " ").title(),
                    location=location,
                    url=j.get("hostedUrl", j.get("applyUrl", "")),
                    source="lever",
                    description=desc,
                    posted=str(j.get("createdAt", "")),
                    remote="remote" in location.lower(),
                    tags=tags,
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"Lever: {len(jobs)} jobs from {len(companies)} companies")
    return jobs


# ---------------------------------------------------------------------------
# Ashby Job Board API (public, per-company, no auth)
# https://developers.ashbyhq.com/docs/public-job-posting-api
# ---------------------------------------------------------------------------

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def scrape_ashby(
    companies: list[str] | None = None,
    keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """
    Scrape Ashby public job board API for specific companies.
    No auth needed. Returns all published job postings.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    companies = companies or ASHBY_COMPANIES
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for slug in companies:
        url = ASHBY_API.format(slug=slug)

        def _fetch(u=url):
            with httpx.Client(timeout=20, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.get(u, params={"includeCompensation": "true"})
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        # Ashby returns {jobs: [...]} or {jobPostings: [...]}
        postings = data.get("jobs", data.get("jobPostings", []))

        for j in postings:
            title = j.get("title", "")
            if kw_lower and not any(k in title.lower() for k in kw_lower):
                continue

            location = j.get("location", j.get("locationName", ""))
            if isinstance(location, dict):
                location = location.get("name", "")

            department = j.get("department", j.get("departmentName", ""))
            if isinstance(department, dict):
                department = department.get("name", "")

            # Compensation
            salary = ""
            comp = j.get("compensation", j.get("compensationTierSummary", ""))
            if isinstance(comp, dict):
                salary_min = comp.get("min", "")
                salary_max = comp.get("max", "")
                currency = comp.get("currency", "")
                if salary_min and salary_max:
                    salary = f"{salary_min}-{salary_max} {currency}"
            elif isinstance(comp, str):
                salary = comp

            desc = j.get("descriptionPlain", j.get("description", ""))
            if desc:
                desc = re.sub(r"<[^>]+>", " ", unescape(str(desc)))[:MAX_DESCRIPTION_LENGTH]

            job_url = j.get("jobUrl", j.get("publishedUrl", j.get("applyUrl", "")))
            tags = [department] if department else []

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=slug.replace("-", " ").title(),
                    location=str(location),
                    url=job_url,
                    source="ashby",
                    description=desc or "",
                    posted=j.get("publishedAt", j.get("updatedAt", "")),
                    remote="remote" in str(location).lower(),
                    salary=salary,
                    tags=tags,
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"Ashby: {len(jobs)} jobs from {len(companies)} companies")
    return jobs


# ---------------------------------------------------------------------------
# startup.jobs (Algolia-backed search, public)
# ---------------------------------------------------------------------------

STARTUPJOBS_ALGOLIA_APP = "45BWZJ1SGC"
STARTUPJOBS_ALGOLIA_KEY = "Zjk5YTMwNmRhYjk4MDlmNWJlZGUyMmIxZjY3ZGRlYTg1ZTRiNGIzOGI1MWY2ZDYzOWEyMWI1NDM5YmFlNzQ0OXRhZ0ZpbHRlcnM9"
STARTUPJOBS_INDEX = "jobs"


def scrape_startupjobs(
    keywords: list[str] | None = None,
    limit: int = 50,
) -> list[ScrapedJob]:
    """
    Scrape startup.jobs via their Algolia search backend.
    Public Algolia keys are embedded in their frontend JS.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    search_terms = keywords or ["product manager", "program manager", "AI", "developer relations"]

    for term in search_terms:

        def _fetch(query=term):
            with httpx.Client(timeout=20, headers={"User-Agent": _get_user_agent()}) as client:
                # Use the Algolia REST search endpoint
                r = client.post(
                    f"https://{STARTUPJOBS_ALGOLIA_APP}-dsn.algolia.net/1/indexes/{STARTUPJOBS_INDEX}/query",
                    headers={
                        "X-Algolia-Application-Id": STARTUPJOBS_ALGOLIA_APP,
                        "X-Algolia-API-Key": STARTUPJOBS_ALGOLIA_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "hitsPerPage": min(limit, 50),
                        "facetFilters": [["remote:true"]],
                    },
                )
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        for hit in data.get("hits", []):
            title = hit.get("title", "")
            company = hit.get("company_name", hit.get("company", ""))
            location = hit.get("location", "")
            job_url = hit.get("url", "")
            if not job_url and hit.get("slug"):
                job_url = f"https://startup.jobs/{hit['slug']}"

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=company if isinstance(company, str) else str(company),
                    location=location if isinstance(location, str) else str(location),
                    url=job_url,
                    source="startupjobs",
                    description=str(hit.get("description", ""))[:MAX_DESCRIPTION_LENGTH],
                    posted=hit.get("published_at", hit.get("created_at", "")),
                    remote=hit.get("remote", False),
                    tags=hit.get("tags", []) if isinstance(hit.get("tags"), list) else [],
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"startup.jobs: {len(jobs)} jobs")
    return jobs


# ---------------------------------------------------------------------------
# TheHub.io (Berlin/Nordic startups, HTML scraping fallback)
# ---------------------------------------------------------------------------

THEHUB_API = "https://thehub.io/api/jobs"


def scrape_thehub(
    keywords: list[str] | None = None,
    location: str = "germany",
    limit: int = 50,
) -> list[ScrapedJob]:
    """
    Scrape TheHub.io job listings. Tries internal JSON API first,
    falls back gracefully on failure.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    search_terms = keywords or ["product manager", "engineer"]

    for term in search_terms:

        def _fetch(query=term):
            with httpx.Client(
                timeout=20,
                headers={
                    "User-Agent": _get_user_agent(),
                    "Accept": "application/json",
                },
            ) as client:
                # Try the internal API endpoint
                r = client.get(
                    "https://thehub.io/jobs",
                    params={
                        "search": query,
                        "location": location,
                        "page": 1,
                        "per_page": min(limit, 50),
                    },
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        # Handle various response shapes
        listings = []
        if isinstance(data, list):
            listings = data
        elif isinstance(data, dict):
            listings = data.get("jobs", data.get("data", data.get("results", [])))

        for j in listings:
            if not isinstance(j, dict):
                continue
            title = j.get("title", "")
            company = j.get("company_name", j.get("company", ""))
            if isinstance(company, dict):
                company = company.get("name", "")

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=str(company),
                    location=j.get("location", location),
                    url=j.get("url", j.get("link", "")),
                    source="thehub",
                    description=str(j.get("description", ""))[:MAX_DESCRIPTION_LENGTH],
                    posted=j.get("published_at", j.get("created_at", "")),
                    remote=j.get("remote", False),
                    tags=j.get("tags", []) if isinstance(j.get("tags"), list) else [],
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"TheHub: {len(jobs)} jobs")
    return jobs


# ---------------------------------------------------------------------------
# Convenience: scrape all new sources at once
# ---------------------------------------------------------------------------


def scrape_all_new_sources(
    keywords: list[str] | None = None,
    greenhouse_companies: list[str] | None = None,
    lever_companies: list[str] | None = None,
    ashby_companies: list[str] | None = None,
    ats_keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """Run all new source scrapers. Each source is independent - failures are logged and skipped."""
    all_jobs: list[ScrapedJob] = []

    # Himalayas
    logger.info("=== New Source: Himalayas ===")
    try:
        all_jobs.extend(scrape_himalayas(keywords=keywords))
    except Exception as e:
        logger.error(f"Himalayas failed: {e}")

    _random_delay()

    # Greenhouse
    logger.info("=== New Source: Greenhouse ATS ===")
    try:
        all_jobs.extend(
            scrape_greenhouse(
                companies=greenhouse_companies,
                keyword_filter=ats_keyword_filter,
            )
        )
    except Exception as e:
        logger.error(f"Greenhouse failed: {e}")

    _random_delay()

    # Lever
    logger.info("=== New Source: Lever ATS ===")
    try:
        all_jobs.extend(
            scrape_lever(
                companies=lever_companies,
                keyword_filter=ats_keyword_filter,
            )
        )
    except Exception as e:
        logger.error(f"Lever failed: {e}")

    _random_delay()

    # Ashby
    logger.info("=== New Source: Ashby ATS ===")
    try:
        all_jobs.extend(
            scrape_ashby(
                companies=ashby_companies,
                keyword_filter=ats_keyword_filter,
            )
        )
    except Exception as e:
        logger.error(f"Ashby failed: {e}")

    _random_delay()

    # startup.jobs
    logger.info("=== New Source: startup.jobs ===")
    try:
        all_jobs.extend(scrape_startupjobs(keywords=keywords))
    except Exception as e:
        logger.error(f"startup.jobs failed: {e}")

    _random_delay()

    # TheHub
    logger.info("=== New Source: TheHub.io ===")
    try:
        all_jobs.extend(scrape_thehub(keywords=keywords))
    except Exception as e:
        logger.error(f"TheHub failed: {e}")

    logger.info(f"New sources total: {len(all_jobs)} jobs (before dedup)")
    return all_jobs
