<!-- Thanks for contributing to Kestrel! Please fill in the sections below. -->

## Summary

<!-- What does this PR do? One or two sentences. -->

## Motivation

<!-- Why is this change needed? Link to related issues: "Fixes #123" -->

## Changes

<!-- Bulleted list of the important changes. Skip trivia. -->

-
-

## Screenshots / recordings

<!-- For UI changes. Delete if not applicable. -->

## Checklist

- [ ] Tests added or updated (backend `pytest`, frontend `vitest`)
- [ ] `ruff check` and `ruff format --check` pass locally
- [ ] `npm run lint`, `npm run build`, and `npx vitest run` pass in `frontend/`
- [ ] If this PR adds/changes an Alembic migration, I verified there is exactly one head (`alembic heads`) and the migration applies cleanly against a fresh SQLite DB
- [ ] No new secrets, API keys, or personal data committed
- [ ] Docs updated (README / QUICKSTART / inline) if behaviour changed
- [ ] Breaking changes are called out in the summary above
