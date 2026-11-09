# SECURITY.md — Phase 0: WXT Skeleton + Pairing + Backend Endpoints (G-1389/G-1390)

Audit of the declared STRIDE threat mitigations (plans 00-01/02/03) against the shipped
code on branch `G-1389/browser-extension`. Method: each declared mitigation was traced to
a concrete code location and its logic checked — documentation/intent was not accepted as
evidence. Implementation files are read-only; this file is the only artifact written.

**Verdict: GO for merge.** All 13 STRIDE threats + the supply-chain threat resolve to
VERIFIED (mitigate) or documented-accepted with bounded, correct dispositions. Two
non-blocking observations and one WARNING (dev-tooling CVEs) are logged below.

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-00-01 | Spoofing (capture/status) | mitigate | VERIFIED | `api/extension.py:47-61` `require_extension_token` on both routes → `verify_extension_token`; enforced independent of `AUTH_ENABLED` (dependency runs after the middleware bypass). `extension_pairing.py:192` `hmac.compare_digest`. |
| T-00-02 | Elevation (middleware bypass) | mitigate | VERIFIED | `middleware.py:26,51` bypass ONLY skips the global `AUTH_API_KEY` check; capture/status still gated per-route; `/pair` code-gated. Prefix `"/api/extension/"` has a trailing slash → `/api/extension-foo` does NOT match (`str.startswith`). |
| T-00-03 | Info disclosure (pair response) | mitigate | VERIFIED | `api/extension.py:40` `_INSTANCE_NAME = "Kestrel"` (not `settings.app_name` "Career OS"); response = brand + `__version__` only. Secret/AUTH key never in any response (`schemas/extension.py`). |
| T-00-04 | Tampering (extension token) | mitigate | VERIFIED | `extension_pairing.py:168-192` token = `b64url(issued)."b64url(HMAC-SHA256(secret,issued))`; verify splits on `.`, requires exactly 2 non-empty parts, `hmac.compare_digest` on full 32-byte digest → truncation/tamper rejected. HMAC is not length-extendable. |
| T-00-05 | Spoofing/CSRF (CORS) | mitigate | VERIFIED (see Obs-1) | `main.py:239` `allow_origin_regex` = `^chrome-extension://[a-p]{32}$`; Starlette uses `.fullmatch` (`starlette/middleware/cors.py:102`) → anchored, never `*`. `allow_origins`/`allow_credentials` untouched. JSON body forces preflight for cross-origin web pages. |
| T-00-06 | Brute force (6-digit pairing code) | accept | VERIFIED (bounded — see Accepted Risks) | No rate limit by design; bounded by localhost binding + Phase-0 token grants no data. G-1391 blocks Phase 1. Judgment sound. |
| T-00-07 | DoS (capture stub) | accept | VERIFIED | `api/extension.py:72-84` capture returns a `uuid4()` only — no DB write, no `score_job` import/call, no LLM. Trivial cost. |
| T-00-08 | Info disclosure (API token) | mitigate | VERIFIED | Token lives in `chrome.storage.local` + SW only (`lib/storage.ts`, `background.ts`); popup/options never `fetch` the backend (grep: no stray `fetch(` outside `client.ts`); requests `credentials:"omit"` (`client.ts:40`). |
| T-00-09 | Tampering (manifest permissions) | mitigate | VERIFIED | Built `.output/chrome-mv3/manifest.json`: `permissions:["activeTab","storage"]`, `host_permissions:["http://localhost/*","http://127.0.0.1/*"]`, MV3, no `<all_urls>`, no `content_scripts`, no `chrome.scripting`. |
| T-00-10 | Spoofing (backend URL) | mitigate | VERIFIED | `lib/storage.ts:16-32` `assertValidBackendUrl` allows `http://` only for localhost/127.0.0.1/[::1]; requires `https://` otherwise; throws on violation; called by `setBackendUrl`. |
| T-00-SC | Tampering (npm supply chain) | mitigate | VERIFIED (see WARNING) | Human checkpoint pre-approved; `npm audit signatures` PASS (461 verified signatures, 79 attestations) recorded in 00-02-SUMMARY.md. |
| T-00-11 | Elevation (options network path) | mitigate | VERIFIED | `options/App.tsx` uses `getBackendUrl/setBackendUrl` + `sendMessage` only; `PairingForm.tsx:29` and `HealthBadge`/`useHealth` route via `chrome.runtime.sendMessage`; no `fetch` in `options/`. |
| T-00-12 | Spoofing (backend URL field) | mitigate | VERIFIED | `options/App.tsx:42-43,90-92` surfaces `assertValidBackendUrl` throw as inline `urlError`. |
| T-00-13 | Info disclosure (pairing-code entry) | accept | VERIFIED | Code entered on the extension options page, sent only to the paired backend via the worker; not logged; `autoComplete="off"` on the input (`PairingForm.tsx:57`). |

---

## Deep-dive on the requested focus areas

### 1. Token forgery / tampering — SOUND
- HMAC-SHA256 over the ASCII issued-timestamp; secret is 256-bit (`secrets.token_urlsafe(32)`) or env-supplied.
- `verify_extension_token` (`extension_pairing.py:175-192`): rejects empty/non-str, requires exactly 2 non-empty dot-parts, catches `binascii.Error`, and compares the full digest with `hmac.compare_digest`. No length-extension exposure (HMAC), no truncation bypass (full-length constant-time compare).
- Pairing code (`_code_for_window`): `HMAC(secret,str(window))[:4] % 1_000_000`. Guessable only by brute force (see accepted risk), not by prediction — derived from the server secret.

