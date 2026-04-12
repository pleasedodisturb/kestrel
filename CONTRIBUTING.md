---
layout: default
permalink: /CONTRIBUTING
title: Contributing to Kestrel
---

<p align="center"><img src="assets/illustrations/hero-bauhaus.webp" alt="Kestrel" width="300"></p>

# Contributing to Kestrel

Note: The Python package is internally named `career_os` (from the original project). The PyPI package name is `kestrel-app`.

Thanks for wanting to help. Here's how to get started.

## Development Setup

1. Fork and clone the repo
2. Run `./setup.sh` or set up manually:

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head

# Frontend
cd frontend
npm install --legacy-peer-deps

# Run both
uvicorn career_os.main:app --port 8100 --reload  # terminal 1
cd frontend && npm run dev                         # terminal 2
```

## Running Tests

```bash
# Backend
pytest tests/ -v

# Frontend
cd frontend && npx vitest run

# Lint
ruff check src/ tests/
ruff format --check src/ tests/
cd frontend && npx eslint src/
```

## Making Changes

1. Create a branch: `git checkout -b feature/your-change`
2. Make your changes
3. Add tests for new functionality
4. Run the full test suite
5. Submit a pull request

## Code Style

- Python: Ruff handles formatting and linting. Run `ruff check --fix` to auto-fix.
- TypeScript: ESLint with strict mode. Run `npx eslint --fix src/`.
- Write tests alongside code, not after.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format. A CI check (`commitlint`) enforces this on all PRs.

```
<type>: <description>

feat:     new feature (bumps minor version)
fix:      bug fix (bumps patch version)
docs:     documentation only
refactor: code restructuring
perf:     performance improvement
test:     adding or fixing tests
ci:       CI/CD changes
chore:    maintenance
deps:     dependency updates
```

For breaking changes, add `!` after the type: `feat!: remove legacy API`

## Pull Request Guidelines

- Keep PRs focused - one feature or fix per PR
- Include a clear description of what changed and why
- All CI checks must pass
- Tests are required for new features

## Merging

The `main` branch is protected with required status checks and a merge queue.

- **PRs must be up-to-date with main** before merging. If main has moved since your last CI run, GitHub will ask you to update your branch and re-run checks. This prevents untested merge combinations from landing.
- **Use the "Merge when ready" button** (not direct merge). This adds your PR to the merge queue, which tests the merge result before actually pushing to main.
- **Squash merge only** — keeps the main branch history clean and bisectable.
- If CI fails after an update, investigate before re-pushing. The failure likely means your changes conflict with something that landed while your PR was in review.

## Dependency Management

### Automated Updates (Renovate Bot)

[Renovate Bot](https://docs.renovatebot.com/) opens PRs weekly for outdated dependencies.

- **Patch and minor updates** auto-merge if CI passes. No action needed.
- **Major updates** require manual review and approval — check the PR for changelog links and breaking changes before merging.

Configuration lives in `renovate.json` at the repo root.

### Review Cadence

| Frequency | Action |
|-----------|--------|
| Weekly | Review auto-merged Renovate PRs for regressions |
| Monthly | Review and merge pending major-version Renovate PRs |
| Immediately | Triage security advisories (pip-audit, npm audit, Socket.dev alerts) |
| Quarterly | Prune unused dependencies (see below) |

### Security Scanning

CI enforces these gates on every PR:

- **pip-audit** (Python) — fails on any known advisory from OSV + PyPI databases. Temporary suppressions go in `.pip-audit-ignore` with a comment and removal date.
- **npm audit** (Node) — fails on `moderate` or higher severity vulnerabilities.
- **npm audit signatures** (Node) — verifies registry signature provenance on installed packages.
- **Socket.dev** — GitHub App that scans PRs for supply-chain threats (typosquatting, install scripts, maintainer takeovers).

### Adding or Removing Dependencies

- **Python**: edit `pyproject.toml` (not `requirements.txt`). Pin with `>=x.y.z,<x+1` to prevent accidental major bumps.
- **Node**: use `npm install --save` or `npm install --save-dev` in the appropriate directory (`frontend/`).
- Run the full test suite before submitting the PR.

### Pruning Unused Dependencies

Run quarterly to keep the dependency tree lean:

```bash
# Python
pip install deptry && deptry src/

# Node (frontend)
cd frontend && npx depcheck
```

## AI Provider Changes

If you add a new AI provider:

1. Create a new file in `src/career_os/ai/`
2. Implement the `AIProvider` protocol
3. Register it in `src/career_os/ai/factory.py`
4. Update the mock provider to support any new features
5. Add tests

## Questions?

Open an issue on GitHub.
