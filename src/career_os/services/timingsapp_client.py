"""TimingsApp (Timing) Web API client.

Wraps the Timing REST API (https://web.timingapp.com/api/v1).
Used to start/stop timers and create time entries in TimingsApp.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TIMINGSAPP_API_BASE = "https://web.timingapp.com/api/v1"

# Category → Timing project name mapping
CATEGORY_PROJECT_MAP = {
    "applying": "Job Search ▸ Applying",
    "researching": "Job Search ▸ Researching",
    "prepping": "Job Search ▸ Prepping",
    "networking": "Job Search ▸ Networking",
    "learning": "Job Search ▸ Learning",
}


class TimingsAppAPIError(Exception):
    """Raised when a TimingsApp API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TimingsAppClient:
    """Synchronous client for the Timing Web API v1."""

    def __init__(
        self, api_token: str, *, base_url: str | None = None, timeout: float = 30.0
    ) -> None:
        self._token = api_token
        self._base_url = (base_url or TIMINGSAPP_API_BASE).rstrip("/")
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request to the Timing API."""
        url = f"{self._base_url}{path}"
        try:
            resp = httpx.request(
                method,
                url,
                headers=self._headers,
                json=json,
                params=params,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise TimingsAppAPIError(f"HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise TimingsAppAPIError("Unauthorized — invalid or expired API token", 401)
        if resp.status_code == 403:
            raise TimingsAppAPIError("Forbidden — insufficient permissions", 403)
        if resp.status_code == 404:
            raise TimingsAppAPIError("Not found", 404)
        if resp.status_code == 429:
            raise TimingsAppAPIError("Rate limited — too many requests", 429)
        if resp.status_code >= 400:
            raise TimingsAppAPIError(
                f"TimingsApp API error {resp.status_code}: {resp.text}",
                resp.status_code,
            )

        if resp.status_code == 204 or not resp.text:
            return None

        return resp.json()

    # ---- Timer operations ----

    def start_timer(
        self,
        *,
        project: str,
        title: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Start a timer in TimingsApp.

        Returns the created time entry dict (inside `data` key).
        """
        body: dict[str, Any] = {
            "project": project,
            "title": title,
        }
        if notes:
            body["notes"] = notes

        result = self._request("POST", "/time-entries/start", json=body)
        logger.info("Started TimingsApp timer: %s", title)
        data = result.get("data", result) if result else {}
        return data

    def stop_timer(self) -> dict[str, Any]:
        """Stop the currently running timer.

        Returns the stopped time entry dict.
        """
        result = self._request("PUT", "/time-entries/stop")
        logger.info("Stopped TimingsApp timer")
        data = result.get("data", result) if result else {}
        return data

    def create_time_entry(
        self,
        *,
        project: str,
        title: str,
        start_date: datetime,
        end_date: datetime,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create a completed time entry in TimingsApp.

        Returns the created time entry dict.
        """
        body: dict[str, Any] = {
            "project": project,
            "title": title,
            "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "end_date": end_date.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        }
        if notes:
            body["notes"] = notes

        result = self._request("POST", "/time-entries", json=body)
        logger.info("Created TimingsApp entry: %s", title)
        data = result.get("data", result) if result else {}
        return data

    def get_running_timer(self) -> dict[str, Any] | None:
        """Get the currently running timer, or None if no timer is running."""
        try:
            result = self._request("GET", "/time-entries/running")
            return result.get("data", result) if result else None
        except TimingsAppAPIError as exc:
            if exc.status_code == 404:
                return None
            raise

    def list_time_entries(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """List time entries within a date range."""
        params: dict[str, str] = {}
        if start_date:
            params["start_date_min"] = start_date
        if end_date:
            params["start_date_max"] = end_date

        result = self._request("GET", "/time-entries", params=params)
        return result.get("data", []) if result else []

    def test_connection(self) -> bool:
        """Test connection by listing projects."""
        try:
            result = self._request("GET", "/projects")
            return result is not None and "data" in result
        except TimingsAppAPIError:
            return False
