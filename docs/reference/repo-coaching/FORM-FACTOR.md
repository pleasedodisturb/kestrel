# Form Factor — what to build with this

This research can crystallize into one of five things. Picking the right one depends on goal, audience, and maintenance budget.

## Options

### A. One-off audit (this folder, as-is)
- **What:** the four files already written: `MASTERLIST.md`, `LANDSCAPE.md`, `AUDIT.md`, `FORM-FACTOR.md`.
- **Audience:** the Kestrel maintainer.
- **Effort:** done.
- **Leverage:** small (one repo) but immediate.
- **Risk:** zero; even if nothing else happens, the audit is actionable.

### B. Public `awesome-repo-coaching` list
- **What:** a curated GitHub repo (e.g. `pleasedodisturb/awesome-repo-coaching`) with the masterlist as the README, sourced from this folder.
- **Audience:** OSS maintainers globally.
- **Effort:** low to start (rename + polish), medium ongoing (PR triage, link rot, biannual refresh).
- **Leverage:** distribution from "awesome" mirrors; cross-link from the [awesome](https://github.com/sindresorhus/awesome) parent. Likely 1–10k ⭐ if positioned well, given the gap shown in `LANDSCAPE.md`.
- **Risk:** awesome-list maintenance fatigue. Stale lists hurt the brand.
- **Decision factors:**
  - Is there genuinely no `awesome-oss-launch` / `awesome-repo-health` already? (`LANDSCAPE.md`: appears not.)
  - Does the maintainer want OSS-meta as a side project?

### C. CLI / GitHub Action: `repo-coach` (opinionated repolinter for 2026)
- **What:** `npx repo-coach audit` → markdown report with checklist results, priority list.
- **Audience:** maintainers who want automation.
- **Effort:** ~2 weeks for MVP that covers ~60 checks (presence-of-file + simple regex). Months to cover the full masterlist properly (qualitative grading needs LLM).
- **Leverage:** medium; competes with repolinter (stale) and Scorecard (security-only). Differentiator: covers marketing/branding rules, which nothing else does.
- **Risk:** repolinter has been stagnant since 2022 — there's a reason. Presence-of-file linting hits a ceiling fast.
- **Decision factors:**
  - Is the maintainer willing to ship + maintain a CLI?
  - Does the marketing-rule set provide enough differentiation?

### D. AI bot / MCP server: `repo-coach`
- **What:** an MCP tool (Claude/Cursor/Continue) or GitHub App that scans a repo and produces a coaching report. LLM grades qualitative items (README hook quality, comparison table presence, hero artifact strength) that no static linter can judge.
- **Audience:** ChatGPT/Claude users; integrators in Cursor/Continue/Claude Code.
- **Effort:** 1–2 weeks for MCP MVP that wraps `gh` + an LLM prompt. Longer for hosted GitHub App with auth + queue + UI.
- **Leverage:** highest — fills the largest gap (`LANDSCAPE.md` Section F: "AI-driven repo-level coaching: none"). MCP form factor is _trending_ in 2026 and undersaturated.
- **Risk:** LLM cost + drift; needs prompt-tuning over time. Quality variance per model release.
- **Decision factors:**
  - Comfort with MCP/Anthropic-SDK glue.
  - Tolerance for ongoing prompt maintenance.

### E. Combination: **awesome-list + MCP server**
- **What:** `awesome-repo-coaching` is the public artifact; the MCP server is the executable form. Awesome-list links to MCP server; MCP server cites awesome-list as source.
- **Effort:** A's effort + D's effort.
- **Leverage:** highest combined. Awesome-list is the SEO surface; MCP server is the verb ("Claude, audit my repo with repo-coach").
- **Risk:** double maintenance, but the surfaces are decoupled.

## Recommendation

> **Ship A now. Then B in 1 week. Then D as a side project over 2–4 weekends.**

Reasoning:

1. **A is already done** and immediately useful for Kestrel itself. Don't gate it behind further build-out.
2. **B (awesome-list) has the clearest gap** (`LANDSCAPE.md` Section F). Cost is low; downside is bounded; upside is meaningful distribution. Existing `awesome-readme` covers ~20% of the surface; nothing covers the cross-cutting view.
3. **D (MCP server)** is the most _interesting_ technical artifact — and matches Kestrel's actual stack (Python + AI providers + MCP-friendly). Prototype is small. Differentiation is real (no AI bot does repo-level coaching today; all of CodeRabbit/Greptile/Ellipsis are PR-level).
4. **C (CLI)** is the weakest of the four — repolinter exists, repolinter is stale, and presence-of-file linting can't grade the marketing layer. Skip unless C-as-an-MCP-backend turns out to be useful infrastructure.

### Why not skip B and go straight to D?

Distribution. An awesome-list converts in GitHub search, in awesome-mirror sites, and in lazy-readers' bookmarks. An MCP server requires Claude Desktop / Cursor / Continue users to install something. The list seeds the bot's audience.

## MVP for each — 1-paragraph specs

### B. `awesome-repo-coaching` MVP

A public repo whose README is `MASTERLIST.md` (renamed) plus a top section explaining the three layers, plus a "Tools" appendix lifted from `LANDSCAPE.md`. Cross-link from `awesome-readme` and `awesome-actions` via PRs. Add a `CONTRIBUTING.md` accepting submissions. Set up a quarterly refresh cadence in a `MAINTENANCE.md`. A curated link list, an opinionated checklist, _and_ a tools-mapping is more useful than any of the three alone.

### D. `repo-coach` MCP server MVP

A Python (or TypeScript) MCP server exposing one tool: `audit_repo(owner, repo)`. Implementation:
1. Pull repo metadata via GitHub REST: file tree, file contents (README, CONTRIBUTING, SECURITY, .github/), repo settings (description, topics, homepage), workflow files, recent issues/PRs stats.
2. Run rule engine: ~80 deterministic rules (presence, regex, length, badge count) for cheap.
3. Send the README + masterlist + audit-template to an LLM (Claude Sonnet 4.6) for qualitative grading on ~30 items (hook quality, comparison present, wedge clear, social preview likely-attractive).
4. Return a single Markdown audit document, prioritized like `AUDIT.md`.

Distribution: publish on the [MCP servers registry](https://github.com/modelcontextprotocol/servers), pin to the awesome-list (Option B), submit to MCP-aware indexes (`mcp.so`, `mcphub.io`), and write one launch post.

### Optional: D2 — GitHub App version

If the MCP server gets traction, port it to a GitHub App that runs quarterly and opens a single tracking issue with a fresh audit. Higher distribution leverage, higher install friction. Defer to Q3/Q4 contingent on D pickup.

## Non-recommendations

- **Don't write a repolinter fork.** Static checks are ~30% of the value; LLM grading is the real unlock.
- **Don't gate this behind a SaaS.** OSS maintainers are price-sensitive and meta-tooling SaaS is a hard sell. Free MCP server + free awesome-list is the right model. If monetized later, sponsorships beat seats.
- **Don't position it against Scorecard.** Position it as _complementary_ — Scorecard is your floor; repo-coach is how you become loved.

## Kill criteria

- **B** dies if it doesn't cross 200 ⭐ in 60 days. Either positioning is wrong or the gap was overestimated.
- **D** dies if the MCP server isn't producing _better_ audits than a generic Claude prompt by version 0.3. The rule-engine + structured prompt has to add real signal.

## Concrete next step (today)

Commit and push this folder. That ships A. Decide on B/D timing in the next planning cycle.
