"""
Additional job-board scrapers.

Covers sources not in the original pipeline:
- Himalayas (free JSON API, remote jobs, no auth)
- Greenhouse Job Board API (public, per-company, no auth)
- Lever Postings API (public, per-company, no auth)
- Ashby Job Board API (public, per-company, no auth)
- Workable Job Board API (public v3, per-company, no auth)
- startup.jobs (Algolia-backed search)
- TheHub.io (Nordic startup ecosystem, HTML scraping)

All scrapers return list[ScrapedJob] and gracefully return [] on failure.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path

import yaml

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
# ---------------------------------------------------------------------------
#
# The slugs are the account identifiers on each ATS (the {slug} in
# boards.greenhouse.io/{slug}, jobs.lever.co/{slug}, and the Ashby job-board
# URL). The embedded defaults below are OBVIOUSLY-FICTIONAL examples; the real
# lists load from ``config/companies.yaml`` (gitignored — copy
# ``config/companies.example.yaml``). This mirrors the example-slug pattern used
# by the other per-company scrapers lower in this module: ship a curated list
# without hardcoding anyone's personal target set into the public repo.

_COMPANIES_CONFIG = Path(__file__).resolve().parent.parent / "config" / "companies.yaml"

# Fictional example slugs — replace via config/companies.yaml.
_FLOOR_GREENHOUSE_COMPANIES: list[str] = ["example-greenhouse-co", "meridianlabs"]
_FLOOR_LEVER_COMPANIES: list[str] = ["example-lever-co", "nimbusworks"]
_FLOOR_ASHBY_COMPANIES: list[str] = ["example-ashby-co", "novadynamics"]


def _load_company_lists() -> dict[str, list[str]]:
    """Load ATS company lists from config/companies.yaml, falling back to the floor.

    Each key (``greenhouse``/``lever``/``ashby``) is optional; a missing or empty
    list keeps the fictional floor so the scrapers still run (returning noise-free
    empty results against the example slugs) without exposing a real target set.
    """
    defaults = {
        "greenhouse": list(_FLOOR_GREENHOUSE_COMPANIES),
        "lever": list(_FLOOR_LEVER_COMPANIES),
        "ashby": list(_FLOOR_ASHBY_COMPANIES),
    }
    try:
        data = yaml.safe_load(_COMPANIES_CONFIG.read_text(encoding="utf-8")) or {}
        for key in defaults:
            vals = data.get(key)
            if isinstance(vals, list) and vals:
                defaults[key] = [str(v).strip() for v in vals if str(v).strip()]
    except (OSError, yaml.YAMLError):
        pass
    return defaults


_COMPANY_LISTS = _load_company_lists()
GREENHOUSE_COMPANIES: list[str] = _COMPANY_LISTS["greenhouse"]
LEVER_COMPANIES: list[str] = _COMPANY_LISTS["lever"]
ASHBY_COMPANIES: list[str] = _COMPANY_LISTS["ashby"]


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
# Workable Job Board API (public v3, per-company, no auth)
# POST https://apply.workable.com/api/v3/accounts/{slug}/jobs -> {total, results}
# Adds an entire ATS the pipeline was otherwise blind to (ported from Eyas
# G-1119). Ships with an EMPTY company list — add your own account slugs (the
# {slug} in apply.workable.com/{slug}); the scraper returns [] until you do.
# ---------------------------------------------------------------------------

WORKABLE_API = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
WORKABLE_COMPANIES: list[str] = []


def scrape_workable(
    companies: list[str] | None = None,
    keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """
    Scrape the Workable public job-board API for specific companies.
    No auth. The list endpoint returns title/location/shortcode (no description);
    the apply URL is built from the slug + shortcode. Returns [] when no
    companies are configured.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    companies = companies or WORKABLE_COMPANIES
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for slug in companies:
        url = WORKABLE_API.format(slug=slug)

        def _fetch(u=url):
            with httpx.Client(timeout=20, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.post(u, json={})
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        for j in data.get("results", []):
            title = j.get("title", "")
            if kw_lower and not any(k in title.lower() for k in kw_lower):
                continue

            loc = j.get("location", {})
            if isinstance(loc, dict):
                parts = [loc.get("city", ""), loc.get("country", "")]
                location = ", ".join(p for p in parts if p)
            else:
                location = str(loc)

            shortcode = j.get("shortcode", "")
            job_url = f"https://apply.workable.com/{slug}/j/{shortcode}/" if shortcode else ""
            department = j.get("department", [])
            tags = department if isinstance(department, list) else [str(department)]

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=slug.replace("-", " ").title(),
                    location=location,
                    url=job_url,
                    source="workable",
                    description="",  # not in list endpoint; avoid N+1 detail calls
                    posted=str(j.get("published", "")),
                    remote=bool(j.get("remote")) or "remote" in location.lower(),
                    salary="",
                    tags=tags,
                    scraped_at=now,
                )
            )

        _random_delay()

    logger.info(f"Workable: {len(jobs)} jobs from {len(companies)} companies")
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
# arbeitnow.com (free public API, EU/DE tech-heavy job board)
# https://documenter.getpostman.com/view/18545278/UVJbJdKh
# ---------------------------------------------------------------------------

