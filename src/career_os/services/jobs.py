"""Jobs search, filter, sort & saved search service (Milestone 3)."""

from __future__ import annotations

import json
import logging
import math
from datetime import UTC, datetime

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from career_os.models.discovery import DiscoveredJob, SavedSearch
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob
from career_os.services.salary import salary_midpoint

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class SavedSearchNotFoundError(Exception):
    """Raised when a saved search is not found."""


# ---------------------------------------------------------------------------
# Job Search & Filter
# ---------------------------------------------------------------------------

SORTABLE_FIELDS = {"score", "date", "salary", "readiness"}
SORT_ORDERS = {"asc", "desc"}

# Lookup dict mapping sort field names to in-memory value extractors.
# Each callable takes an enriched row dict and returns the sortable value.
_SORT_KEY_EXTRACTORS: dict = {
    "salary": lambda r: r["_salary_mid"],
    "score": lambda r: r["job"].fit_score,
    "readiness": lambda r: r["readiness_score"],
    "date": lambda r: r["job"].created_at,
}

# Lookup dict mapping sort field names to SQL columns.
_SQL_SORT_COLUMNS: dict = {
    "score": lambda: DiscoveredJob.fit_score,
    "readiness": lambda: ScoredJob.readiness_score,
    "date": lambda: DiscoveredJob.created_at,
}


def _apply_date_filter(query, date_str: str | None, *, column, op: str):
    """Parse an ISO date string and apply a >= or <= filter. Ignores invalid dates."""
    if not date_str:
        return query
    try:
        dt = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
    except ValueError:
        return query
    if op == "gte":
        return query.filter(column >= dt)
    return query.filter(column <= dt)


def _build_job_filters(
    query,
    q,
    source,
    remote,
    company_filter,
    location_filter,
    min_score,
    max_score,
    date_from,
    date_to,
):
    """Apply all SQL-level WHERE filters to *query* and return it."""
    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                DiscoveredJob.title.ilike(term),
                DiscoveredJob.company.ilike(term),
                DiscoveredJob.description.ilike(term),
                DiscoveredJob.location.ilike(term),
            )
        )

    if source:
        query = query.filter(DiscoveredJob.sources.ilike(f'%"{source}"%'))

    if remote is not None:
        query = query.filter(DiscoveredJob.remote == remote)

    if company_filter:
        query = query.filter(DiscoveredJob.company.ilike(f"%{company_filter}%"))

    if location_filter:
        query = query.filter(DiscoveredJob.location.ilike(f"%{location_filter}%"))

    if min_score is not None:
        query = query.filter(DiscoveredJob.fit_score >= min_score)

    if max_score is not None:
        query = query.filter(DiscoveredJob.fit_score <= max_score)

    query = _apply_date_filter(query, date_from, column=DiscoveredJob.created_at, op="gte")
    query = _apply_date_filter(query, date_to, column=DiscoveredJob.created_at, op="lte")

    return query


def _apply_salary_sorting(query, sort_field, sort_order, salary_min, salary_max, page, page_size):
    """Fetch all rows, apply salary filter/sort in Python, paginate in-memory.

    Returns ``(jobs, total, page, page_size, total_pages)``.
    """
    all_rows = query.all()

    enriched = [
        {
            "job": row[0],
            "readiness_score": row[1],
            "_salary_mid": salary_midpoint(row[0].salary_range),
        }
        for row in all_rows
    ]

    if salary_min is not None:
        enriched = [
            r for r in enriched if r["_salary_mid"] is not None and r["_salary_mid"] >= salary_min
        ]
    if salary_max is not None:
        enriched = [
            r for r in enriched if r["_salary_mid"] is not None and r["_salary_mid"] <= salary_max
        ]

    extractor = _SORT_KEY_EXTRACTORS.get(sort_field, _SORT_KEY_EXTRACTORS["date"])
    enriched = _sort_nulls_last(enriched, key=extractor, reverse=(sort_order == "desc"))

    jobs, total, page, page_size, total_pages = _paginate_results(enriched, page, page_size)
    jobs = [{"job": r["job"], "readiness_score": r["readiness_score"]} for r in jobs]
    return jobs, total, page, page_size, total_pages


