# 06 — Marketing & Launch Choreography

Format per item: **Why** / **How** / **Pitfall**. Sources cited inline.

## External Discovery

- **Awesome-list inclusion** — Why: high-intent referrals. How: PR one alphabetized line `[Name](url) - description.` matching `contributing.md`. Pitfall: drive-bys ignoring sort/format are auto-closed.
- **AlternativeTo / SaaSHub / StackShare / Slant** — Why: catch comparison-stage searchers. How: claim listing, add screenshots, cross-link competitors. Pitfall: stale logo + no screenshots reads as abandoned.

## Newsletter Pitches

- **TLDR / console.dev / bytes.dev / Hacker Newsletter / Changelog Weekly / This Week in [Lang]** — Why: thousands of niche devs per issue ([console.dev](https://console.dev) hand-curates dev tools). How: pitch each submission form 2–3 weeks pre-launch with one-line hook + link + screenshot. Pitfall: same-week-as-HN pitches — editors want exclusivity windows.

## Communities

- **Reddit** — Why: subreddit-native posts drive 10k+ visits. How: read sub rules, build karma first, post problem-narrative not promo, answer every comment. Pitfall: low-karma self-promo gets shadow-removed in r/programming, r/webdev, r/selfhosted.
- **Show HN** — Why: front-page = 20k–80k visits + durable backlink. How: title `Show HN: <Tool> – <plain claim>`; Tue–Thu 08:00–11:00 ET; founder live from minute 1; try-able without signup ([HN guidelines](https://news.ycombinator.com/showhn.html); [DEV launch guide](https://dev.to/dfarrell/how-to-crush-your-hacker-news-launch-10jk)). Pitfall: hype titles, vote-rings, absent founder.
- **Lobsters** — Why: small, high-signal sysadmin/PL audience. How: get invited by someone who knows your work; new users can't submit unseen domains ([Lobsters about](https://lobste.rs/about)). Pitfall: pestering #lobsters IRC for invites.
- **Product Hunt** — Why: worth it for B2B SaaS/consumer tools, less for pure CLIs. How: Tue/Wed week 2–3 of month, 12:01am PT; gold-badge hunter writing first comment helps; pre-build subscribers via "coming soon" ([iris1031 PH playbook](https://dev.to/iris1031/product-hunt-launch-playbook-the-definitive-guide-30x-1-winner-1pbh)). Pitfall: paying for upvotes = ban.
- **dev.to / Hashnode** — Why: SEO + community discovery. How: cross-post with `canonical_url` to your domain. Pitfall: missing canonical splits Google authority.
- **Indie Hackers** — Why: founder audience values journey. How: share milestones with numbers and lessons. Pitfall: vague "we launched!" posts get ignored.

## Owned Surfaces

- **Docs on own domain** — Why: SEO equity compounds; you keep traffic if you migrate hosts. How: `docs.kestrel.app` with sitemap, OG tags, canonical URLs, Schema.org `SoftwareApplication`, FAQ JSON-LD. Pitfall: docs only on github.io — Google attributes authority to GitHub.
- **Comparison landing pages** — Why: capture `kestrel vs X` and `migrate from X` queries. How: honest table + migration script. Pitfall: dishonest comparisons get dunked on HN.
- **Audience landings** — `/for-django`, `/for-data-scientists` — Why: long-tail + relevance. How: one page per persona with their stack's terminology. Pitfall: thin content = Google demotes site-wide.
- **Tutorial SEO** — Why: "how to X with Y" outranks marketing pages. How: 2 tutorials/month, real code, embed video. Pitfall: AI-generated thin tutorials hurt domain.
- **llms.txt + llms-full.txt** — Why: AI assistants cite your docs accurately ([spec](https://llmstxt.org/)). How: serve both at root; `llms.txt` = TOC with one-sentence summaries; `llms-full.txt` = concatenated docs. Pitfall: serving stale copies — wire to docs build.

## Content

- **Launch blog post** — Structure: problem → why existing tools fail → solution → demo gif → architecture → CTA (star + try). Pitfall: leading with architecture before pain.
- **Weekly/monthly changelog** — Why: signals momentum to stargazers. How: blog + email + RSS, one paragraph per shipped item. Pitfall: skipping months kills the habit.
- **Engineering deep-dives** — Why: Stripe/Supabase/PlanetScale/Fly.io built reputation here. How: 1500–2500 words on one hard problem you solved with diagrams + benchmarks. Pitfall: marketing-flavored "deep dives" with no real internals.

## Audio/Video/Live

- **Conference talks, podcasts, YouTube demos** — Why: durable backlinks + trust. How: pitch CFPs 6 months out; offer founder for podcast slots. Pitfall: 60-min screen recordings nobody finishes — keep demos under 3 min.

## Social

- **Build-in-public on X / Bluesky / Mastodon** — Why: compounds attention before launch. How: 3–5 weekly posts mixing screenshots, metrics, decisions. Pitfall: only posting wins.
- **Project handle namecheck** — Reserve `@kestrel` on every network day one. Pitfall: squatters force rebrands.
- **Founder vs project handle** — Why: founders gain followers faster; project handle is institutional. How: run both; founder posts personal, project posts releases. Pitfall: empty project handle looks dead.
- **Reply-guy strategy** — Why: relevant replies to authority accounts > original posts early. How: 5 thoughtful replies/day in your niche. Pitfall: spammy "check out our tool" replies = blocks.
- **Milestone posts (1k/10k stars)** — Why: free amplification. How: thank early users + share what you learned. Pitfall: gloating without gratitude.

## Launch Choreography

- **Pre-launch (T-30 to T-1):** waitlist landing, recruit 5–10 design partners, draft HN/PH/Reddit copy, prime newsletters.
- **Launch day (T+0):** publish HN + Reddit + X/Bluesky + Product Hunt within 2 hours; founder online 12 hours; reply to every comment.
- **Post-launch (T+1 to T+30):** thank-you blog with metrics, follow-up newsletter to waitlist, ship visible improvement weekly.
- **Don't buy stars** — vendors are detected; GitHub purges; trust evaporates ([AFFiNE 60K case study](https://dev.to/iris1031/how-to-get-more-github-stars-the-definitive-guide-33k-stars-case-study-2kjo)).

## Differentiation

- Explicit "**not X**" line in README; "**X for Y**" positioning; one **wedge feature** competitors lack; **10× claim with proof** (benchmark/screenshot/repo).
- **Anti-patterns:** badge soup, missing screenshots, jargon-dense intros, "production-ready" with no users, clone-of-clone.

## Measurement

- **Star velocity** (stars/week trend), **GitHub Insights → Traffic** (referrers + clones), **Plausible/Fathom** on docs, **UTM** every outbound link, conversion funnel (visit → star → install → retain), newsletter open/CTR, **Discord WAM** (weekly active members). Pitfall: tracking stars only — vanity without retention.

---

**Summary:** Concentrate launch traffic into 48h across HN (Tue–Thu morning), Reddit, X, and Product Hunt; own your docs domain with llms.txt, comparison and audience landings; ship weekly changelogs and deep-dives; measure star velocity, traffic referrers, and retention — never buy stars.
