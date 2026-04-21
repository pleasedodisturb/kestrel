# Project Research Summary

**Project:** Kestrel Onboarding Experience (CLI + Web UI)
**Domain:** First-run onboarding for self-hosted CLI + web application; non-developer target users
**Researched:** 2026-04-19
**Confidence:** MEDIUM-HIGH

## Executive Summary

Kestrel's onboarding must bridge a fundamental gap: the target user has never opened a terminal, yet the primary install path is `pip install`. This is solvable but requires deliberate investment at every layer — from pre-install documentation through the last tooltip of the interactive tour. Research across competing tools (gh CLI, Vercel, Linear, Figma, Nextcloud) shows that the highest-impact onboarding pattern is sequential: get users to a "scored result they recognize as real" in under 10 minutes, with every step skippable and every error explained in plain English. Kestrel can own a unique niche — no self-hosted job tool currently combines CLI wizard + local CV parsing + pre-baked demo scores + interactive web tour.

The recommended approach centers on four pillars: (1) a `kestrel init` Typer command using `questionary` for rich interactive prompts, (2) privacy-first local CV parsing with `pdfplumber` + `python-docx` + optional `spaCy` NER behind an `[cv]` extras flag, (3) pre-baked JSON fixture demo data so users see scored results before touching any API key, and (4) a Shepherd.js-powered interactive tour for the web UI (see Conflicts Resolved section for the library decision). The architecture is additive — no new services are introduced; all components integrate into existing Typer CLI, FastAPI routers, SQLAlchemy models, and React + TanStack Query patterns.

The single highest-risk area is CV parsing: PDFs are a presentation format, not a data format, and text extraction fails silently on two-column layouts, design-tool exports, and image-heavy resumes. This pitfall, combined with the non-developer audience's low tolerance for opaque errors, demands a mandatory human confirmation step after every parse and a graceful guided-questions fallback that is an equal-quality path, not a consolation prize. The second critical risk is wizard execution environment: `kestrel init` must detect non-TTY environments (Docker without `-it`, piped commands) and exit clearly rather than crash cryptically.

## Key Findings

### Recommended Stack

The stack philosophy is "use what's already there, add only what's necessary." Both the CLI (`typer`, `rich`, `rapidfuzz`) and the web frontend (`Tailwind CSS`, `lucide-react`, `react-router-dom`, `@tanstack/react-query`) already carry everything needed for onboarding UI scaffolding. Net-new dependencies are minimal: `questionary` for rich CLI prompts, `pdfplumber` + `python-docx` for local CV extraction, and Shepherd.js for the web tour. The `spaCy` NER layer must be an optional install extra (`pip install kestrel-app[cv]`) to avoid breaking non-developer setups on ARM Linux, minimal Ubuntu, or systems without C build toolchains.

**Core technologies:**
- `questionary 2.1.1`: Multi-step CLI wizard prompts — actively maintained, MIT, best pairing with Typer; InquirerPy is unmaintained since 2023
- `pdfplumber 0.11.x`: PDF text extraction — best accuracy on machine-generated PDFs (most resumes), MIT, wraps pdfminer.six with better DX; PyMuPDF is GPL-contaminated
- `python-docx 1.2.0`: DOCX extraction — de facto standard, production-stable
- `spaCy 3.8.x + en_core_web_sm` (optional): NER for name/org/location/date — 13MB model, must be an optional extra
- `Shepherd.js` (MIT): Web UI interactive tour — see Conflicts Resolved section
- `rich` + `typer` + `rapidfuzz`: Already present, no new install needed

### Conflicts Resolved

**react-joyride vs Shepherd.js — Use Shepherd.js.**

The STACK.md researcher recommended `react-joyride v3.0.2` with HIGH confidence, citing React 19 support and 6.7k+ GitHub stars. The FEATURES.md researcher explicitly flagged react-joyride as "unmaintained 9+ months, React 19 incompatible" and recommended Shepherd.js instead.

**Shepherd.js is the correct choice.** The decisive factors:

1. **Maintenance trajectory:** Shepherd.js had 170+ releases and 100+ contributors with activity through March 2026. React-joyride's last meaningful release was mid-2025; v3's "React 19 support" is listed in docs but reported broken against React 19's concurrent features in live testing.
2. **Tailwind compatibility:** Shepherd.js uses CSS class-based theming, which works natively with Tailwind's utility classes. React-joyride uses inline styles, creating friction every time a style needs overriding.
3. **License:** Both are MIT. No difference.
4. **Bundle size:** Shepherd.js ~20kb vs react-joyride ~15kb — a 5kb difference that is immaterial for self-hosted.
5. **Accessibility:** Shepherd.js has better built-in focus management; react-joyride's inline-style approach (Pitfall 13) makes accessibility overrides harder.

