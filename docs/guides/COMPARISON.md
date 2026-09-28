---
layout: default
permalink: /docs/COMPARISON
title: Competitive Landscape
---

<p align="center"><img src="../assets/illustrations/hero-sky.webp" alt="Kestrel" width="300"></p>

# Competitive Landscape

## TL;DR

The job search tool space splits into two camps: polished SaaS trackers that help you organize and auto-fill applications (Huntr, Teal, Simplify), and open-source tools that give you control over your data and pipeline (Career-Ops, JobSync, JobOps, Kestrel). Several open-source projects now combine multi-board discovery, AI scoring against your profile and a tracking pipeline in one self-hosted package. What sets Kestrel apart is that it is built as a measured system: a scoring eval gate in nightly CI, a 7-way geo-eligibility engine with a committed 277-item reference set, a source registry that reports every scan source on every run, provider privacy tiers with an enforced personal-data boundary, EU eligibility depth, and no auto-apply by design. <!-- DECISION #99: positioning one-liner; the differentiator list above is interim wording --> If you want a Chrome extension that fills forms on 1000+ sites today, use Huntr or Simplify. If you want to own your data and automate the discovery-to-application pipeline without paying $30+/month, Kestrel is worth evaluating - but it is new, unproven, and requires a terminal or a Docker/Railway/Codespaces click.

## The Landscape

Job search tools fall into five categories:

**Commercial trackers** (Huntr, Teal) - Polished SaaS with Chrome extensions, kanban boards, and AI resume builders. Good UX, cloud-only, $25-40/month for full features. Manual job discovery - you clip jobs yourself.

**Commercial auto-fill tools** (Simplify) - Laser-focused on filling out applications fast via browser extension. Less pipeline management, more speed-of-apply.

**Open source tools** (Career-Ops, JobSync, Kestrel) - Self-hosted, data stays with you, free or near-free. Each takes a different approach: Career-Ops is an agent-skill framework with a ~140-script layer, a Go TUI, an opt-in web UI and 93 scanners, JobSync is a tracker with AI review, Kestrel adds automated discovery and scoring.

**Agent-skill frameworks** (ai-job-search, Career-Ops) - Skill bundles that run inside Claude Code, Codex or another agent CLI rather than as a standalone app. ai-job-search (44.3k stars as of 2026-09-28) is a Claude Code framework; Career-Ops is the larger and broader of the two. Elsewhere in the open-source camp: JobOps (about 4k stars) combines 13 boards, scoring and a tracker but is source-available under the Commons Clause, not MIT; freehire is an MIT aggregator with an API and an MCP server; JobNavigator polls 11 ATS endpoints and ships an extension and a tracker.

**AI assistants** (ChatGPT, Claude, vanilla Perplexity) - Can do any individual task well (evaluate a JD, draft a cover letter) but cannot maintain state across sessions, run daily scans, or manage a pipeline over weeks. ChatGPT now has an Indeed app for discovery; LinkedIn Premium drafts and prefills but you submit.

**Agentic AI** (Perplexity Computer) - The new middle ground: a cloud-hosted multi-model agent with persistent memory, scheduled tasks, and a companion browser (Comet) that can auto-fill applications. Covers most of Kestrel's workflow at $20/mo Pro entry (credit-metered, one-time grant) or $200/mo Max, but closed, US-centric, credit-metered, and has no structured scoring rubric or pipeline/kanban model.

## Comparison Table

