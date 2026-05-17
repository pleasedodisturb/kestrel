# GitHub Repo Marketing & README Practices

Research notes for Kestrel. Format: WHY / HOW / PITFALL per topic. Sources inline.

## Identity

**Repo name** — WHY: memorable, searchable names get stars; collisions kill SEO. HOW: short verb-or-noun (≤2 syllables), namecheck npm, PyPI, GitHub, domain, USPTO TESS in one pass. PITFALL: clever puns that no one can spell or trademark (see https://www.namecheckr.com).

**One-liner formula** — WHY: visitors decide in 5 seconds. HOW: `<verb> <thing> for <who>` — Supabase: "the open source Firebase alternative"; Cal.com: "scheduling infrastructure for everyone." PITFALL: starting with "A library that…" — leads with implementation, not value.

**Tagline (5–7 words)** — WHY: fits the About panel and OG card. HOW: pair with the one-liner; htmx uses "high power tools for HTML." PITFALL: marketing fluff ("revolutionary AI-powered…") triggers skepticism.

**Logo (light + dark, SVG)** — WHY: a wordmark is the strongest recall surface. HOW: ship `logo-light.svg`, `logo-dark.svg`, `logo-mark.svg` (favicon-safe at 32px), 256/512/1024 PNG fallbacks, in `/.github/assets/` or `/docs/assets/`. PITFALL: rasterized logos blur on Retina; never inline base64 in README.

**Brand colors + domain** — WHY: consistency = trust. HOW: pick 1 primary + 1 accent + neutral ramp; `.dev` reads modern, `.com` reads default-trusted, `.io` reads dev-tool but is saturated. PITFALL: `.io` has a contested origin and rising renewal costs (https://every.to/p/the-disappearing-io).

## README Hero

**Centered logo, light/dark via `<picture>`** — WHY: GitHub renders dark/light themes; one image looks broken in half your audience. HOW:
```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./.github/assets/logo-dark.svg">
  <img alt="Kestrel" src="./.github/assets/logo-light.svg" width="320">
</picture>
```
PITFALL: relative paths break on npm/PyPI mirrors — use absolute `https://raw.githubusercontent.com/...` for package registries.

**Hero artifact (asciinema / VHS / GIF)** — WHY: a 10-second demo beats 200 lines of prose. HOW: charmbracelet/vhs renders `.tape` files to GIF/MP4/WebM (https://github.com/charmbracelet/vhs); asciinema for terminal flows (https://asciinema.org); Loom/Tella for product walkthroughs. PITFALL: 8 MB GIFs hang mobile; cap ≤2 MB, ≤30 s, use WebM where supported.

**30-second CTA** — WHY: every README must answer "how do I try this in 30 s?". HOW: one `curl | sh`, `npx`, or `docker run` line above the fold. PITFALL: burying install behind a TOC.

## Badges

**Pick 3–5; avoid soup** — WHY: badges are trust signals; >6 looks like over-compensation. HOW: choose CI status, latest version, license, downloads, OpenSSF Scorecard (https://shields.io, https://securityscorecards.dev). PITFALL: stale "build passing" badges from a deleted CI service — audit quarterly.

**Codespaces / Replit buttons** — WHY: zero-install try-it-now is the highest-converting CTA. HOW: `https://github.com/codespaces/new?repo=<owner>/<repo>` shield (https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces). PITFALL: Codespaces fails without a working `.devcontainer.json`.

## README Body

**Quickstart-first, then features** — WHY: working code earns the right to explain architecture. HOW: order = Hero → Quickstart → Features (with screenshots) → Comparison table → Architecture (Mermaid) → Use-cases → Who Uses → Roadmap → Community → Sponsors. Astro and Prisma both follow this (https://github.com/withastro/astro, https://github.com/prisma/prisma). PITFALL: leading with philosophy/manifesto.

**Comparison table** — WHY: positions you against incumbents fast. HOW: 4–6 rows, your project as left column, checkmarks not prose; n8n vs Zapier is canonical (https://github.com/n8n-io/n8n). PITFALL: dishonest checkmarks invite HN dunk threads.

**Architecture diagram (Mermaid)** — WHY: GitHub renders Mermaid natively, no image pipeline. HOW: ` ```mermaid ` fenced block; keep ≤12 nodes. PITFALL: Mermaid doesn't render on npm/PyPI — provide an SVG fallback for package pages.

**"Who uses X" wall + testimonials** — WHY: logos are the fastest social proof. HOW: a logo grid in `/.github/assets/users/`; supabase and tailwindcss both run one. PITFALL: never add logos without written permission.

**Roadmap link, star history, community, sponsors** — WHY: signals momentum + sustainability. HOW: link to a `ROADMAP.md` or GitHub Project; embed star-history.com chart; link Discord/Slack; add GitHub Sponsors + OpenCollective. PITFALL: a roadmap that hasn't moved in 6 months is worse than no roadmap.

**TOC only if >500 lines** — WHY: short READMEs don't need them; GitHub auto-generates one in the file header. PITFALL: hand-maintained TOCs drift.

## Visual Assets

**Social preview 1280×640** — WHY: every link share renders the OG card. HOW: Settings → Social preview; per-page OG via og-image generators (https://github.com/vercel/og-image). PITFALL: text under 24 px is unreadable in Slack/Twitter previews.

**Code screenshots** — WHY: prose-quality code in marketing pages. HOW: carbon.now.sh or ray.so (https://carbon.now.sh, https://ray.so). PITFALL: hand-screenshotting your editor — inconsistent fonts and themes.

**Brand kit / Figma** — WHY: contributors and press need assets. HOW: a public Figma file linked from `/BRAND.md` with logo, colors, type, do/don't. PITFALL: shipping JPGs of logos.

## On-GitHub Discovery

**Topics (≤20)** — WHY: drives `github.com/topics/<x>` traffic. HOW: audit popular topics on https://github.com/topics (e.g., `ai`, `llm`, `ai-agents`, `python`, `fastapi`, `react`, `typescript`, `job-search`, `self-hosted`); pick 10–15. PITFALL: topics like `awesome` without an `awesome-list` are spam-flagged.

**Description (About panel)** — WHY: appears in search snippets and OG fallback. HOW: keyword-rich, ≤120 chars, ends with link to docs. PITFALL: emoji-only descriptions hurt SEO.

**Pinned repos + org profile README** — WHY: a `.github` repo with a `profile/README.md` becomes your org landing page. HOW: see https://docs.github.com/en/account-and-profile. PITFALL: unmaintained pins look abandoned.

**GitHub Trending — star velocity** — WHY: 50–200 stars in 24–48 h pushes you to language-Trending; once there, organic adds 300–1,000/day. HOW: coordinate launch (HN, Product Hunt, mailing list) on one day; geographic diversity matters. PITFALL: bought stars get the repo flagged.

**GitHub Stars program** — WHY: Stars get early features and amplification (https://stars.github.com). HOW: nominate via the form; consistent content + community work qualify. PITFALL: it's not a growth hack — it follows traction, not the other way around.

## Excellent Examples

supabase, withastro/astro, bigskysoftware/htmx, tailwindlabs/tailwindcss, prisma/prisma, n8n-io/n8n, calcom/cal.com, makeplane/plane — all use the picture-element logo, hero GIF/screenshot, quickstart-above-the-fold, comparison table, and `.github/assets/` convention.

## Sources
- https://github.com/matiassingers/awesome-readme
- https://github.com/topics
- https://github.com/charmbracelet/vhs
- https://asciinema.org
- https://carbon.now.sh, https://ray.so
- https://shields.io, https://securityscorecards.dev
- https://stars.github.com
- https://dev.to/iris1031/how-to-get-more-github-stars-the-definitive-guide-33k-stars-case-study-2kjo
- https://earezki.com/ai-news/2026-04-03-github-stars-history-how-to-track-analyze-grow-your-repository/
- https://tom.preston-werner.com/2010/08/23/readme-driven-development.html
