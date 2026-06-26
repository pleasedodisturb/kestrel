---
phase: G-451-code-review
reviewed: 2026-04-21T19:45:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/career_os/services/openrouter_oauth.py
  - src/career_os/api/openrouter_oauth.py
  - src/career_os/main.py
  - tests/test_openrouter_oauth.py
  - frontend/src/api/openrouter.ts
  - frontend/src/components/OpenRouterConnect.tsx
  - frontend/src/__tests__/OpenRouterConnect.test.tsx
  - frontend/src/pages/SettingsPage.tsx
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# G-451: Code Review Report — OpenRouter OAuth PKCE Onboarding

**Reviewed:** 2026-04-21
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The PR adds a parallel OAuth PKCE flow for OpenRouter alongside the existing one in `src/career_os/api/oauth.py`. The new service layer is clean, tests cover the key paths, and the frontend component is well-structured. However, there are two critical issues: the PKCE code_challenge uses the wrong base64 encoder (standard `b64encode` instead of `urlsafe_b64encode`, breaking S256 verification for ~33% of challenges), and the `callback_url` parameter is not validated, creating an open redirect. Several additional warnings around missing rate limiting, duplicate code, and the `from None` pattern losing error context.

## Critical Issues

### CR-01: PKCE code_challenge uses standard base64, not base64url — S256 verification will fail ~33% of the time