| Dimension | Huntr | Teal | Simplify | Career-Ops | JobSync | Kestrel | Perplexity Computer | AI Assistants |
|-----------|-------|------|----------|------------|---------|---------|---------------------|---------------|
| **Cost** | $40/mo | $29/mo | $25-39/mo | Free; runs on ten-plus agent CLIs including free tiers (Antigravity, Ollama, DeepSeek via OpenRouter); the agent path loads ~26K tokens of instructions per evaluation and one user reported $14 for a single run | Free | Free (AI: $0-3/mo) | $20/mo Pro entry (credit-metered, one-time grant) or $200/mo Max | $0-20/mo |
| **Self-hosted** | No | No | No | Yes (terminal) | Yes (Docker) | Yes (Docker) | No (cloud sandbox) | No |
| **Data ownership** | Vendor-held | Vendor-held | Vendor-held | Local files | Local SQLite | Local SQLite | Vendor-held (no training) | Session-only |
| **Web UI** | Yes (polished) | Yes (polished) | Minimal | Go TUI plus an opt-in local Next.js web UI (alpha) | Yes (Shadcn) | Yes (React) | Yes (Max app) | Chat interface |
| **Mobile app** | Yes | No | No | No | No | No | Yes | Yes (chat) |
| **Chrome extension** | Yes (1000+ ATS) | Yes | Yes (1000+ ATS) | No <sup>1</sup> | No | Yes (capture, inline score, consented auto-log on LinkedIn jobs, Greenhouse, Lever, Ashby; no auto-fill) | Comet browser (integrated) | No |
| **Job discovery** | Manual clip | Manual clip | Curated board | 93 provider modules (zero-auth ATS APIs, national job banks incl. Arbeitsagentur, aggregators, HN Who is Hiring), reverse-ATS company sweep | Basic | Multi-board automated | Ad-hoc (web + LinkedIn via Comet) | Ad-hoc search |
| **Scheduled auto-scan** | No | No | No | Yes (cron/launchd/Task Scheduler recipes, zero-token scans) | No | On a schedule (weekly by default in the app; daily via the optional GitHub Actions workflow) | Yes (scheduled tasks) | No |
| **AI scoring** | Resume-vs-JD | Job match score | No | A-H evaluation (8 blocks) plus Risk Summary; 5 dimensions to one 1-5 score; evidence-tiered requirement importance | Job matching | Custom profile rubric | Conversational | Conversational |
| **Custom scoring rubric** | No | No | No | Yes (prompt-based) | No | Yes (per-profile weights in the app, 288 job-family presets, feedback calibration) | No (prompt-based) | Sort of |
| **Cover letter gen** | No | No | No | Yes | No | Brainstorm mode (conversational text); rendering in tools/ | Yes | Yes (one-off) |
| **CV tailoring** | AI resume builder | AI resume builder | AI resume (premium) | Yes (excellent) | Resume review | Keyword checklist in-app; RenderCV tooling in tools/ | Yes | Yes (one-off) |
| **Auto-fill/apply** | Yes (killer feature) | No | Yes (killer feature) | Pre-fill on Greenhouse/Ashby/Lever/Workable, never submits, knock-out pre-scan | No | Experimental (Playwright) | Yes (Comet, killer feature) | No |
| **Interview prep** | No | No | No | Yes | No | Yes | Yes | Yes (one-off) |
| **EU job boards** | No | No | No (US-focused) | Yes (Arbeitsagentur, Interamt, Arbeitnow, VDAB, join.com, WTTJ and more) | No | Yes (Arbeitsagentur, Arbeitnow; Arbeitsagentur adapter being migrated to API v6) | No | No |
| **REST API** | No | No | No | No | Yes | Yes | No (closed platform) | API exists but different |
| **Setup effort** | 2 min | 2 min | 2 min | 15 min | 10 min (Docker) | 5-10 min (pip, npm, Homebrew, Docker, Railway button, Codespaces) | 0 min | 0 min |
| **Community** | Large (commercial) | Large (commercial) | Large (commercial) | ~73k stars, 13.7k forks, 427 contributors (as of 2026-09-28) | 1.3k stars (as of 2026-09-28) | 7 stars (new, as of 2026-09-28) | Massive (Perplexity) | Massive |
| **Geo-eligibility engine** | Not advertised | Not advertised | Not advertised | Not advertised | Not advertised | Yes (7 classes, 277-item committed reference set) | Not advertised | No |
| **Rule-based red flags** | Not advertised | Not advertised | Not advertised | Not advertised | Not advertised | Yes (10 detectors incl. WARN Act layoffs) | Not advertised | No |
| **Scoring eval gate in CI** | Not advertised | Not advertised | Not advertised | Not advertised | Not advertised | Yes (golden set, nightly) | Not advertised | No |
| **Source registry** | Not advertised | Not advertised | Not advertised | Not advertised | Not advertised | Yes (every source reported every run) | Not advertised | No |
| **Provider privacy tiers** | Single vendor | Single vendor | Single vendor | Not advertised | Not advertised | Yes (per-provider tier) | Single vendor | Single vendor |
| **PII boundary enforcement** | Not advertised | Not advertised | Not advertised | Not advertised | Not advertised | Yes (personal-data features refuse providers outside a by-name allowlist: Ollama, Anthropic, mock) | Not advertised | No |
| **Encrypted local response cache** | Vendor-held | Vendor-held | Vendor-held | Not advertised | Not advertised | Yes (Fernet at rest) | Vendor-held | No |

<sup>1</sup> Career-Ops has no Chrome extension today, but its web API already allowlists a `chrome-extension://` origin, so one is being prepared.

