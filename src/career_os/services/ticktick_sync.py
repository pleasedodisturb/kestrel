"""TickTick bidirectional sync service.

Handles:
- Pipeline actions → TickTick tasks (push)
- TickTick task completion → Career OS status updates (pull)
- Follow-ups as TickTick tasks with due dates
- Learning goals synced with learning tag
"""

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_ as db_or
from sqlalchemy.orm import Session

from career_os.models.integrations import IntegrationConfig
from career_os.models.models import ActivityLog, Application, FollowUp
from career_os.models.skills import Goal
from career_os.models.ticktick_sync import TickTickSyncTask
from career_os.services.ticktick_client import (
    TickTickAPIError,
    TickTickClient,
)

logger = logging.getLogger(__name__)


class TickTickNotConfiguredError(Exception):
    """Raised when TickTick integration is not configured or disabled."""


class TickTickSyncError(Exception):
    """Raised when a sync operation fails."""


def _get_ticktick_credentials(db: Session) -> tuple[str, str]:
    """Retrieve TickTick API token and project ID from integration config.

    Returns (api_token, project_id).
    Raises TickTickNotConfiguredError if not configured or disabled.
    """
    row = db.query(IntegrationConfig).filter(IntegrationConfig.name == "ticktick").first()
    if row is None or not row.enabled:
        raise TickTickNotConfiguredError("TickTick integration is not enabled")

    creds: dict[str, str] = {}
    if row.credentials:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            creds = json.loads(row.credentials)

    api_token = creds.get("api_token", "").strip()
    project_id = creds.get("project_id", "").strip()

    if not api_token:
        raise TickTickNotConfiguredError("TickTick API token not configured")
    if not project_id:
        raise TickTickNotConfiguredError("TickTick project ID not configured")

    return api_token, project_id


def get_client(db: Session) -> tuple[TickTickClient, str]:
    """Get a TickTickClient and project_id from stored credentials.

    Returns (client, project_id).
    """
    api_token, project_id = _get_ticktick_credentials(db)
    return TickTickClient(api_token), project_id


# ---------------------------------------------------------------------------
# Push: Career OS → TickTick
# ---------------------------------------------------------------------------


def sync_follow_up_to_ticktick(
    db: Session,
    follow_up: FollowUp,
    *,
    client: TickTickClient | None = None,
    project_id: str | None = None,
) -> TickTickSyncTask:
    """Create or update a TickTick task for a follow-up.

    Returns the sync mapping record.
    """
    if client is None or project_id is None:
        client, project_id = get_client(db)

    # Check if already synced
    existing = (
        db.query(TickTickSyncTask)
        .filter(
            TickTickSyncTask.entity_type == "follow_up",
            TickTickSyncTask.entity_id == follow_up.id,
        )
        .first()
    )

    # Build title with application context
    app_obj = db.query(Application).filter(Application.id == follow_up.application_id).first()
    app_context = f"{app_obj.company} — {app_obj.role}" if app_obj else "Unknown"
    title = f"[Follow-up] {app_context} ({follow_up.follow_up_type})"
    content = follow_up.notes or f"Follow-up for {app_context}"

    try:
        if existing:
            # Update existing task
            client.update_task(
                existing.ticktick_task_id,
                project_id,
                title=title,
                content=content,
                due_date=follow_up.due_date,
                priority="medium",
            )
            existing.title = title
            existing.last_synced_at = datetime.now(UTC)
            existing.status = "synced"
            existing.error_message = None
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new task
            result = client.create_task(
                title=title,
                project_id=project_id,
                content=content,
                due_date=follow_up.due_date,
                priority="medium",
            )
            sync_task = TickTickSyncTask(
                profile_id=follow_up.profile_id,
                entity_type="follow_up",
                entity_id=follow_up.id,
                ticktick_task_id=result.get("id", ""),
                ticktick_project_id=project_id,
                title=title,
                status="synced",
            )
            db.add(sync_task)
            db.commit()
            db.refresh(sync_task)
            return sync_task
    except TickTickAPIError as exc:
        logger.error("Failed to sync follow-up %d to TickTick: %s", follow_up.id, exc)
        if existing:
            existing.status = "error"
            existing.error_message = str(exc)
            db.commit()
            db.refresh(existing)
            return existing
        raise TickTickSyncError(str(exc)) from exc


