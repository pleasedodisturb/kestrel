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

## AI Provider Changes

If you add a new AI provider:

1. Create a new file in `src/career_os/ai/`
2. Implement the `AIProvider` protocol
3. Register it in `src/career_os/ai/factory.py`
4. Update the mock provider to support any new features
5. Add tests

## Questions?

Open an issue on GitHub.
