# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kestrel** is an AI-powered, self-hosted job search platform with a REST API and web frontend:

| Component | Location | Stack | Dev Port |
|-----------|----------|-------|----------|
| Backend API | `src/career_os/` | Python 3.11+, FastAPI, SQLAlchemy, SQLite | 8100 |
| Web Frontend | `frontend/` | React 19, Vite, TypeScript, Tailwind CSS | 8101 |

The Python package is internally named `career_os` (historical). PyPI name is `kestrel-app`. The `mobile/` directory is preserved for a future release — do not develop against it.

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

- **AI Provider Abstraction** (`src/career_os/ai/`): Factory pattern — `AI_PROVIDER` env var selects provider. 9 providers: Mock, OpenRouter, Anthropic, OpenAI, Together, Groq, xAI, Gemini, Ollama. All implement `complete()` and `score()` async methods. Fallback chain via `AI_PROVIDER_FALLBACK`.
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
**Output directory:** `_bmad-output/planning-artifacts/` (PRD, architecture docs, etc.)
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
