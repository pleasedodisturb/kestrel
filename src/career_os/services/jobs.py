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
    # Validate profile exists
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

    # --- Full-text search across title, company, description, location ---
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

    # --- Facet filters (AND logic) ---
    if source:
        # sources is a JSON array stored as text
        query = query.filter(DiscoveredJob.sources.ilike(f'%"{source}"%'))

    if remote is not None:
        query = query.filter(DiscoveredJob.remote == remote)

    if company:
        query = query.filter(DiscoveredJob.company.ilike(f"%{company}%"))

    if location:
        query = query.filter(DiscoveredJob.location.ilike(f"%{location}%"))

    if score_min is not None:
        query = query.filter(DiscoveredJob.fit_score >= score_min)

    if score_max is not None:
        query = query.filter(DiscoveredJob.fit_score <= score_max)

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
            query = query.filter(DiscoveredJob.created_at >= dt_from)
        except ValueError:
            pass  # ignore invalid date

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to).replace(tzinfo=UTC)
            query = query.filter(DiscoveredJob.created_at <= dt_to)
        except ValueError:
            pass

    # --- Determine sort ---
    sort_field = sort if sort in SORTABLE_FIELDS else "date"
    sort_order = order if order in SORT_ORDERS else "desc"

    # For salary filtering and sorting we need numeric parsing (SQLite
    # can't natively parse "130,000-160,000 EUR" → number).  When salary
    # filter or salary sort is active we fetch all SQL-filtered rows and
    # apply salary logic in Python, then paginate in-memory.
    need_python_salary = salary_min is not None or salary_max is not None or sort_field == "salary"

    if need_python_salary:
        # Fetch all matching rows (no pagination yet)
        all_rows = query.all()

        # Enrich with parsed salary midpoint
        enriched = []
        for row in all_rows:
            job_obj = row[0]
            readiness = row[1]
            mid = salary_midpoint(job_obj.salary_range)
            enriched.append(
                {
                    "job": job_obj,
                    "readiness_score": readiness,
                    "_salary_mid": mid,
                }
            )

        # Apply salary filters using numeric comparison
        if salary_min is not None:
            enriched = [
                r
                for r in enriched
                if r["_salary_mid"] is not None and r["_salary_mid"] >= salary_min
            ]
        if salary_max is not None:
            enriched = [
                r
                for r in enriched
                if r["_salary_mid"] is not None and r["_salary_mid"] <= salary_max
            ]

        # Sort: nulls always last, non-null values sorted by direction.
        reverse = sort_order == "desc"

        def _get_sort_val(item: dict):
            if sort_field == "salary":
                return item["_salary_mid"]
            elif sort_field == "score":
                return item["job"].fit_score
            elif sort_field == "readiness":
                return item["readiness_score"]
            else:
                return item["job"].created_at

        # Split into non-null and null groups so nulls always appear last
        with_val = [r for r in enriched if _get_sort_val(r) is not None]
        without_val = [r for r in enriched if _get_sort_val(r) is None]
        with_val.sort(key=lambda r: _get_sort_val(r), reverse=reverse)
        enriched = with_val + without_val

        # Paginate in-memory
        total = len(enriched)
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        total_pages = max(1, math.ceil(total / page_size))

        page_items = enriched[offset : offset + page_size]
        jobs = [{"job": r["job"], "readiness_score": r["readiness_score"]} for r in page_items]
    else:
        # --- Count total before pagination ---
        total = query.count()

        # --- SQL Sorting ---
        if sort_field == "score":
            sort_col = DiscoveredJob.fit_score
        elif sort_field == "readiness":
            sort_col = ScoredJob.readiness_score
        else:  # date
            sort_col = DiscoveredJob.created_at

        # SQLite doesn't support NULLS LAST natively, so use a CASE expression
        null_sort = case((sort_col.is_(None), 1), else_=0)
        if sort_order == "asc":
            query = query.order_by(null_sort, sort_col.asc())
        else:
            query = query.order_by(null_sort, sort_col.desc())

        # --- Pagination ---
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        total_pages = max(1, math.ceil(total / page_size))

        rows = query.offset(offset).limit(page_size).all()

        # Map rows to result dicts
        jobs = []
        for row in rows:
            job_obj = row[0]
            readiness = row[1]
            jobs.append(
                {
                    "job": job_obj,
                    "readiness_score": readiness,
                }
            )

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
