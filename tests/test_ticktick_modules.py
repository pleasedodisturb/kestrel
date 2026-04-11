"""Unit tests for the three TickTick service modules.

Per the test-coverage gap issue, this file consolidates dedicated tests for:

- `services.ticktick_client` — synchronous TickTick Open API HTTP client
- `services.ticktick_scheduler` — asyncio-driven sync loop
- `services.ticktick_sync` — credentials helper edge cases (complementary
  to `test_ticktick.py`, which already covers the high-level sync flows)

The client tests patch `httpx.request` and assert URL, headers, and body
shape. The scheduler tests use `pytest-asyncio` and mock the database +
sync function so we don't poke real config rows.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.integrations import IntegrationConfig
from career_os.models.models import Profile
from career_os.services import ticktick_scheduler as scheduler_mod
from career_os.services.ticktick_client import (
    PRIORITY_MAP,
    STATUS_COMPLETED,
    TickTickAPIError,
    TickTickClient,
    _format_ticktick_date,
)
from career_os.services.ticktick_scheduler import (
    _sync_single_profile,
    start_ticktick_scheduler,
    stop_ticktick_scheduler,
)
from career_os.services.ticktick_sync import (
    TickTickNotConfiguredError,
    _get_ticktick_credentials,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 200, payload=None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or (json.dumps(payload) if payload is not None else "")
    resp.json.return_value = payload if payload is not None else {}
    return resp


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    yield session
    session.close()
    connection.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# TickTickClient — _format_ticktick_date
# ---------------------------------------------------------------------------


def test_format_ticktick_date_format():
    dt = datetime(2026, 4, 11, 9, 30, 0)
    out = _format_ticktick_date(dt)
    # yyyy-MM-dd'T'HH:mm:ss+0000
    assert out == "2026-04-11T09:30:00+0000"


# ---------------------------------------------------------------------------
# TickTickClient — create_task
# ---------------------------------------------------------------------------


def test_client_create_task_sends_expected_body():
    client = TickTickClient("token-abc")
    payload = {"id": "task-1", "title": "Hello", "projectId": "p1"}

    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, payload),
    ) as req:
        result = client.create_task(
            title="Hello",
            project_id="p1",
            content="body",
            priority="high",
            tags=["work"],
            due_date=datetime(2026, 5, 1, 12, 0, 0),
        )

    assert result == payload
    assert req.call_count == 1
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/task")
    body = kwargs["json"]
    assert body["title"] == "Hello"
    assert body["projectId"] == "p1"
    assert body["priority"] == PRIORITY_MAP["high"]
    assert body["content"] == "body"
    assert body["tags"] == ["work"]
    assert body["isAllDay"] is True
    assert body["dueDate"] == "2026-05-01T12:00:00+0000"
    assert kwargs["headers"]["Authorization"] == "Bearer token-abc"


def test_client_create_task_minimal_body_omits_optional_fields():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, {"id": "x"}),
    ) as req:
        client.create_task(title="t", project_id="p")

    body = req.call_args.kwargs["json"]
    assert "content" not in body
    assert "tags" not in body
    assert "dueDate" not in body
    assert body["priority"] == 0  # 'none' default


# ---------------------------------------------------------------------------
# TickTickClient — error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "snippet"),
    [
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (404, "Not found"),
        (500, "TickTick API error 500"),
    ],
)
def test_client_request_raises_on_http_errors(status_code, snippet):
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(status_code, text="server boom"),
    ):
        with pytest.raises(TickTickAPIError) as exc_info:
            client.create_task(title="x", project_id="p")
    assert snippet in str(exc_info.value)
    assert exc_info.value.status_code == status_code


def test_client_request_wraps_httpx_connect_errors():
    """A network-level httpx error is wrapped in TickTickAPIError."""
    import httpx

    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        side_effect=httpx.ConnectError("boom"),
    ):
        with pytest.raises(TickTickAPIError) as exc_info:
            client.create_task(title="x", project_id="p")
    assert "HTTP error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TickTickClient — other endpoints
# ---------------------------------------------------------------------------


def test_client_complete_task_returns_none_on_empty_body():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, text=""),
    ) as req:
        result = client.complete_task("p1", "t1")
    assert result is None
    assert req.call_args.args[1].endswith("/project/p1/task/t1/complete")


def test_client_get_project_tasks_unwraps_tasks_field():
    client = TickTickClient("tkn")
    payload = {"id": "p1", "name": "Proj", "tasks": [{"id": "t1"}, {"id": "t2"}]}
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, payload),
    ):
        tasks = client.get_project_tasks("p1")
    assert [t["id"] for t in tasks] == ["t1", "t2"]


def test_client_get_completed_tasks_returns_list():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, [{"id": "a"}, {"id": "b"}]),
    ):
        out = client.get_completed_tasks(
            "p1",
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 30),
        )
    assert [t["id"] for t in out] == ["a", "b"]


def test_client_test_connection_swallows_errors_and_returns_false():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(401, text="nope"),
    ):
        assert client.test_connection() is False


def test_client_test_connection_returns_true_on_list_payload():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, [{"id": "p1"}]),
    ):
        assert client.test_connection() is True


def test_client_update_task_sends_status_and_priority():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, {"id": "t1"}),
    ) as req:
        client.update_task(
            "t1",
            "p1",
            title="new",
            priority="medium",
            status=STATUS_COMPLETED,
            tags=["done"],
        )
    body = req.call_args.kwargs["json"]
    assert body["status"] == STATUS_COMPLETED
    assert body["priority"] == PRIORITY_MAP["medium"]
    assert body["title"] == "new"
    assert body["tags"] == ["done"]


def test_client_delete_task_calls_delete_endpoint():
    client = TickTickClient("tkn")
    with patch(
        "career_os.services.ticktick_client.httpx.request",
        return_value=_mock_response(200, text=""),
    ) as req:
        client.delete_task("p1", "t1")
    assert req.call_args.args[0] == "DELETE"
    assert req.call_args.args[1].endswith("/project/p1/task/t1")


# ---------------------------------------------------------------------------
# ticktick_sync — credentials helper edge cases
# ---------------------------------------------------------------------------


def test_get_credentials_raises_when_row_missing(db: Session):
    with pytest.raises(TickTickNotConfiguredError):
        _get_ticktick_credentials(db)


def test_get_credentials_raises_when_disabled(db: Session):
    db.add(
        IntegrationConfig(
            name="ticktick",
            display_name="TickTick",
            enabled=False,
            credentials=json.dumps({"api_token": "t", "project_id": "p"}),
        )
    )
    db.commit()
    with pytest.raises(TickTickNotConfiguredError):
        _get_ticktick_credentials(db)


def test_get_credentials_raises_when_token_missing(db: Session):
    db.add(
        IntegrationConfig(
            name="ticktick",
            display_name="TickTick",
            enabled=True,
            credentials=json.dumps({"project_id": "p"}),
        )
    )
    db.commit()
    with pytest.raises(TickTickNotConfiguredError):
        _get_ticktick_credentials(db)


def test_get_credentials_raises_when_project_id_missing(db: Session):
    db.add(
        IntegrationConfig(
            name="ticktick",
            display_name="TickTick",
            enabled=True,
            credentials=json.dumps({"api_token": "abc"}),
        )
    )
    db.commit()
    with pytest.raises(TickTickNotConfiguredError):
        _get_ticktick_credentials(db)


def test_get_credentials_returns_stripped_values(db: Session):
    db.add(
        IntegrationConfig(
            name="ticktick",
            display_name="TickTick",
            enabled=True,
            credentials=json.dumps({"api_token": "  abc  ", "project_id": "  p1  "}),
        )
    )
    db.commit()
    api_token, project_id = _get_ticktick_credentials(db)
    assert api_token == "abc"
    assert project_id == "p1"


# ---------------------------------------------------------------------------
# ticktick_scheduler
# ---------------------------------------------------------------------------


def test_sync_single_profile_swallows_not_configured(db: Session):
    profile = Profile(id=1, name="A", email="a@a.com")
    db.add(profile)
    db.commit()

    with patch(
        "career_os.services.ticktick_scheduler.sync_completions_from_ticktick",
        side_effect=TickTickNotConfiguredError("nope"),
    ):
        # Should not raise
        _sync_single_profile(db, profile)


def test_sync_single_profile_swallows_unexpected_exception(db: Session):
    profile = Profile(id=1, name="A", email="a@a.com")
    db.add(profile)
    db.commit()

    with patch(
        "career_os.services.ticktick_scheduler.sync_completions_from_ticktick",
        side_effect=RuntimeError("boom"),
    ):
        # Should not raise
        _sync_single_profile(db, profile)


def test_sync_single_profile_logs_stats_when_synced(db: Session, caplog):
    profile = Profile(id=1, name="A", email="a@a.com")
    db.add(profile)
    db.commit()

    with patch(
        "career_os.services.ticktick_scheduler.sync_completions_from_ticktick",
        return_value={"synced": 3, "errors": 0, "skipped": 1},
    ):
        with caplog.at_level("INFO", logger="career_os.services.ticktick_scheduler"):
            _sync_single_profile(db, profile)
    assert any("3 synced" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_start_and_stop_scheduler_creates_and_cancels_task():
    # Pass a long interval so the loop sleeps and we can cancel cleanly
    task = start_ticktick_scheduler(interval_seconds=3600)
    try:
        assert isinstance(task, asyncio.Task)
        assert scheduler_mod._ticktick_scheduler_task is task
    finally:
        stop_ticktick_scheduler()
        # Give the loop one tick to process cancellation
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1.0)
    assert scheduler_mod._ticktick_scheduler_task is None


@pytest.mark.asyncio
async def test_stop_scheduler_when_not_started_is_noop():
    # Reset module state
    scheduler_mod._ticktick_scheduler_task = None
    stop_ticktick_scheduler()  # should not raise
    assert scheduler_mod._ticktick_scheduler_task is None
