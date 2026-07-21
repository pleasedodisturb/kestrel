"""Authentication middleware — API key bearer token with toggle."""

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Paths that bypass auth even when enabled
_PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/openrouter/callback",  # browser redirect — PKCE state protects it
    }
)

# Prefixes that bypass the GLOBAL AUTH_API_KEY check. The browser-extension routes
# use a DEDICATED token space (a separate secret, see services.extension_pairing)
# enforced per-route by require_extension_token, so the global key must not shadow
# them — otherwise a user with AUTH_ENABLED=true could not pair without also
# knowing AUTH_API_KEY. This bypass ONLY skips the global key: /capture and /status
# remain gated by the per-route extension token, and /pair is code-gated (T-00-02).
_PUBLIC_PREFIXES = ("/api/extension/",)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require Authorization: Bearer <key> when auth is enabled.

    When ``auth_enabled`` is False (default), all requests pass through.
    Uses ``hmac.compare_digest`` for timing-safe key comparison.
    """

    def __init__(self, app, *, auth_enabled: bool, auth_api_key: str) -> None:
        super().__init__(app)
        self._enabled = auth_enabled
        self._key = auth_api_key

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)

        # Public paths always pass
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Extension routes use a dedicated token enforced per-route — the global
        # AUTH_API_KEY must not shadow them (see _PUBLIC_PREFIXES rationale).
        if any(request.url.path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
            )

        token = auth_header[7:]  # Strip "Bearer " prefix
        if not hmac.compare_digest(token, self._key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
            )

        return await call_next(request)
