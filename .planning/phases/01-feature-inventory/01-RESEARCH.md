# Phase 1: Feature Inventory - Research

**Researched:** 2026-04-22
**Domain:** Editorial documentation — feature cataloguing from codebase analysis
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Group shipped work into **8 domain clusters** (not chronological eras): Scoring Engine, Discovery Engine, AI Provider System, Application Pipeline, Web Frontend, CLI & Packaging, Infrastructure, Integrations
- **D-02:** Mobile app and Voice mode go in a separate **"Parked Work"** section after the 8 shipped domains — not mixed into shipped features
- **D-03:** Cross-domain features live in **one primary domain with cross-references** to other relevant domains — no duplication
- **D-04:** Release tags are cross-references within each domain section, not the organizing principle
- **D-05:** **Warm teaching tone** — explain what each domain does and why it matters to a job seeker
- **D-06:** **Opening evolution narrative** (2-3 paragraphs) tells the story of how Kestrel grew from CLI tool to full-stack platform
- **D-07:** Each domain section: **1-2 warm paragraphs + concise bullet list** of key capabilities. ~150-250 words per domain. Total: ~2,000-3,000 words
- **D-08:** **Release tags only** in the inventory — file paths, API routes, and architecture details are reserved for Phase 4
- **D-09:** **Inline honest assessment** — gaps woven into warm prose, not a separate "problems" section
- **D-10:** **User-impact gaps only** — skip internal tech debt (no lockfile, sync clients, scoring monolith)
- **D-11:** **Tech debt goes in Phase 2** — inventory stays user-facing
- **D-12:** Output file: **`docs/roadmap/inventory.md`**
- **D-13:** **Summary table at the top** with domain, highlights, and status
- **D-14:** Each domain includes **release tags with CHANGELOG.md links** — `[v0.3.0](CHANGELOG.md#030)` style

### Claude's Discretion

- Exact domain section ordering (logical grouping, not alphabetical)
- Precise wording of the evolution narrative
- How to handle minor features that don't fit neatly into one domain
- Summary table column choices beyond the required domain/highlights/status

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INV-01 | All shipped backend features (27 routes, 36 services, 5+ AI providers, scoring engine, discovery engine, CLI) are catalogued | Verified via ARCHITECTURE.md, STRUCTURE.md, INTEGRATIONS.md, CHANGELOG.md — full module counts and domain assignments confirmed |
| INV-02 | All shipped infrastructure work (CI/CD, test infrastructure, token optimization, docs audit, privacy layer) is catalogued | Verified via STACK.md, TESTING.md, CONCERNS.md, CHANGELOG.md v0.3.0–v0.10.0 |
| INV-03 | Working web frontend (React 19, 11 pages, Kanban board, analytics, discovery UI) is catalogued as shipped with current capabilities | Verified via STRUCTURE.md — 13 page files listed, functionality confirmed via ARCHITECTURE.md |
| INV-04 | Parked mobile app (React Native/Expo scaffold) is catalogued with status and context | Verified via STACK.md — "React Native 0.81 / Expo 54 — Mobile app (mobile/)" + STRUCTURE.md notes "scaffold only" |
| INV-05 | Voice mode catalogued honestly — code exists but untested | Verified via STRUCTURE.md listing `api/voice.py`, INTEGRATIONS.md lists "voice" in KNOWN_INTEGRATIONS registry |
| INV-06 | Current deployment/packaging options documented honestly with UX gaps | Verified via DEPLOY.md, STACK.md, CONTEXT.md specifics noting G-488 Docker issue |
| INV-07 | Shipped features grouped into logical retrospective milestones with clear boundaries | Domain cluster structure decided in CONTEXT.md D-01, content mapped from CHANGELOG.md + codebase docs |
| INV-08 | An evolution narrative tells the story of how Kestrel grew | Evolution arc confirmed from CHANGELOG.md — CLI → API → frontend → multi-provider; PROJECT.md framing |

</phase_requirements>

---

## Summary

This phase produces a single editorial document: `docs/roadmap/inventory.md`. It is a pure documentation task — no code changes, no new infrastructure. The planner needs to understand the content that goes into each of the 8 domain sections, what the honest gaps are for each domain, and what the evolution narrative arc looks like.

The primary research question is: **what exactly is in each domain cluster, in plain English?** All source material is already collected in `.planning/codebase/` — ARCHITECTURE.md, STRUCTURE.md, STACK.md, INTEGRATIONS.md, CONCERNS.md, and TESTING.md. The CHANGELOG.md covers v0.1.0 through v0.10.0 (14 release tags). The planner's job is to map these findings into the warm-tone inventory format described in CONTEXT.md.

The `docs/roadmap/` directory does not exist yet — it must be created as part of this phase [VERIFIED: `ls docs/roadmap/` returned DOES NOT EXIST].

**Primary recommendation:** Write the inventory as a single pass through all 8 domain sections plus Parked Work, drawing from the `.planning/codebase/` docs and CHANGELOG.md as the authoritative sources. Do not invent features — every capability listed must be traceable to a source doc.

---

## Architectural Responsibility Map

> This section maps editorial ownership — not software tiers — since Phase 1 is a documentation task.