ARBEITNOW_BOARD_API = "https://www.arbeitnow.com/api/job-board-api"


def scrape_arbeitnow(
    keyword_filter: list[str] | None = None,
    max_pages: int = 1,
    per_page_limit: int = 100,
) -> list[ScrapedJob]:
    """Scrape the public arbeitnow.com job board API.

    Returns the latest postings (newest first) across the full board, with
    optional client-side title-keyword filter. arbeitnow is heavily EU/DE
    tech-skewed and complements the existing germany_jobs Arbeitnow path
    (which filters through ``is_likely_german_only`` and burns through
    keyword presets); this adapter pulls the unfiltered firehose so we
    don't miss English-language EU postings.

    Args:
        keyword_filter: Optional list of substrings; if any matches the job
            title (case-insensitive), the job is kept. ``None`` keeps all.
        max_pages: How many pages of 100 results to walk (default: 1).
        per_page_limit: Defensive cap on per-page results.

    Returns:
        List of ScrapedJob, or ``[]`` on transport failure.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for page in range(1, max_pages + 1):

        def _fetch(p=page):
            with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.get(ARBEITNOW_BOARD_API, params={"page": p})
                r.raise_for_status()
                return r.json()

        data = _retry_with_backoff(_fetch)
        if not data:
            continue

        listings = data.get("data", []) if isinstance(data, dict) else []
        if not isinstance(listings, list):
            continue

        for j in listings[:per_page_limit]:
            if not isinstance(j, dict):
                continue
            title = j.get("title", "")
            if kw_lower and not any(k in title.lower() for k in kw_lower):
                continue

            tags = j.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            # arbeitnow exposes posted timestamp as unix seconds in created_at
            posted = ""
            created_at = j.get("created_at")
            if isinstance(created_at, int):
                try:
                    posted = datetime.fromtimestamp(created_at).isoformat()
                except (OverflowError, OSError, ValueError):
                    posted = str(created_at)
            elif created_at:
                posted = str(created_at)

            desc = str(j.get("description", ""))
            # Strip HTML tags — arbeitnow descriptions are HTML
            desc = re.sub(r"<[^>]+>", " ", unescape(desc))[:MAX_DESCRIPTION_LENGTH]

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=str(j.get("company_name", "")),
                    location=str(j.get("location", "")),
                    url=str(j.get("url", "")),
                    source="arbeitnow",
                    description=desc,
                    posted=posted,
                    remote=bool(j.get("remote", False)),
                    tags=[str(t) for t in tags],
                    scraped_at=now,
                )
            )

        # If page returned fewer than 100, no point asking for the next one.
        if len(listings) < 100:
            break

        _random_delay()

    logger.info(f"arbeitnow: {len(jobs)} jobs")
    return jobs


# ---------------------------------------------------------------------------
# remotely.de (German remote/hybrid job board, JSON-LD per page via sitemap)
# Public sitemap-jobs.xml + JSON-LD JobPosting schema on every job detail page.
# No public list API, no auth needed for read-only crawl.
# ---------------------------------------------------------------------------

REMOTELY_SITEMAP = "https://www.remotely.de/sitemap-jobs.xml"


def scrape_remotely_de(
    keyword_filter: list[str] | None = None,
    limit: int = 50,
    max_age_hours: int | None = 48,
) -> list[ScrapedJob]:
    """Scrape recent job postings from remotely.de.

    Pulls the public sitemap to get the freshest job URLs (sorted newest
    first by lastmod), then fetches each detail page and parses the
    embedded ``schema.org/JobPosting`` JSON-LD block. No API key needed.

    Historically high-yield for Munich/Köln deep-tech and AI roles that
    don't appear on the international boards. See GitHub issue #348 /
    Linear G-630 for the original motivation (4 strong picks surfaced
    only from this board on a single March 9 scan).

    Args:
        keyword_filter: Optional substrings; if any matches the job title
            (case-insensitive) the posting is kept. ``None`` keeps all.
        limit: Maximum number of detail-page fetches (default: 50). Keeps
            the run under the 20-min total pipeline budget.
        max_age_hours: If set, drop sitemap entries with ``lastmod`` older
            than this many hours. ``None`` disables the freshness filter.

    Returns:
        List of ScrapedJob, ``[]`` on sitemap or repeated detail failures.
    """
    jobs: list[ScrapedJob] = []
    now_dt = datetime.now()
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%S")
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    def _fetch_sitemap():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(REMOTELY_SITEMAP)
            r.raise_for_status()
            return r.text

    sitemap_xml = _retry_with_backoff(_fetch_sitemap)
    if not sitemap_xml:
        logger.info("remotely.de: sitemap unavailable")
        return jobs

    # Parse sitemap — sitemap-jobs.xml lists newest entries first
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(sitemap_xml)
    except ET.ParseError as exc:
        logger.error(f"remotely.de sitemap parse error: {exc}")
        return jobs

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries = root.findall(".//sm:url", ns)

    candidates: list[str] = []
    for entry in entries:
        loc_el = entry.find("sm:loc", ns)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()

        if max_age_hours is not None:
            lastmod_el = entry.find("sm:lastmod", ns)
            if lastmod_el is not None and lastmod_el.text:
                try:
                    lastmod = datetime.fromisoformat(lastmod_el.text.strip().replace("Z", "+00:00"))
                    age_hours = (now_dt.astimezone(lastmod.tzinfo) - lastmod).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        continue
                except (ValueError, TypeError):
                    pass  # don't drop on parse failure; keep candidate

        candidates.append(url)
        if len(candidates) >= limit:
            break

    logger.info(f"remotely.de: {len(candidates)} candidate URLs from sitemap")

    detail_failures = 0
    for url in candidates:

        def _fetch_detail(u=url):
            with httpx.Client(timeout=20, headers={"User-Agent": _get_user_agent()}) as client:
                r = client.get(u, follow_redirects=True)
                r.raise_for_status()
                return r.text

        html = _retry_with_backoff(_fetch_detail)
        if not html:
            detail_failures += 1
            continue

        # Find JSON-LD JobPosting block
        ld_blocks = re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.S,
        )
        posting = None
        for raw in ld_blocks:
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                posting = d
                break
            if isinstance(d, list):
                for item in d:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        posting = item
                        break
                if posting:
                    break

        if not posting:
            detail_failures += 1
            continue

        title = str(posting.get("title", "")).strip()
        if kw_lower and not any(k in title.lower() for k in kw_lower):
            continue

        org = posting.get("hiringOrganization", {})
        company = org.get("name", "") if isinstance(org, dict) else str(org)

        loc_obj = posting.get("jobLocation", {})
        location = ""
        if isinstance(loc_obj, dict):
            addr = loc_obj.get("address", {})
            if isinstance(addr, dict):
                location = ", ".join(
                    filter(
                        None,
                        [addr.get("addressLocality", ""), addr.get("addressCountry", "")],
                    )
                )
        elif isinstance(loc_obj, list) and loc_obj:
            first = loc_obj[0]
            if isinstance(first, dict):
                addr = first.get("address", {})
                if isinstance(addr, dict):
                    location = ", ".join(
                        filter(
                            None,
                            [
                                addr.get("addressLocality", ""),
                                addr.get("addressCountry", ""),
                            ],
                        )
                    )

        desc = posting.get("description", "")
        if isinstance(desc, str):
            desc = re.sub(r"<[^>]+>", " ", unescape(desc))[:MAX_DESCRIPTION_LENGTH]
        else:
            desc = ""

        category = posting.get("occupationalCategory", "")
        tags = [category] if isinstance(category, str) and category else []

        jobs.append(
            ScrapedJob(
                title=title,
                company=str(company),
                location=location,
                url=str(posting.get("url", url)),
                source="remotely.de",
                description=desc,
                posted=str(posting.get("datePosted", "")),
                remote=True,
                tags=tags,
                scraped_at=now,
            )
        )

    if detail_failures:
        logger.info(f"remotely.de: {detail_failures} detail fetches failed (skipped)")
    logger.info(f"remotely.de: {len(jobs)} jobs")
    return jobs


# ---------------------------------------------------------------------------
# SmartRecruiters public postings API (no auth, per-company)
# https://api.smartrecruiters.com/v1/companies/{slug}/postings
# ---------------------------------------------------------------------------

SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
SMARTRECRUITERS_JOB_URL = "https://jobs.smartrecruiters.com/{slug}/{job_id}"

# EXAMPLE company slugs only — replace with the SmartRecruiters account slugs you
# want to track (the slug is the path segment on jobs.smartrecruiters.com/<slug>).
SMARTRECRUITERS_COMPANIES: list[str] = ["example-company-slug"]

# Relevance queries run server-side (q=) against big-corp boards. q= is fuzzy, so a
# client-side title keyword_filter then trims the noise. This keeps a several-thousand
# role board down to the handful of target-shaped roles instead of paging it all.
_SR_QUERIES: tuple[str, ...] = (
    "product manager",
    "program manager",
    "technical program manager",
    "developer advocate",
    "solutions architect",
    "ai engineer",
    "founding engineer",
)


def scrape_smartrecruiters(
    companies: list[str] | None = None,
    keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """Scrape the SmartRecruiters public postings API for big-corp boards.

    No auth. Runs a small set of relevance queries server-side, dedups by posting id,
    and (when ``keyword_filter`` is given) keeps only matching titles -- big-corp
    boards are huge, so unlike curated boards these DO get a title gate. Defaults to
    an EXAMPLE company list; pass your own slugs.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    companies = companies or SMARTRECRUITERS_COMPANIES
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for slug in companies:
        seen: set[str] = set()
        for query in _SR_QUERIES:

            def _fetch(s=slug, q=query):
                with httpx.Client(
                    timeout=20, headers={"User-Agent": _get_user_agent()}, follow_redirects=True
                ) as client:
                    r = client.get(
                        SMARTRECRUITERS_API.format(slug=s),
                        params={"q": q, "limit": 50},
                    )
                    r.raise_for_status()
                    return r.json()

            data = _retry_with_backoff(_fetch)
            if not data:
                continue

            for p in data.get("content", []):
                job_id = str(p.get("id", ""))
                if not job_id or job_id in seen:
                    continue
                title = p.get("name", "")
                if kw_lower and not any(k in title.lower() for k in kw_lower):
                    continue
                seen.add(job_id)

                loc = p.get("location", {}) or {}
                location = loc.get("fullLocation") or ", ".join(
                    part for part in (loc.get("city"), loc.get("country")) if part
                )
                dept = (p.get("department", {}) or {}).get("label", "")

                jobs.append(
                    ScrapedJob(
                        title=title,
                        company=slug.replace("-", " ").title(),
                        location=location,
                        url=SMARTRECRUITERS_JOB_URL.format(slug=slug, job_id=job_id),
                        source="smartrecruiters",
                        description="",
                        posted=p.get("releasedDate", ""),
                        remote=bool(loc.get("remote")),
                        tags=[dept] if dept else [],
                        scraped_at=now,
                    )
                )
        _random_delay()

    logger.info(f"SmartRecruiters: {len(jobs)} jobs from {len(companies)} companies")
    return jobs


