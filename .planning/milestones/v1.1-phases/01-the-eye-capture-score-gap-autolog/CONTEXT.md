# Phase 1 Context — THE EYE (capture + inline score + gap + auto-log)

*Milestone: browser-extension · Ticket: G-1391 · Author: Claude (autonomous) + prior user decisions, 2026-07-21 · Builds on merged Phase 0 (PR #470)*

## Phase goal
One button on any job posting scrapes it, pushes it to Kestrel, scores it inline with a plain-language fit gap, adds it to the pipeline, and auto-logs an application on submit. **This is the v1 committed deliverable — the payoff.** Companion, review-first; NEVER blind auto-apply.

## Phase 0 foundation to build on (merged, live)
- `POST /api/extension/pair` (dedicated stateless-HMAC token), `POST /api/extension/capture` (STUB — this phase makes it real), `GET /api/extension/status`. Token via `Authorization: Bearer`; CORS `^chrome-extension://[a-p]{32}$` credential-less; middleware bypass scoped to `/api/extension/`.
- Extension: WXT+React19+TS-strict MV3, background service worker = sole backend caller (`extension/lib/api/client.ts`), typed message API (PAIR/CAPTURE/HEALTH/STATUS), options/pairing page + health badge, `extension/lib/storage.ts`.

## PART A — Pairing hardening (BLOCKING prerequisite, from G-1390 review + G-1391)
Phase 0 shipped an inert capture stub, so the pairing path was accepted as-is. **Before capture carries real profile data, harden it.** Autonomous security defaults (planner/executor: implement these; flag if a better option emerges):
1. **Rate-limit `POST /api/extension/pair`** with `slowapi` (already a dep, used on OAuth routes): default **5 attempts / minute / IP** → 429. Kills the ~10⁶ brute-force on the 6-digit code.
2. **Single-use, user-initiated pairing code.** Replace the always-valid time-windowed code with a **random one-time code minted on demand** by `kestrel extension pair`: store its hash + expiry (~2 min) in `data/.extension_pairing` (0600, atomic create — mirror `.extension_secret`; **NO Alembic migration**), `/pair` validates + marks used (single-use), regenerate on each CLI call. Closes the always-on guessing window.
3. **Token expiry.** The stateless HMAC token already embeds issued-ts; add a max-age check in `verify_extension_token`. Default TTL **30 days** (new setting `extension_token_ttl_days`, configurable); expired → 401 "re-pair". Revocation remains secret-rotation (documented); a persisted revocable store stays a later upgrade. **← FLAG: confirm 30d TTL + that a file-based single-use nonce (vs a DB table) is acceptable; both avoid a migration.**
4. Update `tests/test_extension_api.py`: rate-limit 429, single-use code rejects reuse, expired token 401, valid flow still works.

## PART B — Capture → real scoring (the eye, backend)
5. **Make `/api/extension/capture` real.** Accept the extension payload (normalized fields OR raw JD text), create/**dedupe** a job, and score it by REUSING `services.scoring.score_job(db, profile_id, job_description, *, job_url, job_title, job_company, discovered_job_id, application_id) -> ScoredJob` — do NOT reimplement scoring or the prompt. Return the score + full breakdown + a plain-language gap.
   - **No standalone JD-parse endpoint exists** — raw JD goes straight into `score_job`; discovery normalization lives in `discovery/adapters.py → RawJobResult`. Follow that shape for the captured job.
   - **LLM extraction fallback:** if the payload is raw text (client couldn't get structured data), the backend uses the configured `AI_PROVIDER` to extract company/title/JD before scoring. Keep it one provider call; mock in tests.
6. **Add-to-pipeline** reuses `POST /api/jobs/{job_id}/promote` (discovered/scored job → Application). Capture returns enough for the extension to offer one-click promote.
7. **Update the guard test** `test_capture_does_not_import_score_job` — capture now legitimately scores; change it to assert scoring goes THROUGH `services.scoring` (not a reimplementation), rather than asserting absence.

## PART C — The eye (extension)
8. **One-button capture** — popup button + a floating in-page button on recognized job pages. Content script does **tiered extraction**: JSON-LD `JobPosting` → OpenGraph/meta → raw-text (send to backend for LLM parse). Extracts company/title/JD/salary/location/url. **User-action-only** on the viewed page — no bulk/background crawl (ToS + ghost-repost trap).
9. **Inline score + breakdown + gap presentation.** Render Kestrel's score + breakdown + plain-language gap ("missing: Kubernetes, Go; seniority ✓"). **← DESIGN CHOICE (flag): MV3 `sidePanel` (persistent companion, Chrome 140+) vs a transient in-page overlay.** Default recommendation from the domain refresh: **sidePanel as the primary surface** + a lightweight in-page trigger button. Confirm feasibility in WXT; fall back to an in-page overlay if sidePanel complicates Phase 1.
10. **One-click add-to-pipeline** from the panel (calls promote via the worker).
11. **Auto-log-on-submit** — detect an application submit on a recognized ATS (Greenhouse/Lever/Ashby to start) and create/advance the pipeline entry, with a **visible, dismissible confirmation** (never silent — Simplify's silent behavior is the anti-pattern).

## Scope
**In:** pairing hardening (A), real capture+scoring+dedupe+LLM-fallback (B), one-button capture + tiered extraction + score/gap panel + add-to-pipeline + auto-log (C). Tests both sides.
**Out (later phases):** form autofill / fill-report (Phase 2), screening-answer gen (Phase 3), scraping Simplify/Jobgether/boards (Phase 4), Workday (Phase 5), Firefox/Safari (Phase 6). NO autofill or form-writing anywhere in Phase 1.

## Constraints
- PUBLIC repo, no PII; competitor research stays in gitignored `private/`.
- Reuse existing scoring/discovery/promote services — no reimplementation.
- Tests per change (pytest + vitest). No `<all_urls>`, no telemetry, companion-only (no auto-submit).
- Branch-per-phase off `main`, worktree required, no direct main commits, 3-pass review (code + security + test) before merge.
- Keep the Phase 0 CORS/auth model intact; don't widen it.

## Reference
- `private/research/2026-07-web-extension/SYNTHESIS.md` + `landscape-and-architecture.md` (extraction tiers), `private/research/2026-07-domain-refresh/03-extension-capabilities.md` (sidePanel, auto-log), `COMPARISON.md` (positioning).
- `.planning/codebase/ARCHITECTURE.md` (Extension Reuse Map), `.planning/intel/api-map.json` (`extension_integration_surface`).
- Phase 0 artifacts in `.planning/phases/00-wxt-skeleton-pairing-backend-endpoints/` (CONTEXT/SUMMARY/SECURITY — the pairing/token design being hardened here).

## Success criteria (from ROADMAP Phase 1)
1. One-button capture (popup + in-page) with tiered extraction (JSON-LD → OG → raw+LLM).
2. Capture POSTs to `/api/extension/capture`, deduped + scored via `score_job`, returns score + breakdown.
3. Inline score + breakdown + plain-language gap on the posting (or sidePanel).
4. One-click add-to-pipeline; auto-log-on-submit with visible confirmation.
5. User-action-only capture; tests green on LinkedIn + a Greenhouse posting.
PLUS (Part A): pairing rate-limited, code single-use, token expires — all tested.
