"""SonarCloud Web API client.

Wraps the SonarCloud REST API (https://sonarcloud.io/web_api).
All methods are synchronous (httpx) — MCP tools run sequentially and
latency is dominated by network round trips, not concurrency.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SONARCLOUD_API_BASE = "https://sonarcloud.io/api"


class SonarCloudAPIError(Exception):
    """Raised when a SonarCloud API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SonarCloudClient:
    """Synchronous client for the SonarCloud Web API."""

    def __init__(
        self,
        token: str,
        project_key: str,
        organization: str,
        timeout: float = 30.0,
    ) -> None:
        self._token = token
        self._project_key = project_key
        self._organization = organization
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request to the SonarCloud API."""
        url = f"{SONARCLOUD_API_BASE}{path}"
        if params is None:
            params = {}
        params["organization"] = self._organization
        # Strip None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            resp = httpx.request(
                method,
                url,
                headers=self._headers,
                params=params,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise SonarCloudAPIError(f"HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise SonarCloudAPIError("Unauthorized — invalid or expired token", 401)
        if resp.status_code == 403:
            raise SonarCloudAPIError("Forbidden — insufficient permissions", 403)
        if resp.status_code == 404:
            raise SonarCloudAPIError("Not found", 404)
        if resp.status_code >= 400:
            raise SonarCloudAPIError(
                f"SonarCloud API error {resp.status_code}: {resp.text}",
                resp.status_code,
            )

        if resp.text:
            return resp.json()
        return None

    # ---- Quality gate ----

    def get_quality_gate(self) -> dict[str, Any]:
        """Get quality gate status for the project."""
        result = self._request(
            "GET",
            "/qualitygates/project_status",
            params={"projectKey": self._project_key},
        )
        return result or {}

    # ---- Issues ----

    def search_issues(
        self,
        *,
        types: str | None = None,
        severities: str | None = None,
        statuses: str | None = None,
        files: str | None = None,
        page: int = 1,
        page_size: int = 20,
        in_new_code: bool | None = None,
    ) -> dict[str, Any]:
        """Search issues (bugs, vulnerabilities, code smells)."""
        params: dict[str, Any] = {
            "componentKeys": self._project_key,
            "p": page,
            "ps": min(page_size, 100),
        }
        if types:
            params["types"] = types
        if severities:
            params["severities"] = severities
        if statuses:
            params["statuses"] = statuses
        else:
            params["statuses"] = "OPEN,CONFIRMED,REOPENED"
        if files:
            params["files"] = files
        if in_new_code is not None:
            params["inNewCodePeriod"] = str(in_new_code).lower()

        result = self._request("GET", "/issues/search", params=params)
        return result or {}

    def get_issue_detail(self, issue_key: str) -> dict[str, Any]:
        """Get full details for a single issue."""
        result = self._request(
            "GET",
            "/issues/search",
            params={
                "issues": issue_key,
                "additionalFields": "comments,rules",
                "componentKeys": self._project_key,
            },
        )
        return result or {}

    # ---- Security hotspots ----

    def search_hotspots(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Search security hotspots."""
        params: dict[str, Any] = {
            "projectKey": self._project_key,
            "p": page,
            "ps": min(page_size, 100),
        }
        if status:
            params["status"] = status
        else:
            params["status"] = "TO_REVIEW"

        result = self._request("GET", "/hotspots/search", params=params)
        return result or {}

    # ---- Metrics ----

    DEFAULT_METRICS = (
        "coverage,duplicated_lines_density,sqale_rating,reliability_rating,"
        "security_rating,ncloc,complexity,cognitive_complexity,"
        "bugs,vulnerabilities,code_smells,security_hotspots"
    )

    def get_measures(
        self,
        *,
        metrics: str | None = None,
        component: str | None = None,
    ) -> dict[str, Any]:
        """Get numeric metrics for a component (defaults to project root)."""
        result = self._request(
            "GET",
            "/measures/component",
            params={
                "component": component or self._project_key,
                "metricKeys": metrics or self.DEFAULT_METRICS,
            },
        )
        return result or {}

    # ---- Project info ----

    def get_project_info(self) -> dict[str, Any]:
        """Get project overview: name, visibility, last analysis."""
        component = self._request(
            "GET",
            "/components/show",
            params={"component": self._project_key},
        )
        analyses = self._request(
            "GET",
            "/project_analyses/search",
            params={"project": self._project_key, "ps": 1},
        )
        return {
            "component": (component or {}).get("component", {}),
            "last_analysis": ((analyses or {}).get("analyses") or [None])[0],
        }

    # ---- Analysis history ----

    def get_analyses(
        self,
        *,
        count: int = 10,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Get recent analysis history."""
        params: dict[str, Any] = {
            "project": self._project_key,
            "ps": min(count, 50),
        }
        if category:
            params["category"] = category

        result = self._request("GET", "/project_analyses/search", params=params)
        return result or {}
