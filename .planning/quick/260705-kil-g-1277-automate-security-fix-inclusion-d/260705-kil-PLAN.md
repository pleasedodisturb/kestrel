---
phase: quick-260705-kil
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/dependabot-automerge.yml
  - renovate.json
  - .github/dependabot.yml
  - .github/workflows/docker-publish.yml
autonomous: true
requirements: [G-1277]

must_haves:
  truths:
    - "Dependabot patch/minor PRs auto-merge without human action once CI passes"
    - "Dependabot major PRs stay manual (no automerge)"
    - "Dead renovate.json no longer exists in the repo"
    - "Dependabot opens PRs for Docker base-image updates"
    - "The published Docker image is rebuilt weekly to pick up OS security patches"
  artifacts:
    - path: ".github/workflows/dependabot-automerge.yml"
      provides: "Dependabot auto-merge workflow (patch/minor via app token)"
      contains: "dependabot/fetch-metadata"
    - path: ".github/dependabot.yml"
      provides: "docker package-ecosystem entry"
      contains: "package-ecosystem: docker"
    - path: ".github/workflows/docker-publish.yml"
      provides: "weekly scheduled image rebuild"
      contains: "cron:"
  key_links:
    - from: ".github/workflows/dependabot-automerge.yml"
      to: "secrets.RELEASE_APP_ID / RELEASE_APP_KEY"
      via: "actions/create-github-app-token"
      pattern: "create-github-app-token"
    - from: ".github/workflows/dependabot-automerge.yml"
      to: "gh pr merge --auto --squash"
      via: "app token GH_TOKEN"
      pattern: "gh pr merge --auto"
---

<objective>
Automate inclusion of dependency and security fixes: auto-merge Dependabot patch/minor PRs, extend Dependabot to the Docker ecosystem, rebuild the published Docker image weekly for OS security patches, and remove the never-installed Renovate config.

Purpose: Security and dependency fixes currently sit in an 8-PR backlog because every Dependabot PR needs manual merge, and OS-level patches never reach the published image between releases. This closes that gap without human intervention for low-risk updates while keeping majors manual.

Output: One new workflow, two edited workflow/config files, one deleted config file. CI config only — no application code, no unit-test surface.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

<interfaces>
<!-- App-token pattern to copy from release-please.yml (verified in repo): -->
```yaml
- name: Generate token
  id: app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
  with:
    app-id: ${{ secrets.RELEASE_APP_ID }}
    private-key: ${{ secrets.RELEASE_APP_KEY }}
    permission-contents: write
    permission-pull-requests: write
```

<!-- Existing dependabot.yml entries (pip, npm, github-actions) MUST stay untouched.
     Existing entries use commit-message.prefix "deps" (pip/npm) and "ci" (github-actions). -->

<!-- docker-publish.yml currently triggers on: push (branches:[main], tags:v*).
     metadata-action tags block: type=ref,event=branch / type=sha / type=semver.
     On a schedule event github.ref is the default branch (main), so
     type=ref,event=branch still yields a "main" tag and type=sha yields a sha tag;
     the semver tags simply no-op off-tag. No metadata-action change required. -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create Dependabot auto-merge workflow and delete dead Renovate config</name>
  <files>.github/workflows/dependabot-automerge.yml, renovate.json</files>
  <action>
Create `.github/workflows/dependabot-automerge.yml` implementing per-PR auto-merge for Dependabot (per G-1277 locked decision: keep Dependabot, drop Renovate).

Workflow shape:
- `name: Dependabot Auto-merge`
- Trigger: `on: pull_request` with `branches: [main]`.
- Single job (e.g. `automerge`) gated by `if: ${{ github.actor == 'dependabot[bot]' }}`, `runs-on: ubuntu-latest`.
- Job-level `permissions: { contents: write, pull-requests: write }`.
- Step 1 — mint an app token using the exact release-please.yml pattern: `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0`, `id: app-token`, with `app-id: ${{ secrets.RELEASE_APP_ID }}`, `private-key: ${{ secrets.RELEASE_APP_KEY }}`, and scoped `permission-contents: write` / `permission-pull-requests: write`. Add a comment explaining WHY the app token is used: auto-merge with the default GITHUB_TOKEN produces merge pushes that do NOT trigger downstream workflows (docker-publish, release-checks, release-please); the app token restores those triggers.
- Step 2 — fetch update metadata: `dependabot/fetch-metadata@21025c705c08248db411dc16f3619e6b5f9ea21a # v2.5.0`, `id: meta`, with `github-token: ${{ secrets.GITHUB_TOKEN }}`.
- Step 3 — enable auto-merge only for patch/minor. Guard with `if: steps.meta.outputs.update-type == 'version-update:semver-patch' || steps.meta.outputs.update-type == 'version-update:semver-minor'`. Run `gh pr merge --auto --squash "$PR_URL"`. Set `env:` with `GH_TOKEN: ${{ steps.app-token.outputs.token }}` and `PR_URL: ${{ github.event.pull_request.html_url }}` (env indirection — do NOT interpolate github context directly in the run: string; zizmor flags template injection). Add a comment stating major bumps intentionally get NO automerge and stay manual.
- No approval step (this repo has no required reviews).

