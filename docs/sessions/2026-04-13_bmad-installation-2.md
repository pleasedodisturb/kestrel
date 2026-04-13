# Session: BMAD Installation & Workflow Documentation
**Date:** 2026-04-13
**Branch:** G-265/install-bmad-gsd-toolkit → main
**Tickets:** G-265

## What was done
- Investigated why BMAD step files were missing (collateral damage from G-225 Ollama revert)
- Installed BMAD v6.3.0 manually from npm cache (interactive TUI incompatible with non-TTY)
- 17 skill directories (core + bmm modules) added to `.claude/skills/bmad-*/`
- Created `_bmad/` config (project: Kestrel, user: Vitalik, English)
- Expanded CLAUDE.md with full "Planning & Workflow Tooling" section (BMAD + GSD command tables)
- Added `.gitignore` entries for `_bmad-output/`, `.planning/`, `GSD-CLAUDE.md`
- Created Linear ticket G-265, PR #162 — reviewed (code quality + security), merged
- Fixed gitignore entries dropped during squash merge (PR #165)
- Learned commitlint enforces conventional commit format — fixed commit message format

## Decisions made
- BMAD installed on main (not feature branch) — it's long-running project infrastructure
- GSD doesn't need per-project install — it's global in `~/.claude/skills/gsd-*/`
- Manual BMAD install preferred over fighting interactive TUI in non-TTY terminals

## Open items
- PRD Step 4 (User Journeys) — original session goal, deferred for BMAD install
- `docs/prd-creation` worktree needs `git pull origin main` before resuming PRD work

## Commits
- `chore: G-265 install BMAD method toolkit and document project workflows` (PR #162)
- `fix: G-265 re-add BMAD/GSD gitignore entries dropped during merge` (PR #165)
