# Phase 0 Context — WXT skeleton + pairing + backend endpoints

*Milestone: browser-extension · Ticket: G-1390 · Author: user + Claude, 2026-07-21*

## Phase goal
A loadable MV3 browser-extension skeleton (WXT + React 19 + TS-strict) that pairs to a running Kestrel instance over an authenticated, CORS-correct channel, with the backend `pair` + `capture`-stub endpoints in place. **Foundation only — no product features** (no capture UI, no scoring overlay, no autofill).

## Locked decisions (do not re-litigate)

### From milestone research (G-1385 → SYNTHESIS.md)
- **Build tool: WXT** (Vite-based). Matches Kestrel's React 19 + Vite + TS-strict. Not Plasmo (maintenance), not CRXJS (shaky).
- **Manifest V3**, narrow permissions: `activeTab`, `storage`, explicit `host_permissions` for the paired backend URL only; long-tail sites via `optional_host_permissions`. **NEVER `<all_urls>`** (that is Simplify's privacy underbelly).
- **All extension→backend network calls originate in the background service worker.** Content scripts / popup never fetch the backend directly (mixed-content / Local Network Access / key isolation).
- **No telemetry** of any kind ships by default.
- **Companion posture** — no auto-submit logic anywhere in the codebase, now or later.

### Phase-0 decisions locked with the user (2026-07-21)
1. **Auth = dedicated pairing token.** The extension obtains its OWN API key/token via a `POST /api/extension/pair` flow, stores it in `chrome.storage`, and sends it as an auth header on every call. This is separate from the global `AUTH_API_KEY`. CORS allows `chrome-extension://` origins **credential-less** (token in header, not cookies) — avoids the `allow_credentials=true` + wildcard trap.
2. **Security posture = always require a paired token**, even on localhost. Most secure; the ~one-time pairing step on first run is acceptable friction. The extension will not call the API without a token.
3. **Package layout = separate top-level `extension/` package** with its own `package.json`, `wxt.config.ts`, and npm scripts. Isolated from `frontend/`; the two build systems stay independent.

## Integration surface (from refreshed intel + codebase map, 2026-07-21)
- **CORS today** (`main.py`): `CORSMiddleware`, `allow_origins` derived from `FRONTEND_URL` (default `localhost:8101`, `*` for wildcard), `allow_credentials=true`. The extension work must add a **`chrome-extension://` allowance without relying on credentialed wildcard** — prefer `allow_origin_regex="chrome-extension://.*"` on the extension routes, credential-less (token via header). Reconcile carefully with the existing middleware (see CONCERNS.md: "CORS wildcard + credentials" is a flagged open risk — do not widen it).
- **Auth today**: `APIKeyAuthMiddleware` (HMAC timing-safe compare, gated by `AUTH_ENABLED`) with `_PUBLIC_PATHS` bypass list. The extension's `pair` endpoint needs a defined auth story: pairing itself must be reachable to establish the token (bootstrap), then `capture` requires the token. Decide the bootstrap (e.g. one-time pairing code shown in the Kestrel UI/CLI, or pair against the existing AUTH_API_KEY once to mint an extension token). Recommend: pairing exchanges a short-lived code / the existing key for a stored extension token; document the chosen bootstrap.
- **Capture reuse (Phase 1, stubbed here)**: `services/scoring.py::score_job(db, profile_id, job_description, *, job_url, job_title, job_company, discovered_job_id, application_id) -> ScoredJob`. Scoring-v2 added ZERO new HTTP routes. There is **no standalone JD-parse endpoint** — raw JD normalizes via `discovery/adapters.py -> RawJobResult`. Phase 0 only stubs `/api/extension/capture` (accept normalized payload, return 200 + job id); wiring to `score_job` is Phase 1.
- **New route module**: `src/career_os/api/extension.py`, registered in `main.py`, following the parallel-naming + `Annotated[Session, Depends(get_db)]` conventions (see CONVENTIONS.md).

## Scope

### In scope (Phase 0)
- `extension/` WXT + React 19 + TS-strict project; MV3 manifest; background service worker; options/pairing page.
- `chrome.storage` persistence of backend URL (default `http://localhost:8100`) + paired token; health-check UX (connected / backend-down / bad-key).
- Backend: `POST /api/extension/pair` (bootstrap → mint/validate extension token), `POST /api/extension/capture` **stub** (accept payload, return 200 + id), CORS for `chrome-extension://` (credential-less), registered router.
- Tests: pytest for pair (valid/invalid/bootstrap), capture stub, CORS preflight; extension unit tests (WXT/vitest) for pairing/storage/health-check.

### Out of scope (later phases)
- Any capture extraction, scoring overlay, gap UI, auto-log (Phase 1).
- Any autofill, selector-config, fill report (Phase 2+).
- Wiring `capture` to `score_job` (Phase 1).

## Constraints
- PUBLIC repo — no PII; competitor teardown stays in gitignored `private/`.
- Tests per change (backend pytest + extension vitest). No `<all_urls>`, no telemetry.
- Branch-per-phase off `main`, **worktree required** (worktree already created: `~/.claude/worktrees/kestrel/G-1389-browser-extension`, branch `G-1389/browser-extension`). No direct main commits. 3-pass review before merge.
- Do not widen the existing CORS credentialed-wildcard risk; the extension path must be the tighter one.

## Reference docs
- `private/research/2026-07-web-extension/SYNTHESIS.md` (copy/drop matrix + architecture), `landscape-and-architecture.md` (WXT/MV3/backend-integration deep dive), `simplify-crx-teardown.md` (permission/architecture reference).
- `.planning/codebase/ARCHITECTURE.md` (Extension Reuse Map), `INTEGRATIONS.md` (CORS/auth section), `CONCERNS.md` (extension risk section), `.planning/intel/api-map.json` (`extension_integration_surface` + `cors` blocks).

## Success criteria (from ROADMAP Phase 0)
1. `cd extension && npm run build` → loadable MV3 unpacked extension, zero `<all_urls>`.
2. Options/pairing page stores URL + token in `chrome.storage`; health check shows connected / backend-down / bad-key.
3. All backend calls via the background service worker.
4. `POST /api/extension/pair` validates/mints token; `/api/extension/capture` stub returns 200 + id; reachable from `chrome-extension://` (CORS regex, credential-less); tested.
5. No default telemetry; `grep -r all_urls extension/` empty; `pytest -k extension` + `cd extension && npm run test` green.
