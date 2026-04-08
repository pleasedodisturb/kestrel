"""Discovery service — unified job discovery with deduplication and pipeline auto-feed."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from career_os.discovery.adapters import (
    RawJobResult,
    ScrapeParams,
    get_available_adapters,
)
from career_os.models.discovery import DiscoveredJob, DiscoveryRun, SearchProfile
from career_os.models.models import Application, Profile
from career_os.services.salary import parse_salary_range

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class SearchProfileNotFoundError(Exception):
    """Raised when a search profile is not found."""


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Normalize text for dedup: lowercase, strip whitespace."""
    return text.strip().lower()


def _dedup_key(job: RawJobResult) -> tuple[str, str, str]:
    """Compute dedup key: (title, company, location) — all normalized."""
    return (
        _normalize(job.title),
        _normalize(job.company),
        _normalize(job.location),
    )


def _passes_sp_filters(merged: dict, sp_filters: dict) -> bool:
    """Check whether a merged job result passes the search profile filters.

    Supported filter keys (matching SavedSearchConfig schema):
    - salary_min / salary_max: numeric salary range comparison
    - score_min / score_max: fit score range (not applicable during discovery)
    - remote: boolean
    - company: substring match (case-insensitive)
    - location: substring match (case-insensitive)
    - source: source name match
    """
    # Salary min/max — parse numeric salary from the string
    salary_min = sp_filters.get("salary_min")
    salary_max = sp_filters.get("salary_max")
    if salary_min is not None or salary_max is not None:
        low, high = parse_salary_range(merged.get("salary_range"))
        mid = ((low or 0) + (high or 0)) / 2 if low or high else None
        if salary_min is not None and (mid is None or mid < salary_min):
            return False
        if salary_max is not None and (mid is None or mid > salary_max):
            return False

    # Remote filter
    remote_filter = sp_filters.get("remote")
    if remote_filter is not None and merged.get("remote") != remote_filter:
        return False

    # Company substring filter
    company_filter = sp_filters.get("company")
    if company_filter and (company_filter.lower() not in (merged.get("company") or "").lower()):
        return False

    # Location substring filter
    location_filter = sp_filters.get("location")
    if location_filter and (location_filter.lower() not in (merged.get("location") or "").lower()):
        return False

    # Source filter
    source_filter = sp_filters.get("source")
    return not (source_filter and source_filter not in (merged.get("sources") or []))


# ---------------------------------------------------------------------------
# Core Discovery Logic
# ---------------------------------------------------------------------------