def _apply_sql_sorting(query, sort_field, sort_order):
    """Apply ORDER BY to the query using SQL columns. Returns the updated query."""
    col_factory = _SQL_SORT_COLUMNS.get(sort_field, _SQL_SORT_COLUMNS["date"])
    sort_col = col_factory()

    # SQLite doesn't support NULLS LAST natively, so use a CASE expression
    null_sort = case((sort_col.is_(None), 1), else_=0)
    if sort_order == "asc":
        return query.order_by(null_sort, sort_col.asc())
    return query.order_by(null_sort, sort_col.desc())


def _sort_nulls_last(items, *, key, reverse):
    """Sort *items* by *key* with ``None`` values always last."""
    with_val = [r for r in items if key(r) is not None]
    without_val = [r for r in items if key(r) is None]
    with_val.sort(key=key, reverse=reverse)
    return with_val + without_val


def _paginate_results(items, page, page_size):
    """Return ``(page_items, total, page, page_size, total_pages)`` for an in-memory list."""
    total = len(items)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    total_pages = max(1, math.ceil(total / page_size))
    return items[offset : offset + page_size], total, page, page_size, total_pages


def search_jobs(
    db: Session,
    profile_id: int,
    *,
    q: str | None = None,
    source: str | None = None,
    remote: bool | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    score_min: float | None = None,
    score_max: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    company: str | None = None,
    location: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search, filter, sort, and paginate discovered jobs.

    Returns dict with keys: jobs, total, page, page_size, total_pages.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Base query: discovered jobs for this profile with optional score join
    query = (
        db.query(DiscoveredJob, ScoredJob.readiness_score)
        .outerjoin(
            ScoredJob,
            (ScoredJob.discovered_job_id == DiscoveredJob.id)
            & (ScoredJob.profile_id == DiscoveredJob.profile_id),
        )
        .filter(DiscoveredJob.profile_id == profile_id)
    )

    query = _build_job_filters(
        query,
        q,
        source,
        remote,
        company,
        location,
        score_min,
        score_max,
        date_from,
        date_to,
    )

    sort_field = sort if sort in SORTABLE_FIELDS else "date"
    sort_order = order if order in SORT_ORDERS else "desc"

    # When salary filter or salary sort is active we must parse salary strings
    # in Python (SQLite can't natively parse "130,000-160,000 EUR" → number).
    need_python_salary = salary_min is not None or salary_max is not None or sort_field == "salary"

    if need_python_salary:
        jobs, total, page, page_size, total_pages = _apply_salary_sorting(
            query,
            sort_field,
            sort_order,
            salary_min,
            salary_max,
            page,
            page_size,
        )
    else:
        total = query.count()
        query = _apply_sql_sorting(query, sort_field, sort_order)

        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        total_pages = max(1, math.ceil(total / page_size))

        rows = query.offset(offset).limit(page_size).all()
        jobs = [{"job": row[0], "readiness_score": row[1]} for row in rows]

    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# Saved Search CRUD
# ---------------------------------------------------------------------------


def create_saved_search(db: Session, profile_id: int, data: dict) -> SavedSearch:
    """Create a saved search configuration."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    config_json = json.dumps(data.get("config", {}))
    ss = SavedSearch(
        profile_id=profile_id,
        name=data["name"],
        config=config_json,
    )
    db.add(ss)
    db.commit()
    db.refresh(ss)
    return ss


def list_saved_searches(db: Session, profile_id: int) -> list[SavedSearch]:
    """List all saved searches for a profile, newest first."""
    return (
        db.query(SavedSearch)
        .filter(SavedSearch.profile_id == profile_id)
        .order_by(SavedSearch.created_at.desc())
        .all()
    )


def get_saved_search(db: Session, search_id: int, *, profile_id: int) -> SavedSearch:
    """Get a single saved search by ID."""
    ss = (
        db.query(SavedSearch)
        .filter(
            SavedSearch.id == search_id,
            SavedSearch.profile_id == profile_id,
        )
        .first()
    )
    if not ss:
        raise SavedSearchNotFoundError(f"Saved search {search_id} not found")
    return ss


def update_saved_search(db: Session, search_id: int, profile_id: int, data: dict) -> SavedSearch:
    """Update a saved search."""
    ss = get_saved_search(db, search_id, profile_id=profile_id)

    if "name" in data and data["name"] is not None:
        ss.name = data["name"]
    if "config" in data and data["config"] is not None:
        ss.config = json.dumps(data["config"])

    db.commit()
    db.refresh(ss)
    return ss


def delete_saved_search(db: Session, search_id: int, profile_id: int) -> None:
    """Delete a saved search."""
    ss = get_saved_search(db, search_id, profile_id=profile_id)
    db.delete(ss)
    db.commit()