<!-- DECISION #95: the Kestrel "Auto-fill/apply" cell stays "Experimental (Playwright)" until the public auto-apply stance is decided -->

## "Can't ChatGPT/Perplexity Do This?"

Honest answer: for any single task, yes. AI assistants are excellent at one-off work. Here is where they fall short for systematic job searching:

| Capability | AI Chatbot (ChatGPT/Claude/vanilla Perplexity) | Perplexity Computer | Dedicated Tool (any) |
|-----------|-----------------------------------------------|---------------------|---------------------|
| Evaluate one JD against your resume | Great | Great | Great |
| Draft a cover letter | Great | Great | Good to great |
| Search for jobs right now | Good (web search) | Good (Comet + LinkedIn) | Good (board APIs) |
| Remember your pipeline state tomorrow | No | Yes (persistent memory) | Yes |
| Run a daily scan while you sleep | No | Yes (scheduled tasks) | Some (Kestrel via the optional GitHub Actions workflow; weekly by default in the app) |
| Track 50 applications across stages | No (resets each session) | Partial (memory, no kanban) | Yes |
| Score 20 new postings against your profile automatically | No | Partial (no structured rubric) | Some (Kestrel yes) |
| Auto-fill application forms | No | Yes (Comet browser) | Some (Huntr, Simplify) |
| Export your history for analysis | No persistent history | No (closed sandbox) | Yes |
| EU job board coverage (Arbeitsagentur) | No | No | Some (Kestrel, Career-Ops) |
| Monthly cost | $0-20 | $20 (Pro, credit-metered) or $200 (Max) | $0-40 |

The gap is not intelligence - it is persistence, domain-specific rubrics, data ownership, and price. Vanilla AI chatbots are stateless. Perplexity Computer fixes persistence and even automates recurring tasks, but it runs in a vendor sandbox at $20/mo Pro entry (credit-metered, one-time grant) or $200/mo Max, has no structured rubric scoring, no pipeline/kanban model, no EU board coverage, no data ownership, and now a credit meter. Job searching is a weeks-long stateful process that rewards a tool shaped for it.

If you are applying to fewer than 10 jobs total, ChatGPT is probably enough. If you are running a sustained search across dozens of positions over weeks and want a SaaS agent with zero setup, Perplexity Computer will cover most of the workflow at a premium. If you want ownership of your data, rubric-driven scoring, EU board support, or near-zero cost, a dedicated tool is the better fit.

<details>
<summary><strong>Want to try the Kestrel approach with just a chatbot?</strong></summary>

Not ready to install anything? Paste this prompt into ChatGPT, Claude, or Perplexity to get a single-session version of Kestrel's methodology. You will lose state between sessions and there is no automation, but it is a good way to test the philosophy before committing to the platform.

