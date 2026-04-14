# Session: Supabase Database Strategy Research
**Date:** 2026-04-14
**Branch:** main
**Tickets:** G-267

## What was done
- Deep research on Supabase as end-game database and web deployment solution for Kestrel
- Compared Supabase, Neon, Turso, SQLite+Litestream across 7 dimensions (migration effort, self-hosting, cost, DX, features, vendor lock-in, Python/FastAPI fit)
- Produced tiered database strategy: SQLite (self-hosted) -> Postgres/Neon (cloud) -> Supabase full platform (SaaS)
- Created Linear ticket G-267 with full research, file impact list, effort estimates, and decision triggers
- Saved research summary to auto-memory for future session context

## Decisions made
- **Don't migrate TO Supabase** — make DB layer pluggable instead, let users choose tier
- **SQLite stays as default** for self-hosted (zero-config, 5-minute setup value prop preserved)
- **Neon preferred over Supabase** for pure managed Postgres needs ($19/mo vs $25/mo)
- **Supabase justified only at Tier 3** (multi-user SaaS with auth, storage, realtime, pgvector)
- **Self-hosted Supabase rejected** — 13 Docker services, ~4GB RAM, destroys simplicity
- **pgvector identified as killer feature** for semantic job matching (strongest argument for Postgres path)
- **ai/cache.py stays SQLite** regardless of DB choice (local performance cache, not app data)

## Open items
- G-267 in Backlog — pluggable DB layer implementation deferred to when hosted offering or SaaS is planned
- Tier 2 migration estimated at 1-2 weeks when triggered
- Tier 3 (full Supabase) estimated at 4-6 additional weeks

## Commits
- No code commits this session (research only, no code changes)
