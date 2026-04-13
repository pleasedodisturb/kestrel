"""Background scheduler for periodic discovery sweeps.

Uses asyncio tasks rather than a heavy dependency like APScheduler.
The scheduler is started during app lifespan and runs weekly discovery
for all profiles with active search profiles.
"""

from __future__ import annotations

import asyncio
import logging

from career_os.database import SessionLocal
from career_os.models.models import Profile
from career_os.services.discovery import run_scheduled_discovery

logger = logging.getLogger(__name__)

# Default interval: 7 days (in seconds)
DEFAULT_INTERVAL_SECONDS = 7 * 24 * 60 * 60

_scheduler_task: asyncio.Task | None = None


async def _discover_single_profile(db: object, profile: object) -> None:
    """Run discovery for one profile, rolling back on failure."""
    try:
        result = await run_scheduled_discovery(db, profile.id)
        if result:
            logger.info(
                "Scheduled discovery for profile %d: %d new, %d duplicates",
                profile.id,
                result["new_jobs"],
                result["duplicates"],
            )
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Scheduled discovery failed for profile %d: %s",
            profile.id,
            exc,
        )


def _handle_discovery_error(
    exc: Exception,
    consecutive_errors: int,
    max_consecutive_errors: int,
) -> tuple[bool, int]:
    """Handle error counting and logging. Returns (should_stop, new_error_count)."""
    if isinstance(exc, asyncio.CancelledError):
        logger.info("Discovery scheduler cancelled")
        return True, consecutive_errors

    if isinstance(exc, (OSError, ConnectionError)):
        consecutive_errors += 1
        logger.warning(
            "Discovery scheduler transient error (%d/%d): %s",
            consecutive_errors,
            max_consecutive_errors,
            exc,
        )
        if consecutive_errors >= max_consecutive_errors:
            logger.error(
                "Discovery scheduler stopping after %d consecutive errors",
                consecutive_errors,
            )
            return True, consecutive_errors
        return False, consecutive_errors

    # Fatal errors (config, programming) — log and stop
    logger.exception("Discovery scheduler fatal error — stopping: %s", exc)
    return True, consecutive_errors


async def _run_sweep() -> None:
    """Execute a single discovery sweep across all profiles."""
    db = SessionLocal()
    try:
        profiles = db.query(Profile).all()
        for profile in profiles:
            await _discover_single_profile(db, profile)
    finally:
        db.close()


async def _discovery_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Periodically run discovery for all profiles with active search profiles."""
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("Scheduled discovery sweep starting...")
            await _run_sweep()
            consecutive_errors = 0
        except asyncio.CancelledError:
            logger.info("Discovery scheduler cancelled")
            raise
        except Exception as exc:
            should_stop, consecutive_errors = _handle_discovery_error(
                exc, consecutive_errors, max_consecutive_errors
            )
            if should_stop:
                break
            await asyncio.sleep(60)


def start_scheduler(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> asyncio.Task:
    """Start the background discovery scheduler.

    Returns the asyncio task for cancellation during shutdown.
    """
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_discovery_loop(interval_seconds))
    logger.info("Discovery scheduler started (interval=%ds)", interval_seconds)
    return _scheduler_task


def stop_scheduler() -> None:
    """Stop the background discovery scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("Discovery scheduler stopped")
    _scheduler_task = None