async def run_discovery(
    db: Session,
    profile_id: int,
    *,
    keywords: list[str] | None = None,
    locations: list[str] | None = None,
    remote_only: bool = False,
    sources: list[str] | None = None,
    limit_per_source: int = 25,
    search_profile_id: int | None = None,
    trigger: str = "manual",
) -> dict:
    """Execute a discovery sweep across multiple sources.

    Returns a dict with run_id, total_found, new_jobs, duplicates, jobs, warnings.
    """
    # Validate profile exists
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Additional filters from saved search profile (salary, score thresholds, etc.)
    sp_filters: dict = {}

    # If using a saved search profile, load its parameters
    if search_profile_id:
        sp = (
            db.query(SearchProfile)
            .filter(
                SearchProfile.id == search_profile_id,
                SearchProfile.profile_id == profile_id,
            )
            .first()
        )
        if not sp:
            raise SearchProfileNotFoundError(f"Search profile {search_profile_id} not found")
        sp_keywords = json.loads(sp.keywords) if sp.keywords else []
        sp_locations = json.loads(sp.locations) if sp.locations else []
        sp_sources = json.loads(sp.sources) if sp.sources else []
        keywords = sp_keywords or keywords
        locations = sp_locations or locations
        remote_only = sp.remote_only
        sources = sp_sources or sources

        # Load additional filters (salary, score, etc.)
        sp_filters = json.loads(sp.filters) if sp.filters else {}

    # Create discovery run log
    run = DiscoveryRun(
        profile_id=profile_id,
        search_profile_id=search_profile_id,
        trigger=trigger,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    params = ScrapeParams(
        keywords=keywords or [],
        locations=locations or [],
        remote_only=remote_only,
        limit_per_source=limit_per_source,
    )

    # Get adapters to use
    adapters = get_available_adapters(sources)
    if not adapters:
        # Default to arbeitsagentur + arbeitnow (always available, no pip dep)
        adapters = get_available_adapters(["arbeitsagentur", "arbeitnow"])

    # Scrape from all adapters (catch individual failures)
    all_raw_jobs: list[RawJobResult] = []
    warnings: list[dict[str, str]] = []
    sources_queried: list[str] = []

    for adapter in adapters:
        try:
            jobs = await adapter.scrape(params)
            all_raw_jobs.extend(jobs)
            sources_queried.append(adapter.source_name)
            logger.info("Source '%s' returned %d results", adapter.source_name, len(jobs))
        except Exception as exc:
            warning = {
                "source": adapter.source_name,
                "error": str(exc),
            }
            warnings.append(warning)
            logger.warning("Source '%s' failed: %s", adapter.source_name, exc)

    # Dedup raw results within this sweep
    dedup_groups: dict[tuple[str, str, str], list[RawJobResult]] = {}
    for job in all_raw_jobs:
        key = _dedup_key(job)
        if key not in dedup_groups:
            dedup_groups[key] = []
        dedup_groups[key].append(job)

    # Apply saved search filters to deduped groups before upserting
    if sp_filters:
        filtered_groups: dict[tuple[str, str, str], list[RawJobResult]] = {}
        for key, group in dedup_groups.items():
            merged_check = _merge_raw_jobs(group)
            if not _passes_sp_filters(merged_check, sp_filters):
                continue
            filtered_groups[key] = group
        dedup_groups = filtered_groups

    # Merge deduplicated results and upsert into DB
    new_jobs_list: list[DiscoveredJob] = []
    duplicates = 0
    new_count = 0

    for key, group in dedup_groups.items():
        merged = _merge_raw_jobs(group)
        title_norm, company_norm, location_norm = key

        # Check if already exists in DB for this profile
        existing = (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.profile_id == profile_id,
                DiscoveredJob.title_normalized == title_norm,
                DiscoveredJob.company_normalized == company_norm,
                DiscoveredJob.location_normalized == location_norm,
            )
            .first()
        )

        if existing:
            # Update existing record with richer data
            _update_existing_job(existing, merged)
            db.add(existing)
            duplicates += 1
        else:
            # Create new discovered job + application in a savepoint
            # so a race condition (concurrent insert) doesn't break the
            # whole transaction. Context manager auto-commits on success,
            # auto-rolls-back on exception.
            try:
                with db.begin_nested():
                    dj = DiscoveredJob(
                        profile_id=profile_id,
                        title=merged["title"],
                        company=merged["company"],
                        location=merged["location"],
                        url=merged["url"],
                        description=merged["description"],
                        salary_range=merged["salary_range"],
                        remote=merged["remote"],
                        posted_at=merged["posted_at"],
                        title_normalized=title_norm,
                        company_normalized=company_norm,
                        location_normalized=location_norm,
                        sources=json.dumps(merged["sources"]),
                        source_urls=json.dumps(merged["source_urls"]),
                    )
                    db.add(dj)
                    db.flush()  # Get the ID

                    # Auto-feed into pipeline as "discovered"
                    app = Application(
                        profile_id=profile_id,
                        company=merged["company"],
                        role=merged["title"],
                        url=merged["url"],
                        source="discovery",
                        status="discovered",
                        salary_range=merged["salary_range"],
                        notes=f"Auto-discovered from: {', '.join(merged['sources'])}",
                    )
                    db.add(app)
                    db.flush()
                    dj.application_id = app.id

                new_jobs_list.append(dj)
                new_count += 1
            except IntegrityError:
                logger.debug(
                    "Duplicate discovered job skipped (race condition)"
                )
                duplicates += 1

    # Finalize the run
    run.status = "completed"
    run.total_found = len(all_raw_jobs)
    run.new_jobs = new_count
    run.duplicates = duplicates
    run.errors = len(warnings)
    run.warnings = json.dumps(warnings)
    run.completed_at = datetime.now(UTC)

    db.commit()

    # Refresh all new jobs to get their final IDs
    for dj in new_jobs_list:
        db.refresh(dj)

    # Auto-score discovered jobs (VAL-SCORE-007)
    if new_jobs_list:
        try:
            from career_os.services.scoring import batch_score_discovery

            await batch_score_discovery(
                db,
                profile_id,
                discovered_job_ids=[dj.id for dj in new_jobs_list],
            )
            logger.info("Auto-scored %d discovered jobs", len(new_jobs_list))

            # Propagate scores to linked applications (VAL-CROSS-002)
            propagated = propagate_discovery_scores(db, profile_id)
            if propagated:
                logger.info("Propagated scores to %d linked applications", propagated)
        except Exception as exc:
            logger.warning("Auto-scoring failed: %s", exc)
            warnings.append(
                {
                    "source": "auto_scoring",
                    "error": str(exc),
                }
            )

    # Auto-refresh market intelligence (VAL-MARKET-006)
    try:
        from career_os.services.market import refresh_market_data

        refresh_market_data(db, profile_id)
        logger.info("Market intelligence refreshed after discovery sweep")
    except Exception as exc:
        logger.warning("Market intelligence refresh failed: %s", exc)

    return {
        "run_id": run.id,
        "total_found": len(all_raw_jobs),
        "new_jobs": new_count,
        "duplicates": duplicates,
        "jobs": new_jobs_list,
        "warnings": warnings,
        "sources_queried": sources_queried,
    }