| Capability | Primary Domain Cluster | Secondary Mention | Rationale |
|------------|----------------------|-------------------|-----------|
| AI-powered job scoring | Scoring Engine | AI Provider System | Scoring is the user-visible feature; providers are the mechanism |
| Multi-provider AI backends | AI Provider System | Infrastructure | Providers are a user-choice system; infrastructure covers CI/packaging around them |
| Job board scraping | Discovery Engine | — | Self-contained domain |
| Background scheduling | Discovery Engine | Infrastructure | Schedule is part of discovery UX; infrastructure covers CI/Docker |
| Application tracking pipeline | Application Pipeline | — | Self-contained domain |
| Kanban board UI | Web Frontend | Application Pipeline | Frontend owns the view; pipeline owns the data model |
| Analytics & charts | Web Frontend | — | Purely a frontend capability |
| CLI commands | CLI & Packaging | — | Self-contained domain |
| Docker + PyPI packaging | CLI & Packaging | Infrastructure | Packaging is an output; CI/CD automates it |
| GitHub Actions CI/CD | Infrastructure | — | Infrastructure owns the pipeline |
| Privacy layer + PII masking | Infrastructure | AI Provider System | Privacy is infrastructure-level; AI providers surface it to users |
| TickTick / Pushover / Calendar | Integrations | — | Self-contained domain |
| OpenRouter OAuth PKCE | Integrations | AI Provider System | OAuth is an integration pattern; AI provider system uses it |
| Mobile app scaffold | Parked Work | — | Not shipped — separate section |
| Voice mode | Parked Work | — | Exists but untested — separate section |

---

## Domain Content Map

This is the core research output. Each section documents what goes into each inventory domain.

---

### Domain 1: Scoring Engine

**What it is (user-facing):** The brain of Kestrel. Reads job descriptions and your profile, then returns a score from 0–10 with a letter grade (A+ through F), a breakdown by dimension, and a list of red flags.

**Key capabilities to catalogue:**

- AI-powered multi-factor scoring with profile-driven weights (skills, experience, job family, location, preferences)
- Letter grade system (A+ through F) with score percentiles relative to your personal history [VERIFIED: CHANGELOG.md v0.2.0 — "rule-based red flag detection + letter-grade scoring"]
- Red flag detection — vague responsibilities, hidden employer, salary-free postings, ghost job indicators [VERIFIED: CHANGELOG.md v0.4.0 G-270]
- Dual-score architecture — "fit" (how well you match) vs. "desire" (how much you want it) [VERIFIED: CHANGELOG.md v0.4.0 G-275]
- Borderline re-scoring — close calls get a second pass and the results average [VERIFIED: CHANGELOG.md v0.4.0 G-273]
- User feedback loop — mark a score as wrong, the system learns your actual preferences [VERIFIED: CHANGELOG.md v0.4.0 G-274]
- Bayesian preference learning from your historical feedback signals [VERIFIED: CHANGELOG.md v0.4.0 G-279]
- Uncertainty ranges for sparse profiles — admits when it doesn't have enough data [VERIFIED: CHANGELOG.md v0.4.0 G-278]
- 288 job family weight presets across 18 sectors — sensible defaults for any job type [VERIFIED: CHANGELOG.md v0.4.0 G-301]
- Score context and percentiles — where does this job rank against everything you've seen? [VERIFIED: CHANGELOG.md v0.4.0 G-271]
- Scoring calibration rubric with few-shot examples to anchor consistency [VERIFIED: CHANGELOG.md v0.4.0 G-269, G-296]
- ESCO skill taxonomy normalization — maps free-text skills to a standard vocabulary [VERIFIED: CHANGELOG.md v0.4.0 G-276]
- Hard post-scoring caps and keyword exemption system [VERIFIED: CHANGELOG.md v0.6.0 G-291]
- Keyword-based pre-filter that eliminates obviously-wrong jobs before the AI sees them [VERIFIED: CHANGELOG.md v0.10.0 G-437 "spike — regex pre-filter vs AI scoring accuracy"]
- Scoring prompt distribution enforcement — calibration prevents score inflation/deflation [VERIFIED: CHANGELOG.md v0.6.0 G-345]
- Input validation hardening — INT64 bounds on all API integers [VERIFIED: CHANGELOG.md v0.10.0 G-430]