```
You are a comprehensive AI-powered job search assistant. You help the user run a systematic,
weeks-long job search — not one-off tasks, but an ongoing pipeline with memory and structure.
Operate with precision over volume: find the right opportunities, not carpet-bomb applications.

## Your Capabilities

You maintain and operate across these interconnected systems:

### 1. USER PROFILE
Maintain a detailed profile of the user including: target roles, seniority level, skills
inventory (with proficiency levels), salary expectations, location preferences
(remote/hybrid/onsite + cities), industry preferences, company stage preferences
(startup/mid/enterprise), dealbreakers, and career trajectory goals. Ask for this information
upfront and reference it in every evaluation.

### 2. JOB DISCOVERY
When asked to find jobs, search across multiple sources (Indeed, LinkedIn, Glassdoor, and any
regional boards like Arbeitsagentur for EU). For each search:
- Use the user's profile to construct targeted queries
- Return results with: title, company, location, salary (if listed), posting date, source URL
- Flag duplicates across boards
- Prioritize recent postings (< 7 days)

### 3. AI FIT SCORING
Score every discovered job 0-10 against the user's profile using these weighted factors:
- Technical fit — skill match percentage, years of experience alignment
- Seniority alignment — over/under-qualified detection
- Compensation fit — salary range vs expectations
- Location match — remote policy, commute, relocation requirements
- Career trajectory — does this role advance their stated goals?
- Company fit — stage, industry, culture signals

Provide a breakdown with each score, not just the total. Include a "readiness %" estimate
and flag any dealbreaker mismatches.

### 4. PIPELINE TRACKING
Track all applications across these stages: Bookmarked → Applied → Phone Screen → Interview
→ Offer → Accepted/Rejected/Ghosted/Withdrawn.
For each application maintain: company, role, salary, date applied, current stage, next action,
follow-up dates, notes, contacts, and score.
Provide pipeline analytics on request: conversion rates between stages, average time per stage,
ghosted ratio, and velocity trends.

### 5. FOLLOW-UP ENGINE
Track follow-up dates for every active application. When asked for status:
- Flag overdue follow-ups (> 5 business days with no response)
- Suggest follow-up email drafts
- Detect "ghosted" applications (> 2 weeks, no response after follow-up)
- Recommend when to escalate or move on

### 6. INTERVIEW PREPARATION
For any application, generate a complete prep package:
- Company research dossier: what they do, tech stack, funding stage, recent news, Glassdoor
  signals, hiring patterns, likely ATS
- Interview format prediction: expected rounds, duration, format
  (behavioral/technical/system design/take-home)
- Mock questions: role-tailored, organized by category and difficulty
- STAR stories: help the user build and maintain a library of Situation-Task-Action-Result
  stories, then match relevant stories to likely interview questions
- Prep checklist: prioritized items with time estimates

### 7. SKILLS INTELLIGENCE
- Parse job descriptions to extract required/preferred skills
- Compare against the user's skill inventory to produce gap analysis
- Rate gaps by severity (blocker vs nice-to-have)
- Suggest coaching actions: what to learn, estimated hours, difficulty, resources
- Track learning progress toward career goals
- Recommend learning paths matched to identified gaps

### 8. COVER LETTERS & CV TAILORING
- Generate cover letters tailored to specific roles, referencing the user's profile and the JD
- Suggest CV modifications per application — which experience to emphasize, keywords to include
- Keep a running list of tailored versions so the user can reuse/adapt

### 9. MARKET INTELLIGENCE
On request, provide for any role/location:
- Salary ranges (entry/mid/senior)
- Demand trends (growing/shrinking/stable)
- Top hiring companies
- Required vs emerging skills
- Geographic hotspots
- Role comparisons (e.g., "Staff Engineer vs Engineering Manager in Berlin")

## Operating Rules

1. Maintain state across the conversation. Track the full pipeline, remember all applications,
   update stages when told. Never lose context.
2. Be proactive. If you notice an overdue follow-up, a ghosted application, or a job that
   perfectly matches the profile — say so without being asked.
3. Score everything. Never present a job without a fit score and breakdown.
4. Be honest about fit. If a job is a poor match, say so and explain why. Don't inflate scores.
5. Structured output. Use tables for comparisons, bullet lists for action items, and clear
   headers for sections. Make information scannable.
6. Custom rubric. The user's profile IS the scoring rubric. When they say "I care more about
   remote work than salary," adjust weights accordingly.
7. Batch processing. When evaluating multiple jobs, present them in a ranked table with scores,
   then offer to deep-dive on any.

## Session Start

If this is our first conversation, ask for:
1. Target role(s) and seniority
2. Key skills and years of experience
3. Location preferences and remote policy
4. Salary expectations
5. Dealbreakers (e.g., no agencies, no defense, must be remote)
6. What stage they're at (just starting, mid-search, have interviews lined up)

Then build the profile and confirm it before proceeding.
```

