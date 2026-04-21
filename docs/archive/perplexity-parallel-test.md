# Perplexity Pro + Comet vs Kestrel — Parallel Test Log

Structured template for running an empirical side-by-side between Kestrel and Perplexity Pro ($20/mo) + Comet browser. Fill this in while running the tests; publish the completed result as a blog post or gist and link it from `docs/COMPARISON.md` as empirical backing for the Perplexity Computer row.

> **Why Pro, not Max?** Perplexity Computer lives on the $200/mo Max tier. Pro ($20/mo) gives you Comet and most of what a job seeker would actually touch day-to-day. The Computer-only capabilities (scheduled tasks, persistent sandbox, 19-model orchestration) are not testable on this plan — rely on primary sources for those claims in the PR.

---

## Metadata

- **Tester:** <!-- your name / handle -->
- **Date:** <!-- YYYY-MM-DD -->
- **Kestrel version / commit:** <!-- git rev-parse HEAD -->
- **Perplexity plan:** Pro ($20/mo)
- **Comet version:** <!-- from About menu -->
- **Browser:** <!-- Comet is the browser; note OS -->

## Setup checklist

Before starting, prepare a clean testing environment:

- [ ] **Throwaway LinkedIn profile** created (burner email, fake-but-plausible work history)
- [ ] **Throwaway resume PDF** saved to disk (matches the burner profile)
- [ ] **Comet installed** and logged into the burner LinkedIn
- [ ] **Kestrel running locally** (`docker compose up -d`, web UI reachable)
- [ ] **Kestrel profile** configured with the same target role/skills as the burner resume, so scoring is comparable
- [ ] **5 real job postings picked** (see table below) — mix of ATS types
- [ ] **Screen recording or screenshot tool** ready (optional but recommended for the writeup)

> **Safety note:** Comet auto-fill runs in a real browser session. Never point it at your real LinkedIn or your actual job applications while testing — you do not want a misfire submitting a half-filled application with your real name on it.

## Test subjects

Pick 5 real postings covering the ATS variety Kestrel claims to handle:

| # | Company | Role | ATS type | URL | Why chosen |
|---|---------|------|----------|-----|------------|
| 1 | | | Greenhouse | | |
| 2 | | | Lever | | |
| 3 | | | Workday | | |
| 4 | | | LinkedIn Easy Apply | | |
| 5 | | | Direct company page | | |

---

## Per-job test protocol

Run this exact script against **each** of the 5 jobs, logging results in both systems. Copy the result block below for each job.

### Steps (run in order)

1. **Discovery** — would the tool have surfaced this job without me specifying the URL?
   - Kestrel: run `kestrel discovery run` with a query matching the role/location; check if the job appears
   - Perplexity: ask Comet `"Find [role] jobs at [company]"` or `"Find recent [role] postings in [location]"`; check if it appears
2. **Scoring** — feed the JD + resume/profile to each
   - Kestrel: import the job and let it score against your profile
   - Perplexity: paste JD + resume, ask `"Score this job against my resume 0-10 and explain the gaps"`
3. **Cover letter** — generate one in each
   - Kestrel: `kestrel apply cover-letter <id>`
   - Perplexity: `"Draft a cover letter for this role using my resume"`
4. **Auto-fill** — navigate to the application form, let each system fill it up to (NOT including) submit
   - Kestrel: `kestrel apply <id>` (dry run / Playwright)
   - Comet: navigate to the form in Comet, invoke the assistant, ask it to apply
5. **Interview prep** — ask each for a company research dossier and likely interview questions
   - Kestrel: `kestrel prep <id>`
   - Perplexity: `"Research [company], predict interview format for a [role], and give me 10 likely questions"`

### Result block (copy for each job)

