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

**Backend:** Layered — `api/` (routes) → `services/` (logic) → `schemas/` (validation) → `models/` (ORM) → SQLite (WAL). Each domain has matching files across all layers. AI providers use factory pattern (`AI_PROVIDER` env var). Alembic auto-migrates on startup.

**Frontend:** React Router SPA. TanStack Query for data fetching (`frontend/src/api/`). Path alias `@/*` → `frontend/src/`. Vite proxies `/api/*` to backend port 8100.

**Cross-cutting:** REST API at `/docs` (Swagger). Profile ID scopes all data. Optional API key auth (`AUTH_ENABLED`).

> **Deep dive:** See `.planning/codebase/ARCHITECTURE.md` and `docs/M6-M9-ARCHITECTURE.md`.

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

Two workflow systems: **GSD** (execution) and **BMAD** (product planning). Both are project infrastructure — committed independently, not bundled with feature work.

- **GSD:** Global (`~/.claude/skills/gsd-*/`). State in `.planning/` (gitignored). Start all repo edits through a GSD command (e.g., `/gsd-quick`, `/gsd-plan-phase`, `/gsd-debug`). Do not bypass unless user explicitly asks.
- **BMAD:** Per-project in `_bmad/` + `.claude/skills/bmad-*/`. Output in `_bmad-output/planning-artifacts/`. Drives PRD → UX → Architecture → Epics → Stories.

> **Full command tables and details:** See `docs/WORKFLOW-TOOLS.md`.
