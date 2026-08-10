"""
Resilient job scraper with rate limiting, retries, and anti-detection.

Wraps existing scrapers (scraper.py, germany_jobs.py) and adds:
- Rate limiting with configurable delays between requests
- User-agent rotation
- Retry with exponential backoff on transient failures
- Optional headless browser fallback via Playwright
- Source prioritization (API-first, browser as fallback)
- Structured output for the daily pipeline

Usage:
    .venv/bin/python tools/scrape_resilient.py
    .venv/bin/python tools/scrape_resilient.py --sources api-only
    .venv/bin/python tools/scrape_resilient.py --sources all --hours 24
"""

from __future__ import annotations

import json
import logging
import random
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Add project root to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent))

import xml.etree.ElementTree as ET

import germany_jobs
import httpx
import source_registry

logger = logging.getLogger("scrape_resilient")

# --- Configuration ---

MAX_DESCRIPTION_LENGTH = 5000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

# Delays between source scrapes (seconds)
MIN_DELAY = 2.0
MAX_DELAY = 5.0

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 2.0


@dataclass
class ScrapedJob:
    """Normalized job record from any source."""

    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    posted: str = ""
    remote: bool = False
    salary: str = ""
    tags: list[str] = field(default_factory=list)
    search_keyword: str = ""
    scraped_at: str = ""

    def dedup_key(self) -> tuple[str, str]:
        return (self.title.lower().strip(), self.company.lower().strip())


def _random_delay():
    """Sleep for a random duration to avoid detection."""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    logger.debug(f"Rate limit delay: {delay:.1f}s")
    time.sleep(delay)


def _get_user_agent() -> str:
    return random.choice(USER_AGENTS)


def _retry_with_backoff(func, *args, **kwargs):
    """Execute func with exponential backoff on failure."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            wait = BACKOFF_BASE**attempt + random.uniform(0, 1)
            logger.warning(
                f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}. Retrying in {wait:.1f}s"
            )
            time.sleep(wait)
    logger.error(f"All {MAX_RETRIES} retries failed: {last_error}")
    return None


# --- Source: Germany APIs (Arbeitsagentur + Arbeitnow) ---


def scrape_germany_apis(
    presets: list[str] | None = None,
    location: str = "Berlin",
    limit: int = 25,
    remote: bool = False,
) -> list[ScrapedJob]:
    """Scrape German job APIs — pure API, no browser needed."""
    presets = presets or ["all"]
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for preset in presets:
        keyword_list = []
        if preset == "all":
            for kws in germany_jobs.PRESETS.values():
                keyword_list.extend(kws)
        elif preset in germany_jobs.PRESETS:
            keyword_list = germany_jobs.PRESETS[preset]
        else:
            keyword_list = [preset]

        def _fetch():
            return germany_jobs.fetch_all_for_keywords(
                keyword_list=keyword_list,
                location=location,
                limit=limit,
                remote=remote,
                sources=["arbeitsagentur", "arbeitnow"],
            )

        result = _retry_with_backoff(_fetch)
        if result is None:
            continue

        raw_jobs, aa_count, an_count = result
        logger.info(f"Germany APIs ({preset}): {len(raw_jobs)} jobs ({aa_count} AA, {an_count} AN)")

        for j in raw_jobs:
            if germany_jobs.is_likely_german_only(j):
                continue
            jobs.append(
                ScrapedJob(
                    title=j.get("title", ""),
                    company=j.get("company", ""),
                    location=j.get("location", ""),
                    url=j.get("url", ""),
                    source=j.get("source", "germany_api"),
                    posted=j.get("posted", ""),
                    remote=j.get("remote", False),
                    tags=j.get("tags", []),
                    scraped_at=now,
                )
            )
        _random_delay()

    return jobs


# --- Source: JobSpy (LinkedIn, Indeed, Glassdoor, Google) ---


def scrape_jobspy(
    keywords: list[str] | None = None,
    location: str | None = None,
    hours_old: int = 24,
    results_per_keyword: int = 20,
    sites: list[str] | None = None,
) -> list[ScrapedJob]:
    """
    Scrape via python-jobspy. This uses HTTP requests (not a browser)
    to search LinkedIn, Indeed, Glassdoor, and Google Jobs.

    NOTE: LinkedIn scraping via jobspy uses public listing pages. For
    authenticated access (saved jobs, Easy Apply), you'd need browser
    automation — but that's fragile and against ToS. We intentionally
    stick to public-facing data.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    try:
        from scraper import scrape_all as jobspy_scrape
    except ImportError:
        logger.warning("scraper.py not available — skipping JobSpy source")
        return jobs

    def _fetch():
        return jobspy_scrape(
            keywords=keywords,
            location=location or "Your City, Country",
            hours_old=hours_old,
            results_per_keyword=results_per_keyword,
            sites=sites,
        )

    df = _retry_with_backoff(_fetch)
    if df is None or df.empty:
        logger.info("JobSpy: no results")
        return jobs

    logger.info(f"JobSpy: {len(df)} unique jobs")

    for _, row in df.iterrows():
        jobs.append(
            ScrapedJob(
                title=str(row.get("title", "")),
                company=str(row.get("company", "")),
                location=str(row.get("location", "")),
                url=str(row.get("job_url", row.get("link", ""))),
                source=str(row.get("site", "jobspy")),
                description=str(row.get("description", "")),
                posted=str(row.get("date_posted", "")),
                search_keyword=str(row.get("search_keyword", "")),
                scraped_at=now,
            )
        )

    return jobs