def sync_learning_goal_to_ticktick(
    db: Session,
    goal: Goal,
    *,
    client: TickTickClient | None = None,
    project_id: str | None = None,
) -> TickTickSyncTask:
    """Create or update a TickTick task for a learning goal with 'learning' tag.

    Returns the sync mapping record.
    """
    if client is None or project_id is None:
        client, project_id = get_client(db)

    existing = (
        db.query(TickTickSyncTask)
        .filter(
            TickTickSyncTask.entity_type == "learning_goal",
            TickTickSyncTask.entity_id == goal.id,
        )
        .first()
    )

    title = f"[Learning] {goal.title}"
    content = goal.description or ""

    try:
        if existing:
            client.update_task(
                existing.ticktick_task_id,
                project_id,
                title=title,
                content=content,
                due_date=goal.target_date,
                priority="low",
                tags=["learning"],
            )
            existing.title = title
            existing.last_synced_at = datetime.now(UTC)
            existing.status = "synced"
            existing.error_message = None
            db.commit()
            db.refresh(existing)
            return existing
        else:
            result = client.create_task(
                title=title,
                project_id=project_id,
                content=content,
                due_date=goal.target_date,
                priority="low",
                tags=["learning"],
            )
            sync_task = TickTickSyncTask(
                profile_id=goal.profile_id,
                entity_type="learning_goal",
                entity_id=goal.id,
                ticktick_task_id=result.get("id", ""),
                ticktick_project_id=project_id,
                title=title,
                status="synced",
            )
            db.add(sync_task)
            db.commit()
            db.refresh(sync_task)
            return sync_task
    except TickTickAPIError as exc:
        logger.error("Failed to sync learning goal %d to TickTick: %s", goal.id, exc)
        if existing:
            existing.status = "error"
            existing.error_message = str(exc)
            db.commit()
            db.refresh(existing)
            return existing
        raise TickTickSyncError(str(exc)) from exc


def sync_pipeline_action_to_ticktick(
    db: Session,
    application: Application,
    action: str,
    *,
    client: TickTickClient | None = None,
    project_id: str | None = None,
) -> TickTickSyncTask:
    """Create a TickTick task for a pipeline action (status change, new app, etc.).

    Returns the sync mapping record.
    """
    if client is None or project_id is None:
        client, project_id = get_client(db)

    # For pipeline actions, entity_id = application.id
    existing = (
        db.query(TickTickSyncTask)
        .filter(
            TickTickSyncTask.entity_type == "pipeline_action",
            TickTickSyncTask.entity_id == application.id,
        )
        .first()
    )

    title = f"[Pipeline] {application.company} — {application.role}: {action}"
    content = (
        f"Company: {application.company}\n"
        f"Role: {application.role}\n"
        f"Status: {application.status}\n"
        f"Action: {action}"
    )

    # Determine priority based on application score
    priority = "none"
    if application.fit_score and application.fit_score >= 8.0:
        priority = "high"
    elif application.fit_score and application.fit_score >= 6.0:
        priority = "medium"

    # Default due date: 1 day from now for pipeline actions
    due_date = datetime.now(UTC) + timedelta(days=1)

    try:
        if existing:
            client.update_task(
                existing.ticktick_task_id,
                project_id,
                title=title,
                content=content,
                priority=priority,
                due_date=due_date,
            )
            existing.title = title
            existing.last_synced_at = datetime.now(UTC)
            existing.status = "synced"
            existing.error_message = None
            db.commit()
            db.refresh(existing)
            return existing
        else:
            result = client.create_task(
                title=title,
                project_id=project_id,
                content=content,
                priority=priority,
                due_date=due_date,
            )
            sync_task = TickTickSyncTask(
                profile_id=application.profile_id,
                entity_type="pipeline_action",
                entity_id=application.id,
                ticktick_task_id=result.get("id", ""),
                ticktick_project_id=project_id,
                title=title,
                status="synced",
            )
            db.add(sync_task)
            db.commit()
            db.refresh(sync_task)
            return sync_task
    except TickTickAPIError as exc:
        logger.error(
            "Failed to sync pipeline action for app %d to TickTick: %s",
            application.id,
            exc,
        )
        if existing:
            existing.status = "error"
            existing.error_message = str(exc)
            db.commit()
            db.refresh(existing)
            return existing
        raise TickTickSyncError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Pull: TickTick → Career OS
