"""WARN Act data loading and querying service (Epic 9 / G-277).

This module handles:
- Company name normalization for fuzzy matching across data sources
- Loading WARN data via the warn-scraper library (optional dependency)
- Querying warn_filings for a given company name
- Graceful degradation when warn-scraper is not installed

warn-scraper (pip install warn-scraper) is an open-source CLI/library that
scrapes WARN Act notices from state government websites. Install via:
    pip install "kestrel-app[warn]"
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from career_os.models.warn import WARNFiling

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: States with consistently good WARN data coverage.
DEFAULT_STATES = ["CA", "NY", "WA", "TX", "IL", "MA", "CO", "GA"]

#: Common company name suffixes to strip for normalization.
_COMPANY_SUFFIXES = re.compile(
    r"""\s*[,.]?\s*\b(
        llc|l\.l\.c\.|
        inc|incorporated|
        corp|corporation|
        ltd|limited|
        co\b|company|
        lp|l\.p\.|
        llp|l\.l\.p\.|
        pllc|
        plc|
        gmbh|ag|sa|bv|
        group|holdings|holding|
        technologies|technology|tech|
        solutions|services|systems|
        international|global|
        north\s+america|usa|us
    )\b\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9\s]")
_EXTRA_WHITESPACE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Company name normalization
# ---------------------------------------------------------------------------


def normalize_company_name(name: str) -> str:
    """Normalize a company name for fuzzy matching across data sources.

    Steps:
    1. Lowercase
    2. Strip trailing legal suffixes (LLC, Inc, Corp, etc.)
    3. Remove punctuation
    4. Collapse whitespace
    5. Strip

    Examples:
        "Google LLC" -> "google"
        "Meta Platforms, Inc." -> "meta platforms"
        "Amazon.com, Inc." -> "amazoncom"  (dot removed, not suffix)
        "Microsoft Corporation" -> "microsoft"
    """
    if not name:
        return ""

    normalized = name.lower().strip()

    # Iteratively strip suffixes — some companies have stacked suffixes like "Corp., Inc."
    prev = None
    while prev != normalized:
        prev = normalized
        normalized = _COMPANY_SUFFIXES.sub("", normalized).strip().rstrip(",.")

    # Remove non-alphanumeric characters (punctuation, special chars)
    normalized = _NON_ALPHANUMERIC.sub("", normalized)

    # Collapse extra whitespace
    normalized = _EXTRA_WHITESPACE.sub(" ", normalized).strip()

    return normalized


def company_names_match(filing_name: str, job_company: str, *, threshold: int = 0) -> bool:
    """Return True if two company names match after normalization.

    For an exact normalized match (threshold=0), both normalized strings must be equal.
    This avoids false positives from substring matching (e.g. "Apple" matching "Pineapple").

    Args:
        filing_name: Company name from a WARN Act filing.
        job_company: Company name from a job posting.
        threshold: Reserved for future fuzzy matching (Levenshtein distance).
                   Currently only exact match (0) is supported.

    Returns:
        True if the normalized names are considered a match.
    """
    norm_filing = normalize_company_name(filing_name)
    norm_job = normalize_company_name(job_company)

    if not norm_filing or not norm_job:
        return False

    if threshold == 0:
        return norm_filing == norm_job

    # Future: Levenshtein / token-set ratio
    return norm_filing == norm_job


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------


def get_filings_for_company(
    db: Session,
    company_name: str,
    *,
    since: date | None = None,
) -> list[WARNFiling]:
    """Return all WARN filings matching the given company name.

    Uses normalized name matching. If `since` is provided, only filings with
    notice_date >= since are returned.

    Args:
        db: SQLAlchemy synchronous session.
        company_name: Company name to look up (will be normalized).
        since: Optional cutoff date for notice_date.

    Returns:
        List of matching WARNFiling ORM objects, ordered by notice_date DESC.
    """
    normalized = normalize_company_name(company_name)
    if not normalized:
        return []

    # Pull all filings for the normalized name from the DB.
    # We do post-filter matching because partial-token matching may be added later.
    query = db.query(WARNFiling).filter(WARNFiling.company_name_normalized == normalized)
    if since is not None:
        query = query.filter(WARNFiling.notice_date >= since)

    return query.order_by(WARNFiling.notice_date.desc()).all()