# --- Source: Remotive (free API, remote-focused) ---

REMOTIVE_API = "https://remotive.com/api/remote-jobs"


def scrape_remotive(
    search: str = "",
    category: str = "",
    limit: int = 50,
) -> list[ScrapedJob]:
    """
    Scrape Remotive's free public API.
    Rate limit: max 4 requests/day. Jobs delayed 24h.
    https://github.com/remotive-com/remote-jobs-api
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    params: dict[str, str | int] = {"limit": limit}
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    def _fetch():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(REMOTIVE_API, params=params)
            r.raise_for_status()
            return r.json()

    data = _retry_with_backoff(_fetch)
    if not data:
        return jobs

    for j in data.get("jobs", []):
        jobs.append(
            ScrapedJob(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                location=j.get("candidate_required_location", ""),
                url=j.get("url", ""),
                source="remotive",
                description=j.get("description", "")[:MAX_DESCRIPTION_LENGTH],
                posted=j.get("publication_date", ""),
                remote=True,
                salary=j.get("salary", ""),
                tags=j.get("tags", []),
                scraped_at=now,
            )
        )

    logger.info(f"Remotive: {len(jobs)} jobs")
    return jobs


# --- Source: RemoteOK (free API, largest remote board) ---

REMOTEOK_API = "https://remoteok.com/api"


def scrape_remoteok(limit: int = 50) -> list[ScrapedJob]:
    """
    Scrape RemoteOK's free JSON API. No auth required.
    Returns all current listings. Must attribute and link back.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _fetch():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(REMOTEOK_API)
            r.raise_for_status()
            return r.json()

    data = _retry_with_backoff(_fetch)
    if not data:
        return jobs

    # First element is a legal notice, skip it
    listings = [item for item in data if isinstance(item, dict) and item.get("id")]

    for j in listings[:limit]:
        tags = j.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        jobs.append(
            ScrapedJob(
                title=j.get("position", ""),
                company=j.get("company", ""),
                location=j.get("location", "Worldwide"),
                url=j.get("url", j.get("apply_url", "")),
                source="remoteok",
                description=j.get("description", "")[:MAX_DESCRIPTION_LENGTH],
                posted=j.get("date", ""),
                remote=True,
                salary=j.get("salary_min", ""),
                tags=tags,
                scraped_at=now,
            )
        )

    logger.info(f"RemoteOK: {len(jobs)} jobs")
    return jobs


# --- Source: Jobicy (free API, remote with geo filter) ---

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


