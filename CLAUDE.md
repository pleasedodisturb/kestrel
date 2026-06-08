# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kestrel** is an AI-powered, self-hosted job search platform with a REST API and web frontend:

| Component | Location | Stack | Dev Port |
|-----------|----------|-------|----------|
| Backend API | `src/career_os/` | Python 3.11+, FastAPI, SQLAlchemy, SQLite | 8100 |
| Web Frontend | `frontend/` | React 19, Vite, TypeScript, Tailwind CSS | 8101 |

The Python package is internally named `career_os` (historical). PyPI name is `kestrel-app`.

A native mobile app is planned but **not yet in this repo** — there is no `mobile/` directory today.

This file does not restate global rules — read `~/.claude/CLAUDE.md` first.

## Development Commands

### Backend
```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head

# Run
uvicorn career_os.main:app --port 8100 --reload

# Test
pytest tests/ -v                          # all tests
pytest tests/test_skills_api.py -v        # single file
pytest tests/ -v --cov=src/career_os      # with coverage
pytest tests/ -k "test_name"              # single test by name

# Lint & Format
ruff check src/ tests/                    # lint
ruff check --fix src/ tests/              # auto-fix
ruff format src/ tests/                   # format
ruff format --check src/ tests/           # check only
```

### Web Frontend
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev                               # Vite dev server (port 8101)
npm run build                             # TypeScript check + Vite build
npm run test                              # Vitest (all tests)
npx vitest run src/__tests__/File.test.tsx # single test file
npx eslint src/                           # lint
npx eslint --fix src/                     # auto-fix
```

### Docker
```bash
docker compose up                         # dev: backend + frontend
docker compose -f docker-compose.prod.yml up  # production: single container
```

## Architecture

### Backend: Layered Architecture
```
API Routes (src/career_os/api/)     → HTTP handling, Pydantic validation
    ↓
Services (src/career_os/services/)  → Business logic, domain exceptions
    ↓
Models (src/career_os/models/)      → SQLAlchemy ORM definitions
    ↓