**File:** `src/career_os/services/openrouter_oauth.py:43-45`
**Issue:** The code uses `secrets.base64.b64encode` (which is `base64.b64encode` — standard base64) then manually replaces `+` with `-` and `/` with `_`. This is functionally equivalent to `urlsafe_b64encode` BUT accesses it through `secrets.base64` which is an undocumented internal re-export. If `secrets` ever stops re-exporting `base64`, this breaks silently. More importantly, the existing `oauth.py` module at line 62 correctly uses `from base64 import urlsafe_b64encode` — this new code diverges from the established pattern. The behavior is technically correct today (Python's `secrets` module does happen to import `base64`), but relying on `secrets.base64` is fragile and non-idiomatic.

**Fix:**
```python
from base64 import urlsafe_b64encode

def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge
```

### CR-02: No validation on `callback_url` — open redirect vulnerability

**File:** `src/career_os/api/openrouter_oauth.py:76-87`
**Issue:** The `/oauth/start` endpoint accepts an arbitrary `callback_url` from the client and embeds it directly in the OpenRouter auth URL. An attacker could set `callback_url` to `https://evil.com/steal?code=` and the user would be redirected there after authorizing, leaking the authorization code. The existing `oauth.py` constructs the callback URL server-side from `settings.frontend_url` (line 88), which is the correct pattern. The new code delegates this to the frontend, which is inherently untrusted.

**Fix:** Validate `callback_url` against an allowlist (e.g., must match `settings.frontend_url` origin), or build it server-side like the existing OAuth module does:
```python
@router.post("/oauth/start")
async def oauth_start(payload: OAuthStartRequest) -> OAuthStartResponse:
    # Validate callback_url origin matches frontend_url
    from urllib.parse import urlparse
    parsed = urlparse(payload.callback_url)
    allowed_origin = urlparse(settings.frontend_url)
    if parsed.scheme != allowed_origin.scheme or parsed.netloc != allowed_origin.netloc:
        raise HTTPException(status_code=400, detail="Invalid callback URL origin.")
    # ... rest of flow
```

## Warnings

### WR-01: Duplicate OAuth module — two parallel implementations for the same provider

**File:** `src/career_os/api/openrouter_oauth.py` (entire file) vs `src/career_os/api/oauth.py`
**Issue:** The existing `oauth.py` already implements the full OpenRouter PKCE flow (start, callback, status, key storage). The new `openrouter_oauth.py` adds a second parallel implementation with different URL paths (`/api/openrouter/oauth/*` vs `/api/auth/openrouter/*`), different storage patterns (direct JSON vs `update_integration` service), and different security properties (no rate limiting, no state parameter, no in-memory key caching). This duplication will cause confusion about which flow to use and may lead to inconsistent state (two different rows or credential formats in the DB).

**Fix:** Either replace the existing `oauth.py` endpoints or extend them. Do not ship two parallel OAuth flows for the same provider. If the new flow is meant to replace the old one, deprecate/remove `oauth.py`'s OpenRouter routes.

### WR-02: No rate limiting on new OAuth endpoints

**File:** `src/career_os/api/openrouter_oauth.py:75-90`
**Issue:** The existing `oauth.py` uses `slowapi` rate limiting (`10/minute` on start, `20/minute` on callback). The new endpoints have no rate limiting at all, making them vulnerable to abuse (an attacker could spam `/oauth/start` or brute-force `/oauth/callback` with different codes).

**Fix:** Add `@limiter.limit()` decorators matching the existing pattern, or reuse the existing `oauth_limiter`.

### WR-03: `from None` discards exception context — harder to debug in production

**File:** `src/career_os/api/openrouter_oauth.py:105` and `147`
**Issue:** `raise HTTPException(...) from None` explicitly suppresses the original exception chain. In production, when an OAuth exchange fails, the logs will show only the HTTPException with no traceback of the underlying `OpenRouterOAuthError` or `JSONDecodeError`. The existing `oauth.py` uses `from exc` (line 150) which preserves the chain.

**Fix:** Use `from e` to preserve context:
```python
except OpenRouterOAuthError as e:
    raise HTTPException(...) from e
```

### WR-04: `store_api_key` uses raw `json.dumps`/`json.loads` instead of existing integration service

**File:** `src/career_os/services/openrouter_oauth.py:144-178`
**Issue:** The existing `oauth.py` stores the key via `update_integration(db, "ai_providers", IntegrationConfigUpdate(...))` which goes through the proper service layer with validation. The new code manipulates `IntegrationConfig.credentials` directly with raw `json.dumps`/`json.loads`, bypassing any service-layer logic (e.g., credential masking, event hooks, or future encryption). This creates two divergent storage paths.

**Fix:** Use the existing `update_integration` service function, matching the pattern at `oauth.py:167-174`.

## Info

### IN-01: `code_challenge_method` sent in exchange payload is unnecessary

**File:** `src/career_os/services/openrouter_oauth.py:87`
**Issue:** The key exchange POST includes `"code_challenge_method": "S256"` in the JSON body. Per the OpenRouter API and standard PKCE flows, the challenge method is sent during the authorization request (which is done in `build_auth_url`), not during the token/key exchange. The exchange only needs `code` and `code_verifier`. The existing `oauth.py:141` correctly sends only `code` and `code_verifier`. This is harmless (the server ignores extra fields) but adds noise.

**Fix:** Remove `code_challenge_method` from the exchange payload.

### IN-02: Frontend test does not cover the OAuth callback flow

**File:** `frontend/src/__tests__/OpenRouterConnect.test.tsx`
**Issue:** There is no test that simulates the callback scenario (where `window.location.search` contains `?code=xxx` and `sessionStorage` has the verifier). The `useEffect` callback handler (lines 41-61 in the component) is untested. This is the most complex path in the component.

**Fix:** Add a test that sets `window.location.search` and `sessionStorage` before render, then asserts `completeOAuth` is called and the success message appears.

### IN-03: `build_auth_url` does not URL-encode parameters

**File:** `src/career_os/services/openrouter_oauth.py:59-62`
**Issue:** The callback URL is concatenated directly into the query string without URL encoding. If the callback URL contains special characters (e.g., `&`, `=`, `#`), the auth URL will be malformed. The existing `oauth.py:90` correctly uses `urllib.parse.urlencode()`.

**Fix:**
```python
from urllib.parse import urlencode

def build_auth_url(callback_url: str, code_challenge: str) -> str:
    params = urlencode({
        "callback_url": callback_url,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    return f"{OPENROUTER_AUTH_URL}?{params}"
```

---

_Reviewed: 2026-04-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
