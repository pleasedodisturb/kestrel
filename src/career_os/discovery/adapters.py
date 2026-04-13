"""Scraper adapters — unified interface for multiple job sources.

Each adapter implements the same interface:
  async def scrape(params) -> list[RawJobResult]

Individual adapter failures are caught and returned as warnings,
never blocking other adapters.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

# Rate limit / backoff settings
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0


@dataclass
class RawJobResult:
    """Unified raw result from any scraper adapter."""

    source: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    salary_range: str = ""
    remote: bool = False
    posted_at: datetime | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ScrapeParams:
    """Parameters for a discovery sweep."""

    keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_only: bool = False
    limit_per_source: int = 25


class ScraperAdapter(ABC):
    """Abstract base class for scraper adapters."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique source identifier (e.g., 'arbeitsagentur')."""

    @abstractmethod
    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Execute scraping and return results.

        Raises on unrecoverable errors. Rate limit retries are handled internally.
        """


def _should_retry(
    exc: Exception | None,
    attempt: int,
    max_retries: int,
) -> bool:
    """Determine if a request should be retried based on the exception and attempt count."""
    if attempt >= max_retries:
        return False
    if exc is None:
        return True  # 429 from response status check
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True
    return isinstance(exc, httpx.RequestError)


async def _request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff on rate limits (429)."""
    backoff = initial_backoff
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        last_exc, response, backoff = await _attempt_request(
            client, method, url, headers, params, attempt, max_retries, backoff
        )
        if response is not None:
            return response
        if last_exc is not None and not _should_retry(last_exc, attempt, max_retries):
            raise last_exc

    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected exit from retry loop")