Database (database.py, config.py)   → SQLite (WAL mode), async via aiosqlite
```

- **AI Provider Abstraction** (`src/career_os/ai/`): Factory pattern — `AI_PROVIDER` env var selects provider. 11 providers: Mock, OpenRouter, Anthropic, OpenAI, Together, Groq, xAI, Gemini, Ollama, Mistral, HuggingFace. All implement `complete()` and `score()` async methods. Fallback chain via `AI_PROVIDER_FALLBACK`.
- **Cost Presets** (`src/career_os/services/presets.py`): One setting (Free/Budget/Quality/Private/Custom) configures provider, model, pre-filter aggressiveness, and batch size. Default: Budget (~$0.81/mo). API: `GET/PUT /api/presets/active`.
- **Pre-filter** (`src/career_os/discovery/prefilter.py`): Eliminates ~60% of jobs before AI scoring. Configurable: `PREFILTER_STRATEGY=strict|moderate|off`.
- **Batch Scoring** (`src/career_os/services/batch_scoring.py`): 10 jobs per prompt. `BATCH_SCORING_SIZE` env var. Fallback to individual on parse failure.
- **Async Batch API** (`src/career_os/services/async_batch.py`): Anthropic + OpenAI Batch APIs for nightly scoring at 50% off. API: `POST /api/score/batch/submit`.
- **Discovery Engine** (`src/career_os/discovery/`): Scrapes multiple job boards via python-jobspy. Adapters normalize results. Pre-filter runs before scoring. Scheduler runs as asyncio background task during app lifespan.
- **Application State Machine**: Status transitions enforced in `src/career_os/schemas/applications.py` via `VALID_TRANSITIONS` dict (not in service layer).
- **Schemas parallel API routes**: Each domain (applications, skills, contacts...) has matching files in `api/`, `services/`, `models/`, `schemas/`.
- **CLI** (`src/career_os/cli/`): Typer-based, entry points `kestrel` and `career` in pyproject.toml. Subcommands: pipeline, skills, goals, interview-prep, contacts.
- **Auto-migration**: Alembic runs automatically on app startup via `_auto_migrate()` in `main.py`.

### Web Frontend
- **Routing**: React Router DOM (SPA), pages in `frontend/src/pages/`
- **Data fetching**: TanStack React Query with hooks in `frontend/src/api/`
- **Path alias**: `@/*` maps to `frontend/src/` in both TypeScript and Vite
- **Dev proxy**: Vite proxies `/api/*`, `/health`, `/docs`, `/openapi.json` to backend on port 8100

### Cross-Cutting
- Both frontends consume the same REST API (documented at `/docs` Swagger, `/redoc`)
- Profile ID scopes all data (multi-user isolation in single instance)
- Optional API key auth (`AUTH_ENABLED=true`, `AUTH_API_KEY=...`)

## Key Configuration

- `pyproject.toml` — Python deps, Ruff config (line-length=100, select E/F/I/UP/B/SIM), pytest config
- `frontend/vite.config.ts` — Vite bundler, dev proxy, React plugin
- `.env` / `.env.example` — Backend environment variables
- `.github/workflows/ci.yml` — CI: Python lint+test, frontend lint+test, CodeQL, PII scan

## Browser routing (2026-05 matrix)

When an *agent session* needs to navigate, scrape, or fill a web page, use these tools in priority order. Fall through to the next tier when the previous fails. Empirical ranking from a Docker-sandboxed 49-attempt sweep on 2026-05-21 (top to bottom = most-correct to least-correct on this corpus; full methodology + numbers in the [web-agent-comparison repo](https://github.com/pleasedodisturb/web-agent-comparison)).

| # | Tool | Use for | Notes |
|---|------|---------|-------|
| 1 | **WebFetch** (built-in, no MCP) | Static-HTML reads — JD pages, "About" pages, blog posts | ~20× more token-efficient than browser snapshots. First choice for read-only public content. |
| 2 | **Playwright MCP** (`@playwright/mcp`) | Interactive agent-driven flows (default driver) | 28 tools, accessibility-tree representation, deterministic. The baseline. |
| 3 | **chrome-devtools MCP** (`chrome-devtools-mcp`) | DevTools-aware work — network panel, perf traces, console | Official ChromeDevTools team. Needs local Chrome/Brave. |
| 4 | **browser-use** (`browser-use --mcp`) | Python-agent flows; high-level extract/act primitives | ~95K-star framework. Direct mode = no LLM key needed. Adds session management on top of Playwright primitives. |
| 5 | **Obscura** (`obscura-mcp`) | Low-RAM stealth scraping — server-rendered or CDP-driven | Rust engine, ~30 MB RAM/tab, anti-fingerprint built in. Container arch packaging is fragile mid-2026 — runs cleanly on macOS host. |
| 6 | **CloakBrowser** (`cloakbrowsermcp`) | Fingerprint-blocked sites (Workday, Cloudflare-protected ATSes) | Patched-Chromium with ~58 C++ stealth patches. **Sandbox only** — closed binary touches cookies, never point at an authenticated session. |
| 7 | **Firecrawl** (`firecrawl-mcp`) | Token-optimised cloud markdown scraping | 96% coverage / 0.638 F1 on 1000-URL benchmark, ~7s avg. Needs `FIRECRAWL_API_KEY`. |
| 8 | **Lightpanda** (`lightpanda mcp`) | Server-rendered HTML only, ~1.8s/page, tiny RAM | Zig engine. SPA/React pages return empty (by design). MCP subcommand verified working on darwin-aarch64 as of 2026-05-21. |
| 9 | **BrowserMCP** (`@browsermcp/mcp`) | Authenticated host pages (LinkedIn, Greenhouse with real cookies) | Project-level `.mcp.json` only. Needs a Chrome Agent profile. **Never use on banking or credential pages** — content goes to the model provider's API. |

**Removed / superseded:** `vercel-labs/agent-browser` (project unmaintained mid-2026; superseded by browser-use direct mode + Playwright MCP).

**Note for `tools/*.py`:** the raw `playwright.sync_api` / `playwright.async_api` imports in batch scripts are correct as-is — those are server-side automation, not agent-driven. The matrix above governs *agent sessions* (Claude Code interactions, MCP tool calls).

## Workflow Rules

### Commits
- **Every commit uses conventional commit format** — `type(scope): description` where the scope includes the Linear ticket ID (e.g., `feat(G-97): add onboarding flow`, `fix(G-265): re-add gitignore entries`). Valid types: `feat`, `fix`, `chore`, `ci`, `deps`, `docs`, `build`, `perf`, `refactor`, `revert`, `style`, `test`.
- **Commit messages must have a body** — title + blank line + explanation of what changed and why
- **Commit after every logical unit of work** — don't batch unrelated changes
- **Push after committing on non-main branches** — work happens across multiple machines/sessions

### Testing
- Every piece of code must have tests. Write tests alongside the code, not after.
- Backend: pytest in `tests/`, Frontend: Vitest in `frontend/src/__tests__/`
- Run tests after writing them to confirm they pass.
- **Full testing standards:** `docs/reference/TESTING.md` (backend rules, mocking decision tree, marker usage)
- **Testing strategy & history:** `docs/reference/testing-strategy.md` (what shipped, what was trimmed, rationale)
- **Frontend testing rules:** Mock at API boundary (`@/api/*`), never mock hooks or react-router-dom. Use `renderWithProviders` from `@/test-utils` (provides QueryClient + MemoryRouter). Use `importOriginal` when mocking modules that export constants alongside functions.

### Code Style
- **Python**: Ruff handles linting + formatting. `ruff check --fix` then `ruff format`.
- **TypeScript**: ESLint with strict mode. `npx eslint --fix src/`.
- **Python line length**: 100 chars. **TypeScript**: no explicit limit.
- **Imports**: Python groups by stdlib/third-party/local. TypeScript uses `type` keyword for type-only imports.
- One React component per file. Python: one class or major function per service module.

### Task Tracking
- All work serves a Linear ticket (team: G). GitHub Issues are NOT used for task tracking.
- <!-- maintainer-specific --> Linear CLI: `linearis` (or `~/.config/linear-cli.sh`). Fork maintainers: replace with your own task tracker.

## Planning & Workflow Tooling

Two workflow systems are installed: **GSD** (execution) and **BMAD** (product planning). Both are long-running project infrastructure — committed independently, not bundled with feature work.

### GSD (Get Shit Done)

**Installation:** Global (`~/.claude/skills/gsd-*/`). Available in all projects automatically.
**State directory:** `.planning/` (created on first use, gitignored)
**Auto-generated context:** `GSD-CLAUDE.md` (gitignored) — this hand-maintained `CLAUDE.md` is the source of truth

Before making repo edits, start work through a GSD command:

| Command | Use when |
|---------|----------|
| `/gsd-quick` | Small fixes, doc updates, ad-hoc tasks |
| `/gsd-fast` | Trivial inline tasks, no subagents |
| `/gsd-debug` | Investigation and bug fixing |
| `/gsd-plan-phase` | Plan a phase before execution |
| `/gsd-execute-phase` | Execute planned phase work |
| `/gsd-discuss-phase` | Gather context before planning (use `--chain` for discuss→plan→execute) |
| `/gsd-autonomous` | Run remaining phases unattended |
| `/gsd-progress` | Check project status and next action |
| `/gsd-resume-work` | Resume from a previous session |
| `/gsd-help` | Full command reference |

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.

### BMAD (Build More, Architect Dreams)

**Installation:** Per-project in `_bmad/` (config) and `.claude/skills/bmad-*/` (skills). Version 6.3.0.
**Output directory:** `_bmad-output/` (PRD, architecture docs, etc. — created on first use; configured in `_bmad/bmm/config.yaml`)
**Config:** `_bmad/bmm/config.yaml` (project name, user, languages, output paths)

BMAD drives the product planning pipeline: PRD → UX Design → Architecture → Epics → Stories.

| Command | Use when |
|---------|----------|
| `/bmad-create-prd` | Create a new PRD from scratch (13-step guided workflow) |
| `/bmad-edit-prd` | Edit an existing PRD |
| `/bmad-validate-prd` | Validate a PRD against BMAD quality standards |
| `/bmad-create-ux-design` | Plan UX patterns and design specs |
| `/bmad-help` | See available BMAD skills and recommendations |
| `/bmad-party-mode` | Multi-agent roundtable discussion |
| `/bmad-advanced-elicitation` | Push LLM to reconsider/refine output (Socratic, red team, etc.) |
| `/bmad-brainstorming` | Facilitated ideation sessions |

**Step-file workflow:** Each BMAD workflow (e.g., create-prd) uses sequential step files in `steps-c/`. Steps are loaded one at a time, executed in order, with A/P/C menus (Advanced Elicitation / Party Mode / Continue). Never skip steps or load multiple simultaneously.

**History:** BMAD was first installed via G-225 (Ollama provider) but got collateral-damaged when that commit was reverted. Reinstalled independently via G-265 to prevent recurrence.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Kestrel Public Roadmap**

A public, demo-ready roadmap for Kestrel — the AI-powered, self-hosted job search platform — that lives on GitHub as the single source of truth for where the product is and where it's going. The roadmap documents everything shipped, lays out the forward vision, and becomes the backbone of a structured planning hierarchy: roadmap → BMAD PRDs → milestones → epics → Linear tickets.

**Core Value:** Make Kestrel's direction visible and structured so users can evaluate the product, contributors can pick meaningful work, and development stays coherent across sessions and milestones.

### Constraints

- **Format**: ROADMAP.md at repo root (GitHub-rendered Markdown), docs/roadmap/ for depth
- **Audience**: Must be readable by non-technical users evaluating the product, developers wanting to contribute, and the maintainer for cross-session planning
- **Accuracy**: Every claim about shipped features must be verifiable against codebase
- **Structure**: Must support future BMAD PRD integration — milestones and epics as plug-in points
- **No code changes**: This milestone is documentation and planning only
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ — Backend API, CLI, AI providers, discovery engine (`src/career_os/`)
- TypeScript 6.0 — Web frontend (`frontend/`)
- SQL — Alembic migrations (`src/career_os/_alembic/versions/`), SQLite pragmas
- JavaScript — Config files (`commitlint.config.js`)
## Runtime
- Python 3.11+ (Docker base: `python:3.11-slim`)
- Node.js 22 (Docker base: `node:22-alpine`)
- pip with setuptools (backend) — `pyproject.toml` build system
- npm (frontend) — `frontend/package-lock.json` present
- Lockfile: pip has no lockfile (deps pinned with >= floors); npm lockfile present
## Frameworks
- FastAPI >=0.115.0 — REST API server (`src/career_os/main.py`)
- React 19.2 — Web frontend SPA (`frontend/`)
- pytest >=8.3.0 — Backend tests (`tests/`)
- pytest-asyncio >=0.25.0 — Async test support (mode: `auto`)
- pytest-cov >=6.1.0 — Coverage reporting
- pytest-timeout >=2.3.0 — Test timeout (30s default)
- Vitest 4.1 — Frontend tests (`frontend/src/__tests__/`)
- Testing Library (React 16.3, DOM 10.4, jest-dom 6.9) — Frontend component testing
- Vite 8.0 — Frontend bundler and dev server (`frontend/vite.config.ts`)
- Ruff >=0.11.0 — Python linting + formatting (replaces flake8/black/isort)
- ESLint 10.2 — TypeScript/React linting (`frontend/`)
- Alembic >=1.15.0 — Database migrations (auto-run on startup)
- Docker — Multi-stage build (`Dockerfile`)
## Key Dependencies
- SQLAlchemy >=2.0 — ORM and database layer (`src/career_os/database.py`, `src/career_os/models/`)
- Pydantic >=2.10.0 — Request/response validation, settings management (`src/career_os/schemas/`)
- pydantic-settings >=2.8.0 — Environment-based configuration (`src/career_os/config.py`)
- httpx >=0.28.0 — Async HTTP client for AI providers, Pushover, TickTick
- aiosqlite >=0.21.0 — Async SQLite driver for FastAPI
- uvicorn[standard] >=0.34.0 — ASGI server
- Typer >=0.15.0 — CLI framework (`src/career_os/cli/`), entry points: `kestrel`, `career`
- slowapi >=0.1.9 — Rate limiting middleware for OAuth endpoints (`src/career_os/api/oauth.py`)
- cryptography >=42.0.0 — Fernet encryption for AI response cache (`src/career_os/ai/cache.py`)
- rapidfuzz >=3.6.0 — Fuzzy string matching (job family presets, skill normalization)
- icalendar >=7.0.0 — Calendar event export (`.ics` files) (`src/career_os/services/calendar.py`)
- Rich >=13.9.0 — CLI output formatting
- python-dotenv >=1.1.0 — `.env` file loading
- @tanstack/react-query 5.90 — Server state management / data fetching (`frontend/src/api/`)
- react-router-dom 7.13 — Client-side routing (`frontend/src/pages/`)
- Tailwind CSS 4.2 — Utility-first styling (via `@tailwindcss/vite` plugin)
- Recharts 3.8 — Chart/visualization library
- @dnd-kit (core 6.3, sortable 10.0) — Drag-and-drop UI
- lucide-react 1.0 — Icon library
- class-variance-authority 0.7 / clsx 2.1 / tailwind-merge 3.5 — CSS utility helpers
- pandas >=2.2.0,<3 — Data analysis (blocked from 3.0 by python-jobspy constraint)
- python-jobspy >=1.1.82,<1.2 — Job board scraping library (`src/career_os/discovery/`)
- fpdf2 >=2.8.0 — PDF generation
- warn-scraper >=0.4.0 — WARN Act data scraping (optional extra: `pip install kestrel-app[warn]`)
## Configuration
- Settings loaded via pydantic-settings from `.env` file (`src/career_os/config.py`)
- All config in `Settings` class with env var mapping and defaults
- Key settings: `AI_PROVIDER`, `DATABASE_URL`, `AUTH_ENABLED`, `AUTH_API_KEY`
- Feature flags: `FEEDBACK_CALIBRATION_ENABLED`, `ACTIVE_QUERY_ENABLED`, `EMBEDDING_PREFILTER_ENABLED`, `BORDERLINE_SCORING_ENABLED`
- `.env.example` documents all available env vars with descriptions
- `pyproject.toml` — Python package config, Ruff config, pytest config
- `frontend/vite.config.ts` — Vite bundler, dev proxy (`/api/*` -> port 8100), path alias `@/`
- `frontend/tsconfig.app.json` — TypeScript strict mode, ES2023 target, bundler module resolution
- `commitlint.config.js` — Conventional commit enforcement
- `Dockerfile` — Multi-stage: Node 22 frontend build -> Python 3.11 runtime
- Target: Python 3.11
- Line length: 100
- Rules: E, F, I, UP, B, SIM
- Per-file ignores for FastAPI Depends patterns, CLI line length, migration files
## Platform Requirements
- Python 3.11+ with venv
- Node.js 22 with npm
- SQLite (bundled with Python, WAL mode enabled)
- No external database server required
- Docker (single container serves API + frontend on port 8100)
- Persistent volume for `data/` directory (SQLite database)
- Optional: AI provider API key (OpenRouter, Anthropic, Together, or Ollama for local)
- GitHub Actions (`/.github/workflows/ci.yml`)
- Jobs: Backend (Python 3.11 lint+test+audit+smoke), Frontend (React lint+test+audit), SonarCloud, actionlint
- Security: pip-audit, npm audit, npm signature verification, PII leak scan
- SonarCloud quality gate on PRs (informational, non-blocking)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- snake_case for all modules: `applications.py`, `gap_analysis.py`, `star_stories.py`
- Prefix `test_` for test files: `test_skills_api.py`, `test_token_usage.py`
- Parallel naming across layers: `api/scoring.py` ↔ `services/scoring.py` ↔ `schemas/scoring.py` ↔ `models/scoring.py`
- Private helpers prefixed with underscore: `_utcnow()`, `_get_active_application()`, `_enrich_with_readiness()`
- PascalCase for React components: `GradeBadge.tsx`, `KanbanBoard.tsx`, `RedFlagBadge.tsx`
- camelCase for API client modules: `applications.ts`, `discovery.ts`, `starStories.ts`
- PascalCase for page components: `Discovery.tsx`, `Pipeline.tsx`, `SettingsPage.tsx`
- Test files in `__tests__/` dir matching component name: `__tests__/GradeBadge.test.tsx`
- snake_case for all functions: `create_application()`, `score_job()`, `get_readiness_score()`
- Private helpers prefixed with underscore: `_derive_package_type()`, `_build_package_summary()`
- Service functions are module-level (no class wrapping): `from career_os.services.applications import create_application`
- camelCase for functions: `fetchApplications()`, `searchJobs()`, `scoreToLetterGrade()`
- PascalCase for React components: `GradeBadge()`, `Layout()`, `Discovery()`
- Prefix `render` for test helper render functions: `renderDiscovery()`, `renderBoard()`
- Prefix `mock` for mock variables: `mockSearchJobs`, `mockFetchApplications`
- SCREAMING_SNAKE for constants: `VALID_TRANSITIONS`, `FK_PROFILES_ID`, `CASCADE_ALL_DELETE_ORPHAN`
- snake_case for variables: `db_session`, `app_obj`, `scored_jobs`
- SCREAMING_SNAKE for constants: `APPLICATION_STATUSES`, `STATUS_LABELS`, `SORT_OPTIONS`, `SAMPLE_JOBS`
- camelCase for variables: `queryClient`, `capturedOnDragEnd`
- PascalCase for classes, exceptions, enums: `ApplicationNotFoundError`, `ApplicationStatus`, `ComplexityTier`
- Exception classes always end with `Error`: `ProfileNotFoundError`, `InvalidStatusTransitionError`, `ScoringError`
- PascalCase for types and interfaces: `ApplicationStatus`, `GradeBadgeProps`, `DiscoveredJob`
- Prefix `readonly` on component props interface fields
- Use `type` keyword for type-only imports: `import type { Application } from "./types"`
## Code Style
- Ruff handles linting and formatting
- Line length: 100 characters
- Config in `pyproject.toml` under `[tool.ruff]`
- Target version: Python 3.11
- No explicit Prettier config — relies on ESLint
- Strict TypeScript mode (`"strict": true` in `tsconfig.app.json`)
- `noUnusedLocals: true`, `noUnusedParameters: true`
- `verbatimModuleSyntax: true` — enforces explicit `type` keyword on type-only imports
- Ruff with rules: E (pycodestyle), F (pyflakes), I (isort), UP (pyupgrade), B (bugbear), SIM (simplify)
- Per-file ignores for expected patterns:
- ESLint flat config in `frontend/eslint.config.js`
- Plugins: `typescript-eslint`, `react-hooks`, `react-refresh`
- Extends: `js.configs.recommended`, `tseslint.configs.recommended`
## Import Organization
- Frontend: `@/*` maps to `frontend/src/*` (configured in `tsconfig.app.json` and `vitest.config.ts`)
## Error Handling
- Define domain-specific exception classes in service modules:
- Services raise domain exceptions; API routes catch and convert to HTTPException:
- Always use `from exc` to chain exceptions
- Catch specific exceptions first, generic `Exception` last as 500 fallback
- `ProviderQuotaError` — base quota/credits exhaustion error in `src/career_os/ai/base.py`
- `CreditsExhaustedError` — OpenRouter-specific in `src/career_os/ai/openrouter_provider.py`
- Provider exceptions store HTTP status code and provider name
- Throw `Error` on non-ok responses with descriptive messages:
- Special-case 404 with meaningful messages: `throw new Error("Application not found")`
- Return typed Promises with `as Promise<T>` assertion
## Logging
- Module-level logger: `logger = logging.getLogger(__name__)` in `src/career_os/api/scoring.py`
- Use logger in API routes for operational events, not in service layer
## Comments
- Module-level docstrings on every Python file: `"""Application pipeline CRUD API routes."""`
- JSDoc on every TypeScript API module and component: `/** API client functions for the applications pipeline. */`
- Section separators with dashed lines for grouping related code:
- Validation reference IDs in test docstrings: `VAL-SKILL-006`, `VAL-SEARCH-001`, `VAL-PIPE-007`
- Triple-quoted docstrings on all classes, functions, fixtures
- First line is a brief summary, then blank line, then details if needed
- Type hints in signatures (not in docstrings)
- Use `/** */` on exported functions and components
- Component files start with a JSDoc block describing purpose and props
## Function Design
- Use keyword-only args for clarity: `def _get_active_application(db, application_id, *, profile_id=None)`
- Type annotations on all parameters and return types
- Use `Annotated[Session, Depends(get_db)]` pattern for FastAPI dependencies
- Destructure props in function signature: `function GradeBadge({ score, letterGrade, className, testId }: GradeBadgeProps)`
- `readonly` on all props interface fields
- Python services return ORM objects or raise exceptions — no None-as-error
- TypeScript API functions return typed Promises
- React components return JSX or `null` for conditional rendering
## Module Design
- No barrel files (`__init__.py` files are mostly empty)
- Import directly from module: `from career_os.services.applications import create_application`
- Named exports only (no default exports): `export function GradeBadge()`
- One React component per file
- Type exports use `export type` or `import type`
- API module exports all client functions for that domain
## Commit Convention
- Conventional commits enforced by commitlint: `type(scope): description`
- Valid types: `build`, `chore`, `ci`, `deps`, `docs`, `feat`, `fix`, `merge`, `perf`, `refactor`, `revert`, `style`, `test`
- Scope includes Linear ticket ID: `feat(G-97): add onboarding flow`
- Config: `commitlint.config.js`
## Pydantic / Schema Patterns
- All API schemas use Pydantic v2 `BaseModel` with `Field()` for validation
- Enum classes use `StrEnum` (Python 3.11+): `class ApplicationStatus(StrEnum)`
- Config via `pydantic-settings` `BaseSettings` in `src/career_os/config.py`
- Settings loaded from env vars automatically (dotenv supported)
- Use `model_validate()` to convert ORM objects to response schemas
## SQLAlchemy Patterns
- Mapped column style (SQLAlchemy 2.0): `Mapped[int] = mapped_column(Integer, ...)`
- Relationships use `Mapped[list["RelatedModel"]]` type hints
- Constants for repeated FK strings: `FK_PROFILES_ID = "profiles.id"`
- `_utcnow()` helper for timezone-aware default timestamps
- In-memory SQLite for tests with FK enforcement pragma
<!-- GSD:conventions-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| bmad-advanced-elicitation | 'Push the LLM to reconsider, refine, and improve its recent output. Use when user asks for deeper critique or mentions a known deeper critique method, e.g. socratic, first principles, pre-mortem, red team.' | `.claude/skills/bmad-advanced-elicitation/SKILL.md` |
| bmad-agent-pm | Product manager for PRD creation and requirements discovery. Use when the user asks to talk to John or requests the product manager. | `.claude/skills/bmad-agent-pm/SKILL.md` |
| bmad-agent-ux-designer | UX designer and UI specialist. Use when the user asks to talk to Sally or requests the UX designer. | `.claude/skills/bmad-agent-ux-designer/SKILL.md` |
| bmad-brainstorming | 'Facilitate interactive brainstorming sessions using diverse creative techniques and ideation methods. Use when the user says help me brainstorm or help me ideate.' | `.claude/skills/bmad-brainstorming/SKILL.md` |
| bmad-create-prd | 'Create a PRD from scratch. Use when the user says "lets create a product requirements document" or "I want to create a new PRD"' | `.claude/skills/bmad-create-prd/SKILL.md` |
| bmad-create-ux-design | 'Plan UX patterns and design specifications. Use when the user says "lets create UX design" or "create UX specifications" or "help me plan the UX"' | `.claude/skills/bmad-create-ux-design/SKILL.md` |
| bmad-distillator | Lossless LLM-optimized compression of source documents. Use when the user requests to 'distill documents' or 'create a distillate'. | `.claude/skills/bmad-distillator/SKILL.md` |
| bmad-edit-prd | 'Edit an existing PRD. Use when the user says "edit this PRD".' | `.claude/skills/bmad-edit-prd/SKILL.md` |
| bmad-editorial-review-prose | 'Clinical copy-editor that reviews text for communication issues. Use when user says review for prose or improve the prose' | `.claude/skills/bmad-editorial-review-prose/SKILL.md` |
| bmad-editorial-review-structure | 'Structural editor that proposes cuts, reorganization, and simplification while preserving comprehension. Use when user requests structural review or editorial review of structure' | `.claude/skills/bmad-editorial-review-structure/SKILL.md` |
| bmad-help | 'Analyzes current state and user query to answer BMad questions or recommend the next skill(s) to use. Use when user asks for help, bmad help, what to do next, or what to start with in BMad.' | `.claude/skills/bmad-help/SKILL.md` |
| bmad-index-docs | 'Generates or updates an index.md to reference all docs in the folder. Use if user requests to create or update an index of all files in a specific folder' | `.claude/skills/bmad-index-docs/SKILL.md` |
| bmad-party-mode | 'Orchestrates group discussions between installed BMAD agents, enabling natural multi-agent conversations where each agent is a real subagent with independent thinking. Use when user requests party mode, wants multiple agent perspectives, group discussion, roundtable, or multi-agent conversation about their project.' | `.claude/skills/bmad-party-mode/SKILL.md` |
| bmad-review-adversarial-general | 'Perform a Cynical Review and produce a findings report. Use when the user requests a critical review of something' | `.claude/skills/bmad-review-adversarial-general/SKILL.md` |
| bmad-review-edge-case-hunter | 'Walk every branching path and boundary condition in content, report only unhandled edge cases. Orthogonal to adversarial review - method-driven not attitude-driven. Use when you need exhaustive edge-case analysis of code, specs, or diffs.' | `.claude/skills/bmad-review-edge-case-hunter/SKILL.md` |
| bmad-shard-doc | 'Splits large markdown documents into smaller, organized files based on level 2 (default) sections. Use if the user says perform shard document' | `.claude/skills/bmad-shard-doc/SKILL.md` |
| bmad-validate-prd | 'Validate a PRD against standards. Use when the user says "validate this PRD" or "run PRD validation"' | `.claude/skills/bmad-validate-prd/SKILL.md` |
<!-- GSD:skills-end -->