The STACK.md recommendation for react-joyride should be discarded. It appears to rely on the v3 changelog rather than live testing against React 19.

### Expected Features

**Must have (table stakes):**
- `kestrel init` CLI wizard — users who `pip install` and get nothing actionable leave immediately
- Post-install next-steps message — printed on first `kestrel` invocation
- CV upload (PDF + DOCX) with auto-extraction — primary data loading mechanism
- Confirmation step before saving extracted data — mandatory trust-building; never auto-accept
- Pre-baked demo data with pre-computed scores — "aha moment" without requiring API key
- Error messages as solutions — every error includes what happened, why, and what to do; no stack traces
- Skip option on every wizard step — `kestrel init --skip` must exist from day one
- Progress indicator — "Step 2/5" in CLI, stepper component in web
- Web welcome screen + route guard — redirect to `/welcome` if onboarding incomplete
- Empty state coaching on Pipeline, Discovery, Contacts, Skills pages

**Should have (differentiators):**
- Smart CV import as primary onboarding path — local parse, instant profile population
- Guided fallback with max 7 questions for CV extraction gaps
- Shepherd.js interactive tour — tooltip walkthrough of Pipeline, Discovery, Scoring
- `kestrel doctor` health check — post-setup confidence builder
- Persistent feedback button — floating bottom-right, GitHub issue pre-filled with system info
- End-of-onboarding summary — what was configured, what was skipped with exact navigation links
- "Do it later" signposting — after each skipped step, show exact navigation path
- Suggested next commands after each CLI action

**Defer (v2+):**
- spaCy NER tier — v1 uses regex-only extraction; NER is an enhancement behind optional install
- Local LLM re-parse (Ollama integration)
- In-app feedback form replacing GitHub Issues link
- Multi-language CV parsing
- `--explain` flag for non-developer terminal guidance (docs page ships first)

**Anti-features (do not build):**
- AI provider setup during onboarding
- Mandatory wizard without escape path
- Animated carousel/slideshow
- External API calls for CV parsing
- OCR for scanned PDFs
- Onboarding telemetry phoning home

### Architecture Approach

The onboarding system is a cross-cutting addition — not a new service. It introduces one new DB table (`onboarding_state`), one new API router (`/api/onboarding`), one new CLI command (`kestrel init`), new service modules (`cv_parser.py`, `demo_seeder.py`, `onboarding.py`), and a set of React components behind an `OnboardingGuard` route wrapper. The backend is the single source of truth for onboarding state; both CLI and web read/write through the same API, preventing the common failure of state living only in localStorage.

**Major components:**
1. **OnboardingState (DB model + API)** — per-profile timestamp-based checklist; tracks which steps completed/skipped; syncs CLI and web; timestamps preferred over booleans for debugging value
2. **CV Parser Service** — local-only PDF/DOCX extraction + two-tier heuristic extraction: regex (email, phone, URLs) + optional spaCy NER; shared by CLI and web via same service layer
3. **`kestrel init` CLI Wizard** — Typer command + questionary prompts; CV import + guided fallback + demo seed + Rich summary; `--skip` and `--cv` flags
4. **OnboardingGuard + WelcomeFlow (React)** — route guard redirects to `/welcome`; multi-step web wizard uses CV parser via API endpoint; separate route, not a modal overlay
5. **Demo Seeder** — loads `sample_jobs.json` fixture; idempotent; `is_demo=True` flag; UUID IDs to prevent collision with real discovery results
6. **Shepherd.js Tour Engine** — CSS-class-based tooltips on existing page elements; `isReady` guards; aria-live + focus management for accessibility
7. **Persistent Feedback Button** — fixed-position React component; v1 opens pre-filled GitHub Issue URL; no backend endpoint needed

### Critical Pitfalls

1. **CV parsing silently returns garbage** — Always show a confirmation screen after parsing; never auto-accept. Detect image-only PDFs and route to manual entry. Test with 20+ real resume formats (two-column, Canva, LaTeX, Google Docs, non-English). Design guided fallback as an equal-quality path.