def propagate_discovery_scores(db: Session, profile_id: int) -> int:
    """Copy fit_score from DiscoveredJobs to their linked Applications.

    Updates the linked Application's fit_score whenever it differs from the
    DiscoveredJob's score (handles both initial scoring and rescoring).
    Returns the number of applications updated.
    """
    updated = 0
    jobs = (
        db.query(DiscoveredJob)
        .filter(
            DiscoveredJob.profile_id == profile_id,
            DiscoveredJob.application_id.isnot(None),
            DiscoveredJob.fit_score.isnot(None),
        )
        .all()
    )
    for dj in jobs:
        app = db.query(Application).filter(Application.id == dj.application_id).first()
        if app and app.fit_score != dj.fit_score:
            app.fit_score = dj.fit_score
            updated += 1
    if updated:
        db.commit()
    return updated


def _merge_raw_jobs(group: list[RawJobResult]) -> dict:
    """Merge multiple raw jobs (same dedup key) keeping richest data."""
    sources: list[str] = []
    source_urls: list[str] = []
    best_description = ""
    best_url = ""
    earliest_posted: datetime | None = None
    salary_range = ""
    remote = False

    for job in group:
        if job.source not in sources:
            sources.append(job.source)
        if job.url and job.url not in source_urls:
            source_urls.append(job.url)
        if len(job.description or "") > len(best_description):
            best_description = job.description or ""
        if not best_url and job.url:
            best_url = job.url
        if job.posted_at and (earliest_posted is None or job.posted_at < earliest_posted):
            earliest_posted = job.posted_at
        if job.salary_range and (not salary_range or len(job.salary_range) > len(salary_range)):
            salary_range = job.salary_range
        if job.remote:
            remote = True

    first = group[0]
    return {
        "title": first.title,
        "company": first.company,
        "location": first.location,
        "url": best_url,
        "description": best_description,
        "salary_range": salary_range,
        "remote": remote,
        "posted_at": earliest_posted,
        "sources": sources,
        "source_urls": source_urls,
    }


def _update_existing_job(existing: DiscoveredJob, merged: dict) -> None:
    """Update an existing discovered job with richer merged data."""
    # Merge sources
    existing_sources = json.loads(existing.sources or "[]")
    for s in merged["sources"]:
        if s not in existing_sources:
            existing_sources.append(s)
    existing.sources = json.dumps(existing_sources)

    # Merge source URLs
    existing_urls = json.loads(existing.source_urls or "[]")
    for u in merged["source_urls"]:
        if u not in existing_urls:
            existing_urls.append(u)
    existing.source_urls = json.dumps(existing_urls)

    # Keep longest description
    if len(merged["description"] or "") > len(existing.description or ""):
        existing.description = merged["description"]

    # Keep earliest posted date
    if merged["posted_at"] and (
        existing.posted_at is None or merged["posted_at"] < existing.posted_at
    ):
        existing.posted_at = merged["posted_at"]

    # Keep richest salary
    if merged["salary_range"] and (
        not existing.salary_range or len(merged["salary_range"]) > len(existing.salary_range or "")
    ):
        existing.salary_range = merged["salary_range"]

    # Remote flag is additive
    if merged["remote"]:
        existing.remote = True


# ---------------------------------------------------------------------------
# Search Profile CRUD
# ---------------------------------------------------------------------------