Then delete `renovate.json` at the repo root (Renovate app was never installed — zero PRs ever produced).
  </action>
  <verify>
    <automated>python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/dependabot-automerge.yml')); print('yaml-ok')" && test ! -e renovate.json && echo "renovate-removed" && grep -q "fetch-metadata@21025c705c08248db411dc16f3619e6b5f9ea21a" .github/workflows/dependabot-automerge.yml && grep -q "gh pr merge --auto --squash" .github/workflows/dependabot-automerge.yml && grep -q 'github.actor == .dependabot\[bot\]' .github/workflows/dependabot-automerge.yml</automated>
  </verify>
  <done>Workflow parses as YAML, gates on dependabot[bot], mints app token, reads fetch-metadata, and auto-merges only patch/minor via env-indirected gh command; renovate.json is gone. No raw github-context interpolation inside any run: block.</done>
</task>

<task type="auto">
  <name>Task 2: Add Docker ecosystem to Dependabot and weekly image rebuild schedule</name>
  <files>.github/dependabot.yml, .github/workflows/docker-publish.yml</files>
  <action>
In `.github/dependabot.yml`, append a new `docker` package-ecosystem entry alongside the existing pip/npm/github-actions entries (leave those untouched):
- `package-ecosystem: docker`
- `directory: "/"`
- `schedule: { interval: weekly }`
- `commit-message: { prefix: "deps" }`

In `.github/workflows/docker-publish.yml`, add a `schedule` trigger to the existing `on:` block (keep the existing `push` branches/tags trigger): `schedule: - cron: '0 5 * * 1'` (Mon 05:00 UTC). Add a comment: weekly rebuild re-runs the Dockerfile's `apt-get upgrade` so the published image picks up OS security patches between releases (G-1274 context). Do NOT change the metadata-action tags block — on a schedule event github.ref is `main`, so `type=ref,event=branch` yields the `main` tag and `type=sha` yields a sha tag; the semver tags no-op harmlessly. The build/push job already tolerates a schedule event (checkout, buildx, GHCR login, build-push all ref-agnostic); make no other changes.
  </action>
  <verify>
    <automated>python3 -c "import yaml; d=yaml.safe_load(open('.github/dependabot.yml')); assert any(u['package-ecosystem']=='docker' for u in d['updates']), 'no docker ecosystem'; print('docker-ecosystem-ok')" && python3 -c "import yaml; w=yaml.safe_load(open('.github/workflows/docker-publish.yml')); on=w[True] if True in w else w['on']; assert 'schedule' in on, 'no schedule'; assert 'push' in on, 'push removed'; print('schedule-ok')"</automated>
  </verify>
  <done>Dependabot has a weekly docker ecosystem entry with deps prefix; docker-publish.yml has both the original push trigger and a Monday 05:00 UTC cron; metadata tags unchanged. Existing pip/npm/github-actions entries intact.</done>
</task>

</tasks>

<verification>
- Both edited/created workflow files parse as YAML (verified in task automated checks).
- No raw `${{ github.* }}` interpolation inside any `run:` block (env indirection used for PR_URL and GH_TOKEN) — satisfies zizmor template-injection rule.
- All action pins use the SHA-pinned versions specified (create-github-app-token v3.2.0, fetch-metadata v2.5.0) — satisfies actionlint/zizmor pinning expectations.
- No application code changed; no unit tests apply (CI config only). YAML validity is the completion signal.
</verification>

<success_criteria>
- `.github/workflows/dependabot-automerge.yml` exists and auto-merges Dependabot patch/minor PRs via a minted app token; majors stay manual.
- `renovate.json` deleted.
- `.github/dependabot.yml` gained a weekly docker ecosystem entry; existing entries untouched.
- `.github/workflows/docker-publish.yml` gained a Monday 05:00 UTC cron rebuild alongside the existing push trigger.
- Changes committed on branch `G-1277/auto-fix-inclusion` with conventional commits (`feat(G-1277):` for the new workflow, `chore(G-1277):` for renovate removal / dependabot + schedule edits).
</success_criteria>

<output>
Create `.planning/quick/260705-kil-g-1277-automate-security-fix-inclusion-d/260705-kil-SUMMARY.md` when done.
</output>