def scrape_jobicy(
    count: int = 50,
    geo: str = "europe",
    tag: str = "",
) -> list[ScrapedJob]:
    """
    Scrape Jobicy's free public API. No auth required.
    Supports geo filtering (usa, europe, uk, etc.) and industry/tag filters.
    https://github.com/Jobicy/remote-jobs-api
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    params: dict[str, str | int] = {"count": count, "geo": geo}
    if tag:
        params["tag"] = tag

    def _fetch():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(JOBICY_API, params=params)
            r.raise_for_status()
            return r.json()

    data = _retry_with_backoff(_fetch)
    if not data:
        return jobs

    for j in data.get("jobs", []):
        jobs.append(
            ScrapedJob(
                title=j.get("jobTitle", ""),
                company=j.get("companyName", ""),
                location=j.get("jobGeo", ""),
                url=j.get("url", ""),
                source="jobicy",
                description=j.get("jobDescription", "")[:MAX_DESCRIPTION_LENGTH],
                posted=j.get("pubDate", ""),
                remote=True,
                salary=j.get("annualSalaryMin", ""),
                tags=j.get("jobIndustry", []) if isinstance(j.get("jobIndustry"), list) else [],
                scraped_at=now,
            )
        )

    logger.info(f"Jobicy: {len(jobs)} jobs")
    return jobs


# --- Source: We Work Remotely (RSS feed, curated quality) ---

WWR_RSS = "https://weworkremotely.com/remote-jobs.rss"


def scrape_weworkremotely(limit: int = 50) -> list[ScrapedJob]:
    """
    Parse We Work Remotely's public RSS feed.
    High-quality curated remote listings. No auth needed.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _fetch():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(WWR_RSS)
            r.raise_for_status()
            return r.text

    xml_text = _retry_with_backoff(_fetch)
    if not xml_text:
        return jobs

    try:
        root = ET.fromstring(xml_text)
        items = root.findall(".//item")

        for item in items[:limit]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")

            title_text = title_el.text if title_el is not None else ""
            # WWR titles are often "Company: Role Title"
            company = ""
            role = title_text
            if ": " in title_text:
                company, role = title_text.split(": ", 1)

            jobs.append(
                ScrapedJob(
                    title=role,
                    company=company,
                    location="Remote",
                    url=link_el.text if link_el is not None else "",
                    source="weworkremotely",
                    description=(desc_el.text or "")[:MAX_DESCRIPTION_LENGTH]
                    if desc_el is not None
                    else "",
                    posted=pubdate_el.text if pubdate_el is not None else "",
                    remote=True,
                    scraped_at=now,
                )
            )
    except ET.ParseError as e:
        logger.error(f"WWR RSS parse error: {e}")

    logger.info(f"We Work Remotely: {len(jobs)} jobs")
    return jobs


# --- Source: GermanTechJobs (XML job feed, Germany-specific) ---

GERMANTECHJOBS_RSS = "https://germantechjobs.de/job_feed.xml"


def _gtj_text(job: ET.Element, *names: str) -> str:
    """First non-empty child text among `names` (the feed carries aliases)."""
    for name in names:
        value = job.findtext(name)
        if value and value.strip():
            return value.strip()
    return ""


