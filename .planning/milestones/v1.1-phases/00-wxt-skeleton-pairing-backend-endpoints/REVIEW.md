---
phase: 00-wxt-skeleton-pairing-backend-endpoints
reviewed: 2026-07-21T15:12:07Z
depth: deep
files_reviewed: 20
files_reviewed_list:
  - src/career_os/services/extension_pairing.py
  - src/career_os/api/extension.py
  - src/career_os/schemas/extension.py
  - src/career_os/cli/extension.py
  - src/career_os/cli/main.py
  - src/career_os/config.py
  - src/career_os/middleware.py
  - src/career_os/main.py
  - tests/test_extension_api.py
  - extension/wxt.config.ts
  - extension/entrypoints/background.ts
  - extension/entrypoints/popup/App.tsx
  - extension/entrypoints/options/App.tsx
  - extension/entrypoints/options/PairingForm.tsx
  - extension/entrypoints/options/HealthBadge.tsx
  - extension/lib/api/client.ts
  - extension/lib/api/messages.ts
  - extension/lib/storage.ts
  - extension/lib/useHealth.ts
  - extension/__tests__/background.test.ts
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 00: Code Review Report — Browser Extension (WXT skeleton + pairing backend)

**Reviewed:** 2026-07-21T15:12:07Z
**Depth:** deep
**Files Reviewed:** 20
**Status:** issues_found

## Summary

This is foundation/auth code and the core mechanics are largely correct: the HMAC token verify is timing-safe (`hmac.compare_digest`) and rejects empty/malformed/truncated/tampered input; the pairing-code window comparison correctly accepts current + previous window without short-circuit; the secret persists to `{data_dir}/.extension_secret` (not only a module global) and re-reads across restarts; the middleware `_PUBLIC_PREFIXES` bypass only skips the global `AUTH_API_KEY` while `require_extension_token` still gates `/capture` and `/status` (proven by `test_middleware_bypass_when_auth_enabled`); CORS `allow_origin_regex` is genuinely additive and narrow (`^chrome-extension://[a-p]{32}$`, never `*`, frontend `allow_origins`/`allow_credentials` untouched); the capture stub does no scoring/DB work and the no-`score_job` guard is structurally tested; `fetch` is isolated to `lib/api/client.ts` (verified — zero occurrences elsewhere), calls are `credentials:"omit"` with the token in the header; and the background worker is genuinely stateless (reads fresh from `chrome.storage` every handler, no module-scope caching). Tests assert real behavior, not hollow smoke.

The findings below are real but none are Critical. The most important is the absence of rate limiting on the unauthenticated `/pair` endpoint, which makes the 6-digit pairing code brute-forceable for network-reachable (AUTH_ENABLED / exposed) deployments — the exact deployment mode `AUTH_API_KEY` exists to serve.

Note on the diff: `git diff main..branch` shows large ESCO deletions (`models/esco.py`, `scripts/load_esco_occupations.py`, the fixture, migration, and test). These are **not** changes made by this branch — ESCO was added to `main` (commit `337dbc3`, G-1351) after this branch's merge-base, so they surface as phantom deletions. No branch commit touches those files. The branch is simply stale; rebase onto `main` before opening the PR (see IN-04).

## Warnings

### WR-01: `/pair` is unauthenticated and unthrottled → 6-digit pairing code is brute-forceable

**File:** `src/career_os/api/extension.py:64-69`, `src/career_os/middleware.py:26,51-52`
**Issue:** `/api/extension/pair` is intentionally exempt from the global `AUTH_API_KEY` (via `_PUBLIC_PREFIXES`) and is code-gated only. The pairing code is a 6-digit number (`_code_for_window` → `% 1_000_000`), i.e. ~20 bits of entropy, valid for the current **and** previous window (~10 minutes at the default 300s). There is no rate limiting, lockout, or backoff on the endpoint. An attacker who can reach the port (any `AUTH_ENABLED`/remote-exposed deployment — precisely the config `AUTH_API_KEY` targets) can brute-force the code at a few thousand req/s (~3,333 req/s exhausts the space within one window; expected success in ~2–3 windows) and mint a token. Because minted tokens have **no expiry** (documented, accepted for Phase 0), a single successful guess yields permanent `/capture` + `/status` access. The project already uses `slowapi` for exactly this purpose (`api/oauth.py`: `@limiter.limit("10/minute")`, `"20/minute"`), so the mitigation pattern exists and was simply not applied here.

Mitigating context (keeps this Warning, not Critical): in the default localhost-only deployment the port is not network-reachable, and a browser-based (DNS-rebinding) attacker cannot read the token response because CORS only reflects `chrome-extension://` origins — so the practical attacker is a non-browser host on the LAN or an exposed instance.

**Fix:** Apply a `slowapi` limit to `/pair` (the request must expose `request: Request` for `get_remote_address`), e.g.:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@router.post("/pair", response_model=PairResponse)
@limiter.limit("5/minute")
def pair(request: Request, payload: PairRequest) -> PairResponse:
    ...
