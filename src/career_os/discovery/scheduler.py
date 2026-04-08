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


async def _discovery_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Periodically run discovery for all profiles with active search profiles."""
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("Scheduled discovery sweep starting...")

            db = SessionLocal()
            try:
                profiles = db.query(Profile).all()
                for profile in profiles:
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
                consecutive_errors = 0
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Discovery scheduler cancelled")
            break
        except (OSError, ConnectionError) as exc:
            # Retryable network/IO errors
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
                break
            await asyncio.sleep(60)
        except Exception as exc:
            # Fatal errors (config, programming) — log and stop
            logger.exception("Discovery scheduler fatal error — stopping: %s", exc)
            break


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