def upsert_filing(
    db: Session,
    *,
    company_name: str,
    state: str,
    notice_date: date,
    effective_date: date | None = None,
    employees_affected: int | None = None,
    source_url: str | None = None,
) -> WARNFiling:
    """Insert a WARN filing or return the existing one if already present.

    Deduplication key: (company_name_normalized, state, notice_date).

    Args:
        db: SQLAlchemy synchronous session.
        company_name: Raw company name from the state filing.
        state: Two-letter state abbreviation.
        notice_date: Date the notice was filed.
        effective_date: Effective date of the layoff (optional).
        employees_affected: Number of employees affected (optional).
        source_url: URL of the source page (optional).

    Returns:
        The existing or newly created WARNFiling instance.
    """
    normalized = normalize_company_name(company_name)
    state_upper = state.upper()[:2]

    existing = (
        db.query(WARNFiling)
        .filter(
            WARNFiling.company_name_normalized == normalized,
            WARNFiling.state == state_upper,
            WARNFiling.notice_date == notice_date,
        )
        .first()
    )

    if existing is not None:
        # Update mutable fields if we have richer data now
        if employees_affected is not None and existing.employees_affected is None:
            existing.employees_affected = employees_affected
        if effective_date is not None and existing.effective_date is None:
            existing.effective_date = effective_date
        return existing

    filing = WARNFiling(
        company_name=company_name,
        company_name_normalized=normalized,
        state=state_upper,
        notice_date=notice_date,
        effective_date=effective_date,
        employees_affected=employees_affected,
        source_url=source_url,
        created_at=datetime.now(UTC),
    )
    db.add(filing)
    return filing


# ---------------------------------------------------------------------------
# Data loading via warn-scraper
# ---------------------------------------------------------------------------


def _is_warnscraper_available() -> bool:
    """Return True if the warn-scraper package is importable."""
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import warn  # noqa: F401

        return True
    except ImportError:
        return False


def load_warn_data_for_state(
    db: Session,
    state: str,
) -> int:
    """Download and store WARN filings for a single state.

    Uses the warn-scraper library to fetch current data from the state's WARN
    portal. Each filing is upserted into the warn_filings table.

    Args:
        db: SQLAlchemy synchronous session (caller commits).
        state: Two-letter state abbreviation (e.g. "CA").

    Returns:
        Number of filings inserted or updated.

    Raises:
        ImportError: If warn-scraper is not installed. Callers should handle
                     this gracefully.
        RuntimeError: If the scraper fails for this state.
    """
    try:
        import warn as warnscraper
    except ImportError as exc:
        raise ImportError(
            "warn-scraper is not installed. Install it with: pip install 'kestrel-app[warn]'"
        ) from exc

    logger.info("Fetching WARN data for state: %s", state)

    try:
        scraper_class = warnscraper.get_scraper(state.upper())
        scraper = scraper_class()
        rows = scraper.scrape()
    except Exception as exc:
        raise RuntimeError(f"warn-scraper failed for state {state}: {exc}") from exc

    count = 0
    for row in rows:
        # warn-scraper uses different column names per state; try common patterns.
        company = (
            row.get("company")
            or row.get("company_name")
            or row.get("employer")
            or row.get("Employer")
            or ""
        )
        if not company:
            continue

        # Notice date parsing — warn-scraper returns strings or date objects
        raw_notice = (
            row.get("notice_date") or row.get("date") or row.get("received_date") or row.get("Date")
        )
        notice_date = _parse_date(raw_notice)
        if notice_date is None:
            logger.debug("Skipping row with unparseable notice date: %r", row)
            continue

        raw_effective = (
            row.get("effective_date") or row.get("layoff_date") or row.get("Effective Date")
        )
        effective_date = _parse_date(raw_effective)

        raw_employees = row.get("employees") or row.get("workers_affected") or row.get("Employees")
        employees_affected = _parse_int(raw_employees)

        upsert_filing(
            db,
            company_name=str(company).strip(),
            state=state.upper(),
            notice_date=notice_date,
            effective_date=effective_date,
            employees_affected=employees_affected,
        )
        count += 1

    db.flush()
    logger.info("State %s: upserted %d filings", state, count)
    return count


def load_warn_data(
    db: Session,
    states: list[str] | None = None,
) -> dict[str, int]:
    """Download and store WARN filings for multiple states.

    Args:
        db: SQLAlchemy synchronous session (caller commits after).
        states: List of two-letter state abbreviations. Defaults to DEFAULT_STATES.

    Returns:
        Dict mapping state -> number of filings processed. States that
        failed are mapped to -1.
    """
    if not _is_warnscraper_available():
        logger.warning(
            "warn-scraper not installed — WARN data loading skipped. "
            "Install with: pip install 'kestrel-app[warn]'"
        )
        return {}

    if states is None:
        states = DEFAULT_STATES

    results: dict[str, int] = {}
    for state in states:
        try:
            results[state] = load_warn_data_for_state(db, state)
        except (RuntimeError, ImportError) as exc:
            logger.warning("Failed to load WARN data for %s: %s", state, exc)
            results[state] = -1

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_date(value: object) -> date | None:
    """Parse a date from various types returned by warn-scraper."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%d-%b-%Y", "%B %d, %Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _parse_int(value: object) -> int | None:
    """Parse an integer from various representations."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d]", "", value)
        if cleaned:
            try:
                return int(cleaned)
            except ValueError:
                pass
    return None
