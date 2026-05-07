# Feature Flags

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Let different deployments of Kestrel show different features based on configuration.

## What This Delivers

Feature flags give Kestrel the ability to enable, disable, or adjust features per deployment. This is infrastructure, not a user-facing milestone. A self-hosted instance might show everything. A hosted free tier might hide premium capabilities. Development builds can test incomplete features without affecting production. Flags make all of this possible with configuration rather than separate codebases.

## Design Considerations

The primary decision is whether flags are evaluated at runtime (checked on every request) or at build time (compiled in during the build step). Runtime flags are more flexible: you can toggle features without redeploying. Build-time flags produce smaller bundles by eliminating dead code entirely, which matters for the open-source distribution where unused hosted-edition code should not ship. A hybrid approach may be needed: build-time elimination for major edition differences, runtime flags for smaller toggles.

Flag storage also needs a decision. For self-hosted users, environment variables or a configuration file is the simplest approach. For a hosted version with multiple tiers, flags need a database-backed system that can differ per user or per subscription level. An admin interface for toggling flags without code changes would reduce operational burden for the hosted version.

## Current Status

*Status: Planned -- not yet started*

No feature flag implementation exists. The application currently uses environment variables for some configuration toggling (feature flags like `FEEDBACK_CALIBRATION_ENABLED` and `ACTIVE_QUERY_ENABLED`), but there is no unified flag system.

## Related Milestones

- **[Hosted Version](hosted-version.md)** -- Feature flags enable different hosted editions and pricing tiers

---

*For Contributors*

## Open Questions

- Runtime flags, build-time flags, or a hybrid approach? Each has different implications for bundle size, flexibility, and complexity
- Flag storage: environment variables (simple), configuration file (portable), database-backed (dynamic, multi-tenant)?
- What categories of flags are needed? Feature flags (enable/disable features), experiment flags (A/B testing), operational flags (maintenance mode, rate limits)?
- Should there be an admin UI for managing flags, or is configuration-file-based management sufficient for the self-hosted use case?
- Default values: should flags default to "on" (self-hosted gets everything) or "off" (explicit opt-in)?
- How should the frontend handle flags? React context provider that gates component rendering, or route-level checks?
- Flag lifecycle: how are flags deprecated and removed after a feature is fully shipped?
- Should flag evaluation be server-side only, client-side only, or synchronized between both?
- What existing flag libraries (LaunchDarkly, Unleash, Flagsmith, or simpler open-source options) should be evaluated versus building a custom system?
- How do flags interact with the existing `Settings` class in `src/career_os/config.py` that already handles environment-based configuration?

## Research Needed

No existing research documents cover feature flags. Research areas include:

- Feature flag library comparison (LaunchDarkly, Unleash, Flagsmith, PostHog, Flipt) and suitability for a self-hosted application
- Build-time flag elimination patterns for tree shaking in Vite/webpack
- Runtime flag evaluation performance (per-request overhead, caching strategies)
- Flag management UI patterns for admin interfaces
- Multi-tenant flag scoping for SaaS deployments

## BMAD Integration

**PRD Status:** Not started

A PRD would cover the flag taxonomy and lifecycle (feature, experiment, operational), the admin interface design for hosted deployments, integration with the hosted version tier management, and the build-time flag elimination strategy for the open-source edition.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
