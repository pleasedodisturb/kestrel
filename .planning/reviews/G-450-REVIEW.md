---
phase: G-450
reviewed: 2026-04-21T18:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tools/kestrel-mcp/server.py
  - tools/kestrel-mcp/__init__.py
  - tools/kestrel-mcp/README.md
  - tools/tests/test_kestrel_mcp.py
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
status: issues_found
---

# G-450: Code Review Report

**Reviewed:** 2026-04-21
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

New MCP server wrapping the Kestrel REST API with 4 tools (list_pipeline, pipeline_stats, score_job, discover_jobs). Clean structure, good formatting helpers, solid test coverage of the happy paths. The main concerns are: (1) incomplete exception handling that will cause unhandled crashes on timeouts and JSON decode errors, (2) error messages leaking raw backend response bodies, and (3) missing SSRF mitigation on the user-configurable base URL.

## Critical Issues

### CR-01: Unhandled httpx exceptions crash the MCP server

**File:** `tools/kestrel-mcp/server.py:131-137` (and all tool functions)
**Issue:** Each tool only catches `httpx.HTTPStatusError` and `httpx.ConnectError`. Other real-world failures -- `httpx.TimeoutException` (30s/60s timeout hit), `httpx.ReadError`, `json.JSONDecodeError` (non-JSON response body), `httpx.TooManyRedirects` -- will propagate as unhandled exceptions. For an MCP server running as a subprocess, an unhandled exception in a tool handler likely kills the server process, requiring a manual restart.
**Fix:** Add a broad `httpx.HTTPError` catch (parent of all httpx errors) as a fallback, plus a `json.JSONDecodeError` catch for `.json()` calls:
```python
@mcp.tool()
def list_pipeline(...) -> str:
    try:
        # ...existing code...
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} — {e.response.text[:200]}"
    except httpx.ConnectError:
        return f"Error: Cannot connect to Kestrel at {KESTREL_URL}. Is the server running?"
    except httpx.TimeoutException:
        return f"Error: Request to Kestrel timed out. The server may be overloaded."
    except (httpx.HTTPError, ValueError) as e:
        return f"Error: {type(e).__name__}: {e}"
```
Apply the same pattern to all 4 tool functions. The `ValueError` catch covers `json.JSONDecodeError` (which is a subclass of `ValueError`).

## Warnings

### WR-01: Error messages leak raw backend response body

**File:** `tools/kestrel-mcp/server.py:135`
**Issue:** `e.response.text` is returned verbatim to the MCP client (Claude). If the Kestrel backend returns a stack trace, internal path, or debug info on a 500 error, that leaks through the MCP tool response. This is especially risky because MCP tool outputs may be included in LLM context and could surface in user-facing conversation.
**Fix:** Truncate and sanitize the error body:
```python
except httpx.HTTPStatusError as e:
    body = e.response.text[:200] if e.response.text else "No details"
    return f"Error: HTTP {e.response.status_code} — {body}"
```

### WR-02: No SSRF mitigation on KESTREL_URL

**File:** `tools/kestrel-mcp/server.py:18`
**Issue:** `KESTREL_URL` is read from env and used directly in `httpx.Client.get/post` with no validation. If misconfigured (e.g., `KESTREL_URL=http://169.254.169.254` on cloud, or `file:///etc/passwd`), it could be used to probe internal network services. Since this is a self-hosted tool configured by the owner, the risk is low but worth a validation check at startup.
**Fix:** Add a startup validation that checks scheme is `http` or `https` and optionally warns on non-localhost URLs:
```python
from urllib.parse import urlparse

def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"KESTREL_URL must use http or https scheme, got: {parsed.scheme}")
    return url.rstrip("/")

KESTREL_URL = _validate_url(os.environ.get("KESTREL_URL", "http://localhost:8100"))
```

### WR-03: PROFILE_ID int() cast crashes at import time on invalid input

**File:** `tools/kestrel-mcp/server.py:19`
**Issue:** `int(os.environ.get("KESTREL_PROFILE_ID", "1"))` will raise `ValueError` at module import time if the env var is set to a non-integer string (e.g., `"abc"`). Since this runs during MCP server startup, the server silently fails to start with no user-friendly message.
**Fix:**
```python
try:
    PROFILE_ID = int(os.environ.get("KESTREL_PROFILE_ID", "1"))
except ValueError:
    raise SystemExit("KESTREL_PROFILE_ID must be an integer")
```

### WR-04: _format_score crashes on non-numeric contribution

**File:** `tools/kestrel-mcp/server.py:100`
**Issue:** `f"{contrib:+.1f}"` uses float formatting. If the API returns `contribution` as a string or None, this will raise `TypeError`/`ValueError` and crash the tool handler (which then hits CR-01 if unhandled).
**Fix:**
```python
for factor in breakdown:
    name = factor.get("factor", "?")
    contrib = factor.get("contribution", 0)
    try:
        contrib_str = f"{float(contrib):+.1f}"
    except (TypeError, ValueError):
        contrib_str = str(contrib)
    desc = factor.get("description", "")
    lines.append(f"  {name}: {contrib_str} — {desc}")
```

### WR-05: Missing test coverage for error paths

**File:** `tools/tests/test_kestrel_mcp.py`
**Issue:** Several error paths are untested:
- No test for `HTTPStatusError` on any tool (only `ConnectError` is tested, and only on `list_pipeline`)
- No test for `pipeline_stats` or `discover_jobs` connection errors
- No test for timeout errors (currently unhandled, but should be after CR-01 fix)
- `_format_score` with missing/malformed `score_breakdown` items not tested

**Fix:** Add at minimum:
```python
def test_http_error(self) -> None:
    """Test that HTTP 4xx/5xx returns error string, not exception."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"
    error = httpx.HTTPStatusError("forbidden", request=MagicMock(), response=mock_resp)

    with patch("server.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = error
        mock_client_cls.return_value = mock_client

        result = list_pipeline()
        assert "403" in result
        assert "Forbidden" in result
```

## Info

### IN-01: Module-level config makes env var testing awkward

**File:** `tools/tests/test_kestrel_mcp.py:59-75`
**Issue:** Tests for `_headers()` directly mutate `srv.API_KEY` and restore it afterward. This is fragile and not thread-safe. The root cause is that `server.py` reads config at module level. Consider a config dataclass or lazy initialization to improve testability.
**Fix:** Not blocking for v1, but a future improvement would be:
```python
@dataclass
class Config:
    url: str = "http://localhost:8100"
    profile_id: int = 1
    api_key: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            url=os.environ.get("KESTREL_URL", "http://localhost:8100"),
            profile_id=int(os.environ.get("KESTREL_PROFILE_ID", "1")),
            api_key=os.environ.get("KESTREL_API_KEY", ""),
        )
```

### IN-02: No requirements.txt or pyproject.toml for the MCP server

**File:** `tools/kestrel-mcp/`
**Issue:** The README lists `mcp` and `httpx` as requirements, but there is no `requirements.txt` or `pyproject.toml` in the `tools/kestrel-mcp/` directory. Users must manually figure out versions. Since this uses the project venv (per README config), the deps should at least be documented with version pins.
**Fix:** Add a `requirements.txt`:
```
httpx>=0.27,<1.0
mcp>=1.0
```
Or add them as optional deps in the root `pyproject.toml` under an `[mcp]` extra.

---

_Reviewed: 2026-04-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