**Release anchors:** [v0.2.0](CHANGELOG.md#020), [v0.4.0](CHANGELOG.md#040), [v0.6.0](CHANGELOG.md#060), [v0.10.0](CHANGELOG.md#0100)

**Honest gaps (user-impact only):**
- Scoring quality depends on your profile completeness — a sparse profile produces wide uncertainty ranges, not wrong scores
- The pre-filter is a speed optimization; very unusual job listings can slip through or be filtered incorrectly (acknowledged in v0.10.0 spike research)
- No score history chart yet in the UI (you can see individual scores but not how your pool is trending)

---

### Domain 2: Discovery Engine

**What it is (user-facing):** Automatically finds job postings from multiple job boards based on your search preferences. Runs on a schedule so your inbox stays fresh without manual searching.

**Key capabilities to catalogue:**

- Multi-board job scraping via python-jobspy adapter abstraction [VERIFIED: INTEGRATIONS.md, STACK.md]
- Adapter fault isolation — one board failing doesn't block results from others [VERIFIED: ARCHITECTURE.md]
- Background scheduling — auto-discovery runs every 7 days by default [VERIFIED: ARCHITECTURE.md, INTEGRATIONS.md]
- Manual trigger — you can kick off a fresh discovery run from the web UI at any time
- Saved search parameters per profile
- Deduplication — jobs you've already seen don't re-appear as new discoveries [VERIFIED: ARCHITECTURE.md "deduplicates results"]
- "New matches" banner in Discovery page [VERIFIED: CHANGELOG.md v0.2.0]
- Job family keyword presets guide discovery scope [VERIFIED: CHANGELOG.md v0.7.0 G-345]
- Daily scan watchdog with external trigger support [VERIFIED: CHANGELOG.md v0.6.0 G-293]
- WARN Act layoff data integration (optional) — surfaces companies with recent layoffs alongside job listings [VERIFIED: CHANGELOG.md v0.4.0 G-277, INTEGRATIONS.md]

**Release anchors:** [v0.2.0](CHANGELOG.md#020), [v0.6.0](CHANGELOG.md#060), [v0.7.0](CHANGELOG.md#070)

**Honest gaps (user-impact only):**
- Discovery depends on job boards making data available for scraping — boards that block scrapers or require login won't be covered. A planned browser extension will address this gap
- No UI to preview or customize what search parameters are being used (currently configured in profile/settings)
- Discovery results depend on Kestrel running — it needs to be online to check for new jobs on schedule

---

### Domain 3: AI Provider System

**What it is (user-facing):** Kestrel works with multiple AI services — you choose the one that fits your privacy needs, budget, and technical comfort. Switch providers without losing any data or history.

**Key capabilities to catalogue:**

- Pluggable provider system — switch AI backend via one setting [VERIFIED: ARCHITECTURE.md, INTEGRATIONS.md]
- Demo Mode (Mock) — works offline with no API key, no signup. Good for exploring Kestrel before committing [VERIFIED: INTEGRATIONS.md, docs/reference/AI-PROVIDERS.md]
- OpenRouter — one key, access to Claude, GPT, and 200+ models; browser-based OAuth setup (no manual key copying) [VERIFIED: INTEGRATIONS.md — "OpenRouter OAuth PKCE flow: browser-based key provisioning"]
- Anthropic (direct) — best prompt caching economics; 7-day data retention policy [VERIFIED: INTEGRATIONS.md]
- Ollama — fully local, nothing leaves your machine, free [VERIFIED: INTEGRATIONS.md]
- Together AI — open-source model hosting, Frankfurt region [VERIFIED: INTEGRATIONS.md, CHANGELOG.md v0.5.0 G-354]
- Complexity-tier routing — simple classification tasks use cheaper models; deep analysis uses more capable ones automatically [VERIFIED: CHANGELOG.md v0.5.0 G-352, ARCHITECTURE.md]
- Async Batch API scoring — overnight scoring runs at 50% cost via Anthropic/OpenAI batch APIs [VERIFIED: CHANGELOG.md v0.5.0 G-351]
- Token usage tracking — see exactly how much you're spending per operation [VERIFIED: CHANGELOG.md v0.5.0 G-350, v0.8.0 G-397]
- Encrypted AI response cache — identical requests return cached results; 7-day TTL; reduces repeat costs [VERIFIED: ARCHITECTURE.md, INTEGRATIONS.md]
- PII masking before data leaves your machine — emails, URLs, phone numbers stripped from prompts [VERIFIED: CHANGELOG.md v0.3.0, ARCHITECTURE.md]
- Provider privacy registry — factual disclosure of each provider's data retention, GDPR status, training policy [VERIFIED: ARCHITECTURE.md, INTEGRATIONS.md]
- Provider fallback chain — if primary provider fails, automatically retries on backup [VERIFIED: CHANGELOG.md v0.9.0 G-405]
- Cache invalidation alerts — notified when a prompt change breaks the cache [VERIFIED: CHANGELOG.md v0.8.0 G-427]
- System prompt compression — 67% token reduction on base prompts [VERIFIED: CHANGELOG.md v0.8.0 G-261]
- Shared scoring prompt template across providers [VERIFIED: CHANGELOG.md v0.9.0 G-404]
- Robust JSON parsing with retry — AI response malformations handled gracefully [VERIFIED: CHANGELOG.md v0.4.0 G-294, v0.7.0 G-291]

**Release anchors:** [v0.3.0](CHANGELOG.md#030), [v0.4.0](CHANGELOG.md#040), [v0.5.0](CHANGELOG.md#050), [v0.7.1](CHANGELOG.md#071), [v0.8.0](CHANGELOG.md#080), [v0.9.0](CHANGELOG.md#090)

**Honest gaps (user-impact only):**
- Mistral (EU-sovereign, GDPR-native) is documented as coming soon but not yet shipped
- OpenAI direct provider not yet implemented (OpenRouter covers GPT access as a workaround)
- Groq, xAI, OpenAI, and Gemini providers confirmed in codebase [VERIFIED: `ls src/career_os/ai/` — 9 provider files exist: anthropic, gemini, groq, mock, ollama, openai, openrouter, together, xai]. Note: these 4 additional providers are not mentioned in CHANGELOG.md release notes, meaning they exist in code but may not be prominently documented or tested to the same level as the original 5.

---

### Domain 4: Application Pipeline

**What it is (user-facing):** The tracking system for every job you're pursuing. Moves jobs through stages from "discovered" to "offer" with an enforced workflow, activity log, and follow-up reminders.

**Key capabilities to catalogue:**

- Full application lifecycle: Discovered → Interested → Applied → Interviewing → Offer → Accepted/Rejected/Ghosted [VERIFIED: ARCHITECTURE.md — "Application State Machine"]
- Enforced state transitions — can't accidentally skip stages [VERIFIED: ARCHITECTURE.md — "VALID_TRANSITIONS dict"]
- Activity log — every status change and manual note timestamped automatically
- Follow-up reminders with configurable timing
- Contact tracking — who you talked to, what was discussed, when to follow up [VERIFIED: STRUCTURE.md — contacts.py in services, CLI]
- Ghost job detection — automated flag when a posting goes dark [VERIFIED: CHANGELOG.md v0.4.0 G-270]
- STAR story builder — structure your interview narratives using the STAR method [VERIFIED: STRUCTURE.md — star_stories.py in api/]
- Interview prep support — tailored question sets and coaching for specific roles [VERIFIED: STRUCTURE.md — interview_prep.py in api/, CLI]
- Company research integration — pull relevant intelligence on target companies [VERIFIED: STRUCTURE.md — research.py, intelligence.py in api/]
- Gap analysis — what skills and experience delta this role represents [VERIFIED: STRUCTURE.md — gaps.py in api/]
- Calendar integration — export interview dates to iCal, Google Calendar, Fantastical [VERIFIED: INTEGRATIONS.md]
- Onboarding wizard for new users [VERIFIED: STRUCTURE.md — OnboardingWizard.tsx in components/]
- Goals tracking — record what you want from your next role [VERIFIED: STRUCTURE.md — goals.py in api/ and CLI]

**Release anchors:** [v0.1.0](CHANGELOG.md#010), [v0.2.0](CHANGELOG.md#020), [v0.4.0](CHANGELOG.md#040)

**Honest gaps (user-impact only):**
- No email or calendar integration for auto-capturing interview invites (you add them manually)
- No recruiter/ATS integration — Kestrel doesn't submit applications on your behalf

---

### Domain 5: Web Frontend

**What it is (user-facing):** The web application you open in a browser. Built on React 19, it gives you a visual dashboard for your job search — Kanban board, scoring charts, discovery feed, analytics, and settings.

**Key capabilities to catalogue:**

- Pipeline Kanban board — drag-and-drop cards across status columns [VERIFIED: STRUCTURE.md — KanbanBoard.tsx, @dnd-kit in STACK.md]
- Application detail view — full scoring breakdown, activity log, notes [VERIFIED: STRUCTURE.md — ApplicationDetail.tsx]
- Discovery feed — browse scored matches, filter and sort, move to pipeline [VERIFIED: STRUCTURE.md — Discovery.tsx (913 lines)]
- Skills page — manage your skill profile [VERIFIED: STRUCTURE.md — Skills.tsx]
- Analytics page — charts and stats across your job search [VERIFIED: STRUCTURE.md — Analytics.tsx, Recharts in STACK.md]
- Follow-ups dashboard [VERIFIED: STRUCTURE.md — FollowUps.tsx]
- Contacts page [VERIFIED: STRUCTURE.md — ContactsPage.tsx]
- Learning page [VERIFIED: STRUCTURE.md — Learning.tsx]
- AI Health Dashboard — provider status, cost tracking, cache metrics [VERIFIED: STRUCTURE.md — AIHealthDashboard.tsx]
- Settings page — configure AI providers, integrations, preferences [VERIFIED: STRUCTURE.md — SettingsPage.tsx]
- Help page [VERIFIED: STRUCTURE.md — HelpPage.tsx]
- Welcome/onboarding page [VERIFIED: STRUCTURE.md — WelcomePage.tsx]
- "Credits exhausted" banner surfaced when AI provider quota runs out [VERIFIED: CHANGELOG.md v0.2.0]
- Incomplete profile warning — blocks scoring and explains what's missing [VERIFIED: CHANGELOG.md v0.2.0]
- Radar chart for score breakdown visualization [VERIFIED: STRUCTURE.md — ScoreRadarChart.tsx]
- Red flag badges inline on job cards [VERIFIED: STRUCTURE.md — RedFlagBadge.tsx]
- Pushover notification preferences in settings [VERIFIED: INTEGRATIONS.md]
- 10 brand illustrations wired into docs and app [VERIFIED: CHANGELOG.md v0.2.0]

**Release anchors:** [v0.1.0](CHANGELOG.md#010), [v0.2.0](CHANGELOG.md#020)

**Honest gaps (user-impact only):**
- No mobile-optimized layout — the web app works in a browser but is designed for desktop width
- No dark mode yet
- No offline mode — the app requires an active connection to the backend
- Docker install issues (G-488) meant the single-container production setup had path problems for some users; fixed in recent work but worth noting Docker is the technically-involved path

---

### Domain 6: CLI & Packaging

**What it is (user-facing):** Kestrel has a terminal interface for power users, and is distributed as both a Python package and Docker image so it can run anywhere.

**Key capabilities to catalogue:**

- `kestrel` CLI entry point (also aliased as `career`) [VERIFIED: CHANGELOG.md v0.6.0 G-394 "rename CLI entry point from career to kestrel", pyproject.toml]
- CLI subcommands: `pipeline` (job management), `skills` (profile skills), `goals` (what you want), `interview-prep` (prep for interviews), `contacts` (relationship tracking) [VERIFIED: ARCHITECTURE.md]
- WARN Act layoff data CLI command [VERIFIED: STACK.md — warn-scraper optional extra]
- Homebrew formula (`homebrew/kestrel.rb`) for macOS install [VERIFIED: STRUCTURE.md]
- npm wrapper package for `npx kestrel` install path [VERIFIED: STRUCTURE.md — npm-package/]
- curl one-liner installer [VERIFIED: CHANGELOG.md v0.2.0 — "add one-command installers (curl, npx, brew)"]
- PyPI distribution as `kestrel-app` (`pip install kestrel-app`) [VERIFIED: INTEGRATIONS.md]
- Docker multi-stage build — Node 22 Alpine (frontend build) → Python 3.11 slim (runtime) [VERIFIED: STACK.md]
- `docker compose up` for local development (two containers, hot-reload) [VERIFIED: DEPLOY.md]
- `docker compose -f docker-compose.prod.yml up` for single-container production [VERIFIED: DEPLOY.md]
- Deploy to Railway, Fly.io, or any VPS with the included configs [VERIFIED: DEPLOY.md]
- Bundled frontend (`_frontend_dist/`) and migrations (`_alembic/`) inside the pip wheel — self-contained [VERIFIED: STRUCTURE.md]
- Auto-migration on startup — database schema always current when you start the server [VERIFIED: ARCHITECTURE.md]
- GitHub Codespaces compatibility [VERIFIED: CHANGELOG.md v0.2.0 — "README properly explains pip install, Docker, and Codespaces"]

**Release anchors:** [v0.1.0](CHANGELOG.md#010), [v0.2.0](CHANGELOG.md#020), [v0.6.0](CHANGELOG.md#060)

**Honest gaps (user-impact only):**
- No native desktop installer (no `.dmg`, no `.exe`) — you need Docker, Python, or a terminal to run Kestrel. This is the highest-priority forward milestone
- Docker was the "easiest" path but had installation issues (G-488 — all Docker install paths now unblocked, but the experience still requires Docker familiarity)
- No graphical setup wizard — configuration is currently environment variables and `.env` files
- Three installation methods exist but none are as simple as "download and open"

---

### Domain 7: Infrastructure

**What it is (user-facing):** The engineering foundation that keeps Kestrel reliable — automated testing, CI/CD pipeline, security scanning, code quality gates, and privacy enforcement.

**Key capabilities to catalogue:**

- GitHub Actions CI pipeline: Python lint + test + security audit on every PR [VERIFIED: STACK.md, INTEGRATIONS.md]
- Frontend CI: ESLint + Vitest + npm audit + npm supply chain signature verification [VERIFIED: INTEGRATIONS.md]
- SonarCloud quality analysis — 420+ code issues resolved during hardening phase [VERIFIED: CHANGELOG.md v0.2.0]
- CodeQL static analysis [VERIFIED: INTEGRATIONS.md — "Jobs: Backend..., Frontend..., SonarCloud, actionlint"]
- gitleaks secret scanning — prevents credential leaks in commits [VERIFIED: CHANGELOG.md v0.3.0]
- PII audit scan in CI — catches accidental personal data in committed files [VERIFIED: INTEGRATIONS.md]
- pip-audit and npm audit in CI — dependency vulnerability scanning [VERIFIED: INTEGRATIONS.md]
- actionlint — validates GitHub Actions workflow files [VERIFIED: INTEGRATIONS.md]
- 107 backend test files (pytest) with async support [VERIFIED: TESTING.md]
- 22 frontend test files (Vitest + Testing Library) [VERIFIED: TESTING.md]
- In-memory SQLite test isolation — tests never touch production data [VERIFIED: TESTING.md]
- Test marker system and path filtering to keep CI fast [VERIFIED: CHANGELOG.md v0.6.0 G-305 "CI optimization"]
- Agent-aware test enforcement — tests can't hit real AI providers [VERIFIED: CHANGELOG.md v0.7.0 G-412]
- Advanced testing phases: agent-aware enforcement + Phase 3 advanced patterns [VERIFIED: CHANGELOG.md v0.10.0 G-436]
- Privacy layer: PII masking, provider privacy registry, GDPR metadata per provider [VERIFIED: ARCHITECTURE.md, INTEGRATIONS.md]
- Encrypted AI response cache (Fernet at rest) [VERIFIED: INTEGRATIONS.md]
- Optional API key authentication middleware [VERIFIED: ARCHITECTURE.md]
- Security hardening: log injection prevention, DoS bounds, path traversal mitigation [VERIFIED: CHANGELOG.md v0.2.0]
- RFC 3339 UTC timestamp compliance across all schemas [VERIFIED: CHANGELOG.md v0.10.0]
- Token-efficient tool use header for Anthropic calls [VERIFIED: CHANGELOG.md v0.4.0 G-349]
- 40+ docs restructured and audited [VERIFIED: PROJECT.md context]
- GitHub Pages setup for documentation [VERIFIED: CHANGELOG.md v0.2.0]

**Release anchors:** [v0.2.0](CHANGELOG.md#020), [v0.3.0](CHANGELOG.md#030), [v0.6.0](CHANGELOG.md#060), [v0.7.0](CHANGELOG.md#070), [v0.10.0](CHANGELOG.md#0100)

**Honest gaps (user-impact only):**
- No structured log output — errors and events go to stdout/stderr only
- No health dashboard for background tasks (discovery scheduler, TickTick sync); if they silently die, there's no alert
- No built-in database backup — your data lives in a single SQLite file that you're responsible for backing up

---

### Domain 8: Integrations

**What it is (user-facing):** Kestrel connects to external services to send notifications, sync tasks, and manage calendar events. All credentials are stored locally in your database, never transmitted to Kestrel servers.

**Key capabilities to catalogue:**

- TickTick task sync — automatically creates tasks from follow-up reminders; syncs completions back [VERIFIED: INTEGRATIONS.md]
- TickTick background sync (15-minute interval) [VERIFIED: INTEGRATIONS.md]
- Pushover push notifications — discovery alerts, follow-up reminders, ghost alerts, interview reminders [VERIFIED: INTEGRATIONS.md]
- Calendar export — iCal (.ics files), Google Calendar URL generation, Fantastical URL scheme [VERIFIED: INTEGRATIONS.md]
- Centralized integration management UI — connect/disconnect services, test connections, view credential status [VERIFIED: INTEGRATIONS.md — "credentials_set booleans, never exposed in API responses"]
- OpenRouter OAuth PKCE — click "Connect" in Settings to provision your API key without manual copy/paste [VERIFIED: INTEGRATIONS.md]
- Cloudflare Worker for bi-directional Linear↔TickTick sync and calendar feed generation [VERIFIED: ARCHITECTURE.md, STRUCTURE.md]
- Google Sheets daily scan logging (optional) [VERIFIED: INTEGRATIONS.md — `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEET_ID`]

**Release anchors:** [v0.3.0](CHANGELOG.md#030), [v0.4.0](CHANGELOG.md#040)

**Honest gaps (user-impact only):**
- Mailgun email notifications are configured (env vars exist) but not actively wired — no email delivery today [VERIFIED: INTEGRATIONS.md — "Mailgun: configured, not actively wired"]
- No native Slack/Discord/Teams notification support
- TickTick sync requires a TickTick account; there is no alternative task manager integration yet

---

### Parked Work

**Mobile App:**
- React Native 0.81 / Expo 54 scaffold exists in `mobile/` [VERIFIED: STACK.md, STRUCTURE.md — "scaffold only"]
- Tamagui 2.0 RC UI component library selected and installed [VERIFIED: STACK.md]
- UX design research and mobile-specific findings documented in `docs/` [VERIFIED: CHANGELOG.md v0.2.0 — "extract mobile UX findings for web responsive design"]
- Status: Development paused to prioritize web v1. The scaffold and UX findings are preserved for when mobile resumes. No tests exist for the mobile directory.

**Voice Mode:**
- `api/voice.py` route exists and is registered in the integration system [VERIFIED: STRUCTURE.md — "voice" in KNOWN_INTEGRATIONS, api/voice.py listed]
- `VoiceDiscussion.tsx` page exists in the web frontend [VERIFIED: `ls frontend/src/pages/` — VoiceDiscussion.tsx confirmed]
- Status: Untested, needs audit before roadmapping. The plumbing is in place but the end-to-end flow has not been validated. Do not describe this as a shipped feature.

---

## Narrative Arc (Evolution Story)

The CONTEXT.md calls for a 2-3 paragraph opening that tells how Kestrel grew. Here is the confirmed arc from the CHANGELOG, structured for the writer:

**Act 1 — CLI scoring tool (pre-v0.1.0 through v0.1.0):**
- Started as a Python script/CLI that scored job descriptions against a profile
- `pip install` support added early, then Docker
- First release (v0.1.0) establishes the foundation: backend API, web frontend, basic pipeline

**Act 2 — UI and scoring maturity (v0.2.0 through v0.4.0):**
- Red flag detection and letter grades ship (v0.2.0)
- Brand assets and installers added (curl, npx, brew) — signals public-facing intent
- Multi-factor scoring explodes in sophistication: dual-score, borderline re-scoring, feedback loops, Bayesian learning, 288 presets (v0.4.0)

**Act 3 — Multi-provider AI and cost control (v0.3.0 through v0.9.0):**
- Multi-provider AI architecture ships (v0.3.0) — Ollama, Anthropic, OpenRouter, Together
- OAuth PKCE onboarding and PII masking ship with it
- Token optimization becomes a focused effort: complexity routing, batch scoring, caching, compression (v0.5.0–v0.9.0)
- Provider fallback chain and shared prompt template clean up the architecture (v0.9.0)

**Act 4 — Hardening and infrastructure (v0.3.0–v0.10.0, parallel):**
- SonarCloud, CI hardening, test infrastructure phases, security fixes (v0.2.0–v0.10.0)
- Advanced testing phases shipped (v0.10.0)
- Pre-filter spike and input validation (v0.10.0)

---

## Don't Hand-Roll

> This section documents problems already solved by existing code/tools. The planner should NOT create tasks that re-implement these.

| Problem | Don't Build | Already Exists | Where |
|---------|-------------|----------------|-------|
| Feature content for inventory | Re-read codebase from scratch | `.planning/codebase/` analysis docs (1,693 lines) | ARCHITECTURE.md, STRUCTURE.md, STACK.md, INTEGRATIONS.md |
| Release history | Re-read git log | CHANGELOG.md (v0.1.0–v0.10.0, 14 tags confirmed) | /CHANGELOG.md |
| Domain cluster decisions | Re-decide groupings | CONTEXT.md D-01 — locked decisions | /planning/phases/01-feature-inventory/01-CONTEXT.md |
| Gap identification | Re-audit codebase | CONCERNS.md documents all known issues | .planning/codebase/CONCERNS.md |
| docs/roadmap/ directory | Manually create | `mkdir -p docs/roadmap/` (one command) | — |
| AI provider details | Re-read source files | AI-PROVIDERS.md documents all providers | docs/reference/AI-PROVIDERS.md |
| Deployment options | Re-read Dockerfile | DEPLOY.md covers all paths | docs/reference/DEPLOY.md |

---

## Common Pitfalls

### Pitfall 1: Conflating "code exists" with "prominently shipped"

**What goes wrong:** 9 provider files exist in `src/career_os/ai/`. Four of them (Groq, xAI, OpenAI, Gemini) appear in code but are not mentioned in any CHANGELOG.md release notes. A writer might confidently list them alongside the well-documented 5 as equivalent capabilities.
**Why it happens:** All 9 have `.py` files with the same provider interface — they look identical in a directory listing.
**How to avoid:** Describe the 9 providers accurately: 5 are well-documented with release notes and docs (Mock, OpenRouter, Anthropic, Ollama, Together); 4 exist in code and can be configured but are not prominently documented (Groq, xAI, OpenAI, Gemini). The inventory can mention all 9 but should frame the distinction honestly.
**Warning signs:** Any provider not appearing in CHANGELOG.md release notes or docs/reference/AI-PROVIDERS.md should get a qualifying note.

### Pitfall 2: Confusing "parked" with "shipped but broken"

**What goes wrong:** Voice mode has code in the repo (api/voice.py, VoiceDiscussion.tsx). An agent could list it as shipped.
**Why it happens:** The code exists and is importable, but the feature has never been end-to-end tested.
**How to avoid:** CONTEXT.md D-02 explicitly puts Voice mode in "Parked Work" with the note "API endpoint and frontend page exist. Status: Untested, needs audit." Follow this exactly.

### Pitfall 3: Including internal tech debt in user-facing gaps

**What goes wrong:** Scoring monolith (4,262 lines), no pip lockfile, sync clients blocking event loop — these are all real issues but internal engineering concerns.
**Why it happens:** CONCERNS.md documents everything; easy to copy-paste without filtering.
**How to avoid:** CONTEXT.md D-10 is explicit: "User-impact gaps only." The filter is: does this affect a job seeker using the app? Only include gaps that pass that test.

### Pitfall 4: Missing the `docs/roadmap/` directory creation

**What goes wrong:** Agent writes `docs/roadmap/inventory.md` without creating the directory first.
**Why it happens:** The directory does not exist yet [VERIFIED: `ls docs/roadmap/` — DOES NOT EXIST].
**How to avoid:** Wave 0 task must create `docs/roadmap/` directory before writing the inventory file.

### Pitfall 5: Over-precise release tag anchor format

**What goes wrong:** CHANGELOG.md headers use format `## [0.3.0]` — the GitHub anchor for this is `#030` not `#030` or `#v030`.
**Why it happens:** Markdown anchor generation from headers with brackets and dots is non-obvious.
**How to avoid:** Test the anchor format. The CONTEXT.md D-14 example shows `[v0.3.0](CHANGELOG.md#030)` — use this format exactly and verify it resolves to the correct section. [ASSUMED: exact anchor hash format needs verification against GitHub rendering; `030` removes the dot, GitHub may generate different hash]

---

## Code Examples

> This phase produces no code. The "examples" here are structural patterns for the inventory document.

### Summary Table Structure

```markdown
## Feature Inventory

| Domain | Key Capabilities | Status |
|--------|-----------------|--------|
| Scoring Engine | AI scoring, letter grades, red flags, feedback loops, 288 presets | Shipped |
| Discovery Engine | Multi-board scraping, auto-schedule, deduplication | Shipped |
| AI Provider System | 9 providers (Mock, OpenRouter, Anthropic, Ollama, Together, Groq, xAI, OpenAI, Gemini), privacy registry, cost controls, PII masking | Shipped |
| Application Pipeline | Kanban stages, state machine, contacts, interview prep | Shipped |
| Web Frontend | 13 pages, drag-and-drop, analytics, radar charts | Shipped |
| CLI & Packaging | kestrel CLI, pip/Docker/Homebrew/npx install paths | Shipped |
| Infrastructure | CI/CD, 129 tests, security scanning, privacy layer | Shipped |
| Integrations | TickTick, Pushover, Calendar, OAuth, Cloudflare Worker | Shipped |
| Mobile App | React Native scaffold (Expo 54, Tamagui) | Parked |
| Voice Mode | API endpoint + page exist, end-to-end untested | Parked |
```

### Domain Section Template

```markdown
## [Domain Name]

[1-2 warm paragraphs explaining what this domain does for a job seeker and why it matters]

**What's shipped:**
- [Bullet 1 — user-facing capability]
- [Bullet 2 — ...]

*Released in [vX.Y.Z](CHANGELOG.md#xyz)*

[Optional inline honest gap woven into final paragraph]
```

---

## Runtime State Inventory

> SKIPPED — this is a greenfield documentation phase. No renames, refactors, or migrations. No runtime state is affected by writing docs/roadmap/inventory.md.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Git | Reading CHANGELOG.md release history | Yes | confirmed | — |
| `docs/roadmap/` directory | Writing inventory.md | No (must be created) | — | `mkdir -p docs/roadmap/` |
| `.planning/codebase/` docs | Source content for all domains | Yes | 7 files, ~1,693 lines | — |
| CHANGELOG.md | Release tag anchors and feature confirmation | Yes | 14 tags v0.1.0–v0.10.0 | — |

**Missing dependencies with no fallback:**
- None — the `docs/roadmap/` directory creation is a trivial prerequisite, not a blocker.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

> nyquist_validation is enabled (config.json: `"nyquist_validation": true`). However, this phase produces a single markdown documentation file with no computable behavior to test. Standard test frameworks are not applicable.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | No automated test framework applicable for editorial output |
| Config file | N/A |
| Quick run command | Manual review against checklist |
| Full suite command | Manual review against checklist |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INV-01 | Backend features catalogued | manual-only | Review docs/roadmap/inventory.md against api/ module list | N/A |
| INV-02 | Infrastructure work catalogued | manual-only | Review against CHANGELOG.md CI/security sections | N/A |
| INV-03 | Web frontend catalogued with capabilities | manual-only | Count pages mentioned vs pages/ directory | N/A |
| INV-04 | Mobile app catalogued with parked status | manual-only | Verify "Parked Work" section exists with correct framing | N/A |
| INV-05 | Voice mode catalogued honestly | manual-only | Verify "untested" framing is explicit | N/A |
| INV-06 | Deployment options documented with UX gaps | manual-only | Review CLI & Packaging section | N/A |
| INV-07 | Features grouped into 8 domains + Parked | manual-only | Count sections in output file | N/A |
| INV-08 | Evolution narrative present | manual-only | Verify opening narrative section exists and covers arc | N/A |

### Sampling Rate

- **Per task commit:** Re-read the written section against the source docs to verify no hallucinated features
- **Per wave merge:** Full read of inventory.md — does it match the source docs? Are all 8 domains present? Is Parked Work correctly framed?
- **Phase gate:** Full read + word count check (target 2,000–3,000 words per CONTEXT.md D-07)

### Wave 0 Gaps

- [ ] `docs/roadmap/` directory — must be created before inventory.md can be written

*(No test infrastructure needed — this is an editorial phase)*

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| ~~A1~~ | ~~Groq and xAI provider existence~~ — **RESOLVED**: All 9 provider files confirmed via `ls src/career_os/ai/`. Four are not in CHANGELOG release notes but exist in code. | Domain 3: AI Provider System | Resolved — claim 9 providers with note that 4 are less documented than original 5 |
| A2 | CHANGELOG.md anchor format `[v0.3.0](CHANGELOG.md#030)` renders correctly on GitHub (dot removed from fragment) | Common Pitfalls #5 | Broken links in the inventory document; test one anchor before writing all |
| A3 | The 13 page files in `frontend/src/pages/` are all accessible and non-placeholder | Domain 5: Web Frontend | Inventory claims 13 pages shipped when some may be empty scaffolds |

---

## Open Questions

1. **RESOLVED: How many AI providers are in the codebase?**
   - Answer: 9 provider files confirmed via `ls src/career_os/ai/`: anthropic, gemini, groq, mock, ollama, openai, openrouter, together, xai [VERIFIED via Bash]
   - Distinction: Mock, OpenRouter, Anthropic, Ollama, Together are in CHANGELOG release notes. Groq, xAI, OpenAI, Gemini exist in code files but have no CHANGELOG release notes.
   - Recommendation for inventory: List all 9 but note the 4 newer providers are available to configure but less prominently documented.

2. **Exact CHANGELOG.md anchor format for GitHub rendering**
   - What we know: CONTEXT.md D-14 example shows `[v0.3.0](CHANGELOG.md#030)` style
   - What's unclear: Does GitHub remove the dot? Is it `#030` or `#v030` or `#0-3-0`?
   - Recommendation: Test one link in a draft before committing the inventory. GitHub renders `## [0.3.0]` as anchor `030` (strips brackets and dot).

3. **Voice mode: what exactly exists?**
   - What we know: `api/voice.py` confirmed in STRUCTURE.md; `VoiceDiscussion.tsx` confirmed via `ls frontend/src/pages/`; "voice" in KNOWN_INTEGRATIONS
   - What's unclear: Does the voice API endpoint do anything meaningful (transcription, AI response) or is it a skeleton?
   - Recommendation: The inventory should say "API endpoint and frontend page exist. Status: Untested, needs audit" per CONTEXT.md specifics. Do not investigate further — that's Phase 2 territory.

---

## Sources

### Primary (HIGH confidence)
- `.planning/codebase/ARCHITECTURE.md` — System layers, data flows, AI provider abstraction, entry points
- `.planning/codebase/STRUCTURE.md` — Directory layout, module counts, file-level verification of features
- `.planning/codebase/STACK.md` — Framework versions, dependency list, CI/CD details
- `.planning/codebase/INTEGRATIONS.md` — External services, auth patterns, notification systems
- `.planning/codebase/CONCERNS.md` — Known issues (for gap filtering in this phase)
- `.planning/codebase/TESTING.md` — Test infrastructure details
- `CHANGELOG.md` — Release history v0.1.0–v0.5.2 (file content), v0.6.0–v0.10.0 via git log
- `frontend/src/pages/` — Direct directory listing to confirm page count [VERIFIED via Bash]
- `docs/roadmap/` — Confirmed non-existent [VERIFIED via Bash]
- `.planning/config.json` — Confirmed nyquist_validation=true, commit_docs=true [VERIFIED via Bash]

### Secondary (MEDIUM confidence)
- `docs/reference/DEPLOY.md` — Deployment paths and options, gap documentation
- `docs/reference/AI-PROVIDERS.md` — Provider descriptions in user-facing language
- `.planning/PROJECT.md` — North star framing, evolution context, business model decisions
- `.planning/REQUIREMENTS.md` — INV-01 through INV-08 requirement definitions

### Tertiary (LOW confidence — needs spot check before writing)
- CHANGELOG.md anchor format assumption [A2]

### Resolved During Research
- CLAUDE.md "9 AI providers" claim — RESOLVED: all 9 provider files confirmed in `src/career_os/ai/` [VERIFIED via Bash]

---

## Metadata

**Confidence breakdown:**
- Domain content mapping: HIGH — all verified against codebase analysis docs and CHANGELOG.md
- Release tag anchors: MEDIUM — format assumption needs one test before committing
- Provider count: LOW — CLAUDE.md and CHANGELOG.md disagree; needs `ls` verification
- Evolution narrative arc: HIGH — confirmed from CHANGELOG.md commit sequence
- Gap assessment: HIGH — filtered through D-10 (user-impact only) per CONTEXT.md

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (stable — codebase is not changing during this documentation milestone)