# ---------------------------------------------------------------------------


def _should_skip_task(task: dict, db: Session, profile_id: int | None) -> bool:
    """Return True if the completed TickTick task should be skipped.

    A task is skipped when it has no ID, no sync mapping exists,
    it is already completed, or it belongs to a different profile.
    """
    task_id = task.get("id", "")
    if not task_id:
        return True

    sync_task = (
        db.query(TickTickSyncTask).filter(TickTickSyncTask.ticktick_task_id == task_id).first()
    )
    if not sync_task:
        return True

    if sync_task.status == "completed":
        return True

    return profile_id is not None and sync_task.profile_id != profile_id


def _apply_task_completion(db: Session, sync_task: TickTickSyncTask, now: datetime) -> None:
    """Apply a TickTick completion to the sync task and its Career OS entity."""
    _apply_completion(db, sync_task)
    sync_task.status = "completed"
    sync_task.last_synced_at = now
    sync_task.error_message = None
    db.commit()


def sync_completions_from_ticktick(
    db: Session,
    *,
    client: TickTickClient | None = None,
    project_id: str | None = None,
    profile_id: int | None = None,
) -> dict[str, int]:
    """Poll TickTick for completed tasks and update Career OS entities.

    Returns {"synced": N, "errors": M, "skipped": S}.
    """
    if client is None or project_id is None:
        client, project_id = get_client(db)

    # Fetch completed tasks from the last 15 minutes (sync cycle)
    now = datetime.now(UTC)
    start_date = now - timedelta(days=7)  # Look back 7 days for safety

    stats = {"synced": 0, "errors": 0, "skipped": 0}

    try:
        completed_tasks = client.get_completed_tasks(
            project_id, start_date=start_date, end_date=now
        )
    except TickTickAPIError as exc:
        logger.error("Failed to fetch completed tasks from TickTick: %s", exc)
        stats["errors"] += 1
        return stats

    for task in completed_tasks:
        if _should_skip_task(task, db, profile_id):
            stats["skipped"] += 1
            continue

        task_id = task.get("id", "")
        sync_task = (
            db.query(TickTickSyncTask).filter(TickTickSyncTask.ticktick_task_id == task_id).first()
        )

        try:
            _apply_task_completion(db, sync_task, now)
            stats["synced"] += 1
        except Exception as exc:
            logger.error(
                "Failed to apply completion for sync task %d: %s",
                sync_task.id,
                exc,
            )
            sync_task.status = "error"
            sync_task.error_message = str(exc)
            db.commit()
            stats["errors"] += 1

    return stats


def _apply_completion(db: Session, sync_task: TickTickSyncTask) -> None:
    """Apply a TickTick completion to the corresponding Career OS entity."""
    now = datetime.now(UTC)

    if sync_task.entity_type == "follow_up":
        follow_up = db.query(FollowUp).filter(FollowUp.id == sync_task.entity_id).first()
        if follow_up and follow_up.completed_at is None:
            follow_up.completed_at = now
            # Log activity
            log = ActivityLog(
                profile_id=sync_task.profile_id,
                application_id=follow_up.application_id,
                action="follow_up_completed",
                details="Completed via TickTick sync",
                source="ticktick_sync",
            )
            db.add(log)

    elif sync_task.entity_type == "learning_goal":
        goal = db.query(Goal).filter(Goal.id == sync_task.entity_id).first()
        if goal and goal.status != "completed":
            goal.status = "completed"
            goal.updated_at = now

    elif sync_task.entity_type == "pipeline_action":
        # Completing a pipeline action task updates the Career OS
        # application state (marks the action as done) and logs activity.
        app_obj = db.query(Application).filter(Application.id == sync_task.entity_id).first()
        if app_obj:
            # Update application's next_step to reflect the action is done
            if app_obj.next_step:
                app_obj.next_step = f"[Done] {app_obj.next_step}"
            app_obj.updated_at = now

            log = ActivityLog(
                profile_id=sync_task.profile_id,
                application_id=app_obj.id,
                action="pipeline_action_completed",
                details=f"TickTick task completed: {sync_task.title}",
                source="ticktick_sync",
            )
            db.add(log)