2. **CLI wizard crashes in non-TTY/Docker** — Check `sys.stdin.isatty()` at wizard entry; print a clear human-readable message if not TTY. Provide `--non-interactive` flag. Document `docker run -it` explicitly.

3. **Onboarding state lost on browser close** — Persist state to backend DB after each step. Resume from last completed step on app load. localStorage as fallback for API errors only; backend is authoritative.

4. **Demo data reveals itself as fake and breaks trust** — Use realistic anonymized data across 3+ job families. Relative dates computed at display time. Clear "sample results" banner. `is_demo=True` flag on all records.

5. **spaCy/heavy NLP breaks installation** — Make spaCy an optional extra. Detect missing spaCy gracefully at runtime and explain what the user gains by installing it.

Additional pitfalls: skill matching false positives (85% threshold + exclusion pairs), error messages remaining as stack traces (build `OnboardingError` hierarchy from day one), tour accessibility (aria-live + focus management required), total time-to-value silently exceeding 10 minutes.

## Implications for Roadmap

The architecture's build-order analysis and feature dependency graph converge on 6 phases. Critical path: onboarding state foundation → CV parser → CLI wizard → demo data → web welcome flow → interactive tour + polish.

### Phase 1: Foundation — Onboarding State + Error Infrastructure

**Rationale:** Everything else reads/writes onboarding state. The `OnboardingError` exception hierarchy must exist before any other onboarding code or error handling will be retrofitted and remain incomplete. Highest leverage, lowest complexity.
**Delivers:** `onboarding_state` DB table + Alembic migration, GET/PATCH `/api/onboarding/status` router, `OnboardingError` exception hierarchy with `user_message` + `resolution` fields, post-install next-steps message
**Addresses:** Progress tracking (table stakes), error messages as solutions (table stakes)
**Avoids:** Pitfall 3 (state lost on browser close), Pitfall 11 (stack traces shown to users)
**Research flag:** Standard patterns — follows existing SQLAlchemy model and FastAPI router conventions. No additional research needed.

### Phase 2: CV Parser Service

**Rationale:** Both CLI and web consume the same parser. Building it standalone before either UI surface enables isolated unit testing and makes Phases 3 and 5 faster. CV parsing is the highest-complexity, highest-failure-risk component and needs real-resume testing time.
**Delivers:** `CVParserService` with PDF + DOCX extraction, regex-tier field extraction, `ParsedCV` Pydantic schema, confirmation/diff output helpers, graceful failure handling for image-only PDFs and unsupported formats, `POST /api/onboarding/cv` endpoint
**Addresses:** Smart CV import (differentiator), auto-extract contact info + skills (table stakes)
**Avoids:** Pitfall 1 (silent parse garbage), Pitfall 9 (DOCX silently ignored), Pitfall 12 (skill false positives)
**Research flag:** Needs a real-resume test corpus before this phase is done. 20+ diverse resume formats required. Budget for test fixture collection alongside implementation.

### Phase 3: CLI Wizard (`kestrel init`)

**Rationale:** CLI is the first touch for pip-install users. A working end-to-end CLI path before the web flow creates a ship-it checkpoint early.
**Delivers:** `kestrel init` Typer command, questionary wizard, TTY detection + `--non-interactive` flag, CV import integration, guided fallback questions (max 7, all skippable), demo seeding trigger, Rich summary + next-step suggestions, `kestrel doctor` health check, `--skip` flag
**Addresses:** CLI wizard (table stakes), health check (differentiator), suggested next commands (differentiator)
**Avoids:** Pitfall 2 (non-TTY crash), Pitfall 4 (non-dev cannot navigate CLI), Pitfall 8 (too many wrong questions), Pitfall 10 (WSL2 rendering)
**Research flag:** Wizard mechanics are standard. Non-standard gap: TTY detection in Docker needs an explicit integration test matrix — flag for QA during this phase.

### Phase 4: Demo Data

**Rationale:** Can partially parallel Phase 3. Must be complete before web welcome flow (Phase 5 Step 3 is "see demo results"). Demo data quality has outsize trust impact and is a content problem as much as a technical one.
**Delivers:** `sample_jobs.json` fixture with 10 realistic anonymized jobs across 3+ job families, `is_demo=True` flag + UUID IDs, relative date computation at display time, "sample results" banner, `DemoSeeder` service (idempotent), `POST /api/onboarding/seed-demo` endpoint, "Clear demo data" action
**Addresses:** Pre-baked demo data (table stakes + differentiator)
**Avoids:** Pitfall 5 (demo reveals itself as fake), Pitfall 17 (endpoint idempotency)
**Research flag:** No technical research gap. Content decision: ensure demo jobs include non-tech roles (marketing, operations, finance) — developer authors default to tech-only.

