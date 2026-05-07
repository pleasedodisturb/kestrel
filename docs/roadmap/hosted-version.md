# Hosted Version

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Let users who do not want to install anything use Kestrel from any browser.

## What This Delivers

Not everyone wants to run software on their own machine. The hosted version gives you the full Kestrel experience through a web browser with zero setup. Sign up, connect an AI provider, and start scoring jobs. No installation, no terminal, no Docker. Same features as the self-hosted version.

Your data is encrypted at rest and deletable whenever you choose. If you decide to leave, you can export everything or delete it permanently. The hosted version is a convenience option, not a lock-in. The self-hosted version remains free, full-featured, and the recommended path for users who want maximum control over their data.

## Design Considerations

Multi-tenant architecture is the central design question. Each user's data must be completely isolated from every other user's data. One approach is shared infrastructure with per-user database isolation (each user gets their own SQLite file or Postgres schema). Another is per-user isolated instances (heavier on resources but simpler to reason about security). The current application uses SQLite, but a hosted version would likely need to migrate to Postgres for concurrent access and operational tooling.

GDPR compliance is non-negotiable for a hosted product that stores personal career data. Users need to know where their data is physically stored (EU residency options), how long it is retained, and exactly what happens when they request deletion. Encryption at rest, access audit logs, and the right to data portability are all requirements. Pricing is a design decision deferred to a future product requirements process. The deep dive here describes what the hosted version does for users, not how it is monetized.

## Current Status

*Status: Considering -- not yet started*

No implementation exists. A pluggable database layer has been researched (SQLite to Postgres migration path), and the existing architecture was designed with profile-scoped data isolation that provides a foundation for multi-tenant support.

## Related Milestones

- **[Desktop App](desktop-app.md)** -- An alternative deployment path: local installation versus cloud
- **[Feature Flags](feature-flags.md)** -- Feature flags enable different hosted editions and pricing tiers

---

*For Contributors*

## Open Questions

- Deployment infrastructure: managed Postgres (Supabase, Railway, Neon), self-managed on a VPS, or a container platform?
- Multi-tenant data isolation model: shared database with row-level security, per-user schema, or per-user database?
- What changes in the application when moving from SQLite to Postgres? The ORM layer abstracts most differences, but SQLite-specific pragmas and WAL mode need replacement
- EU data residency: which hosting regions should be offered? Is a single EU region sufficient or do users need to choose?
- Pricing model: flat subscription, usage-based, freemium? This is deferred to a BMAD PRD but shapes architectural decisions now
- How should the hosted version handle AI provider keys? User-provided (BYOK) or bundled with the subscription?
- Data export format: JSON dump, database backup, or a structured archive with human-readable files?

## Research Needed

- [LLMs, Tokens, and Privacy](../research/llms-tokens-privacy.md) -- Comprehensive 2026 provider landscape analysis covering privacy implications, GDPR considerations, and data handling policies relevant to a hosted deployment

No dedicated hosted version research exists yet. Research areas include: multi-tenant architecture patterns for Python/FastAPI, Postgres migration from SQLite, GDPR compliance requirements for SaaS products, data encryption at rest strategies, and infrastructure cost modeling.

## BMAD Integration

**PRD Status:** Not started

A PRD would define the infrastructure architecture and hosting provider selection, data isolation model between tenants, encryption-at-rest and deletion guarantee requirements, and the pricing tier structure tied to feature flag configurations.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