```
Also consider widening the pairing code to 8 digits and/or adding a short global failure-count lockout. Longer term, give minted tokens an `exp` claim so a single brute-forced code doesn't grant permanent access.

### WR-02: Secret file is world-readable in the window between creation and `chmod` (and races across workers)

**File:** `src/career_os/services/extension_pairing.py:94-98`
**Issue:** The root secret is written with `secret_path.write_text(value, ...)` and only *afterwards* `os.chmod(secret_path, 0o600)`. `write_text` creates the file honoring the process umask (commonly `0644`), so for the interval between the `write_text` and the `chmod` the secret — from which every extension token and pairing code is derived — is readable by other local users. Additionally the create path is neither atomic nor exclusive: two workers/processes hitting first-run simultaneously (e.g. `uvicorn --workers N`) each generate a *different* secret and race the write; the loser caches a secret that disagrees with the on-disk file, so tokens minted by one worker are rejected by another. (This mirrors the pre-existing `ai/cache.py:62-63` pattern, so it is project-consistent — but it is still a real exposure for the auth root.)
**Fix:** Create atomically with restrictive perms and fall back to read-on-exists:
```python
try:
    fd = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(value)
except FileExistsError:
    value = secret_path.read_text(encoding="utf-8").strip()
_cached_file_secret = value.encode()
return _cached_file_secret
```
This closes the readable window and makes concurrent first-run deterministic (first writer wins, others re-read).

### WR-03: URL guard permits hosts the manifest `host_permissions` cannot reach → silent "backend-down"

**File:** `extension/lib/storage.ts:16-32` vs `extension/wxt.config.ts:19`
**Issue:** `assertValidBackendUrl` accepts any `https://` host and `http://[::1]`, but `host_permissions` is limited to `["http://localhost/*", "http://127.0.0.1/*"]`. A user who enters `https://kestrel.example.com` (or an `http://[::1]` backend) passes validation and the URL is stored, but the service-worker `fetch` has no host permission for it. The request will fail or be blocked, and the health logic reports a misleading `backend-down` with no indication that the URL was actually the problem. The guard's contract (https-anywhere is "safe") and the manifest's capability (localhost only) disagree.
**Fix:** For Phase 0, tighten the guard to match the manifest — reject non-localhost hosts entirely until later phases add explicit `host_permissions`/`optional_host_permissions` — or, if remote https is meant to work now, add `optional_host_permissions: ["https://*/*"]` and request it at save time. At minimum, surface a distinct error state when a stored URL is outside the granted host permissions rather than collapsing to `backend-down`.

## Info

### IN-01: `extension_pairing_window_seconds = 0` is inconsistently handled

**File:** `src/career_os/services/extension_pairing.py:129` vs `src/career_os/cli/extension.py:31`
**Issue:** `_current_window()` guards against a zero window with `settings.extension_pairing_window_seconds or 300` (avoiding a `ZeroDivisionError`), but the CLI computes `settings.extension_pairing_window_seconds // 60`, which for `0` prints "valid for about 0 minute(s)" — a confusing contradiction with the effective 300s window actually in use. A negative value would also pass through both paths unguarded.
**Fix:** Validate the setting once (e.g. a Pydantic `Field(gt=0)` on `extension_pairing_window_seconds`) so both the window math and the CLI display use the same positive source of truth, and drop the ad-hoc `or 300` fallback.

### IN-02: `verify_extension_token` decodes unbounded base64 from an attacker-controlled header

**File:** `src/career_os/services/extension_pairing.py:183-192`
**Issue:** There is no length bound on the token before `_b64url_decode`, so an arbitrarily large `Authorization` header is fully base64-decoded before the HMAC check. Server/proxy header-size caps make this low impact, but a cheap length guard is defense-in-depth for an unauthenticated-reachable code path.
**Fix:** Reject implausibly long tokens early, e.g. `if len(token) > 512: return False` before splitting/decoding.

### IN-03: `_PUBLIC_PREFIXES` is a standing footgun for future extension routes

**File:** `src/career_os/middleware.py:26,51-52`
**Issue:** Every route mounted under `/api/extension/` now auto-bypasses the global `AUTH_API_KEY`. Today all three routes are correctly gated (`/pair` by code, `/capture` + `/status` by `require_extension_token`), but a future handler added to this router without the `Depends(require_extension_token)` dependency would be globally unauthenticated with no compile-time or test-time signal.
**Fix:** Add a test that iterates the extension router's routes and asserts every non-`/pair` route declares the `require_extension_token` dependency, so a forgotten guard fails CI. A short comment on `router = APIRouter(...)` in `api/extension.py` reminding that new routes must add the dependency would also help.

### IN-04: Branch is stale relative to `main` (phantom ESCO deletions in the diff)

**File:** repository-wide (diff artifact)
**Issue:** `git diff main..G-1389/browser-extension` reports deletion of `src/career_os/models/esco.py`, `scripts/load_esco_occupations.py`, the ESCO fixture, migration `v4w5x6y7z8a9_...`, and `tests/test_esco_occupations.py`. No branch commit touches these — they were added to `main` after the merge-base (G-1351, `337dbc3`) — but a reviewer skimming the raw diff could mistake them for intentional removals, and the stale base risks Alembic/history conflicts on merge given the just-reconciled in-package migration chain (G-1350).
**Fix:** Rebase `G-1389/browser-extension` onto current `main` before opening the PR so the diff shows only the extension changes.

---

_Reviewed: 2026-07-21T15:12:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