# ---------------------------------------------------------------------------
# Personio Job Board XML feed (public, per-company, no auth)
# https://{slug}.jobs.personio.de/xml
# ---------------------------------------------------------------------------

PERSONIO_XML = "https://{slug}.jobs.personio.de/xml"
PERSONIO_JOB_URL = "https://{slug}.jobs.personio.de/job/{job_id}"

# EXAMPLE company slugs only — replace with the Personio subdomain slugs you want to
# track (the slug is the subdomain on <slug>.jobs.personio.de).
PERSONIO_COMPANIES: list[str] = ["example-company-slug"]


def scrape_personio(
    companies: list[str] | None = None,
    keyword_filter: list[str] | None = None,
) -> list[ScrapedJob]:
    """Scrape Personio public XML job feeds. No auth.

    Personio boards are small (EU mid-market), so the full feed is fetched and
    title-filtered client-side. Defaults to an EXAMPLE company list; pass your own.
    """
    import xml.etree.ElementTree as ET

    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    companies = companies or PERSONIO_COMPANIES
    kw_lower = [k.lower() for k in (keyword_filter or [])]

    for slug in companies:

        def _fetch(s=slug):
            with httpx.Client(
                timeout=20, headers={"User-Agent": _get_user_agent()}, follow_redirects=True
            ) as client:
                r = client.get(PERSONIO_XML.format(slug=s))
                r.raise_for_status()
                return r.text

        raw = _retry_with_backoff(_fetch)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            logger.warning("Personio: XML parse failed for '%s': %s", slug, exc)
            continue

        for pos in root.findall(".//position"):
            title = (pos.findtext("name") or "").strip()
            if not title:
                continue
            if kw_lower and not any(k in title.lower() for k in kw_lower):
                continue
            job_id = (pos.findtext("id") or "").strip()
            primary = (pos.findtext("office") or "").strip()
            offices = [primary] if primary else []
            offices += [
                o.text.strip()
                for o in pos.findall("./additionalOffices/office")
                if o.text and o.text.strip()
            ]
            dept = (pos.findtext("department") or "").strip()

            jobs.append(
                ScrapedJob(
                    title=title,
                    company=slug.replace("-", " ").title(),
                    location=primary or (offices[0] if offices else ""),
                    url=PERSONIO_JOB_URL.format(slug=slug, job_id=job_id),
                    source="personio",
                    description="",
                    posted=(pos.findtext("createdAt") or ""),
                    remote="remote" in primary.lower(),
                    tags=[dept] if dept else [],
                    scraped_at=now,
                )
            )
        _random_delay()

    logger.info(f"Personio: {len(jobs)} jobs from {len(companies)} companies")
    return jobs


