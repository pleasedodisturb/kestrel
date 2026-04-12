# Kestrel — Claude Code conventions

The Python package is internally named `career_os`. The PyPI package name is `kestrel-app`.

## Commit messages

Use Conventional Commits format. Prefix every commit with a type:

- `feat:` — new feature (bumps minor version)
- `fix:` — bug fix (bumps patch version)
- `docs:` — documentation only
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `perf:` — performance improvement
- `test:` — adding or correcting tests
- `ci:` — CI/CD changes
- `chore:` — maintenance (deps, config, etc.)
- `deps:` — dependency updates

For breaking changes, add `!` after the type: `feat!: remove legacy API`

Examples:
- `feat: add LinkedIn job source integration`
- `fix: prevent duplicate jobs in daily scan`
- `docs: update deployment guide for Railway`
