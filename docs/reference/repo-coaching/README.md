# Repo Coaching

A masterlist + research notes + audit + form-factor recommendation + ready-to-paste templates and a time-budgeted playbook, for taking a public GitHub repo from "exists" to "thriving."

## What's in here

| Path | What it is |
|---|---|
| [`MASTERLIST.md`](./MASTERLIST.md) | The big checklist — three layers (Technical, Operational, Marketing/Branding), ~200 items, with `·` marking nice-to-have. |
| [`QUICK-APPLY.md`](./QUICK-APPLY.md) | **Start here if you want to act.** 9 phases, time-budgeted (15 min → 1 day), copy-paste commands referencing files in `snippets/`. |
| [`snippets/`](./snippets/) | Drop-in templates: `CODE_OF_CONDUCT.md`, `FUNDING.yml`, `CITATION.cff`, `.gitattributes`, `SUPPORT.md`, `SECURITY.md`, `bug_report.yml`, `feature_request.yml`, `issue-config.yml`, `pull_request_template.md`, `dependabot.yml`, `release.yml`, `CODEOWNERS`, `labels.yml`, `topics.txt`, `ci.yml`, `scorecard.yml`, `workflow-lint.yml`, `README-template.md`. |
| [`research/`](./research/) | Deep-dive notes per area, with citations. Six files: `01-files`, `02-ci`, `03-supply-chain`, `04-operational`, `05-marketing-readme`, `06-marketing-launch`. |
| [`LANDSCAPE.md`](./LANDSCAPE.md) | What already exists in the repo-coaching / repo-auditing space. Gap analysis. |
| [`AUDIT.md`](./AUDIT.md) | Kestrel-specific audit against the masterlist — what's good, what's missing, prioritized. |
| [`FORM-FACTOR.md`](./FORM-FACTOR.md) | Recommendation: one-off audit, awesome-list, MCP server, or combination? |

## Two ways to use it

### A. "I want to fix my repo today"
1. Open [`QUICK-APPLY.md`](./QUICK-APPLY.md).
2. Pick the phase that matches your hour budget.
3. Copy from `snippets/`, edit the placeholders (`OWNER`, `REPO`, `email`), commit.

### B. "I want to understand the whole picture first"
1. Skim [`MASTERLIST.md`](./MASTERLIST.md). Mark obvious skips.
2. Read [`research/`](./research/) for any item where the masterlist's one-liner isn't enough.
3. Read [`AUDIT.md`](./AUDIT.md) to see the masterlist applied to a real repo.
4. Read [`FORM-FACTOR.md`](./FORM-FACTOR.md) if you're thinking of building tooling on top.
5. Then go to A.

## Source quality

- High-signal docs (GitHub, OpenSSF, opensource.guide, kubernetes.dev, conventionalcommits.org, semver.org, Sigstore, SLSA, Apache/CNCF maturity models).
- Maintainer writing and case studies (AFFiNE 60K stars, Astro, htmx, Supabase, Tailwind, n8n, Plane, Cal.com).
- Live web searches in May 2026 — links cited inline.

This is not a survey paper. It's an opinionated coaching system built to be acted on.