# ---------------------------------------------------------------------------
# Convenience: scrape all new sources at once
# ---------------------------------------------------------------------------


def scrape_all_new_sources(
    keywords: list[str] | None = None,
    greenhouse_companies: list[str] | None = None,
    lever_companies: list[str] | None = None,
    ashby_companies: list[str] | None = None,
    workable_companies: list[str] | None = None,
    ats_keyword_filter: list[str] | None = None,
    remotely_limit: int = 50,
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

    # Workable
    logger.info("=== New Source: Workable ATS ===")
    try:
        all_jobs.extend(
            scrape_workable(
                companies=workable_companies,
                keyword_filter=ats_keyword_filter,
            )
        )
    except Exception as e:
        logger.error(f"Workable failed: {e}")

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

    _random_delay()

    # arbeitnow (public board, no auth)
    logger.info("=== New Source: arbeitnow.com ===")
    try:
        all_jobs.extend(scrape_arbeitnow(keyword_filter=ats_keyword_filter))
    except Exception as e:
        logger.error(f"arbeitnow failed: {e}")

    _random_delay()

    # remotely.de (sitemap + JSON-LD per job page)
    logger.info("=== New Source: remotely.de ===")
    try:
        all_jobs.extend(
            scrape_remotely_de(
                keyword_filter=ats_keyword_filter,
                limit=remotely_limit,
            )
        )
    except Exception as e:
        logger.error(f"remotely.de failed: {e}")

    logger.info(f"New sources total: {len(all_jobs)} jobs (before dedup)")
    return all_jobs