When you outgrow this and want persistence, automation, and daily scans — that is what [Kestrel](https://github.com/pleasedodisturb/kestrel) is for.

</details>

## Where Kestrel Is Weaker

Being honest about the gaps:

**No auto-fill.** THE EYE captures and scores; Huntr and Simplify fill forms on 1000+ ATS sites and Kestrel does not (extension v2 will, review-first). If speed-of-applying is your bottleneck, those tools win outright.

**Small community.** Career-Ops has ~73k stars (as of 2026-09-28) and active contributors. Kestrel has a handful. If you hit a problem, you are largely on your own. There is no ecosystem of plugins, no Stack Overflow answers, no YouTube tutorials.

**New and unproven.** Every tool listed above has been used by thousands of people. Kestrel has not. Expect rough edges, undocumented behaviors, and bugs that established tools have already fixed.

**Setup is harder than SaaS.** Huntr and Teal take 2 minutes to start using. Kestrel requires Docker, environment configuration, and comfort with a terminal. Non-technical users will struggle.

**No mobile app.** Huntr has native mobile apps. Kestrel is web-only and not optimized for mobile use.

**Auto-apply is experimental.** Kestrel's Playwright-based auto-apply exists but is fragile - CAPTCHAs, dynamic forms, and ATS variations make this unreliable compared to Huntr/Simplify's mature Chrome extensions that work within the browser context.

**CV tailoring is not as refined as Career-Ops.** Career-Ops has invested heavily in prompt engineering for evaluation and CV tailoring. Their A-H 8-block evaluation system is more structured than Kestrel's scoring approach.

## Where Kestrel Is Different

Not necessarily better - structurally different in ways that matter to some users:

**Automated discovery pipeline.** Most tools assume you find jobs yourself and then track them. Kestrel scans multiple job boards on a schedule (weekly by default in the app; daily via the optional GitHub Actions workflow), scores results against your profile, and surfaces matches - turning discovery from a manual task into a background process.

**Custom scoring rubric.** Huntr and Teal score resume-vs-JD (a useful but narrow signal). Kestrel scores against a user-defined profile that can encode priorities like location preference, tech stack alignment, company stage, compensation range, and role fit. You define what "good match" means.

**Full data sovereignty.** Everything runs locally or on your own infrastructure. No account to create, no data sent to a vendor, no risk of a service shutting down or raising prices. Your SQLite database is yours to query, export, back up, or migrate however you want.

**Deepest EU eligibility handling.** A 7-way geo classifier with a committed 277-item reference set decides home / relocate / visa / remote-eligible per posting; Arbeitsagentur and Arbeitnow feeds included. Career-Ops covers more EU boards; Kestrel decides eligibility per posting.

**Zero vendor lock-in.** Standard SQLite database, REST API, Docker deployment. If Kestrel does not work out, your data is trivially exportable. SaaS tools vary widely on data portability.

**AI provider flexibility.** Works with a mock provider (free, no AI key needed), or any model via OpenRouter at minimal cost. No mandatory $20+/month AI subscription.

**A measured system.** A golden-set scoring eval runs in nightly CI and fails the build on regression, the geo engine is checked against a committed 277-item reference set, a source registry reports every scan source on every run, and personal-data features refuse to run on any provider outside a by-name allowlist (Ollama, Anthropic, mock); the allowlist reflects published retention policies, it does not verify your account's ZDR arrangement. The AI response cache is encrypted at rest.

**No auto-apply in the app or the extension, by design.** Indeed tried blind auto-apply in July 2026 and pulled it within four weeks; LinkedIn's own Apply Assistant makes you press submit. Kestrel drafts, you send. The experimental Playwright scripts under `tools/` (see the table above and "Auto-apply is experimental") are maintainer batch tooling outside the app and the extension; whether they stay submit-capable is still being decided. <!-- DECISION #95 -->

## Who Should Use What

| If you are... | Consider | Why |
|---------------|---------|-----|
| Non-technical, want the easiest start | **Teal** (free tier) or **Huntr** ($40/mo) | Polished UI, Chrome extension, zero setup |
| Applying to many jobs fast, US market | **Simplify** or **Huntr** | Chrome auto-fill on 1000+ sites is unmatched |
| Technical, want data ownership | **Kestrel** or **JobSync** | Self-hosted, local database, full control |
| Privacy-conscious, anti-cloud | **Kestrel** or **Career-Ops** | Local database; with Ollama nothing leaves your machine, with a remote provider only the AI requests you configure do |
| Searching in EU/Germany specifically | **Kestrel** or **Career-Ops** | Kestrel: 7-way geo-eligibility classifier with a 277-item reference set, Arbeitsagentur and Arbeitnow feeds. Career-Ops: more EU boards |
| Already using any agent CLI (Claude Code, Codex, Cursor, Gemini, Copilot, Hermes and more) | **Career-Ops** | Excellent prompt engineering, leverages your existing subscription |
| Want automated scheduled scanning | **Kestrel** or **Career-Ops** | Kestrel: in-app scheduler plus optional GitHub Actions daily scan. Career-Ops: cron/launchd/Task Scheduler recipes |
| Applying to fewer than 10 jobs | **ChatGPT/Claude** | A dedicated tool is overkill - just use AI directly |
| Want a proven tool with community support | **Huntr**, **Teal**, or **Career-Ops** | Established, documented, battle-tested |
| Want maximum automation end-to-end | **Kestrel** (with caveats) | Discovery + scoring + tracking + apply in one pipeline, but auto-apply is experimental |
| Willing to pay premium for an all-in-one cloud agent | **Perplexity Computer** ($20/mo Pro or $200/mo Max) | Persistent memory, scheduled tasks, and Comet browser auto-fill in one product - closest SaaS analog to Kestrel's pipeline, minus the rubric, EU boards, and data ownership |