### Phase 5: Web Welcome Flow

**Rationale:** Depends on onboarding state (Phase 1), CV parser (Phase 2), and demo data (Phase 4). Frontend-heavy phase that requires all backend primitives to be stable first.
**Delivers:** `OnboardingGuard` route wrapper, `/welcome` route + `WelcomeFlow` container, StepCVUpload, StepProfile, StepDemo, StepComplete, `useOnboarding` TanStack Query hook, empty state coaching for all major pages, web welcome screen on first visit
**Addresses:** Web welcome screen (table stakes), empty state coaching (table stakes), CV upload UI, demo results display (differentiator), end-of-onboarding summary (differentiator), "do it later" signposting (differentiator)
**Avoids:** Pitfall 3 (backend persistence, not localStorage), Pitfall 15 (skip creates full default profile, not incomplete one)
**Research flag:** Standard React patterns. One QA gate: skip path must create a complete default profile — validate by clicking Skip then trying every dashboard action.

### Phase 6: Interactive Tour + Feedback Channel + Polish

**Rationale:** Tour must attach to existing rendered elements — genuinely cannot be built before the pages it annotates. Feedback channel is independent but logically grouped with polish.
**Delivers:** Shepherd.js tour with step definitions for Pipeline, Discovery, Scoring pages; `isReady` guards; aria-live + focus management; non-tour checklist alternative; persistent feedback button; end-of-onboarding feedback prompt; "do it later" breadcrumbs; non-developer terminal guidance docs page
**Addresses:** Interactive tour (differentiator), persistent feedback channel (differentiator), non-dev guidance (differentiator)
**Avoids:** Pitfall 7 (tour accessibility), Pitfall 13 (tour targets missing elements), Pitfall 14 (feedback channel is GitHub-only dead end)
**Research flag:** Shepherd.js + React 19 concurrent mode compatibility is unverified. Run a minimal compatibility sandbox before starting implementation. Accessibility sign-off (VoiceOver + keyboard-only) required before marking done.

### Phase Ordering Rationale

- State-first because the onboarding state model is the integration point between CLI and web — building it first prevents each surface inventing its own persistence strategy
- Parser-second because CV parsing is the riskiest component and needs isolated test time; both CLI and web consume it, so it's a shared dependency
- CLI-before-web because pip is the primary install path; having a working CLI end-to-end before building the web flow creates an early ship-it checkpoint
- Demo data in Phase 4 because it is a content problem as much as a technical one; it can run partially in parallel with Phase 3 but must be complete before Phase 5
- Tour last because attaching tooltips to elements that don't yet exist is not solvable by engineering — the elements must be rendered first

### Research Flags

Needs deeper research or careful QA during planning:
- **Phase 2 (CV Parser):** Real-resume test corpus is the gap. Plan to collect 20+ diverse resumes (format, industry, language) during this phase. Do not rely on synthetic test CVs alone.
- **Phase 3 (CLI Wizard):** TTY detection in Docker requires an explicit integration test matrix — not a research gap but a testing infrastructure gap to flag early.
- **Phase 6 (Tour):** Shepherd.js + React 19 concurrent mode compatibility is unverified. Run a minimal sandbox proof-of-concept before committing to implementation. Accessibility testing (VoiceOver, NVDA, keyboard-only) is a gate, not a checkbox.

