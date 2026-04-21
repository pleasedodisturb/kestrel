"""Kestrel MCP Server.

Exposes Kestrel job search platform tools for Claude Code.
Wraps the REST API so it works from any directory/session.

Run with: python tools/kestrel-mcp/server.py

Required env vars:
  KESTREL_URL      — Base URL of running Kestrel instance (default: http://localhost:8100)
  KESTREL_PROFILE_ID — Profile ID to scope all operations (default: 1)
  KESTREL_API_KEY  — Optional API key if auth is enabled
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

# ---- Configuration ----

KESTREL_URL = os.environ.get("KESTREL_URL", "http://localhost:8100")
PROFILE_ID = int(os.environ.get("KESTREL_PROFILE_ID", "1"))
API_KEY = os.environ.get("KESTREL_API_KEY", "")

mcp = FastMCP("kestrel")


# ---- HTTP client ----


def _headers() -> dict[str, str]:
    """Build request headers with optional auth."""
    h: dict[str, str] = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def _get(path: str, params: dict | None = None) -> dict:
    """GET request to Kestrel API. Raises on non-2xx."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{KESTREL_URL}{path}", headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, payload: dict) -> dict:
    """POST request to Kestrel API. Raises on non-2xx."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{KESTREL_URL}{path}", headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


# ---- Formatting helpers ----


def _format_pipeline(data: dict) -> str:
    """Format pipeline listing into readable text."""
    apps = data.get("applications", [])
    total = data.get("total", len(apps))

    if not apps:
        return "Pipeline is empty."

    lines = [f"Pipeline: {total} applications", ""]

    for app in apps:
        status = app.get("status", "?")
        company = app.get("company", "?")
        role = app.get("role", "?")
        score = app.get("fit_score")
        score_str = f" (fit: {score})" if score is not None else ""
        app_id = app.get("id", "?")
        lines.append(f"  [{status}] {company} — {role}{score_str}  (id: {app_id})")

    return "\n".join(lines)


def _format_stats(data: dict) -> str:
    """Format pipeline stats into readable text."""
    lines = ["Pipeline Statistics", ""]

    for key, value in sorted(data.items()):
        if isinstance(value, dict):
            lines.append(f"  {key}:")
            for k, v in sorted(value.items()):
                lines.append(f"    {k}: {v}")
        else:
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def _format_score(data: dict) -> str:
    """Format a score response into readable text."""
    lines = [
        f"Fit Score: {data.get('fit_score', '?')}/10",
        f"Readiness: {data.get('readiness_score', '?')}%",
        f"Career Alignment: {data.get('career_alignment', '?')}/10",
        f"Effort: {data.get('effort_flag', '?')}",
        f"Prep Level: {data.get('prep_level', '?')}",
        "",
        f"Reasoning: {data.get('reasoning', 'N/A')}",
    ]

    salary = data.get("estimated_salary")
    if salary:
        lines.append(f"Estimated Salary: {salary}")

    prep = data.get("prep_notes")
    if prep:
        lines.append(f"Prep Notes: {prep}")

    breakdown = data.get("score_breakdown")
    if isinstance(breakdown, list) and breakdown:
        lines.append("")
        lines.append("Score Breakdown:")
        for factor in breakdown:
            name = factor.get("factor", "?")
            contrib = factor.get("contribution", "?")
            desc = factor.get("description", "")
            lines.append(f"  {name}: {contrib:+.1f} — {desc}")

    return "\n".join(lines)


def _format_discovery(data: dict) -> str:
    """Format a discovery run response into readable text."""
    lines = [
        f"Discovery Run: {data.get('total_found', 0)} found, "
        f"{data.get('new_jobs', 0)} new, "
        f"{data.get('duplicates', 0)} duplicates",
        f"Sources: {', '.join(data.get('sources_queried', []))}",
        "",
    ]

    jobs = data.get("jobs", [])
    if not jobs:
        lines.append("No new jobs found.")
        return "\n".join(lines)

    for job in jobs[:20]:  # Cap display at 20
        title = job.get("title", "?")
        company = job.get("company", "?")
        location = job.get("location", "?")
        score = job.get("fit_score")
        score_str = f" (fit: {score})" if score is not None else ""
        remote = " [remote]" if job.get("remote") else ""
        lines.append(f"  {company} — {title} @ {location}{remote}{score_str}")

    if len(jobs) > 20:
        lines.append(f"  ... and {len(jobs) - 20} more")

    return "\n".join(lines)


# ---- MCP Tools ----


@mcp.tool()
def list_pipeline(
    status: str = "",
    search: str = "",
    sort: str = "created_at",
    order: str = "desc",
) -> str:
    """List applications in the Kestrel job pipeline.

    Args:
        status: Filter by status (discovered, applied, interviewing,
            offered, rejected, withdrawn, ghosted)
        search: Search by company or role name
        sort: Sort field (created_at, fit_score, company, status). Default: created_at
        order: Sort order (asc, desc). Default: desc
    """
    try:
        params: dict = {"profile_id": PROFILE_ID, "sort": sort, "order": order}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        data = _get("/api/applications", params=params)
        return _format_pipeline(data)
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return f"Error: Cannot connect to Kestrel at {KESTREL_URL}. Is the server running?"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)[:200]}"


@mcp.tool()
def pipeline_stats() -> str:
    """Get pipeline statistics: counts by status, activity trends, follow-up summary."""
    try:
        data = _get("/api/applications/stats", params={"profile_id": PROFILE_ID})
        return _format_stats(data)
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return f"Error: Cannot connect to Kestrel at {KESTREL_URL}. Is the server running?"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)[:200]}"


@mcp.tool()
def score_job(
    job_description: str,
    job_title: str = "",
    job_company: str = "",
    job_url: str = "",
) -> str:
    """Score a job against the user's profile.

    Returns fit score, readiness, career alignment, and prep notes.

    Args:
        job_description: Full job description text (required)
        job_title: Job title (optional, improves context)
        job_company: Company name (optional, improves context)
        job_url: Job posting URL (optional)
    """
    try:
        payload: dict = {
            "profile_id": PROFILE_ID,
            "job_description": job_description,
        }
        if job_title:
            payload["job_title"] = job_title
        if job_company:
            payload["job_company"] = job_company
        if job_url:
            payload["job_url"] = job_url

        data = _post("/api/score", payload)
        return _format_score(data)
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return f"Error: Cannot connect to Kestrel at {KESTREL_URL}. Is the server running?"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)[:200]}"


@mcp.tool()
def discover_jobs(
    keywords: str = "",
    locations: str = "",
    remote_only: bool = False,
    sources: str = "",
    limit_per_source: int = 50,
) -> str:
    """Run a job discovery sweep across configured sources.

    Args:
        keywords: Comma-separated search keywords (e.g., "python,backend,senior")
        locations: Comma-separated locations (e.g., "Berlin,Remote")
        remote_only: Only return remote positions
        sources: Comma-separated job sources to query (default: all configured)
        limit_per_source: Max results per source (default: 50)
    """
    try:
        payload: dict = {
            "profile_id": PROFILE_ID,
            "remote_only": remote_only,
            "limit_per_source": limit_per_source,
        }
        if keywords:
            payload["keywords"] = [k.strip() for k in keywords.split(",")]
        if locations:
            payload["locations"] = [loc.strip() for loc in locations.split(",")]
        if sources:
            payload["sources"] = [s.strip() for s in sources.split(",")]

        data = _post("/api/discover", payload)
        return _format_discovery(data)
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return f"Error: Cannot connect to Kestrel at {KESTREL_URL}. Is the server running?"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)[:200]}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
