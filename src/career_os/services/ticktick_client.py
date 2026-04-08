"""TickTick Open API client.

Wraps the TickTick REST API (https://developer.ticktick.com/docs/).
All methods are synchronous (httpx) for simplicity in the sync service.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TICKTICK_API_BASE = "https://api.ticktick.com/open/v1"

# TickTick priority values: None=0, Low=1, Medium=3, High=5
PRIORITY_MAP = {
    "none": 0,
    "low": 1,
    "medium": 3,
    "high": 5,
}

# TickTick task status: Normal=0, Completed=2
STATUS_NORMAL = 0
STATUS_COMPLETED = 2


class TickTickAPIError(Exception):
    """Raised when a TickTick API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TickTickClient:
    """Synchronous client for the TickTick Open API v1."""

    def __init__(self, access_token: str, timeout: float = 30.0) -> None:
        self._token = access_token
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | list[Any] | None = None,
    ) -> Any:
        """Make an HTTP request to the TickTick API."""
        url = f"{TICKTICK_API_BASE}{path}"
        try:
            resp = httpx.request(
                method,
                url,
                headers=self._headers,
                json=json,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise TickTickAPIError(f"HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise TickTickAPIError("Unauthorized — invalid or expired token", 401)
        if resp.status_code == 403:
            raise TickTickAPIError("Forbidden — insufficient permissions", 403)
        if resp.status_code == 404:
            raise TickTickAPIError("Not found", 404)
        if resp.status_code >= 400:
            raise TickTickAPIError(
                f"TickTick API error {resp.status_code}: {resp.text}",
                resp.status_code,
            )

        # Some endpoints return empty body on success (e.g., complete/delete)
        if resp.status_code == 200 and resp.text:
            return resp.json()
        return None

    # ---- Task operations ----

    def create_task(
        self,
        *,
        title: str,
        project_id: str,
        content: str | None = None,
        due_date: datetime | None = None,
        priority: str = "none",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a task in TickTick.

        Returns the created task dict with id, projectId, title, etc.
        """
        body: dict[str, Any] = {
            "title": title,
            "projectId": project_id,
            "priority": PRIORITY_MAP.get(priority, 0),
        }
        if content:
            body["content"] = content
        if due_date:
            body["dueDate"] = _format_ticktick_date(due_date)
            body["isAllDay"] = True
            body["timeZone"] = "Europe/Berlin"
        if tags:
            body["tags"] = tags
        result = self._request("POST", "/task", json=body)
        logger.info("Created TickTick task: %s", result.get("id") if result else "unknown")
        return result or {}

    def update_task(
        self,
        task_id: str,
        project_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        due_date: datetime | None = None,
        priority: str | None = None,
        status: int | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing TickTick task."""
        body: dict[str, Any] = {
            "id": task_id,
            "projectId": project_id,
        }
        if title is not None:
            body["title"] = title
        if content is not None:
            body["content"] = content
        if due_date is not None:
            body["dueDate"] = _format_ticktick_date(due_date)
            body["isAllDay"] = True
            body["timeZone"] = "Europe/Berlin"
        if priority is not None:
            body["priority"] = PRIORITY_MAP.get(priority, 0)
        if status is not None:
            body["status"] = status
        if tags is not None:
            body["tags"] = tags
        result = self._request("POST", f"/task/{task_id}", json=body)
        return result or {}

    def complete_task(self, project_id: str, task_id: str) -> None:
        """Mark a task as completed in TickTick."""
        self._request("POST", f"/project/{project_id}/task/{task_id}/complete")

    def get_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        """Get a single task by project and task ID."""
        result = self._request("GET", f"/project/{project_id}/task/{task_id}")
        return result or {}

    def get_project_tasks(self, project_id: str) -> list[dict[str, Any]]:
        """Get all tasks in a project (undone tasks)."""
        result = self._request("GET", f"/project/{project_id}/data")
        return (result or {}).get("tasks", [])

    def get_completed_tasks(
        self,
        project_id: str,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get completed tasks for a project within a time range."""
        body: dict[str, Any] = {"projectIds": [project_id]}
        if start_date:
            body["startDate"] = _format_ticktick_date(start_date)
        if end_date:
            body["endDate"] = _format_ticktick_date(end_date)
        result = self._request("POST", "/task/completed", json=body)
        return result if isinstance(result, list) else []

    def test_connection(self) -> bool:
        """Test connection by listing projects."""
        try:
            result = self._request("GET", "/project")
            return isinstance(result, list)
        except TickTickAPIError:
            return False

    def delete_task(self, project_id: str, task_id: str) -> None:
        """Delete a task from TickTick."""
        self._request("DELETE", f"/project/{project_id}/task/{task_id}")


def _format_ticktick_date(dt: datetime) -> str:
    """Format datetime for TickTick API (yyyy-MM-dd'T'HH:mm:ssZ)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
