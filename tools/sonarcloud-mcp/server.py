"""SonarCloud MCP Server.

Exposes SonarCloud code quality data as MCP tools for Claude Code.
Run with: python tools/sonarcloud-mcp/server.py
"""

import os
import sys

from mcp.server.fastmcp import FastMCP

from sonarcloud_client import SonarCloudClient, SonarCloudAPIError

# ---- Configuration ----

SONAR_TOKEN = os.environ.get("SONAR_TOKEN", "")
PROJECT_KEY = os.environ.get("SONAR_PROJECT_KEY", "")
ORGANIZATION = os.environ.get("SONAR_ORGANIZATION", "")

_missing = [name for name, val in [("SONAR_TOKEN", SONAR_TOKEN), ("SONAR_PROJECT_KEY", PROJECT_KEY),
            ("SONAR_ORGANIZATION", ORGANIZATION)] if not val]
if _missing:
    print(f"ERROR: required environment variables not set: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

client = SonarCloudClient(SONAR_TOKEN, PROJECT_KEY, ORGANIZATION)
mcp = FastMCP("sonarcloud")


# ---- Formatting helpers ----


def _format_quality_gate(data: dict) -> str:
    status_info = data.get("projectStatus", {})
    status = status_info.get("status", "UNKNOWN")
    lines = [f"Quality Gate: {status}", ""]

    conditions = status_info.get("conditions", [])
    if conditions:
        lines.append("Conditions:")
        for c in conditions:
            tag = "PASS" if c.get("status") == "OK" else "FAIL"
            metric = c.get("metricKey", "?")
            actual = c.get("actualValue", "?")
            op = c.get("comparator", "?")
            threshold = c.get("errorThreshold", "?")
            lines.append(f"  [{tag}] {metric}: {actual} (threshold: {op} {threshold})")
    else:
        lines.append("No conditions found.")

    return "\n".join(lines)


def _format_issues(data: dict) -> str:
    total = data.get("total", 0)
    paging = data.get("paging", {})
    page = paging.get("pageIndex", 1)
    page_size = paging.get("pageSize", 20)
    total_pages = (total + page_size - 1) // page_size if page_size else 1

    lines = [f"Issues: {total} total (page {page}/{total_pages})", ""]

    issues = data.get("issues", [])
    if not issues:
        lines.append("No issues found.")
        return "\n".join(lines)

    for i, issue in enumerate(issues, start=(page - 1) * page_size + 1):
        itype = issue.get("type", "?")
        severity = issue.get("severity", "?")
        component = issue.get("component", "?")
        # Strip project key prefix from component path
        if ":" in component:
            component = component.split(":", 1)[1]
        line_num = issue.get("line", "?")
        message = issue.get("message", "")
        rule = issue.get("rule", "?")
        effort = issue.get("effort", "?")
        created = issue.get("creationDate", "?")[:10] if issue.get("creationDate") else "?"

        lines.append(f"{i}. [{itype}] {severity} — {component}:{line_num}")
        lines.append(f"   {message}")
        lines.append(f"   Rule: {rule} | Effort: {effort} | Created: {created}")
        lines.append("")

    return "\n".join(lines)


def _format_issue_detail(data: dict) -> str:
    issues = data.get("issues", [])
    if not issues:
        return "Issue not found."

    issue = issues[0]
    component = issue.get("component", "?")
    if ":" in component:
        component = component.split(":", 1)[1]

    lines = [
        f"Issue: {issue.get('key', '?')}",
        f"Type: {issue.get('type', '?')} | Severity: {issue.get('severity', '?')}",
        f"Status: {issue.get('status', '?')}",
        f"File: {component}:{issue.get('line', '?')}",
        f"Rule: {issue.get('rule', '?')}",
        f"Message: {issue.get('message', '')}",
        f"Effort: {issue.get('effort', '?')}",
        f"Created: {issue.get('creationDate', '?')}",
        f"Author: {issue.get('author', '?')}",
        f"Tags: {', '.join(issue.get('tags', []))}",
    ]

    comments = issue.get("comments", [])
    if comments:
        lines.append("")
        lines.append("Comments:")
        for c in comments:
            lines.append(f"  [{c.get('createdAt', '?')[:10]}] {c.get('login', '?')}: {c.get('markdown', '')}")

    return "\n".join(lines)


def _format_hotspots(data: dict) -> str:
    paging = data.get("paging", {})
    total = paging.get("total", 0)
    page = paging.get("pageIndex", 1)
    page_size = paging.get("pageSize", 20)
    total_pages = (total + page_size - 1) // page_size if page_size else 1

    lines = [f"Security Hotspots: {total} total (page {page}/{total_pages})", ""]

    hotspots = data.get("hotspots", [])
    if not hotspots:
        lines.append("No hotspots found.")
        return "\n".join(lines)

    for i, hs in enumerate(hotspots, start=(page - 1) * page_size + 1):
        component = hs.get("component", "?")
        if ":" in component:
            component = component.split(":", 1)[1]
        lines.append(f"{i}. [{hs.get('vulnerabilityProbability', '?')}] {component}:{hs.get('line', '?')}")
        lines.append(f"   {hs.get('message', '')}")
        lines.append(f"   Category: {hs.get('securityCategory', '?')} | Status: {hs.get('status', '?')}")
        lines.append("")

    return "\n".join(lines)


def _format_measures(data: dict) -> str:
    comp = data.get("component", {})
    name = comp.get("name", "?")
    measures = comp.get("measures", [])

    lines = [f"Metrics for: {name}", ""]

    if not measures:
        lines.append("No metrics found.")
        return "\n".join(lines)

    # Rating values: 1=A, 2=B, 3=C, 4=D, 5=E
    rating_map = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}
    rating_metrics = {"sqale_rating", "reliability_rating", "security_rating"}

    for m in sorted(measures, key=lambda x: x.get("metric", "")):
        metric = m.get("metric", "?")
        value = m.get("value", "?")
        if metric in rating_metrics:
            value = rating_map.get(value, value)
        lines.append(f"  {metric}: {value}")

    return "\n".join(lines)


