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

## AI Provider Changes

If you add a new AI provider:

1. Create a new file in `src/career_os/ai/`
2. Implement the `AIProvider` protocol
3. Register it in `src/career_os/ai/factory.py`
4. Update the mock provider to support any new features
5. Add tests

## Questions?

Open an issue on GitHub.
