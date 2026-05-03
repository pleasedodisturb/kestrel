# Operational Practices for Healthy Public GitHub Repos

Each item: WHY / HOW / PITFALL with citations.

## Issue Triage

**Weekly triage cadence** — WHY: Stale issues lose context, signal neglect. HOW: Weekly slot; rotate "triage captain" on larger projects (k8s SIGs do per-SIG rotations). PITFALL: A solo permanent triager burns out, becomes SPOF. <https://www.kubernetes.dev/docs/guide/issue-triage/> <https://devguide.python.org/triage/>

**Label taxonomy `type/* area/* priority/* status/*`** — WHY: Orthogonal axes filter by any dimension. HOW: k8s-style `kind/bug`, `area/api`, `priority/important-soon`, `triage/accepted`; keep canonical `good first issue` + `help wanted`. PITFALL: 80 bespoke labels nobody applies — keep <30, document each.

**Issue forms over markdown templates** — WHY: YAML forms enforce required fields. HOW: `.github/ISSUE_TEMPLATE/bug_report.yml` with `validations: required: true` on env + repro. PITFALL: Too many required fields make casual reporters bounce.

**Sane stale-bot policy** — WHY: Auto-closing legitimate bugs erodes trust. HOW: Run only on `status/needs-info`, >=90 days idle; exempt `kind/bug`, `kind/security`, `pinned`, `help wanted`. PITFALL: Default config closes everything. <https://github.com/actions/stale>

**Discussions vs Issues** — WHY: Issues = actionable; Discussions = Q&A and ideas. HOW: Enable Discussions, redirect support questions, convert when warranted. PITFALL: Aggressive splitting fragments search.

**Auto-lock old threads** — WHY: Necro-comments fragment context, ping unrelated participants. HOW: `dessant/lock-threads`, lock 60–90 days post-close, allow re-open via new issue. PITFALL: Locking <30d blocks legitimate "I hit this too" follow-ups.

## Pull Request Workflow

**Small PRs (<400 LOC)** — WHY: SmartBear/Cisco study: defect detection collapses past ~400 LOC; sweet spot 200–400. HOW: Stack PRs (Graphite/spr) or split prep + behavior + cleanup. PITFALL: Counting generated/lockfile lines — exempt in PR-size bot. <https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf>

**Draft PRs by default** — WHY: Signals "feedback welcome, not ready to merge". HOW: Open as Draft; mark Ready when CI green and self-review done. PITFALL: Drafts skip CODEOWNERS auto-assign — re-trigger on Ready.

**PR template + self-review checklist** — WHY: Forces author to articulate intent, catch own bugs. HOW: `.github/pull_request_template.md` with Why/What/How-tested/Screenshots + checkboxes. PITFALL: Templates so long contributors delete them — keep under 10 lines.

**Conventional Commit PR titles** — WHY: Auto-generates changelogs, triggers semantic-release. HOW: `amannn/action-semantic-pull-request` enforces `type(scope): subject`, paired with squash so the squash inherits the title. PITFALL: Without squash, PR title never lands in history.

**Pick one merge strategy** — WHY: Mixing destroys `git log --first-parent` and bisect. HOW: Disable two of three; default = squash for apps, rebase for libraries with clean commits, merge for long-lived release branches. PITFALL: Allowing all three lets reviewers pick at random.

**GitHub Merge Queue** — WHY: Eliminates "green PR breaks main" race. HOW: Enable on protected branch once you exceed ~5 merges/day with non-trivial CI. PITFALL: Wasted overhead on low-velocity repos.

**Auto-merge for Dependabot** — WHY: Patch/minor security bumps shouldn't need a human if CI passes. HOW: `dependabot/fetch-metadata` + `gh pr merge --auto --squash`, gated on `version-update:semver-patch`. PITFALL: Auto-merging majors silently breaks consumers.

**CODEOWNERS routing** — WHY: Auto-assigned, required reviewers; no chat-nagging. HOW: `.github/CODEOWNERS` + branch-protection "require code-owner review". PITFALL: Wildcards owning everything route every PR to two people who burn out.

**Public review SLA** — WHY: Sets expectations, prevents PR rot. HOW: CONTRIBUTING.md states "first response 5 business days, merge or actionable feedback within 2 weeks"; track via CHAOSS time-to-first-response. PITFALL: Promising 24h and missing — commit only to what's sustainable.