```
## Job N: <Company> — <Role> (<ATS>)

URL: <paste>
Date tested: <YYYY-MM-DD>

### 1. Discovery
- Kestrel: [found / missed / partial] — <notes>
- Perplexity Comet: [found / missed / partial] — <notes>
- Winner: [Kestrel / Perplexity / tie]

### 2. Scoring
- Kestrel: <score>/10 — <one-sentence rationale from the tool>
- Perplexity: <score>/10 — <one-sentence rationale from the tool>
- Was the Kestrel rubric breakdown more useful than Perplexity's prose? [yes / no / about the same]
- Winner: [Kestrel / Perplexity / tie]

### 3. Cover letter
- Kestrel output quality (1-5): <n>
- Perplexity output quality (1-5): <n>
- Which felt more tailored to the specific JD? [Kestrel / Perplexity / tie]
- Which required less post-editing? [Kestrel / Perplexity / tie]
- Winner: [Kestrel / Perplexity / tie]

### 4. Auto-fill
- Kestrel (Playwright): [completed / partial / failed] — fields filled: <count> / <total>, errors: <list>
- Perplexity Comet: [completed / partial / failed] — fields filled: <count> / <total>, errors: <list>
- Did either fumble multi-page forms, CAPTCHAs, or custom questions? <notes>
- Winner: [Kestrel / Perplexity / tie]

### 5. Interview prep
- Kestrel output depth (1-5): <n>
- Perplexity output depth (1-5): <n>
- Which had more specific, verifiable company facts? [Kestrel / Perplexity / tie]
- Which had more role-appropriate mock questions? [Kestrel / Perplexity / tie]
- Winner: [Kestrel / Perplexity / tie]

### Overall for this job
- Kestrel wins: <count> / 5
- Perplexity wins: <count> / 5
- Ties: <count> / 5
- Surprising observations: <free text>
```

---

## Summary tally

Fill this in after all 5 jobs are tested.

| Dimension | Kestrel wins | Perplexity wins | Ties | Notes |
|-----------|--------------|-----------------|------|-------|
| Discovery | | | | |
| Scoring | | | | |
| Cover letter | | | | |
| Auto-fill | | | | |
| Interview prep | | | | |
| **Total** | | | | |

## Gaps not covered by this test

The following Kestrel / Perplexity Computer claims **cannot** be verified on the Pro plan — flag them as "documented but not empirically tested" in the writeup:

- [ ] Persistent memory across sessions (Computer-only)
- [ ] Scheduled / recurring daily scans (Computer-only)
- [ ] Multi-model orchestration (Computer-only)
- [ ] Pipeline analytics across 50+ applications (Computer lacks; Kestrel has — but hard to test in one session)
- [ ] EU job board coverage (Kestrel: Arbeitsagentur; Perplexity: no — Pro can confirm absence, not presence)
- [ ] Data export / sovereignty (Kestrel: SQLite; Perplexity: closed sandbox — architectural, not behavioral)

For these, the PR body already cites Perplexity's help center, the Semafor launch coverage, and Sentisight pricing — that's the defensible documentation trail.

## Gotchas observed during testing

<!-- Free-text section — log anything weird, fragile, or surprising. This is where the real value of the test lives. Examples: -->

- <!-- "Comet asked for my resume every time — no persistent profile in Pro tier" -->
- <!-- "Kestrel's Playwright auto-apply got stuck on a Cloudflare challenge on job 3" -->
- <!-- "Perplexity scored 2 points higher than Kestrel on job 2, but couldn't explain why" -->
- <!-- "Comet's LinkedIn discovery returned 3 roles from companies that don't actually have that opening listed publicly" -->

## Writeup seed

Use this to draft the public post / gist once the test is complete. Link it from `docs/COMPARISON.md` as empirical backing.

### TL;DR
<!-- One paragraph: who won per category, overall verdict, caveats -->

### Methodology
<!-- Reference this doc; note date, plan, sample size -->

### Results per dimension
<!-- For each of discovery / scoring / cover letter / auto-fill / interview prep: 1 paragraph + the relevant tally row -->

### Where Perplexity Pro + Comet was better than expected
<!-- Honest praise — don't slant this -->

### Where Kestrel was better than expected
<!-- Same — honest -->

### What $200/mo Max (Computer) would additionally unlock
<!-- Cite primary sources, don't speculate -->

### Recommendation
<!-- Who should use what -->

---

*Template version 1. Revise as needed. When a completed run is published, add a `Runs/` subdirectory under `docs/validation/` and archive completed test logs there so we build up empirical history across tool versions.*
