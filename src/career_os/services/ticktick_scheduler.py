"""Background scheduler for periodic TickTick completion pulls.

Runs every 15 minutes using asyncio, mirroring the discovery scheduler pattern.
Pulls completed tasks from TickTick and updates Career OS entities.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from career_os.database import SessionLocal
from career_os.models.models import Profile
from career_os.services.ticktick_sync import (
    TickTickNotConfiguredError,
    sync_completions_from_ticktick,
)

logger = logging.getLogger(__name__)

# Default interval: 15 minutes (in seconds)
DEFAULT_INTERVAL_SECONDS = 15 * 60

_ticktick_scheduler_task: asyncio.Task | None = None


def _sync_single_profile(db: Session, profile: Profile) -> None:
    """Run TickTick completion sync for a single profile with error handling."""
    try:
        stats = sync_completions_from_ticktick(db, profile_id=profile.id)
    except TickTickNotConfiguredError:
        return
    except Exception as exc:
        logger.warning("TickTick sync failed for profile %d: %s", profile.id, exc)
        return

    if stats["synced"] > 0 or stats["errors"] > 0:
        logger.info(
            "TickTick sync for profile %d: %d synced, %d errors, %d skipped",
            profile.id,
            stats["synced"],
            stats["errors"],
            stats["skipped"],
        )


async def _ticktick_sync_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Periodically pull completed tasks from TickTick for all profiles."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("TickTick sync cycle starting...")

            db = SessionLocal()
            try:
                profiles = db.query(Profile).all()
                for profile in profiles:
                    _sync_single_profile(db, profile)
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("TickTick scheduler cancelled")
            raise
        except Exception as exc:
            logger.exception("TickTick scheduler error: %s", exc)
            # Continue running even on unexpected errors
            await asyncio.sleep(60)


def start_ticktick_scheduler(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> asyncio.Task:
    """Start the background TickTick sync scheduler.

    Returns the asyncio task for cancellation during shutdown.
    """
    global _ticktick_scheduler_task
    _ticktick_scheduler_task = asyncio.create_task(_ticktick_sync_loop(interval_seconds))
    logger.info("TickTick sync scheduler started (interval=%ds)", interval_seconds)
    return _ticktick_scheduler_task


def stop_ticktick_scheduler() -> None:
    """Stop the background TickTick sync scheduler."""
    global _ticktick_scheduler_task
    if _ticktick_scheduler_task and not _ticktick_scheduler_task.done():
        _ticktick_scheduler_task.cancel()
        logger.info("TickTick sync scheduler stopped")
    _ticktick_scheduler_task = None