# ---------------------------------------------------------------------------
# Auto-sync hooks (called from mutation flows)
# ---------------------------------------------------------------------------


def try_auto_push_follow_up(db: Session, follow_up: FollowUp) -> None:
    """Attempt to auto-push a follow-up to TickTick.

    Silently does nothing if TickTick is not configured.
    """
    try:
        sync_follow_up_to_ticktick(db, follow_up)
    except (TickTickNotConfiguredError, TickTickSyncError):
        pass  # TickTick not configured or sync failed — no-op
    except Exception:
        logger.debug("Auto-push follow-up %d to TickTick failed", follow_up.id, exc_info=True)


def try_auto_push_pipeline_action(db: Session, application: Application, action: str) -> None:
    """Attempt to auto-push a pipeline action to TickTick.

    Silently does nothing if TickTick is not configured.
    """
    try:
        sync_pipeline_action_to_ticktick(db, application, action)
    except (TickTickNotConfiguredError, TickTickSyncError):
        pass
    except Exception:
        logger.debug(
            "Auto-push pipeline action for app %d to TickTick failed",
            application.id,
            exc_info=True,
        )


def try_auto_push_learning_goal(db: Session, goal: Goal) -> None:
    """Attempt to auto-push a learning goal to TickTick.

    Silently does nothing if TickTick is not configured.
    """
    try:
        sync_learning_goal_to_ticktick(db, goal)
    except (TickTickNotConfiguredError, TickTickSyncError):
        pass
    except Exception:
        logger.debug("Auto-push goal %d to TickTick failed", goal.id, exc_info=True)


# ---------------------------------------------------------------------------
# Sync status & management
# ---------------------------------------------------------------------------


def get_sync_status(db: Session, *, profile_id: int) -> dict:
    """Get overall TickTick sync status for a profile.

    Excludes tasks linked to archived applications (VAL-CROSS-019).
    """
    all_tasks = (
        db.query(TickTickSyncTask)
        .outerjoin(
            Application,
            (TickTickSyncTask.entity_type == "application")
            & (TickTickSyncTask.entity_id == Application.id),
        )
        .filter(
            TickTickSyncTask.profile_id == profile_id,
            # Exclude tasks for archived applications;
            # keep non-application entities (follow_ups, goals) and
            # application tasks where the app is not archived.
            db_or(
                TickTickSyncTask.entity_type != "application",
                Application.archived_at.is_(None),
            ),
        )
        .all()
    )

    total = len(all_tasks)
    synced = sum(1 for t in all_tasks if t.status == "synced")
    completed = sum(1 for t in all_tasks if t.status == "completed")
    errors = sum(1 for t in all_tasks if t.status == "error")

    last_sync = max(
        (t.last_synced_at for t in all_tasks if t.last_synced_at),
        default=None,
    )

    return {
        "total_tasks": total,
        "synced": synced,
        "completed": completed,
        "errors": errors,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
        "tasks": [
            {
                "id": t.id,
                "entity_type": t.entity_type,
                "entity_id": t.entity_id,
                "ticktick_task_id": t.ticktick_task_id,
                "title": t.title,
                "status": t.status,
                "last_synced_at": t.last_synced_at.isoformat() if t.last_synced_at else None,
                "error_message": t.error_message,
            }
            for t in all_tasks
        ],
    }


def check_ticktick_connection(db: Session) -> tuple[bool, str]:
    """Test the TickTick API connection using stored credentials.

    Returns (success, message).
    """
    try:
        client, project_id = get_client(db)
    except TickTickNotConfiguredError as exc:
        return False, str(exc)

    try:
        ok = client.test_connection()
        if ok:
            # Update integration status
            row = db.query(IntegrationConfig).filter(IntegrationConfig.name == "ticktick").first()
            if row:
                row.status = "connected"
                row.status_message = "TickTick API connection successful"
                row.last_tested_at = datetime.now(UTC)
                db.commit()
            return True, "TickTick API connection successful"
        return False, "TickTick API connection failed"
    except TickTickAPIError as exc:
        return False, f"TickTick API error: {exc}"
