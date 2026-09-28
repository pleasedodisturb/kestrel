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
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
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
    """Scraper wrapping python-jobspy — requests only the boards in SITES.

    One scrape_jobs call is made per board in SITES so that one board raising
    never costs another board's rows (see SITES for why only Indeed is here).
    """

    # Indeed only (G-1802), verified live on 2026-09-28 against python-jobspy
    # 1.1.82:
    #   - Glassdoor answers with HTTP 400 and 0 rows (upstream PRs #384, #347)
    #   - Google Jobs answers with 0 rows: the page is a JavaScript bootstrap
    #     shell, not server-rendered listings (upstream issue #302)
    #   - A single multi-board scrape_jobs call loses EVERY board's rows when
    #     one board raises (upstream PR #388, unmerged); per-board calls below
    #     fix that independently of the board list.
    SITES: tuple[str, ...] = ("indeed",)

    # A timed-out jobspy thread cannot be cancelled; it keeps running until
    # jobspy returns. Left on the default executor, every hang occupied a
    # shared worker until the pool was exhausted and every later discovery
    # call queued behind them (Codex on G-1802). So jobspy runs on its own
    # bounded pool and the adapter counts calls it has abandoned: once that
    # reaches the pool size, new calls fail fast ("quarantined") instead of
    # queueing, and the count drops again as abandoned threads finish.
    MAX_WORKERS = 4
    _executor: ThreadPoolExecutor | None = None
    _hung = 0
    _hung_lock = threading.Lock()

    @classmethod
    def _pool(cls) -> ThreadPoolExecutor:
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(
                max_workers=cls.MAX_WORKERS, thread_name_prefix="jobspy"
            )
        return cls._executor

    @classmethod
    def hung_calls(cls) -> int:
        with cls._hung_lock:
            return cls._hung

    @property
    def source_name(self) -> str:
        return "jobspy"

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        """Scrape python-jobspy, one call per board in SITES per keyword.

        This runs synchronous jobspy code in a thread executor, bounded by
        settings.jobspy_timeout_seconds. A board or keyword failing is logged
        and skipped; if every attempt fails, raises RuntimeError so the sweep
        records it as a warning (career_os.services.discovery).
        """
        from career_os.config import settings

        scrape_jobs = self._import_jobspy()

        keywords = params.keywords or [""]
        location = params.locations[0] if params.locations else "Germany"
        timeout = settings.jobspy_timeout_seconds

        results: list[RawJobResult] = []
        failures: list[str] = []
        attempts = 0
        for kw in keywords:
            rows, kw_failures, kw_attempts = await self._scrape_keyword(
                scrape_jobs, kw, location, params.limit_per_source, timeout
            )
            results.extend(rows)
            failures.extend(kw_failures)
            attempts += kw_attempts

        if attempts and len(failures) == attempts:
            raise RuntimeError(
                f"JobSpy: all {attempts} site call(s) failed: " + "; ".join(failures)
            )
        if failures:
            logger.warning("JobSpy: %d of %d site call(s) failed", len(failures), attempts)
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
        self,
        scrape_jobs,
        keyword: str,
        location: str,
        limit: int,
        timeout: float,
    ) -> tuple[list[RawJobResult], list[str], int]:
        """Scrape one keyword across every board in SITES.

        Each board is its own call: one board raising or timing out never
        costs another board's rows (does NOT re-raise, unlike the old
        multi-board call this replaces). Returns (rows, failure strings,
        attempts made).
        """
        rows: list[RawJobResult] = []
        failures: list[str] = []
        attempts = 0
        for site in self.SITES:
            attempts += 1
            try:
                rows.extend(
                    await self._scrape_site(scrape_jobs, site, keyword, location, limit, timeout)
                )
            except TimeoutError:
                failure = f"{site} ('{keyword}'): timed out after {timeout:g}s"
                failures.append(failure)
                logger.warning("JobSpy %s", failure)
            except Exception as exc:
                failures.append(f"{site} ('{keyword}'): {type(exc).__name__}: {exc}")
                logger.warning(
                    "JobSpy scrape error for site '%s', keyword '%s': %s", site, keyword, exc
                )
        return rows, failures, attempts

    async def _scrape_site(
        self,
        scrape_jobs,
        site: str,
        keyword: str,
        location: str,
        limit: int,
        timeout: float,
    ) -> list[RawJobResult]:
        """Scrape a single (site, keyword) pair via python-jobspy, timeout-bound.

        A timed-out executor thread cannot be cancelled (Python threads run to
        completion): it keeps running jobspy until it returns, and this simply
        stops waiting for it, counting it as hung until it does. When as many
        calls are hung as the pool has workers, the call is refused up front.
        """
        cls = type(self)
        with cls._hung_lock:
            if cls._hung >= cls.MAX_WORKERS:
                raise RuntimeError(
                    f"quarantined: {cls._hung} abandoned jobspy call(s) still running "
                    f"(pool of {cls.MAX_WORKERS}); not scheduling more until they return"
                )
        state = {"started": False, "finished": False, "abandoned": False}

        def run():
            with cls._hung_lock:
                state["started"] = True
            try:
                return scrape_jobs(
                    site_name=[site],
                    search_term=keyword,
                    location=location,
                    results_wanted=limit,
                    hours_old=168,
                    country_indeed="Germany",
                )
            finally:
                with cls._hung_lock:
                    state["finished"] = True
                    if state["abandoned"]:
                        cls._hung -= 1

        cf = cls._pool().submit(run)
        try:
            jobs_df = await asyncio.wait_for(asyncio.wrap_future(cf), timeout=timeout)
        except TimeoutError:
            # wait_for cancels the wrapped future, which cancels queued work
            # that never started; only a call that is actually running on a
            # worker is hung. Counting a cancelled-before-start submission
            # would inflate the counter forever (Codex on G-1802).
            with cls._hung_lock:
                if state["started"] and not state["finished"]:
                    state["abandoned"] = True
                    cls._hung += 1
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