def _format_project_info(data: dict) -> str:
    comp = data.get("component", {})
    analysis = data.get("last_analysis")

    lines = [
        f"Project: {comp.get('name', '?')}",
        f"Key: {comp.get('key', '?')}",
        f"Qualifier: {comp.get('qualifier', '?')}",
        f"Visibility: {comp.get('visibility', '?')}",
    ]

    if analysis:
        lines.append(f"Last Analysis: {analysis.get('date', '?')}")
        events = analysis.get("events", [])
        if events:
            lines.append("Events:")
            for e in events:
                lines.append(f"  - [{e.get('category', '?')}] {e.get('name', '')}")
    else:
        lines.append("Last Analysis: none")

    return "\n".join(lines)


def _format_analyses(data: dict) -> str:
    analyses = data.get("analyses", [])
    if not analyses:
        return "No analyses found."

    lines = [f"Analysis History ({len(analyses)} entries)", ""]

    for a in analyses:
        date = a.get("date", "?")
        key = a.get("key", "?")[:12]
        events = a.get("events", [])
        event_str = ""
        if events:
            event_str = " | " + ", ".join(
                f"[{e.get('category', '?')}] {e.get('name', '')}" for e in events
            )
        lines.append(f"  {date}  ({key}){event_str}")

    return "\n".join(lines)


# ---- MCP Tools ----


@mcp.tool()
def sonar_quality_gate() -> str:
    """Get the quality gate status (PASS/FAIL/WARN) and condition details for the project."""
    try:
        data = client.get_quality_gate()
        return _format_quality_gate(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


@mcp.tool()
def sonar_issues(
    types: str = "",
    severities: str = "",
    statuses: str = "",
    files: str = "",
    page: int = 1,
    page_size: int = 20,
    in_new_code: bool = False,
) -> str:
    """Search issues (bugs, vulnerabilities, code smells) with optional filters.

    Args:
        types: Comma-separated types: BUG, VULNERABILITY, CODE_SMELL (default: all)
        severities: Comma-separated: BLOCKER, CRITICAL, MAJOR, MINOR, INFO (default: all)
        statuses: Comma-separated: OPEN, CONFIRMED, REOPENED, RESOLVED, CLOSED (default: OPEN,CONFIRMED,REOPENED)
        files: Comma-separated file paths relative to project root to scope the search
        page: Page number (default: 1)
        page_size: Results per page, max 100 (default: 20)
        in_new_code: If true, only issues in the new code period
    """
    try:
        data = client.search_issues(
            types=types or None,
            severities=severities or None,
            statuses=statuses or None,
            files=files or None,
            page=page,
            page_size=page_size,
            in_new_code=in_new_code if in_new_code else None,
        )
        return _format_issues(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


@mcp.tool()
def sonar_issue_detail(issue_key: str) -> str:
    """Get full details for a specific issue including comments and rule info.

    Args:
        issue_key: The SonarCloud issue key (e.g., AZN...)
    """
    try:
        data = client.get_issue_detail(issue_key)
        return _format_issue_detail(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


@mcp.tool()
def sonar_hotspots(
    status: str = "TO_REVIEW",
    page: int = 1,
    page_size: int = 20,
) -> str:
    """List security hotspots that need review.

    Args:
        status: TO_REVIEW or REVIEWED (default: TO_REVIEW)
        page: Page number (default: 1)
        page_size: Results per page, max 100 (default: 20)
    """
    try:
        data = client.search_hotspots(
            status=status or None,
            page=page,
            page_size=page_size,
        )
        return _format_hotspots(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


@mcp.tool()
def sonar_metrics(
    metrics: str = "",
    component: str = "",
) -> str:
    """Get numeric metrics for the project or a specific file/directory.

    Args:
        metrics: Comma-separated metric keys (default: coverage, duplication, ratings, counts)
        component: Specific file or directory path (default: project root)
    """
    try:
        data = client.get_measures(
            metrics=metrics or None,
            component=component or None,
        )
        return _format_measures(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


@mcp.tool()
def sonar_project_status() -> str:
    """Get project overview: name, visibility, and last analysis date."""
    try:
        data = client.get_project_info()
        return _format_project_info(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


@mcp.tool()
def sonar_analysis_history(
    count: int = 10,
    category: str = "",
) -> str:
    """Get recent analysis history to track quality trends.

    Args:
        count: Number of recent analyses to return (default: 10, max: 50)
        category: Filter by event category: VERSION, QUALITY_GATE, QUALITY_PROFILE, OTHER
    """
    try:
        data = client.get_analyses(
            count=count,
            category=category or None,
        )
        return _format_analyses(data)
    except SonarCloudAPIError as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