async def _attempt_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict | None,
    params: dict | None,
    attempt: int,
    max_retries: int,
    backoff: float,
) -> tuple[Exception | None, httpx.Response | None, float]:
    """Execute a single request attempt, returning (exception, response, new_backoff)."""
    try:
        response = await client.request(method, url, headers=headers, params=params)
        if response.status_code == 429 and _should_retry(None, attempt, max_retries):
            logger.warning(
                "Rate limited (429) from %s, retrying in %.1fs (attempt %d/%d)",
                url,
                backoff,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(backoff)
            return None, None, backoff * BACKOFF_MULTIPLIER
        response.raise_for_status()
        return None, response, backoff
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        if not _should_retry(exc, attempt, max_retries):
            return exc, None, backoff
        _log_retry(exc, url, backoff, attempt, max_retries)
        await asyncio.sleep(backoff)
        return exc, None, backoff * BACKOFF_MULTIPLIER


def _log_retry(exc: Exception, _url: str, backoff: float, attempt: int, max_retries: int) -> None:
    """Log a retry warning with context about the error type."""
    if isinstance(exc, httpx.HTTPStatusError):
        logger.warning(
            "Rate limited (429), retrying in %.1fs (attempt %d/%d)",
            backoff,
            attempt + 1,
            max_retries,
        )
    else:
        logger.warning(
            "Request error: %s, retrying in %.1fs (attempt %d/%d)",
            exc,
            backoff,
            attempt + 1,
            max_retries,
        )


# ---------------------------------------------------------------------------
# Arbeitsagentur adapter
# ---------------------------------------------------------------------------


def _build_arbeitsagentur_params(
    keyword: str,
    location: str,
    remote_only: bool,
    limit: int,
) -> dict[str, str | int]:
    """Build query params dict for the Arbeitsagentur API."""
    query_params: dict[str, str | int] = {
        "size": min(limit, 100),
        "page": 1,
        "veroeffentlichtseit": 30,
        "angebotsart": 1,
    }
    if keyword:
        query_params["was"] = keyword
    if location:
        query_params["wo"] = location
    if remote_only:
        query_params["arbeitszeit"] = "ho"
    return query_params


def _resolve_arbeitsagentur_url(job_dict: dict) -> str:
    """Resolve the job URL from hashId, refnr, or return empty string."""
    hash_id = job_dict.get("hashId", "")
    if hash_id:
        return f"https://www.arbeitsagentur.de/jobboerse/jobsuche/detail/{hash_id}"
    refnr = job_dict.get("refnr", "")
    if refnr:
        return f"https://www.arbeitsagentur.de/jobsuche/suche?was={quote_plus(refnr)}"
    return ""


def _parse_arbeitsagentur_job(job_dict: dict, source_name: str) -> RawJobResult:
    """Parse a single Arbeitsagentur job dict into a RawJobResult."""
    arbeitgeber = job_dict.get("arbeitgeber", "")
    beruf = job_dict.get("beruf", "")
    refnr = job_dict.get("refnr", "")
    ar = job_dict.get("arbeitsort", {}) or {}
    ort = ar.get("ort", "") or ar.get("region", "") or ""
    land = ar.get("land", "Deutschland")

    location_str = f"{ort}, {land}".strip(", ") if ort or land else "Deutschland"

    return RawJobResult(
        source=source_name,
        title=beruf or f"Stelle {refnr}",
        company=arbeitgeber,
        location=location_str,
        url=_resolve_arbeitsagentur_url(job_dict),
        posted_at=_parse_date(job_dict.get("aktuelleVeroeffentlichungsdatum", "")),
    )


class ArbeitsagenturAdapter(ScraperAdapter):
    """Scraper for Germany's Federal Employment Agency API."""

    ARBEITSAGENTUR_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
    ARBEITSAGENTUR_API_KEY = "jobboerse-jobsuche"

    @property
    def source_name(self) -> str:
        return "arbeitsagentur"

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Scrape Arbeitsagentur for job listings."""
        results: list[RawJobResult] = []
        keyword_list = params.keywords or [""]
        locations = params.locations or [""]

        async with httpx.AsyncClient(timeout=30) as client:
            for kw in keyword_list:
                for loc in locations:
                    jobs = await self._fetch_arbeitsagentur_page(
                        client, kw, loc, params.remote_only, params.limit_per_source
                    )
                    results.extend(jobs)

        return results

    async def _fetch_arbeitsagentur_page(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        location: str,
        remote_only: bool,
        limit: int,
    ) -> list[RawJobResult]:
        """Fetch and parse a single keyword/location combination."""
        query_params = _build_arbeitsagentur_params(keyword, location, remote_only, limit)
        url = f"{self.ARBEITSAGENTUR_BASE}/pc/v4/jobs"
        headers = {"X-API-Key": self.ARBEITSAGENTUR_API_KEY}

        try:
            response = await _request_with_backoff(
                client, "GET", url, headers=headers, params=query_params
            )
            data = response.json()
        except Exception as exc:
            logger.warning("Arbeitsagentur API error: %s", exc)
            raise

        return [
            _parse_arbeitsagentur_job(j, self.source_name) for j in data.get("stellenangebote", [])
        ]


# ---------------------------------------------------------------------------
# Arbeitnow adapter
# ---------------------------------------------------------------------------


def _matches_arbeitnow_filters(
    job: dict,
    keywords: list[str],
    locations: list[str],
) -> bool:
    """Check if a job matches the keyword and location filters."""
    title = job.get("title", "")
    company = job.get("company_name", "")
    loc = job.get("location", "")

    if locations and not any(lc in loc.lower() for lc in locations):
        return False
    return not keywords or any(k in (title + " " + company).lower() for k in keywords)


def _parse_arbeitnow_job(job: dict, source_name: str) -> RawJobResult:
    """Parse a single Arbeitnow job dict into a RawJobResult."""
    posted_at = None
    created_at = job.get("created_at")
    if created_at:
        with contextlib.suppress(ValueError, TypeError, OSError):
            posted_at = datetime.fromtimestamp(created_at)

    return RawJobResult(
        source=source_name,
        title=job.get("title", ""),
        company=job.get("company_name", ""),
        location=job.get("location", ""),
        url=job.get("url", ""),
        remote=job.get("remote", False),
        tags=job.get("tags", []),
        posted_at=posted_at,
        description=job.get("description", ""),
        salary_range=job.get("salary", ""),
    )


class ArbeitnowAdapter(ScraperAdapter):
    """Scraper for Arbeitnow (EU tech focus)."""

    ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"

    @property
    def source_name(self) -> str:
        return "arbeitnow"

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Scrape Arbeitnow for job listings."""
        all_jobs = await self._fetch_arbeitnow_jobs()
        return self._filter_arbeitnow_jobs(all_jobs, params)

    async def _fetch_arbeitnow_jobs(self) -> list[dict]:
        """Fetch raw job data from the Arbeitnow API."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await _request_with_backoff(client, "GET", self.ARBEITNOW_API)
                data = response.json()
            except Exception as exc:
                logger.warning("Arbeitnow API error: %s", exc)
                raise
        return data.get("data", [])

    def _filter_arbeitnow_jobs(
        self, all_jobs: list[dict], params: ScrapeParams
    ) -> list[RawJobResult]:
        """Apply filters and parse Arbeitnow jobs up to the limit."""
        kw_lower = [k.lower() for k in params.keywords] if params.keywords else []
        loc_lower = [loc.lower() for loc in params.locations] if params.locations else []

        results: list[RawJobResult] = []
        for j in all_jobs:
            if params.remote_only and not j.get("remote", False):
                continue
            if not _matches_arbeitnow_filters(j, kw_lower, loc_lower):
                continue
            results.append(_parse_arbeitnow_job(j, self.source_name))
            if len(results) >= params.limit_per_source:
                break
        return results


# ---------------------------------------------------------------------------
# python-jobspy adapter (wraps jobspy library)
# ---------------------------------------------------------------------------


def _parse_jobspy_row(row: object, source_name: str) -> RawJobResult:
    """Parse a single DataFrame row from python-jobspy into a RawJobResult."""
    posted_at = None
    if "date_posted" in row and row["date_posted"]:
        with contextlib.suppress(ValueError, TypeError):
            posted_at = datetime.fromisoformat(str(row["date_posted"]))

    return RawJobResult(
        source=source_name,
        title=str(row.get("title", "")),
        company=str(row.get("company", "")),
        location=str(row.get("location", "")),
        url=str(row.get("job_url", "")),
        description=str(row.get("description", "")),
        remote=bool(row.get("is_remote", False)),
        posted_at=posted_at,
    )


class JobSpyAdapter(ScraperAdapter):
    """Scraper using python-jobspy for LinkedIn, Indeed, Glassdoor, Google Jobs."""

    @property
    def source_name(self) -> str:
        return "jobspy"

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Scrape multiple job boards via python-jobspy.

        This runs synchronous jobspy code in a thread executor.
        """
        scrape_jobs = self._import_jobspy()

        keywords = params.keywords or [""]
        location = params.locations[0] if params.locations else "Germany"
        loop = asyncio.get_event_loop()

        results: list[RawJobResult] = []
        for kw in keywords:
            rows = await self._scrape_keyword(
                loop, scrape_jobs, kw, location, params.limit_per_source
            )
            results.extend(rows)
        return results

    @staticmethod
    def _import_jobspy():
        """Import and return the jobspy scrape_jobs function."""
        try:
            from jobspy import scrape_jobs
        except ImportError as exc:
            raise RuntimeError(
                "python-jobspy is not installed. Install it with: pip install python-jobspy"
            ) from exc
        return scrape_jobs

    async def _scrape_keyword(
        self, loop, scrape_jobs, keyword: str, location: str, limit: int
    ) -> list[RawJobResult]:
        """Scrape a single keyword via python-jobspy and return parsed results."""
        try:
            jobs_df = await loop.run_in_executor(
                None,
                lambda k=keyword: scrape_jobs(
                    site_name=["indeed", "glassdoor"],
                    search_term=k,
                    location=location,
                    results_wanted=limit,
                    hours_old=168,
                    country_indeed="Germany",
                ),
            )
        except Exception as exc:
            logger.warning("JobSpy scrape error for '%s': %s", keyword, exc)
            raise

        if jobs_df is None or jobs_df.empty:
            return []
        return [_parse_jobspy_row(row, self.source_name) for _, row in jobs_df.iterrows()]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(date_str: str) -> datetime | None:
    """Parse a date string into a datetime, returning None on failure."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# All available adapters
ADAPTER_REGISTRY: dict[str, type[ScraperAdapter]] = {
    "arbeitsagentur": ArbeitsagenturAdapter,
    "arbeitnow": ArbeitnowAdapter,
    "jobspy": JobSpyAdapter,
}


def get_available_adapters(requested: list[str] | None = None) -> list[ScraperAdapter]:
    """Get adapter instances.

    If *requested* is None or empty, return all available adapters.
    Otherwise, return only the requested ones (silently skip unknown names).
    """
    if not requested:
        return [cls() for cls in ADAPTER_REGISTRY.values()]

    adapters = []
    for name in requested:
        cls = ADAPTER_REGISTRY.get(name.lower())
        if cls:
            adapters.append(cls())
    return adapters
