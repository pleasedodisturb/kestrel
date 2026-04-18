---
title: Scoring Evolution
---

# Session: Scoring Evolution — 11 Epics in 2 Days
**Date:** 2026-04-14 to 2026-04-15
**Branch:** main (all merged)
**Tickets:** G-268 (master), G-269 through G-279 (11 sub-epics), G-282, G-283, G-284 (follow-ups)

## What was done
- Cleaned up 8 local + 29 remote stale branches
- Ran 3 parallel deep research agents (competitors, academic, engineering)
- Synthesized research into `private/research-scoring-deep-dive-2026-04-14.md`
- Designed 11-epic roadmap across 5 phases in `docs/scoring-evolution-epics.md`
- Created 12 Linear tickets (G-268 master + G-269 through G-279)
- REDACTED (3 sessions Day 1, 2 sessions Day 2)
- Reviewed all 7 Day 1 branches with parallel review agents
- Fixed G-274 calibration injection gap (agent on Mac Mini)
- Resolved Alembic migration conflicts across 4 branches (revision chain + ID collisions)
- Merged all 11 PRs (#177-#187) to main
- Closed all 12 Linear tickets as Done
- Created 3 follow-up tickets (G-282 edutainment doc, G-283 alembic consolidation, G-284 test fix)

## Features shipped
- Scoring rubric with 3 calibration examples + golden set (G-269)
- Ghost job detection from discovery history (G-270)
- Score percentiles and context (G-271)
- Embedding pre-filter with Ollama shadow mode (G-272)
- Borderline 2-pass scoring for 4.0-6.5 zone (G-273)
- User feedback loop with calibration injection (G-274)
- Dual-score: fit_score + desire_score with quadrant classification (G-275)
- ESCO skill normalization with 3-pass matching (G-276)
- WARN Act layoff red flags from public data (G-277)
- Uncertainty ranges for sparse profiles (G-278)
- Bayesian preference learning from feedback (G-279)

## Decisions made
- Opus for judgment-heavy epics (rubric, embeddings, dual-score, Bayesian), Sonnet for execution
- Mac Mini + tmux + `--dangerously-skip-permissions` for agent execution
- Option B (AI-generated) as default desire_score method, Option A (derived) as fallback
- No sqlite-vec C extension — pure Python cosine similarity for now
- Feedback calibration gated behind feature flag, requires ≥10 corrections
- Shadow mode default for embedding pre-filter (log similarities, don't filter yet)

## Open items
- G-282: Edutainment doc "How Kestrel Scores"
- G-283: Consolidate dual Alembic migration directories
- G-284: Fix pre-existing test_md_to_pdf.py failures
- Integration testing across all 11 features combined
- REDACTED `REDACTED`

## PRs merged
- #175: docs(G-268): scoring evolution epic specs
- #177: feat(G-269): scoring rubric & few-shot calibration
- #178: feat(G-270): ghost job detection
- #179: feat(G-271): score context & percentiles
- #180: feat(G-275): dual-score architecture
- #181: feat(G-274): user feedback loop
- #182: feat(G-276): ESCO skill normalization
- #183: feat(G-277): WARN Act layoff integration
- #184: feat(G-278): uncertainty ranges
- #185: feat(G-279): Bayesian preference learning
- #187: feat(G-273): borderline 2-pass scoring (includes G-272 embeddings)