def create_search_profile(db: Session, profile_id: int, data: dict) -> SearchProfile:
    """Create a saved search profile."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    sp = SearchProfile(
        profile_id=profile_id,
        name=data["name"],
        keywords=json.dumps(data.get("keywords", [])),
        locations=json.dumps(data.get("locations", [])),
        remote_only=data.get("remote_only", False),
        sources=json.dumps(data.get("sources", [])),
        filters=json.dumps(data.get("filters")) if data.get("filters") else None,
        cadence=data.get("cadence"),
        next_run=data.get("next_run"),
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp


def list_search_profiles(
    db: Session, profile_id: int, *, active_only: bool = False
) -> list[SearchProfile]:
    """List search profiles for a given profile."""
    query = db.query(SearchProfile).filter(SearchProfile.profile_id == profile_id)
    if active_only:
        query = query.filter(SearchProfile.is_active.is_(True))
    return query.order_by(SearchProfile.created_at.desc()).all()


def get_search_profile(db: Session, sp_id: int, *, profile_id: int | None = None) -> SearchProfile:
    """Get a search profile by ID."""
    filters = [SearchProfile.id == sp_id]
    if profile_id is not None:
        filters.append(SearchProfile.profile_id == profile_id)
    sp = db.query(SearchProfile).filter(*filters).first()
    if not sp:
        raise SearchProfileNotFoundError(f"Search profile {sp_id} not found")
    return sp


def update_search_profile(db: Session, sp_id: int, profile_id: int, data: dict) -> SearchProfile:
    """Update a search profile."""
    sp = get_search_profile(db, sp_id, profile_id=profile_id)

    if "name" in data and data["name"] is not None:
        sp.name = data["name"]
    if "keywords" in data and data["keywords"] is not None:
        sp.keywords = json.dumps(data["keywords"])
    if "locations" in data and data["locations"] is not None:
        sp.locations = json.dumps(data["locations"])
    if "remote_only" in data and data["remote_only"] is not None:
        sp.remote_only = data["remote_only"]
    if "sources" in data and data["sources"] is not None:
        sp.sources = json.dumps(data["sources"])
    if "filters" in data and data["filters"] is not None:
        sp.filters = json.dumps(data["filters"])
    if "is_active" in data and data["is_active"] is not None:
        sp.is_active = data["is_active"]

    db.commit()
    db.refresh(sp)
    return sp


def delete_search_profile(db: Session, sp_id: int, profile_id: int) -> None:
    """Delete a search profile."""
    sp = get_search_profile(db, sp_id, profile_id=profile_id)
    db.delete(sp)
    db.commit()


# ---------------------------------------------------------------------------
# Discovery Runs
# ---------------------------------------------------------------------------


def list_discovery_runs(db: Session, profile_id: int, *, limit: int = 20) -> list[DiscoveryRun]:
    """List discovery runs for a profile, most recent first."""
    return (
        db.query(DiscoveryRun)
        .filter(DiscoveryRun.profile_id == profile_id)
        .order_by(DiscoveryRun.started_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Scheduled Discovery
# ---------------------------------------------------------------------------


def _compute_next_run(cadence: str | None, from_time: datetime | None = None) -> datetime | None:
    """Compute the next run time based on cadence.

    Supported cadences: 'daily', 'weekly'. Returns None for unknown cadences.
    """
    if not cadence:
        return None
    base = from_time or datetime.now(UTC)
    if cadence == "daily":
        return base + timedelta(days=1)
    if cadence == "weekly":
        return base + timedelta(weeks=1)
    return None


async def run_scheduled_discovery(db: Session, profile_id: int) -> dict | None:
    """Run discovery for all active search profiles for a given profile.

    Used by the background scheduler. Gates execution by cadence/next_run:
    skips profiles where next_run > now. Updates next_run after execution.
    Returns combined results or None if no active search profiles ran.
    """
    active_profiles = list_search_profiles(db, profile_id, active_only=True)
    if not active_profiles:
        return None

    now = datetime.now(UTC)
    combined_result = None
    for sp in active_profiles:
        # Gate: skip profiles without an explicit cadence (no schedule configured)
        if sp.cadence is None:
            logger.info(
                "Skipping search profile %d (%s): no cadence configured",
                sp.id,
                sp.name,
            )
            continue

        # Gate by next_run: skip if the next run is in the future
        if sp.next_run is not None:
            next_run = sp.next_run
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=UTC)
            if next_run > now:
                logger.info(
                    "Skipping search profile %d (%s): next_run %s > now %s",
                    sp.id,
                    sp.name,
                    next_run.isoformat(),
                    now.isoformat(),
                )
                continue

        sp_keywords = json.loads(sp.keywords) if sp.keywords else []
        sp_locations = json.loads(sp.locations) if sp.locations else []
        sp_sources = json.loads(sp.sources) if sp.sources else []

        result = await run_discovery(
            db,
            profile_id,
            keywords=sp_keywords,
            locations=sp_locations,
            remote_only=sp.remote_only,
            sources=sp_sources,
            search_profile_id=sp.id,
            trigger="scheduled",
        )

        # Update next_run after successful execution
        sp.next_run = _compute_next_run(sp.cadence, now)
        db.commit()

        if combined_result is None:
            combined_result = result
        else:
            combined_result["new_jobs"] += result["new_jobs"]
            combined_result["duplicates"] += result["duplicates"]
            combined_result["total_found"] += result["total_found"]
            combined_result["jobs"].extend(result["jobs"])
            combined_result["warnings"].extend(result["warnings"])

    return combined_result