**Conventional Comments tone** — WHY: Prefixes (`praise:`, `nit:`, `suggestion:`, `issue:`, `question:`, `thought:`, `chore:`) defuse tone ambiguity. HOW: Link conventionalcomments.org in CONTRIBUTING; saved-replies. PITFALL: `nit:` on blocking concerns confuses authors. <https://conventionalcomments.org/>

**Trunk-based development** — WHY: Short branches + CI beat long feature branches on integration cost. HOW: Branches <2 days, feature flags for incomplete work. PITFALL: TBD without flags ships half-built features. <https://trunkbaseddevelopment.com/>

## Governance

**BDFL vs committee vs foundation; lazy consensus** — WHY: Decision rights must be explicit or every dispute escalates. HOW: GOVERNANCE.md; lazy consensus = "silence = approval after 72h" for low-stakes calls. PITFALL: BDFL with no named successor = guaranteed crisis.

**RFC process** — WHY: Big changes deserve written rationale before code. HOW: Rust/React-style `rfcs/` directory, template Motivation/Design/Drawbacks/Alternatives, 1–2 week window. PITFALL: RFC required for trivia kills momentum — set a scope threshold.

**Public roadmap (project board)** — WHY: Contributors self-select work; users see what's coming. HOW: GitHub Projects Now/Next/Later, linked from README. PITFALL: Roadmap = perceived promise — mark "non-binding".

**Maintainer onboarding/offboarding** — WHY: Clear ladder reduces hazing; offboarding prevents ghost-maintainer bottlenecks. HOW: MAINTAINERS.md + emeritus list; revoke perms on >12mo inactivity (with consent). PITFALL: Abandoned 2FA accounts are a supply-chain risk.

**DCO over CLA (default DCO)** — WHY: DCO (`Signed-off-by`) is lightweight; CLAs deter casual contributions, centralize copyright. HOW: Enable DCO app; require signed-off commits. PITFALL: Corporate adopters sometimes need CLA — pick deliberately.

**Contributor ladder** — WHY: Visible progression (Contributor → Reviewer → Approver → Maintainer) distributes load. HOW: Document criteria (e.g., 10 merged PRs to Reviewer); OWNERS files (k8s pattern). PITFALL: No ladder = maintainers do everything forever.

## Community

**CoC enforcement path** — WHY: A CoC without enforcement contact is theater. HOW: Named person + email in CODE_OF_CONDUCT.md, ack within 72h, document outcomes. PITFALL: Pointing reports at a generic alias nobody reads.

**all-contributors bot** — WHY: Recognizes non-code contributions (docs, design, triage). HOW: `@all-contributors please add @user for docs,design`. PITFALL: Table becomes unmanageable — move to CONTRIBUTORS.md. <https://allcontributors.org/>

**Community channel choice** — WHY: One canonical channel concentrates signal. HOW: Discord (casual), Slack (corporate, hides free-tier history), Matrix (FOSS, federated), Discourse (searchable, async). PITFALL: Slack free tier deletes history >90d.

## Burnout / Sustainability

**Burnout prevention** — WHY: Maintainer burnout kills more projects than tech debt. HOW: Pinned "scope" issue; saved reply for saying no; named successor (bus factor). PITFALL: Heroics become unspoken expectation.

**Funding: Sponsors / Open Collective / Polar.sh / Tidelift** — WHY: Recurring funding signals legitimacy, funds triage time. HOW: Sponsors for individuals, Open Collective for fiscal hosting, Polar.sh for bounties, Tidelift for enterprise subscriptions. PITFALL: Funding raises SLA expectations — set them explicitly.

**CHAOSS metrics** — WHY: Measure health objectively. HOW: Track Contributor Absence (bus/lottery) Factor (smallest set producing 50% of contributions), time-to-first-response, time-to-merge via Augur/GrimoireLab. PITFALL: Optimizing time-to-merge alone encourages rubber-stamp reviews. <https://chaoss.community/kb/metric-bus-factor/> <https://chaoss.community/>

---

**Summary (≤50 words):** Healthy public repos need weekly triage with orthogonal labels, structured issue forms, and a sane stale policy; small (<400 LOC) draft PRs with Conventional Commits + one merge strategy; explicit governance (DCO, ladder, RFC) and a named CoC contact; and CHAOSS-measured sustainability with funding plus succession to prevent burnout.
