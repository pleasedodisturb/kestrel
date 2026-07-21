"""Browser-extension API routes: pair, capture (stub), status (Phase 0 / G-1390).

The extension authenticates with a DEDICATED token (see services.extension_pairing)
that is separate from the global AUTH_API_KEY and required even when AUTH_ENABLED is
off. `/pair` is the bootstrap (code-gated, no token yet); `/capture` and `/status`
require a valid extension token via the `require_extension_token` dependency.

Phase 0 is foundation ONLY: `/capture` is a STUB that accepts a normalized payload
and returns an id — it does NO scoring and touches NO database. Wiring capture to
the scoring service is Phase 1 (which is why the scoring service is deliberately
never imported here; there is a structural test guarding that).
"""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from career_os import __version__
from career_os.api.oauth import limiter
from career_os.schemas.extension import (
    CaptureRequest,
    CaptureResponse,
    InstanceInfo,
    PairRequest,
    PairResponse,
    StatusResponse,
)
from career_os.services.extension_pairing import (
    consume_pairing_code,
    mint_extension_token,
    verify_extension_token,
)

router = APIRouter(prefix="/api/extension", tags=["extension"])

# Brand name surfaced to the extension. Deliberately "Kestrel" (project brand) and
# NOT settings.app_name ("Career OS", the internal package name) — T-00-03.
_INSTANCE_NAME = "Kestrel"


def _instance_info() -> InstanceInfo:
    return InstanceInfo(name=_INSTANCE_NAME, version=__version__)


def require_extension_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract and validate the Bearer extension token; raise 401 otherwise.

    Enforced per-route so it governs even though the global AUTH_API_KEY
    middleware bypasses /api/extension/ (the extension uses a separate token
    space). Returns the validated token for handlers that want it.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Extension not paired")
    token = authorization[7:]  # strip "Bearer "
    if not verify_extension_token(token):
        raise HTTPException(status_code=401, detail="Extension not paired")
    return token


@router.post(
    "/pair",
    response_model=PairResponse,
    responses={429: {"description": "Too many pairing attempts"}},
)
@limiter.limit("5/minute")
def pair(request: Request, payload: PairRequest) -> PairResponse:
    """Validate a pairing code and mint a dedicated extension token.

    Rate-limited to 5 attempts/min/IP (shared slowapi limiter, same instance the
    app wires to ``app.state.limiter``) to kill brute-force of the 6-digit code —
    T-01A-01. slowapi requires the ``request: Request`` first parameter.
    """
    if not consume_pairing_code(payload.pairing_code):
        raise HTTPException(status_code=401, detail="Invalid or expired pairing code")
    return PairResponse(token=mint_extension_token(), instance=_instance_info())


@router.post("/capture", response_model=CaptureResponse)
def capture(
    payload: CaptureRequest,
    _token: Annotated[str, Depends(require_extension_token)],
) -> CaptureResponse:
    """STUB: accept a captured job and return an id. No scoring, no DB write.

    Phase 1 wires this to the scoring service (via the discovery adapters
    normalization path). Until then it is intentionally inert so the extension
    channel can be built and tested end-to-end with zero product/LLM cost.
    """
    job_id = str(uuid4())
    return CaptureResponse(job_id=job_id, status="accepted", scored=False)


@router.get("/status", response_model=StatusResponse)
def status(
    _token: Annotated[str, Depends(require_extension_token)],
) -> StatusResponse:
    """Report instance info to a paired extension (health/identity check)."""
    return StatusResponse(ok=True, instance=_instance_info())
