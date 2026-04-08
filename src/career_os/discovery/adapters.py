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
        try:
            response = await client.request(
                method, url, headers=headers, params=params
            )
            if response.status_code == 429:
                if attempt < max_retries:
                    logger.warning(
                        "Rate limited (429) from %s, retrying in %.1fs (attempt %d/%d)",
                        url,
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER
                    continue
                else:
                    logger.warning("Rate limited (429) from %s after %d retries", url, max_retries)
                    response.raise_for_status()
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries:
                logger.warning(
                    "Rate limited (429), retrying in %.1fs (attempt %d/%d)",
                    backoff,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(backoff)
                backoff *= BACKOFF_MULTIPLIER
                last_exc = exc
                continue
            raise
        except httpx.RequestError as exc:
            if attempt < max_retries:
                logger.warning(
                    "Request error: %s, retrying in %.1fs (attempt %d/%d)",
                    exc,
                    backoff,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(backoff)
                backoff *= BACKOFF_MULTIPLIER
                last_exc = exc
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected exit from retry loop")


# ---------------------------------------------------------------------------
# Arbeitsagentur adapter
# ---------------------------------------------------------------------------


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
                    query_params: dict[str, str | int] = {
                        "size": min(params.limit_per_source, 100),
                        "page": 1,
                        "veroeffentlichtseit": 30,
                        "angebotsart": 1,
                    }
                    if kw:
                        query_params["was"] = kw
                    if loc:
                        query_params["wo"] = loc
                    if params.remote_only:
                        query_params["arbeitszeit"] = "ho"

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

                    jobs = data.get("stellenangebote", [])
                    for j in jobs:
                        arbeitgeber = j.get("arbeitgeber", "")
                        beruf = j.get("beruf", "")
                        refnr = j.get("refnr", "")
                        ar = j.get("arbeitsort", {}) or {}
                        ort = ar.get("ort", "") or ar.get("region", "") or ""
                        land = ar.get("land", "Deutschland")
                        hash_id = j.get("hashId", "")

                        if hash_id:
                            job_url = f"https://www.arbeitsagentur.de/jobboerse/jobsuche/detail/{hash_id}"
                        elif refnr:
                            job_url = (
                                f"https://www.arbeitsagentur.de/jobsuche/suche"
                                f"?was={quote_plus(refnr)}"
                            )
                        else:
                            job_url = ""

                        location_str = (
                            f"{ort}, {land}".strip(", ") if ort or land else "Deutschland"
                        )

                        results.append(
                            RawJobResult(
                                source="arbeitsagentur",
                                title=beruf or f"Stelle {refnr}",
                                company=arbeitgeber,
                                location=location_str,
                                url=job_url,
                                posted_at=_parse_date(
                                    j.get("aktuelleVeroeffentlichungsdatum", "")
                                ),
                            )
                        )

        return results


# ---------------------------------------------------------------------------
# Arbeitnow adapter
# ---------------------------------------------------------------------------


class ArbeitnowAdapter(ScraperAdapter):
    """Scraper for Arbeitnow (EU tech focus)."""

    ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"

    @property
    def source_name(self) -> str:
        return "arbeitnow"

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Scrape Arbeitnow for job listings."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await _request_with_backoff(client, "GET", self.ARBEITNOW_API)
                data = response.json()
            except Exception as exc:
                logger.warning("Arbeitnow API error: %s", exc)
                raise

        all_jobs = data.get("data", [])
        kw_lower = [k.lower() for k in params.keywords] if params.keywords else []
        loc_lower = [loc.lower() for loc in params.locations] if params.locations else []

        results: list[RawJobResult] = []
        for j in all_jobs:
            if params.remote_only and not j.get("remote", False):
                continue

            title = j.get("title", "")
            company = j.get("company_name", "")
            loc = j.get("location", "")

            if loc_lower and not any(lc in loc.lower() for lc in loc_lower):
                continue
            if kw_lower and not any(
                k in (title + " " + company).lower() for k in kw_lower
            ):
                continue

            posted_at = None
            created_at = j.get("created_at")
            if created_at:
                with contextlib.suppress(ValueError, TypeError, OSError):
                    posted_at = datetime.fromtimestamp(created_at)

            results.append(
                RawJobResult(
                    source="arbeitnow",
                    title=title,
                    company=company,
                    location=loc,
                    url=j.get("url", ""),
                    remote=j.get("remote", False),
                    tags=j.get("tags", []),
                    posted_at=posted_at,
                    description=j.get("description", ""),
                    salary_range=j.get("salary", ""),
                )
            )
            if len(results) >= params.limit_per_source:
                break

        return results


# ---------------------------------------------------------------------------
# python-jobspy adapter (wraps jobspy library)
# ---------------------------------------------------------------------------


class JobSpyAdapter(ScraperAdapter):
    """Scraper using python-jobspy for LinkedIn, Indeed, Glassdoor, Google Jobs."""

    @property
    def source_name(self) -> str:
        return "jobspy"

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Scrape multiple job boards via python-jobspy.

        This runs synchronous jobspy code in a thread executor.
        """
        try:
            from jobspy import scrape_jobs
        except ImportError as exc:
            raise RuntimeError(
                "python-jobspy is not installed. "
                "Install it with: pip install python-jobspy"
            ) from exc

        keywords = params.keywords or [""]
        location = params.locations[0] if params.locations else "Germany"

        loop = asyncio.get_event_loop()
        results: list[RawJobResult] = []

        for kw in keywords:
            try:
                jobs_df = await loop.run_in_executor(
                    None,
                    lambda k=kw: scrape_jobs(
                        site_name=["indeed", "glassdoor"],
                        search_term=k,
                        location=location,
                        results_wanted=params.limit_per_source,
                        hours_old=168,
                        country_indeed="Germany",
                    ),
                )
            except Exception as exc:
                logger.warning("JobSpy scrape error for '%s': %s", kw, exc)
                raise

            if jobs_df is not None and not jobs_df.empty:
                for _, row in jobs_df.iterrows():
                    posted_at = None
                    if "date_posted" in row and row["date_posted"]:
                        with contextlib.suppress(ValueError, TypeError):
                            posted_at = datetime.fromisoformat(str(row["date_posted"]))

                    results.append(
                        RawJobResult(
                            source="jobspy",
                            title=str(row.get("title", "")),
                            company=str(row.get("company", "")),
                            location=str(row.get("location", "")),
                            url=str(row.get("job_url", "")),
                            description=str(row.get("description", "")),
                            remote=bool(row.get("is_remote", False)),
                            posted_at=posted_at,
                        )
                    )

        return results


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
