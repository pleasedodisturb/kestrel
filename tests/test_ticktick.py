"""Tests for TickTick bidirectional sync.

Covers:
- VAL-TICKTICK-001: Pipeline action creates TickTick task
- VAL-TICKTICK-002: TickTick completion syncs back
- VAL-TICKTICK-003: Follow-ups as TickTick tasks with due dates
- VAL-TICKTICK-004: Learning goals synced with learning tag
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.integrations import IntegrationConfig
from career_os.models.models import ActivityLog, Application, FollowUp, Profile
from career_os.models.skills import Goal
from career_os.models.ticktick_sync import TickTickSyncTask
from career_os.services.ticktick_client import (
    TickTickAPIError,
    TickTickClient,
)
from career_os.services.ticktick_sync import (
    TickTickSyncError,
    check_ticktick_connection,
    get_sync_status,
    sync_completions_from_ticktick,
    sync_follow_up_to_ticktick,
    sync_learning_goal_to_ticktick,
    sync_pipeline_action_to_ticktick,
)
from tests.profile_data import DEFAULT_PROFILE_KWARGS, SECOND_PROFILE_KWARGS

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def profile(db_session) -> Profile:
    """Create a test profile."""
    p = Profile(**DEFAULT_PROFILE_KWARGS)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def profile_b(db_session) -> Profile:
    """Create a second test profile for isolation tests."""
    p = Profile(**SECOND_PROFILE_KWARGS)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def application(db_session, profile) -> Application:
    """Create a test application."""
    app_obj = Application(
        profile_id=profile.id,
        company="Acme Corp",
        role="Senior Engineer",
        status="applied",
        fit_score=8.5,
        url="https://acme.com/jobs/1",
    )
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


@pytest.fixture()
def follow_up(db_session, profile, application) -> FollowUp:
    """Create a test follow-up."""
    fu = FollowUp(
        profile_id=profile.id,
        application_id=application.id,
        due_date=datetime.now(UTC) + timedelta(days=3),
        follow_up_type="email",
        notes="Check on application status",
    )
    db_session.add(fu)
    db_session.commit()
    db_session.refresh(fu)
    return fu


@pytest.fixture()
def learning_goal(db_session, profile) -> Goal:
    """Create a test learning goal."""
    g = Goal(
        profile_id=profile.id,
        title="Learn Kubernetes",
        goal_type="realistic",
        target_date=datetime.now(UTC) + timedelta(days=30),
        status="active",
        description="Master K8s for cloud-native roles",
    )
    db_session.add(g)
    db_session.commit()
    db_session.refresh(g)
    return g


@pytest.fixture()
def ticktick_config(db_session) -> IntegrationConfig:
    """Create a configured and enabled TickTick integration."""
    config = IntegrationConfig(
        name="ticktick",
        display_name="TickTick",
        enabled=True,
        credentials=json.dumps(
            {
                "api_token": "test-token-123",
                "project_id": "test-project-id",
            }
        ),
        status="connected",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture()
def mock_ticktick_client():
    """Create a mock TickTick client."""
    mock_client = MagicMock(spec=TickTickClient)
    mock_client.create_task.return_value = {
        "id": "ticktick-task-123",
        "projectId": "test-project-id",
        "title": "Test Task",
        "status": 0,
    }
    mock_client.update_task.return_value = {
        "id": "ticktick-task-123",
        "projectId": "test-project-id",
        "title": "Updated Task",
        "status": 0,
    }
    mock_client.get_completed_tasks.return_value = []
    mock_client.test_connection.return_value = True
    return mock_client


# ---------------------------------------------------------------------------
# VAL-TICKTICK-001: Pipeline action creates TickTick task
# ---------------------------------------------------------------------------


class TestPipelineActionSync:
    """Pipeline actions create TickTick tasks within 60s."""

    def test_pipeline_action_creates_ticktick_task(
        self, db_session, profile, application, ticktick_config, mock_ticktick_client
    ):
        """Creating a pipeline action syncs to TickTick with matching details."""
        sync_task = sync_pipeline_action_to_ticktick(
            db_session,
            application,
            "Applied to position",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert sync_task.entity_type == "pipeline_action"
        assert sync_task.entity_id == application.id
        assert sync_task.ticktick_task_id == "ticktick-task-123"
        assert sync_task.status == "synced"
        assert "Acme Corp" in sync_task.title
        assert "Senior Engineer" in sync_task.title

        # Verify the client was called with correct params
        mock_ticktick_client.create_task.assert_called_once()
        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["project_id"] == "test-project-id"
        assert "Acme Corp" in call_kwargs.kwargs["title"]

    def test_pipeline_action_high_score_gets_high_priority(
        self, db_session, profile, application, ticktick_config, mock_ticktick_client
    ):
        """Application with score >= 8.0 gets high priority."""
        application.fit_score = 9.0
        db_session.commit()

        sync_pipeline_action_to_ticktick(
            db_session,
            application,
            "High-priority application",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["priority"] == "high"

    def test_pipeline_action_medium_score_gets_medium_priority(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Application with score 6-8 gets medium priority."""
        app_obj = Application(
            profile_id=profile.id,
            company="MedCo",
            role="Engineer",
            status="discovered",
            fit_score=7.0,
        )
        db_session.add(app_obj)
        db_session.commit()

        sync_pipeline_action_to_ticktick(
            db_session,
            app_obj,
            "Discovered",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["priority"] == "medium"

    def test_pipeline_action_updates_existing_sync(
        self, db_session, profile, application, ticktick_config, mock_ticktick_client
    ):
        """Subsequent sync updates existing task instead of creating new."""
        # First sync
        sync_pipeline_action_to_ticktick(
            db_session,
            application,
            "Applied",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        # Second sync (should update)
        sync_pipeline_action_to_ticktick(
            db_session,
            application,
            "Status changed",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        # Should have one create and one update
        assert mock_ticktick_client.create_task.call_count == 1
        assert mock_ticktick_client.update_task.call_count == 1

        # Only one sync task in DB
        count = (
            db_session.query(TickTickSyncTask)
            .filter(
                TickTickSyncTask.entity_type == "pipeline_action",
                TickTickSyncTask.entity_id == application.id,
            )
            .count()
        )
        assert count == 1

    def test_pipeline_action_api_error_records_error(
        self, db_session, profile, application, ticktick_config, mock_ticktick_client
    ):
        """API failure on first sync raises TickTickSyncError."""
        mock_ticktick_client.create_task.side_effect = TickTickAPIError("Server error", 500)

        with pytest.raises(TickTickSyncError):
            sync_pipeline_action_to_ticktick(
                db_session,
                application,
                "Action",
                client=mock_ticktick_client,
                project_id="test-project-id",
            )


# ---------------------------------------------------------------------------
# VAL-TICKTICK-002: TickTick completion syncs back
# ---------------------------------------------------------------------------


class TestCompletionSync:
    """TickTick task completion updates Career OS action status."""

    def test_follow_up_completion_syncs_back(
        self, db_session, profile, application, follow_up, ticktick_config, mock_ticktick_client
    ):
        """Completing a follow-up task in TickTick marks it complete in Career OS."""
        # Create sync mapping
        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="follow_up",
            entity_id=follow_up.id,
            ticktick_task_id="tt-fu-123",
            ticktick_project_id="test-project-id",
            title="Follow-up task",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        # Mock completed tasks from TickTick
        mock_ticktick_client.get_completed_tasks.return_value = [
            {"id": "tt-fu-123", "status": 2, "completedTime": "2026-03-14T10:00:00+0000"}
        ]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["synced"] == 1
        assert stats["errors"] == 0

        # Verify follow-up is completed
        db_session.refresh(follow_up)
        assert follow_up.completed_at is not None

        # Verify sync task status updated
        db_session.refresh(sync_task)
        assert sync_task.status == "completed"

    def test_learning_goal_completion_syncs_back(
        self, db_session, profile, learning_goal, ticktick_config, mock_ticktick_client
    ):
        """Completing a learning goal task in TickTick marks it complete in Career OS."""
        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="learning_goal",
            entity_id=learning_goal.id,
            ticktick_task_id="tt-lg-456",
            ticktick_project_id="test-project-id",
            title="Learning goal task",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        mock_ticktick_client.get_completed_tasks.return_value = [{"id": "tt-lg-456", "status": 2}]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["synced"] == 1

        db_session.refresh(learning_goal)
        assert learning_goal.status == "completed"

    def test_pipeline_action_completion_creates_activity_log(
        self, db_session, profile, application, ticktick_config, mock_ticktick_client
    ):
        """Completing a pipeline action task creates activity log entry."""
        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="pipeline_action",
            entity_id=application.id,
            ticktick_task_id="tt-pa-789",
            ticktick_project_id="test-project-id",
            title="Pipeline action task",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        mock_ticktick_client.get_completed_tasks.return_value = [{"id": "tt-pa-789", "status": 2}]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["synced"] == 1

        # Check activity log
        log = (
            db_session.query(ActivityLog)
            .filter(
                ActivityLog.application_id == application.id,
                ActivityLog.source == "ticktick_sync",
            )
            .first()
        )
        assert log is not None
        assert "ticktick" in log.source.lower()

    def test_already_completed_tasks_skipped(
        self, db_session, profile, follow_up, ticktick_config, mock_ticktick_client
    ):
        """Already-completed sync tasks are skipped."""
        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="follow_up",
            entity_id=follow_up.id,
            ticktick_task_id="tt-done-123",
            ticktick_project_id="test-project-id",
            title="Already done",
            status="completed",
        )
        db_session.add(sync_task)
        db_session.commit()

        mock_ticktick_client.get_completed_tasks.return_value = [{"id": "tt-done-123", "status": 2}]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["skipped"] == 1
        assert stats["synced"] == 0

    def test_unknown_ticktick_tasks_skipped(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Tasks with no sync mapping are skipped."""
        mock_ticktick_client.get_completed_tasks.return_value = [
            {"id": "unknown-task-id", "status": 2}
        ]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["skipped"] == 1
        assert stats["synced"] == 0

    def test_completion_api_error_counted(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """API error during fetch is counted as error."""
        mock_ticktick_client.get_completed_tasks.side_effect = TickTickAPIError("Timeout")

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["errors"] == 1

    def test_completion_respects_profile_filter(
        self, db_session, profile, profile_b, follow_up, ticktick_config, mock_ticktick_client
    ):
        """Profile filter prevents cross-profile completion sync."""
        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="follow_up",
            entity_id=follow_up.id,
            ticktick_task_id="tt-profile-a",
            ticktick_project_id="test-project-id",
            title="Profile A task",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        mock_ticktick_client.get_completed_tasks.return_value = [
            {"id": "tt-profile-a", "status": 2}
        ]

        # Sync with profile_b filter — should skip profile_a's task
        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
            profile_id=profile_b.id,
        )

        assert stats["skipped"] == 1
        assert stats["synced"] == 0


# ---------------------------------------------------------------------------
# VAL-TICKTICK-003: Follow-ups as TickTick tasks with due dates
# ---------------------------------------------------------------------------


class TestFollowUpSync:
    """Follow-up reminders create TickTick tasks with correct due date."""

    def test_follow_up_creates_ticktick_task_with_due_date(
        self, db_session, profile, application, follow_up, ticktick_config, mock_ticktick_client
    ):
        """Follow-up creates TickTick task with matching due date."""
        sync_task = sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert sync_task.entity_type == "follow_up"
        assert sync_task.entity_id == follow_up.id
        assert sync_task.status == "synced"
        assert "Follow-up" in sync_task.title
        assert "Acme Corp" in sync_task.title

        # Verify due_date was passed to client
        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["due_date"] == follow_up.due_date
        assert call_kwargs.kwargs["priority"] == "medium"

    def test_follow_up_includes_application_context(
        self, db_session, profile, application, follow_up, ticktick_config, mock_ticktick_client
    ):
        """Follow-up task title includes company and role."""
        sync_task = sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert "Acme Corp" in sync_task.title
        assert "email" in sync_task.title.lower()

    def test_follow_up_updates_existing_task(
        self, db_session, profile, application, follow_up, ticktick_config, mock_ticktick_client
    ):
        """Re-syncing a follow-up updates the existing TickTick task."""
        # First sync
        sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        # Update follow-up notes
        follow_up.notes = "Updated notes"
        db_session.commit()

        # Second sync (update)
        sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert mock_ticktick_client.create_task.call_count == 1
        assert mock_ticktick_client.update_task.call_count == 1

    def test_follow_up_api_error_on_first_sync_raises(
        self, db_session, profile, application, follow_up, ticktick_config, mock_ticktick_client
    ):
        """API error on first follow-up sync raises TickTickSyncError."""
        mock_ticktick_client.create_task.side_effect = TickTickAPIError("Failed", 500)

        with pytest.raises(TickTickSyncError):
            sync_follow_up_to_ticktick(
                db_session,
                follow_up,
                client=mock_ticktick_client,
                project_id="test-project-id",
            )

    def test_follow_up_api_error_on_update_records_error(
        self, db_session, profile, application, follow_up, ticktick_config, mock_ticktick_client
    ):
        """API error on update sets sync task status to error."""
        # First sync succeeds
        sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        # Update fails
        mock_ticktick_client.update_task.side_effect = TickTickAPIError("Timeout", 504)

        result = sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert result.status == "error"
        assert result.error_message is not None


# ---------------------------------------------------------------------------
# VAL-TICKTICK-004: Learning goals synced with learning tag
# ---------------------------------------------------------------------------


class TestLearningGoalSync:
    """Learning goals appear as TickTick tasks with learning tag."""

    def test_learning_goal_creates_task_with_learning_tag(
        self, db_session, profile, learning_goal, ticktick_config, mock_ticktick_client
    ):
        """Learning goal creates TickTick task with 'learning' tag."""
        sync_task = sync_learning_goal_to_ticktick(
            db_session,
            learning_goal,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert sync_task.entity_type == "learning_goal"
        assert sync_task.entity_id == learning_goal.id
        assert sync_task.status == "synced"
        assert "Learning" in sync_task.title
        assert "Kubernetes" in sync_task.title

        # Verify learning tag
        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["tags"] == ["learning"]
        assert call_kwargs.kwargs["due_date"] == learning_goal.target_date

    def test_learning_goal_includes_target_date(
        self, db_session, profile, learning_goal, ticktick_config, mock_ticktick_client
    ):
        """Learning goal task has the target date as due date."""
        sync_learning_goal_to_ticktick(
            db_session,
            learning_goal,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["due_date"] == learning_goal.target_date

    def test_learning_goal_updates_existing(
        self, db_session, profile, learning_goal, ticktick_config, mock_ticktick_client
    ):
        """Re-syncing learning goal updates existing task."""
        sync_learning_goal_to_ticktick(
            db_session,
            learning_goal,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        learning_goal.title = "Updated: Learn Advanced K8s"
        db_session.commit()

        sync_learning_goal_to_ticktick(
            db_session,
            learning_goal,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert mock_ticktick_client.create_task.call_count == 1
        assert mock_ticktick_client.update_task.call_count == 1

        # Verify learning tag still present on update
        update_kwargs = mock_ticktick_client.update_task.call_args
        assert update_kwargs.kwargs["tags"] == ["learning"]


# ---------------------------------------------------------------------------
# Sync status
# ---------------------------------------------------------------------------


class TestSyncStatus:
    """Test sync status reporting."""

    def test_empty_sync_status(self, db_session, profile):
        """No sync tasks returns zeroed status."""
        status = get_sync_status(db_session, profile_id=profile.id)
        assert status["total_tasks"] == 0
        assert status["synced"] == 0
        assert status["completed"] == 0
        assert status["errors"] == 0
        assert status["last_sync_at"] is None

    def test_sync_status_counts(self, db_session, profile):
        """Status correctly counts by type."""
        for i, status in enumerate(["synced", "completed", "error"]):
            task = TickTickSyncTask(
                profile_id=profile.id,
                entity_type="follow_up",
                entity_id=i + 1,
                ticktick_task_id=f"tt-{i}",
                ticktick_project_id="proj",
                title=f"Task {i}",
                status=status,
            )
            db_session.add(task)
        db_session.commit()

        result = get_sync_status(db_session, profile_id=profile.id)
        assert result["total_tasks"] == 3
        assert result["synced"] == 1
        assert result["completed"] == 1
        assert result["errors"] == 1

    def test_sync_status_profile_isolated(self, db_session, profile, profile_b):
        """Sync status is profile-scoped."""
        task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="follow_up",
            entity_id=1,
            ticktick_task_id="tt-a",
            ticktick_project_id="proj",
            title="Profile A task",
            status="synced",
        )
        db_session.add(task)
        db_session.commit()

        status_a = get_sync_status(db_session, profile_id=profile.id)
        status_b = get_sync_status(db_session, profile_id=profile_b.id)

        assert status_a["total_tasks"] == 1
        assert status_b["total_tasks"] == 0


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------


class TestConnectionTest:
    """Test TickTick connection testing."""

    def test_not_configured_returns_false(self, db_session):
        """Not configured integration returns failure."""
        success, msg = check_ticktick_connection(db_session)
        assert success is False
        assert "not enabled" in msg.lower() or "not configured" in msg.lower()

    def test_configured_and_connected(self, db_session, ticktick_config):
        """Configured integration with mocked API returns success."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.test_connection.return_value = True

            success, msg = check_ticktick_connection(db_session)
            assert success is True
            assert "successful" in msg.lower()

    def test_configured_but_api_fails(self, db_session, ticktick_config):
        """Configured integration with API failure returns failure."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.test_connection.return_value = False

            success, _msg = check_ticktick_connection(db_session)
            assert success is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestTickTickAPI:
    """Tests for the TickTick sync API routes."""

    def test_get_sync_status_empty(self, db_session, profile):
        """GET /api/ticktick/status returns empty status."""
        resp = client.get(f"/api/ticktick/status?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 0
        assert data["tasks"] == []

    def test_push_follow_up_without_config_returns_400(self, db_session, profile, follow_up):
        """POST /api/ticktick/push without config returns 400."""
        resp = client.post(
            "/api/ticktick/push",
            json={
                "entity_type": "follow_up",
                "entity_id": follow_up.id,
                "profile_id": profile.id,
            },
        )
        assert resp.status_code == 400

    def test_push_nonexistent_entity_returns_404(self, db_session, profile, ticktick_config):
        """POST /api/ticktick/push with bad entity_id returns 404."""
        resp = client.post(
            "/api/ticktick/push",
            json={
                "entity_type": "follow_up",
                "entity_id": 99999,
                "profile_id": profile.id,
            },
        )
        assert resp.status_code == 404

    def test_push_invalid_entity_type_returns_422(self, db_session, profile, ticktick_config):
        """POST /api/ticktick/push with invalid entity_type returns 422."""
        resp = client.post(
            "/api/ticktick/push",
            json={
                "entity_type": "invalid_type",
                "entity_id": 1,
                "profile_id": profile.id,
            },
        )
        assert resp.status_code == 422

    def test_push_follow_up_success(
        self, db_session, profile, application, follow_up, ticktick_config
    ):
        """POST /api/ticktick/push successfully syncs follow-up."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.create_task.return_value = {
                "id": "tt-api-test",
                "projectId": "test-project-id",
                "title": "Test",
                "status": 0,
            }

            resp = client.post(
                "/api/ticktick/push",
                json={
                    "entity_type": "follow_up",
                    "entity_id": follow_up.id,
                    "profile_id": profile.id,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["sync_task"]["entity_type"] == "follow_up"

    def test_push_learning_goal_success(self, db_session, profile, learning_goal, ticktick_config):
        """POST /api/ticktick/push successfully syncs learning goal."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.create_task.return_value = {
                "id": "tt-lg-api",
                "projectId": "test-project-id",
                "title": "Learning",
                "status": 0,
            }

            resp = client.post(
                "/api/ticktick/push",
                json={
                    "entity_type": "learning_goal",
                    "entity_id": learning_goal.id,
                    "profile_id": profile.id,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["sync_task"]["entity_type"] == "learning_goal"

    def test_push_pipeline_action_success(self, db_session, profile, application, ticktick_config):
        """POST /api/ticktick/push successfully syncs pipeline action."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.create_task.return_value = {
                "id": "tt-pa-api",
                "projectId": "test-project-id",
                "title": "Pipeline",
                "status": 0,
            }

            resp = client.post(
                "/api/ticktick/push",
                json={
                    "entity_type": "pipeline_action",
                    "entity_id": application.id,
                    "profile_id": profile.id,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_pull_without_config_returns_400(self, db_session, profile):
        """POST /api/ticktick/pull without config returns 400."""
        resp = client.post(f"/api/ticktick/pull?profile_id={profile.id}")
        assert resp.status_code == 400

    def test_pull_success(self, db_session, profile, ticktick_config):
        """POST /api/ticktick/pull returns sync results."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.get_completed_tasks.return_value = []

            resp = client.post(f"/api/ticktick/pull?profile_id={profile.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["synced"] == 0

    def test_test_connection_endpoint(self, db_session, ticktick_config):
        """POST /api/ticktick/test returns connection status."""
        with patch("career_os.services.ticktick_sync.TickTickClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.test_connection.return_value = True

            resp = client.post("/api/ticktick/test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["tested_at"] is not None


# ---------------------------------------------------------------------------
# TickTick client unit tests
# ---------------------------------------------------------------------------


class TestTickTickClient:
    """Unit tests for the TickTick API client."""

    def test_create_task_formats_request(self):
        """Client formats create_task request correctly."""
        with patch("career_os.services.ticktick_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"id": "new-task", "title": "Test"}'
            mock_resp.json.return_value = {"id": "new-task", "title": "Test"}
            mock_req.return_value = mock_resp

            tt_client = TickTickClient("test-token")
            result = tt_client.create_task(
                title="Test Task",
                project_id="proj-123",
                content="Description",
                priority="high",
            )

            assert result["id"] == "new-task"
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            assert call_args.kwargs["json"]["title"] == "Test Task"
            assert call_args.kwargs["json"]["projectId"] == "proj-123"
            assert call_args.kwargs["json"]["priority"] == 5  # high = 5

    def test_create_task_with_due_date(self):
        """Client formats due date correctly."""
        with patch("career_os.services.ticktick_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"id": "new-task"}'
            mock_resp.json.return_value = {"id": "new-task"}
            mock_req.return_value = mock_resp

            tt_client = TickTickClient("test-token")
            due = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
            tt_client.create_task(
                title="Due Date Task",
                project_id="proj-123",
                due_date=due,
            )

            call_args = mock_req.call_args
            body = call_args.kwargs["json"]
            assert "dueDate" in body
            assert body["isAllDay"] is True
            assert body["timeZone"] == "Europe/Berlin"

    def test_create_task_with_tags(self):
        """Client passes tags correctly."""
        with patch("career_os.services.ticktick_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"id": "tagged"}'
            mock_resp.json.return_value = {"id": "tagged"}
            mock_req.return_value = mock_resp

            tt_client = TickTickClient("test-token")
            tt_client.create_task(
                title="Tagged Task",
                project_id="proj-123",
                tags=["learning", "priority"],
            )

            call_args = mock_req.call_args
            assert call_args.kwargs["json"]["tags"] == ["learning", "priority"]

    def test_unauthorized_raises_error(self):
        """401 response raises TickTickAPIError."""
        with patch("career_os.services.ticktick_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_req.return_value = mock_resp

            tt_client = TickTickClient("bad-token")
            with pytest.raises(TickTickAPIError) as exc_info:
                tt_client.create_task(title="Test", project_id="proj")
            assert exc_info.value.status_code == 401

    def test_test_connection_success(self):
        """test_connection returns True on successful project list."""
        with patch("career_os.services.ticktick_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '[{"id": "proj1"}]'
            mock_resp.json.return_value = [{"id": "proj1"}]
            mock_req.return_value = mock_resp

            tt_client = TickTickClient("good-token")
            assert tt_client.test_connection() is True

    def test_test_connection_failure(self):
        """test_connection returns False on API error."""
        with patch("career_os.services.ticktick_client.httpx.request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_req.return_value = mock_resp

            tt_client = TickTickClient("bad-token")
            assert tt_client.test_connection() is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case scenarios for TickTick sync."""

    def test_sync_with_no_notes_follow_up(
        self, db_session, profile, application, ticktick_config, mock_ticktick_client
    ):
        """Follow-up without notes still syncs correctly."""
        fu = FollowUp(
            profile_id=profile.id,
            application_id=application.id,
            due_date=datetime.now(UTC) + timedelta(days=1),
            follow_up_type="phone",
            notes=None,
        )
        db_session.add(fu)
        db_session.commit()
        db_session.refresh(fu)

        sync_task = sync_follow_up_to_ticktick(
            db_session,
            fu,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )
        assert sync_task.status == "synced"

    def test_sync_goal_without_target_date(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Learning goal without target_date syncs (no due date)."""
        g = Goal(
            profile_id=profile.id,
            title="Open-ended learning",
            goal_type="aspirational",
            target_date=None,
            status="active",
        )
        db_session.add(g)
        db_session.commit()
        db_session.refresh(g)

        sync_task = sync_learning_goal_to_ticktick(
            db_session,
            g,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )
        assert sync_task.status == "synced"

    def test_sync_application_without_score(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Application without fit_score gets 'none' priority."""
        app_obj = Application(
            profile_id=profile.id,
            company="NoScore Inc",
            role="Developer",
            status="discovered",
            fit_score=None,
        )
        db_session.add(app_obj)
        db_session.commit()
        db_session.refresh(app_obj)

        sync_pipeline_action_to_ticktick(
            db_session,
            app_obj,
            "Discovered",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        call_kwargs = mock_ticktick_client.create_task.call_args
        assert call_kwargs.kwargs["priority"] == "none"

    def test_multiple_sync_tasks_for_different_entities(
        self,
        db_session,
        profile,
        application,
        follow_up,
        learning_goal,
        ticktick_config,
        mock_ticktick_client,
    ):
        """Different entity types can all be synced independently."""
        # Sync all three
        task_ids = ["tt-fu-1", "tt-lg-1", "tt-pa-1"]
        mock_ticktick_client.create_task.side_effect = [
            {"id": tid, "projectId": "proj", "title": "T", "status": 0} for tid in task_ids
        ]

        sync_follow_up_to_ticktick(
            db_session,
            follow_up,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )
        sync_learning_goal_to_ticktick(
            db_session,
            learning_goal,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )
        sync_pipeline_action_to_ticktick(
            db_session,
            application,
            "Test",
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        all_tasks = db_session.query(TickTickSyncTask).all()
        assert len(all_tasks) == 3
        types = {t.entity_type for t in all_tasks}
        assert types == {"follow_up", "learning_goal", "pipeline_action"}


# ---------------------------------------------------------------------------
# Pipeline task completion updates Career OS application state
# ---------------------------------------------------------------------------


class TestPipelineCompletionUpdatesState:
    """Pipeline action completion via TickTick updates application state."""

    def test_pipeline_completion_updates_application_next_step(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Completing a pipeline action task marks next_step with [Done] prefix."""
        app_obj = Application(
            profile_id=profile.id,
            company="StateTest Inc",
            role="PM",
            status="applied",
            next_step="Send follow-up email",
        )
        db_session.add(app_obj)
        db_session.commit()
        db_session.refresh(app_obj)

        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="pipeline_action",
            entity_id=app_obj.id,
            ticktick_task_id="tt-state-1",
            ticktick_project_id="test-project-id",
            title="Pipeline task",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        mock_ticktick_client.get_completed_tasks.return_value = [{"id": "tt-state-1", "status": 2}]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["synced"] == 1

        db_session.refresh(app_obj)
        assert app_obj.next_step.startswith("[Done]")
        assert "Send follow-up email" in app_obj.next_step
        assert app_obj.updated_at is not None

    def test_pipeline_completion_without_next_step(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Completing a pipeline action task works when next_step is None."""
        app_obj = Application(
            profile_id=profile.id,
            company="NoStep Inc",
            role="Dev",
            status="applied",
            next_step=None,
        )
        db_session.add(app_obj)
        db_session.commit()
        db_session.refresh(app_obj)

        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="pipeline_action",
            entity_id=app_obj.id,
            ticktick_task_id="tt-state-2",
            ticktick_project_id="test-project-id",
            title="Pipeline task",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        mock_ticktick_client.get_completed_tasks.return_value = [{"id": "tt-state-2", "status": 2}]

        stats = sync_completions_from_ticktick(
            db_session,
            client=mock_ticktick_client,
            project_id="test-project-id",
        )

        assert stats["synced"] == 1

        # Check that activity log was created
        log = (
            db_session.query(ActivityLog)
            .filter(
                ActivityLog.application_id == app_obj.id,
                ActivityLog.source == "ticktick_sync",
            )
            .first()
        )
        assert log is not None


# ---------------------------------------------------------------------------
# Goal create/update auto-pushes to TickTick
# ---------------------------------------------------------------------------


class TestGoalAutoPush:
    """Goal create/update auto-pushes to TickTick when configured."""

    def test_create_goal_auto_pushes_to_ticktick(
        self, db_session, profile, ticktick_config, mock_ticktick_client
    ):
        """Creating a goal via service auto-pushes to TickTick."""
        from career_os.services.goals import create_goal

        with patch(
            "career_os.services.ticktick_sync.get_client",
            return_value=(mock_ticktick_client, "test-project-id"),
        ):
            goal = create_goal(
                db_session,
                profile.id,
                {
                    "title": "Learn Docker",
                    "goal_type": "realistic",
                    "target_date": datetime.now(UTC) + timedelta(days=30),
                    "status": "active",
                },
            )

        assert goal.id is not None
        # The auto-push should have attempted to create a TickTick task
        mock_ticktick_client.create_task.assert_called_once()
        call_kwargs = mock_ticktick_client.create_task.call_args
        assert "Learn Docker" in call_kwargs.kwargs["title"]

    def test_update_goal_auto_pushes_to_ticktick(
        self, db_session, profile, learning_goal, ticktick_config, mock_ticktick_client
    ):
        """Updating a goal via service auto-pushes to TickTick."""
        from career_os.services.goals import update_goal

        # First create the sync mapping (as if it was previously pushed)
        sync_task = TickTickSyncTask(
            profile_id=profile.id,
            entity_type="learning_goal",
            entity_id=learning_goal.id,
            ticktick_task_id="tt-update-goal",
            ticktick_project_id="test-project-id",
            title="Old title",
            status="synced",
        )
        db_session.add(sync_task)
        db_session.commit()

        with patch(
            "career_os.services.ticktick_sync.get_client",
            return_value=(mock_ticktick_client, "test-project-id"),
        ):
            updated = update_goal(
                db_session,
                learning_goal.id,
                profile.id,
                {"title": "Learn Kubernetes Advanced"},
            )

        assert updated.title == "Learn Kubernetes Advanced"
        mock_ticktick_client.update_task.assert_called_once()

    def test_create_goal_without_ticktick_config_succeeds(self, db_session, profile):
        """Creating a goal without TickTick config still works (no error)."""
        from career_os.services.goals import create_goal

        goal = create_goal(
            db_session,
            profile.id,
            {
                "title": "Standalone Goal",
                "goal_type": "realistic",
                "status": "active",
            },
        )
        assert goal.id is not None
        assert goal.title == "Standalone Goal"


# ---------------------------------------------------------------------------
# TickTick scheduler
# ---------------------------------------------------------------------------


class TestTickTickScheduler:
    """Background TickTick sync scheduler tests."""

    def test_start_and_stop_scheduler(self):
        """Scheduler starts and stops without errors."""
        import asyncio

        from career_os.services.ticktick_scheduler import (
            start_ticktick_scheduler,
            stop_ticktick_scheduler,
        )

        async def _test():
            task = start_ticktick_scheduler(interval_seconds=3600)
            assert not task.done()
            stop_ticktick_scheduler()
            # Give it a moment to cancel
            await asyncio.sleep(0.1)
            assert task.done()

        asyncio.run(_test())