Standard patterns (skip additional research):
- **Phase 1:** SQLAlchemy models and FastAPI routers follow well-established Kestrel codebase patterns.
- **Phase 4:** JSON fixtures + idempotent seeder is a solved pattern already used in `migration/seed.py`.
- **Phase 5:** React route guards, TanStack Query hooks, and multi-step forms are standard patterns with abundant precedent.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core choices (questionary, pdfplumber, python-docx) well-documented, MIT-licensed, actively maintained. Tour library conflict resolved with clear rationale. spaCy optional-extra strategy is sound. |
| Features | MEDIUM-HIGH | Table stakes and anti-features grounded in competitor analysis (gh CLI, Vercel, Linear, Figma, Nextcloud). Differentiator list is opinionated but defensible. |
| Architecture | HIGH | Directly grounded in reading the Kestrel codebase. All integration points identified with existing patterns. No assumptions about unknown code. |
| Pitfalls | MEDIUM-HIGH | Multiple sources corroborate each pitfall. CV parsing failures and TTY issues are well-documented in high-confidence sources. Demo data quality pitfall is informed domain knowledge. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **CV test corpus:** No standardized set of real-world resume PDFs exists. Needed before CV parser can be considered production-ready. Plan to collect 20+ diverse resumes during Phase 2.
- **Shepherd.js + React 19 concurrent mode:** Neither agent verified this in a live test. Run a minimal React 19 sandbox proof-of-concept before Phase 6 planning.
- **Non-developer usability validation:** All usability claims are developer-authored or based on SaaS product analysis. Real usability testing with a non-developer user is required before the flow is considered validated. Budget time during or after Phase 5.
- **spaCy graceful degradation UX:** Research recommends the optional-extra pattern but does not specify the exact user-facing message when spaCy is absent. This needs explicit design during Phase 2.

## Sources

### Primary (HIGH confidence)
- Kestrel codebase direct analysis (`cli/main.py`, `api/profiles.py`, `models/models.py`, `migration/seed.py`) — architecture integration points
- [Command Line Interface Guidelines (clig.dev)](https://clig.dev/) — CLI design standards
- [Carbon Design System: Empty States Pattern](https://carbondesignsystem.com/patterns/empty-states-pattern/) — empty state UX
- [NN/g: Designing Empty States](https://www.nngroup.com/articles/empty-state-interface-design/) — empty state research
- [GitHub Blog: Building Accessible GitHub CLI](https://github.blog/engineering/user-experience/building-a-more-accessible-github-cli/) — CLI accessibility patterns
- [Nextcloud First Run Wizard](https://github.com/nextcloud/firstrunwizard) — self-hosted onboarding precedent
- [Google Site Kit issue 6638](https://github.com/google/site-kit-wp/issues/6638) — real tour focus-trap accessibility bug
- [Mozilla Bugzilla 1707575](https://bugzilla.mozilla.org/show_bug.cgi?id=1707575) — onboarding accessibility failure (real bug report)
- [pdfplumber GitHub known limitations](https://github.com/jsvine/pdfplumber/issues) — CV parsing failure modes
- [spaCy installation troubleshooting](https://spacy.io/usage) — optional dependency strategy
- [questionary PyPI](https://pypi.org/project/questionary/) + [questionary GitHub](https://github.com/tmbo/questionary) — CLI wizard library validation

### Secondary (MEDIUM confidence)
- [OnboardJS: 5 Best React Onboarding Libraries 2026](https://onboardjs.com/blog/5-best-react-onboarding-libraries-in-2025-compared) — tour library comparison
- [Formbricks: 7 User Onboarding Best Practices 2026](https://formbricks.com/blog/user-onboarding-best-practices) — progressive disclosure patterns
- [Figma's Onboarding Flow (Appcues GoodUX)](https://goodux.appcues.com/blog/figmas-animated-onboarding-flow) — tooltip onboarding analysis
- [Userorbit: Best Open-Source Product Tour Libraries 2026](https://userorbit.com/blog/best-open-source-product-tour-libraries) — tour library landscape
- [Sentry User Feedback Widget](https://blog.sentry.io/user-feedback-widget-for-mobile-apps/) — feedback collection pattern
- [UserPilot: Onboarding Wizard analysis](https://userpilot.com/blog/onboarding-wizard/) — wizard pitfalls
- [Dev.to: 7 Python PDF Extractors Tested 2025](https://dev.to/onlyoneaman/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-akm) — extractor comparison
- [Appcues: 7 User Onboarding Retention Mistakes](https://www.appcues.com/blog/your-retention-problem-starts-with-these-7-user-onboarding-mistakes) — retention pitfalls
- [OnboardJS: State Persistence for Onboarding](https://onboardjs.com/blog/supabase-onboarding-persistence-onboardjs) — persistence patterns
- [UserPilot: Demo Content 101](https://userpilot.com/blog/demo-content/) — demo data quality guidance
- "input device is not a TTY" error (Harold Finch, Medium) — non-TTY crash pattern

---
*Research completed: 2026-04-19*
*Ready for roadmap: yes*