### 2. Accepted risks — bounded correctly for Phase 0; G-1391 judgment CONFIRMED sound
- **T-00-06 (no rate limit) + no token expiry.** Both are real and both are correctly deferred:
  - **Why harmless in Phase 0:** even a *successfully* brute-forced or forged token buys nothing — `/capture` is an inert stub (no DB write, no data), `/status` returns only public brand+version. There is no data behind the token yet.
  - **Localhost boundary:** uvicorn binds `127.0.0.1` by default; a cross-origin *web page* cannot brute-force because the JSON body forces a CORS preflight that fails for non-extension origins, and no-cors mode cannot read the response.
  - **Exact conditions under which it becomes exploitable (must be closed before Phase 1):**
    1. `/capture` starts writing to the DB / triggering scoring, or `/status` exposes profile data — then a forged token grants real access.
    2. The backend is bound beyond localhost (`0.0.0.0`, reverse proxy, tunnel) — the pairing endpoint becomes remotely brute-forceable (~1M codes, no throttle, always-on code).
    3. A malicious **co-installed browser extension** can already read pair responses today (its `chrome-extension://` origin matches the broad regex, and extensions with host permissions bypass CORS entirely) — so the ~1M-guess brute force is feasible for that local actor now, but yields only a Phase-0-useless token.
  - **G-1391 (rate-limit + hardening blocking Phase 1): SOUND.** Recommend it also switch to a **single-use / user-initiated** pairing code (the current code is a continuous function of secret+window and is *always* accepted — an "always-on" guessing target), and add token expiry, before capture/status carry real data.

### 3. Middleware bypass — SOUND, one defense-in-depth note (Obs-2)
- Bypass matches `request.url.path.startswith("/api/extension/")`. Trailing slash defeats the `/api/extension-foo` prefix-confusion class.
- Only the *global AUTH_API_KEY* check is skipped; capture/status keep their per-route token dependency; the bypass returns `call_next` (normal routing), it does not short-circuit to a handler.

### 4. CORS regex — anchoring correct; breadth acceptable (Obs-1)
- `^chrome-extension://[a-p]{32}$` with Starlette `.fullmatch` is correctly anchored; a trailing `\n` fails fullmatch; `https://evil.com` cannot match. Interaction with `allow_credentials=True` is safe because the extension is cookie-less (bearer header) and the backend uses no cookies.
- **Breadth:** the regex matches *any* 32-char Chrome extension ID, not only Kestrel's. This is acceptable — extensions can already bypass CORS via `host_permissions`, and the token/pairing-code (not CORS) is the auth boundary — but see Obs-1.

### 5. Secret handling — SOUND, one minor note (Obs-3)
- `data/.extension_secret` created via `write_text` then `os.chmod(0o600)` (`extension_pairing.py:94-97`). Never logged, never returned in any response (grep: no logger/print of secret or token in the backend module; `_instance_info` returns brand+version only).
- Env `EXTENSION_TOKEN_SECRET` read from `os.environ`, used only as HMAC key.

### 6. Extension side — SOUND
- Token confined to SW + `chrome.storage.local`; UI (popup/options) talks only to the worker via `sendMessage`; `client.ts` is the sole `fetch` site, always `credentials:"omit"`, token in `Authorization: Bearer`, never in a URL/query. Manifest has no `<all_urls>`, no content scripts, narrow permissions.

---

## New findings (not in the threat register)

- **WARNING — dev-tooling CVEs (unregistered, non-blocking).** `npm install` reported
  `11 vulnerabilities (1 low, 2 moderate, 5 high, 3 critical)` in transitive dev
  dependencies (e.g. esbuild dev-server advisory), per 00-02-SUMMARY.md. These are
  known-CVE advisories in build-only tooling, distinct from the T-00-SC *signature/forgery*
  threat (which PASSED). They do not ship in the extension bundle and do not block this
  foundation phase, but should be tracked and tightened (dependabot / `npm audit fix`)
  before any code from these tools runs in a less-trusted context. Recommend a follow-up
  ticket.

- **Obs-1 (CORS breadth, informational).** Regex admits every Chrome extension origin.
  Harmless today (token is the boundary; host_permissions already bypass CORS) — noted so
  a future reviewer does not mistake CORS for the extension-identity control.

- **Obs-2 (path normalization, defense-in-depth).** The bypass evaluates the raw
  `request.url.path`; Starlette does not collapse `..`, and no protected route matches a
  `/api/extension/../…` literal, so there is no bypass-to-protected-route. Safe today;
  would warrant re-check only if a normalizing reverse proxy is placed in front.

- **Obs-3 (secret file perms window, minor).** Brief window between `write_text` and
  `os.chmod(0o600)` where the file exists at umask perms; single-user localhost makes this
  negligible. Optional hardening: `os.open(..., 0o600)` / `open(..., opener=)`.

---

## Accepted Risks Log

| ID | Risk | Bound in Phase 0 | Must close before |
|----|------|------------------|-------------------|
| T-00-06 | 6-digit pairing code, no rate limit, always-on | Token grants no data (capture stub, status non-sensitive); localhost binding; web-origin preflight blocks browser brute force | Phase 1 (G-1391): rate-limit + single-use code + token expiry |
| (token no-expiry) | Minted token valid until secret rotated | Same as above; revoke = rotate `EXTENSION_TOKEN_SECRET` | Phase 1: add expiry / revocable store |
| T-00-07 | Capture-stub DoS | No DB/LLM cost in stub | When capture does real work (add input size limits + rate limit) |
| T-00-13 | Pairing code shown on user's own instance | Not logged/transmitted except to paired backend | n/a (accepted) |

---

## Closed / Open

- **Closed (VERIFIED or documented-accepted): 14/14** (T-00-01..13 + T-00-SC).
- **Open (BLOCKER): 0.**
- **Warnings: 1** (dev-tooling CVEs — track, non-blocking).
