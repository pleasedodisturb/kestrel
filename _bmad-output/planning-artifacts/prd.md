---
stepsCompleted:
  - 'step-01-init'
  - 'step-02-discovery'
  - 'step-02b-vision'
  - 'step-02c-executive-summary'
vision:
  statement: 'Build the definitive open-source job search platform by absorbing the best features from the paid ecosystem, giving them away free, and making job searching feel less awful'
  differentiator: 'Full pipeline ownership (discover → score → track → prepare) running locally with data sovereignty, transparent AI, and emotional design that treats job seekers as humans'
  coreInsight: 'Job search tools optimize for throughput (apply to more, faster). Kestrel optimizes for signal and control — apply to fewer, better-matched jobs, and feel in control'
  jtbd: 'Feel like I have my situation under control'
  license: 'AGPL-3.0-or-later'
  monetization: 'screenpi.pe model — free core for job seekers, paid premium/hosted services for convenience and scale'
classification:
  projectType: 'Multi-Surface Platform (Web + PWA + CLI)'
  domain: 'Career Technology / Job Search Automation'
  complexity: 'High'
  projectContext: 'brownfield'
inputDocuments:
  - 'private/GTM-PLAN.md'
  - 'private/STRATEGY-2026-04-08.md'
  - 'private/research/01-browser-extension.md'
  - 'private/research/02-scoring-overhaul.md'
  - 'private/research/03-analytics-dashboard.md'
  - 'private/research/04-ghost-job-detection.md'
  - 'private/research/05-networking-crm.md'
  - 'private/research/06-discovery-adapters.md'
  - 'private/research/07-frontend-polish.md'
  - 'docs/M6-M9-ARCHITECTURE.md'
  - 'docs/market-research-apr2026.md'
  - 'docs/pricing-strategy.md'
  - 'docs/ux-persona-testing.md'
  - 'docs/JOB_SEARCH_TOOLS_RESEARCH.md'
  - 'docs/AI-PROVIDERS.md'
  - 'docs/COMPARISON.md'
  - 'docs/FAQ.md'
  - 'docs/HELP.md'
  - 'docs/QUICKSTART.md'
  - 'docs/REFERENCE.md'
  - 'docs/validation-contract-m2-skills.md'
  - 'docs/validation-contract-m5-integrations.md'
  - 'docs/validation/M1_VALIDATION_CONTRACT.md'
  - 'external/CareerOS/docs/archive/compass_artifact.md'
documentCounts:
  briefs: 0
  research: 8
  strategic: 2
  projectDocs: 12
  external: 1
workflowType: 'prd'
---

# Product Requirements Document - Kestrel

**Author:** [redacted]
**Date:** 2026-04-12

## Executive Summary

Kestrel is a self-hosted, open-source job search platform that owns the full discovery-to-application pipeline — automated multi-board job scraping, AI-powered dimensional scoring, Kanban pipeline tracking, interview preparation, and networking CRM — all running locally. It is the only open-source tool that combines these capabilities in a single package with full data sovereignty.

The job search market is structurally broken: 242 applications per opening, 27-40% ghost job postings, 75% of applications never reaching human eyes, and 61% of candidates experiencing post-interview ghosting. The tools that claim to help cost $25-40/month and hold sensitive career data hostage in opaque cloud systems. Every tool optimizes for volume — apply to more jobs, faster. Nobody helps you apply to fewer, better-matched jobs.

Kestrel inverts this. The core job-to-be-done is not "manage applications" — it is **"feel like I have my situation under control."** Job seekers are under sustained psychological stress, and every design decision in Kestrel prioritizes signal over noise, emotional support over data density, and clarity over feature count. The product is built for people who are going through one of the hardest experiences of adult life and deserve a tool that respects that.

The long-term vision is to become the definitive open-source job search platform by systematically absorbing the best features from the paid ecosystem — Huntr's tracking, Teal's resume matching, Career-Ops's archetype scoring, Simplify's ATS integration — and making them available to everyone, for free. Revenue follows the screenpi.pe model: the core tool is free because people need it (often while unemployed), with optional premium hosted services for convenience and scale. Licensed under AGPL-3.0 to protect the commons from cloud freeloading while keeping it free for every self-hoster.

### What Makes This Special

**Full pipeline ownership, locally.** No other open-source project combines scraping + scoring + tracking + prep + CRM in one platform. Career-Ops (23K stars) is a prompt framework with no web UI or daily automation. Huntr and Teal are cloud SaaS that can't offer data sovereignty by design. Kestrel fills a structural gap.

**Transparent, tunable AI scoring.** Competitors score resume-vs-JD as a black box. Kestrel scores against a user-defined profile with 6 dimensional axes, tunable weights, job-family presets, and open prompt logic. The user defines what "good match" means and can read the code that decides.

**Emotional design as a first-class constraint.** Every screen answers "what do I do next?" Empty states encourage. Rejection screens redirect attention forward. Scoring results lead with narrative, not numbers. The product voice is a calm, competent friend — not a corporate dashboard. This is codified in a developer-facing emotional design contract, not left to implementation judgment.

**Zero recurring cost, full data sovereignty.** Everything runs on the user's machine. No account, no subscription, no vendor lock-in. SQLite database is theirs to query, export, back up, or migrate. In a market where France Travail's breach exposed 36.8M people, this is not theoretical.

## Project Classification

- **Project Type:** Multi-Surface Platform (Web + PWA + CLI)
- **Domain:** Career Technology / Job Search Automation
- **Complexity:** High — four planned client surfaces (web, PWA, browser extension, CLI), web scraping with legal exposure, AI provider abstraction, open-source distribution and support surface, and an emotional design constraint that touches every screen
- **Project Context:** Brownfield — extending an existing platform (5 shipped milestones, 11 web routes, 3 discovery adapters, 20+ API modules) with new features for open-source GTM launch and future mobile/extension surfaces