def _gtj_posted(raw: str) -> str:
    """GermanTechJobs `pubdate` is DD.MM.YYYY — normalize to ISO, else pass through."""
    raw = (raw or "").strip()
    try:
        return datetime.strptime(raw, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return raw


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _freshest_first(jobs: list[ScrapedJob]) -> list[ScrapedJob]:
    """Sort newest-first, but let ONLY a validated ISO date reorder anything.

    A plain ``sort(key=lambda j: j.posted, reverse=True)`` is wrong here, and
    wrong in the direction that hurts: ``_gtj_posted`` passes anything it cannot
    parse through verbatim, and under a reverse-lexical sort every string
    starting above ``'2'`` outranks every real ISO date. One row reading
    ``"Mon, 01 Jan 2010 …"`` or ``"vor 3 Tagen"`` takes the top slot, and with a
    ``limit`` applied afterwards it evicts a genuinely fresh posting.

    The mirror case is worse: a job with no date at all sorts dead last and is
    then *deterministically* excluded by ``limit`` — permanently invisible,
    which is exactly the silent-loss failure this module exists to prevent.

    So: rows with a parseable ISO date sort among themselves, newest first;
    everything else keeps feed order and lands after them. Undated jobs stay
    reachable, and an unparseable date can no longer hijack rank 1.
    """
    dated = [(i, j) for i, j in enumerate(jobs) if _ISO_DATE.match(j.posted or "")]
    undated = [(i, j) for i, j in enumerate(jobs) if not _ISO_DATE.match(j.posted or "")]
    dated.sort(key=lambda pair: (pair[1].posted, -pair[0]), reverse=True)
    return [j for _, j in dated] + [j for _, j in undated]


def scrape_germantechjobs(limit: int = 1500) -> list[ScrapedJob]:
    """
    Parse the GermanTechJobs XML job feed. Germany-specific tech jobs, free, no auth.

    **The feed is NOT RSS.** Its schema is ``<jobs><job>…</job></jobs>`` with flat
    child elements (``title``/``name``, ``company``/``company-name``, ``city``,
    ``region``, ``country``, ``location``, ``url``/``link``/``apply_url``,
    ``salary``, ``pubdate``, ``description``) — no ``<channel>``, no ``<item>``.

    This parser previously looked for ``.//item`` and therefore returned 0
    forever while the board served a full listing. Measured 2026-08-10 against
    the live feed: 4.2 MB, **1,011 ``<job>`` elements, 0 ``<item>`` elements**.
    A source that can never return a row is indistinguishable from a board with
    nothing to offer, which is precisely the failure mode worth refusing to ship.

    An RSS-shaped feed is still accepted as a fallback in case they switch back,
    and a feed that matches *neither* shape logs a PARSER failure rather than
    passing silently as an empty result.

    Entries are returned freshest-first so a `limit` trims the stale tail rather
    than letting a promoted 2020 listing keep a role from this week out.
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _fetch():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(GERMANTECHJOBS_RSS)
            r.raise_for_status()
            return r.text

    xml_text = _retry_with_backoff(_fetch)
    if not xml_text:
        return jobs

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"GermanTechJobs feed parse error: {e}")
        return jobs

    # `.//job` unconditionally — it is a strict superset of `findall("job")`.
    # The tempting `findall("job") or findall(".//job")` is wrong: on a grouped
    # feed (<jobs><category><job>…) the direct-child form returns a NON-EMPTY
    # partial list, `or` short-circuits, and the nested entries are dropped with
    # no warning — a silent wrong subset, which is worse than the zero this
    # function was written to eliminate.
    entries = root.findall(".//job")
    if entries:
        for job in entries:
            # Prefer the explicit location string; only compose from city/country
            # when it is absent. Composing first discards the most specific
            # signal: a posting with <country>Germany</country> beside
            # <location>Frankfurt am Main, Germany</location> would yield bare
            # "Germany", which this project's own geo classifier reads as
            # home_relocate instead of home_local — downgrading a no-move local
            # role to a relocation on a parser detail.
            city = _gtj_text(job, "city")
            country = _gtj_text(job, "country")
            location = (
                _gtj_text(job, "location")
                or ", ".join(p for p in (city, country) if p)
                or _gtj_text(job, "region")
                or "Germany"
            )

            jobs.append(
                ScrapedJob(
                    title=_gtj_text(job, "title", "name"),
                    company=_gtj_text(job, "company", "company-name"),
                    location=location,
                    url=_gtj_text(job, "url", "link", "apply_url"),
                    source="germantechjobs",
                    description=_gtj_text(job, "description")[:MAX_DESCRIPTION_LENGTH],
                    # Aliases here too. XML is case-sensitive and this feed has
                    # already changed shape once; a lone "pubdate" spelling means
                    # a camelCase <pubDate> silently zeroes every date and
                    # "freshest-first" degrades to arbitrary feed order.
                    posted=_gtj_posted(_gtj_text(job, "pubdate", "pubDate", "date", "published")),
                    salary=_gtj_text(job, "salary"),
                    scraped_at=now,
                )
            )
        jobs = _freshest_first(jobs)[:limit]
    else:
        # Legacy/fallback RSS shape, kept in case the board switches back.
        # Normalized and sorted the SAME way as the primary branch: `posted`
        # must not be ISO in one branch and RFC-822 in the other, or a
        # downstream date comparison silently depends on which branch fired.
        items = root.findall(".//item")
        for item in items:
            jobs.append(
                ScrapedJob(
                    title=(item.findtext("title") or "").strip(),
                    company="",
                    location="Germany",
                    url=(item.findtext("link") or "").strip(),
                    source="germantechjobs",
                    description=(item.findtext("description") or "")[:MAX_DESCRIPTION_LENGTH],
                    posted=_gtj_posted((item.findtext("pubDate") or "").strip()),
                    scraped_at=now,
                )
            )
        jobs = _freshest_first(jobs)[:limit]

        if not items:
            # Neither shape matched. Report what was actually observed and let the
            # reader judge — do NOT assert "the schema changed", because a board
            # that genuinely has no openings serves a well-formed empty document
            # and would trip this same branch. Claiming a parser failure there is
            # a false alarm, and an alarm that cries wolf is how a real one gets
            # ignored.
            child_count = len(list(root))
            logger.warning(
                "GermanTechJobs: feed parsed (root <%s>, %d children) but no <job> "
                "or <item> entries matched either known schema. If the document is "
                "non-empty this is a PARSER failure, not an empty board — check the "
                "feed shape before assuming the source has nothing to offer.",
                root.tag,
                child_count,
            )

    logger.info(f"GermanTechJobs: {len(jobs)} jobs")
    return jobs


# --- Source: AI-Jobs.net (free JSON API, AI/ML-specific) ---

AIJOBS_API = "https://ai-jobs.net/api/list-jobs/"


def scrape_aijobs(limit: int = 100) -> list[ScrapedJob]:
    """
    Scrape ai-jobs.net's free JSON API. No auth required.
    Returns most recent 200 jobs, updated every ~2 hours.
    Covers AI, ML, NLP, Computer Vision, Data Science.
    https://insights.ai-jobs.net/jobs-via-rss-feed-and-json-api/
    """
    jobs: list[ScrapedJob] = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _fetch():
        with httpx.Client(timeout=30, headers={"User-Agent": _get_user_agent()}) as client:
            r = client.get(AIJOBS_API)
            r.raise_for_status()
            return r.json()

    data = _retry_with_backoff(_fetch)
    if not data:
        return jobs

    # API returns a list of job dicts
    listings = data if isinstance(data, list) else data.get("jobs", data.get("data", []))

    for j in listings[:limit]:
        # Fields vary — handle flexibly
        salary = ""
        if j.get("salary_min") and j.get("salary_max"):
            currency = j.get("salary_currency", "USD")
            salary = f"{j['salary_min']}-{j['salary_max']} {currency}"

        jobs.append(
            ScrapedJob(
                title=j.get("title", j.get("job_title", "")),
                company=j.get("company", j.get("company_name", "")),
                location=j.get("location", ""),
                url=j.get("url", j.get("apply_url", j.get("link", ""))),
                source="aijobs",
                description=str(j.get("description", j.get("body", "")))[:MAX_DESCRIPTION_LENGTH],
                posted=j.get("date", j.get("published", j.get("pubDate", ""))),
                remote="remote" in str(j.get("location", "")).lower() or j.get("remote", False),
                salary=salary,
                tags=j.get("tags", []) if isinstance(j.get("tags"), list) else [],
                scraped_at=now,
            )
        )

    logger.info(f"AI-Jobs.net: {len(jobs)} jobs")
    return jobs


# --- Source: Headless browser (Playwright) — fallback only ---


def scrape_with_browser(
    urls: list[str],
    extract_selector: str = "body",
) -> list[dict]:
    """
    Headless browser scraping via Playwright — USE SPARINGLY.

    This is the fallback for sites that:
    1. Require JavaScript rendering
    2. Block HTTP scrapers
    3. Have data behind client-side rendering

    Anti-detection measures:
    - Random viewport sizes
    - Human-like delays between actions
    - Stealth mode (no webdriver flag)
    - Random user agents

    IMPORTANT: This should NOT be used for LinkedIn or Indeed at scale.
    Those sites actively detect and block headless browsers. Use their
    public listings via python-jobspy instead.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning(
            "Playwright not installed. Skipping browser scraping. Install: pip install playwright && playwright install chromium"
        )
        return []

    results = []
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        for url in urls:
            try:
                context = browser.new_context(
                    viewport=random.choice(viewports),
                    user_agent=_get_user_agent(),
                )
                page = context.new_page()

                # Remove webdriver flag
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)

                page.goto(url, wait_until="networkidle", timeout=30000)

                # Human-like delay
                time.sleep(random.uniform(2, 5))

                content = page.query_selector(extract_selector)
                text = content.inner_text() if content else page.content()

                results.append(
                    {
                        "url": url,
                        "content": text,
                        "title": page.title(),
                        "scraped_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                )

                context.close()
                _random_delay()

            except Exception as e:
                logger.error(f"Browser scrape failed for {url}: {e}")
                results.append({"url": url, "content": "", "error": str(e)})

        browser.close()

    return results


# --- Deduplication ---


def deduplicate(jobs: list[ScrapedJob]) -> list[ScrapedJob]:
    """Remove duplicate jobs by (title, company) key."""
    seen: set[tuple[str, str]] = set()
    unique: list[ScrapedJob] = []
    for job in jobs:
        key = job.dedup_key()
        if key not in seen:
            seen.add(key)
            unique.append(job)
    logger.info(f"Dedup: {len(jobs)} → {len(unique)} unique jobs")
    return unique


# --- New sources (imported after ScrapedJob & helpers are defined to avoid circular import) ---

try:
    from scrape_new_sources import (
        scrape_all_new_sources,
        scrape_arbeitnow,
        scrape_ashby,
        scrape_greenhouse,
        scrape_himalayas,
        scrape_lever,
        scrape_remotely_de,
        scrape_startupjobs,
    )

    NEW_SOURCES_AVAILABLE = True
except ImportError:
    NEW_SOURCES_AVAILABLE = False


# --- Main orchestrator ---


def scrape_all_sources(
    mode: str = "api-only",
    keywords: list[str] | None = None,
    location: str | None = None,
    hours_old: int = 24,
    germany_presets: list[str] | None = None,
    jobspy_sites: list[str] | None = None,
    browser_urls: list[str] | None = None,
) -> list[ScrapedJob]:
    """
    Scrape all configured sources and return deduplicated jobs.

    Modes:
        api-only   — Germany APIs + JobSpy HTTP only (safest, fastest)
        api-plus   — Above + career page browser scraping
        all        — All sources including browser fallback
    """
    all_jobs: list[ScrapedJob] = []

    # 1. Germany APIs (always — pure API, zero risk)
    logger.info("=== Source 1/9: Germany APIs ===")
    try:
        germany_results = scrape_germany_apis(
            presets=germany_presets or ["all"],
            location=location or "Berlin",
            remote=True,
        )
        all_jobs.extend(germany_results)
    except Exception as e:
        logger.error(f"Germany APIs failed: {e}")

    _random_delay()

    # 2. JobSpy HTTP scraper (LinkedIn, Indeed, Glassdoor, Google)
    logger.info("=== Source 2/9: JobSpy ===")
    try:
        jobspy_results = scrape_jobspy(
            keywords=keywords,
            location=location,
            hours_old=hours_old,
            sites=jobspy_sites,
        )
        all_jobs.extend(jobspy_results)
    except Exception as e:
        logger.error(f"JobSpy failed: {e}")

    _random_delay()

    # 3. Remotive (free API, remote-focused — max 4 requests/day!)
    logger.info("=== Source 3/9: Remotive ===")
    try:
        # Single call to avoid burning rate limit (4 req/day max)
        search_term = keywords[0] if keywords else "product manager"
        remotive_results = scrape_remotive(search=search_term, limit=50)
        all_jobs.extend(remotive_results)
    except Exception as e:
        logger.error(f"Remotive failed: {e}")

    _random_delay()

    # 4. RemoteOK (free API, largest remote board)
    logger.info("=== Source 4/9: RemoteOK ===")
    try:
        remoteok_results = scrape_remoteok(limit=50)
        all_jobs.extend(remoteok_results)
    except Exception as e:
        logger.error(f"RemoteOK failed: {e}")

    _random_delay()

    # 5. Jobicy (free API, remote with European geo filter)
    logger.info("=== Source 5/9: Jobicy ===")
    try:
        jobicy_results = scrape_jobicy(count=50, geo="europe")
        all_jobs.extend(jobicy_results)
    except Exception as e:
        logger.error(f"Jobicy failed: {e}")

    _random_delay()

    # 6. AI-Jobs.net (free JSON API, AI/ML-specific — unique listings)
    logger.info("=== Source 6/9: AI-Jobs.net ===")
    try:
        aijobs_results = scrape_aijobs(limit=100)
        all_jobs.extend(aijobs_results)
    except Exception as e:
        logger.error(f"AI-Jobs.net failed: {e}")

    _random_delay()

    # 7. We Work Remotely + GermanTechJobs (RSS feeds)
    logger.info("=== Source 7/9: RSS Feeds (WWR + GermanTechJobs) ===")
    try:
        wwr_results = scrape_weworkremotely(limit=50)
        all_jobs.extend(wwr_results)
    except Exception as e:
        logger.error(f"We Work Remotely failed: {e}")

    _random_delay()

    try:
        # No limit pin. The fetch is a single request for the whole 4.2 MB feed
        # either way, so capping at 50 threw away ~95% of what was already
        # downloaded — and made the parser fix above almost pointless in the one
        # place it ships.
        gtj_results = scrape_germantechjobs()
        all_jobs.extend(gtj_results)
    except Exception as e:
        logger.error(f"GermanTechJobs failed: {e}")

    # 8. New sources: Himalayas, Greenhouse, Lever, Ashby, startup.jobs
    if NEW_SOURCES_AVAILABLE:
        logger.info(
            "=== Source 8/9: New Market Sources (Himalayas, ATS boards, startup.jobs) ==="
        )
        try:
            new_results = scrape_all_new_sources(keywords=keywords)
            all_jobs.extend(new_results)
            logger.info(f"New sources: {len(new_results)} jobs")
        except Exception as e:
            logger.error(f"New market sources failed: {e}")
    else:
        logger.info("=== Source 8/9: New Market Sources — SKIPPED (import unavailable) ===")

    _random_delay()

    # 9. Browser scraping (only in api-plus or all mode)
    if mode in ("api-plus", "all") and browser_urls:
        logger.info("=== Source 9/9: Browser (career pages) ===")
        _random_delay()
        raw = scrape_with_browser(browser_urls)
        for item in raw:
            if item.get("content") and not item.get("error"):
                all_jobs.append(
                    ScrapedJob(
                        title=item.get("title", ""),
                        company="",
                        location="",
                        url=item["url"],
                        source="browser",
                        description=item["content"][:MAX_DESCRIPTION_LENGTH],
                        scraped_at=item.get("scraped_at", ""),
                    )
                )

    # Per-source health BEFORE dedup — dedup removes cross-posted duplicates and
    # would understate a source's real contribution, making a healthy board look
    # like it is fading.
    report_source_health(all_jobs)

    # Deduplicate
    all_jobs = deduplicate(all_jobs)
    logger.info(f"Total after all sources: {len(all_jobs)} jobs")

    return all_jobs


def report_source_health(jobs: list[ScrapedJob]) -> list[str]:
    """Log the per-source status table and every non-ok warning.

    Counts come from what actually landed in ``ScrapedJob.source`` rather than
    from counters threaded through each call site — so a source cannot report a
    number it did not produce, and a source that returned nothing simply does not
    appear, which ``source_registry.check`` already treats as ZERO.

    This is the whole point of the registry: without it a broken scraper
    contributes zero forever while the run looks healthy, which is exactly how
    two sources in this repo stayed dead for months.

    Returns the warning list (also logged) so callers and tests can assert on it.
    """
    counts = Counter(j.source for j in jobs)
    logger.info("Per-source health:\n%s", source_registry.status_table(counts))
    warnings = source_registry.check(counts)
    for line in warnings:
        logger.warning("SOURCE HEALTH — %s", line)
    return warnings


def save_results(jobs: list[ScrapedJob], output_dir: Path) -> Path:
    """Save scraped jobs to JSON for downstream processing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"scraped_raw_{date_str}.json"

    data = [asdict(j) for j in jobs]
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info(f"Saved {len(data)} jobs to {output_path}")
    return output_path


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Resilient multi-source job scraper")
    parser.add_argument(
        "--mode",
        choices=["api-only", "api-plus", "all"],
        default="api-only",
        help="Scraping mode (default: api-only)",
    )
    parser.add_argument("--keywords", nargs="+", help="Search keywords for JobSpy")
    parser.add_argument("--location", help="Location filter")
    parser.add_argument(
        "--hours", type=int, default=24, help="Max posting age in hours (default: 24)"
    )
    parser.add_argument(
        "--germany-presets", nargs="+", default=["all"], help="Germany job presets (default: all)"
    )
    parser.add_argument("--jobspy-sites", nargs="+", help="JobSpy sites to search")
    parser.add_argument("--browser-urls", nargs="+", help="Career page URLs for browser scraping")
    parser.add_argument("--output-dir", default="tracking", help="Output directory")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    output_dir = project_root / args.output_dir

    jobs = scrape_all_sources(
        mode=args.mode,
        keywords=args.keywords,
        location=args.location,
        hours_old=args.hours,
        germany_presets=args.germany_presets,
        jobspy_sites=args.jobspy_sites,
        browser_urls=args.browser_urls,
    )

    if jobs:
        output_path = save_results(jobs, output_dir)
        print(f"\nDone. {len(jobs)} jobs saved to {output_path}")
    else:
        print("\nNo jobs found across any source.")


if __name__ == "__main__":
    main()
