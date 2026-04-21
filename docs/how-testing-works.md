---
title: "How Testing Works"
description: "A guide to how Kestrel stays reliable — and why we test so aggressively for a solo project"
---

# How Testing Works

## Why This Matters

Every time you open Kestrel, search for jobs, or check your pipeline, over 2,800 automated checks have already confirmed that things work the way they should. Before any code change reaches you, it passes through layers of verification that catch mistakes, regressions, and subtle bugs.

That might sound like overkill for a self-hosted app. It's not.

Kestrel manages your career data — the companies you're tracking, the applications you've submitted, the skills you've mapped out. A scoring bug that quietly drops a dream job to the bottom of your list, or an application status that silently gets lost, isn't just annoying. It costs you real opportunities. So we test like the stakes are real, because they are.

Here's how all of that works, explained for humans.


## The Kitchen Analogy

The easiest way to understand software testing is to think of it like quality control in a restaurant kitchen.

**Tasting while you cook.** Before any dish leaves the station, the chef tastes individual components. Is the sauce seasoned right? Is the pasta cooked through? These are *unit tests* — small, fast checks on individual pieces of code. Does this function calculate the right score? Does that button render with the correct label? We have over 2,800 of these, and they run in about two minutes.

**The full plate check.** Once the components come together, someone checks the complete dish. Does the steak play well with the sauce? Is the presentation right? These are *integration tests* — they verify that different parts of the system work together. When the frontend asks the backend for your pipeline data, does the whole chain deliver the right answer?

**Is it as good as last time?** A great restaurant doesn't just make good food today — it makes the *same* good food every night. Regulars expect consistency. These are *regression tests*, and for Kestrel they're especially important for scoring. We maintain golden sets of hand-labeled jobs so that every code change gets checked against known-good results. If a change to the scoring algorithm suddenly rates a dream job as mediocre, the tests catch it before it ever reaches you.

**The health inspection.** Behind the scenes, someone checks that the kitchen itself is safe — clean surfaces, proper storage, no cross-contamination. These are *security and dependency scans*. Every pull request gets checked for known vulnerabilities in our dependencies and scanned for accidentally leaked personal data.

**The surprise visit from a food critic.** Occasionally, someone walks in unannounced and orders something unusual. These are *smoke tests and exploratory checks* — they exercise the app in ways the structured tests might not cover, catching the kind of issue that only shows up when someone does something slightly unexpected.

Each layer catches a different kind of problem. Together, they make it really hard for bugs to slip through.


## What Gets Tested

Here's what all of this means in terms of the features you actually use.

### When You Search for Jobs

The scoring algorithm is tested against three golden sets — curated collections of jobs that have been hand-labeled by category. Some are dream matches. Some are mediocre. Some are clear misses. Every time the scoring code changes, it gets re-evaluated against all of these jobs to make sure dream matches still score high and bad fits still score low.

This is how we prevent score drift. Without it, a well-intentioned optimization could silently rearrange your entire job ranking overnight.

### When You Manage Applications

The application pipeline has a strict state machine — you can go from "discovered" to "applied" to "interviewing," but you can't jump from "discovered" straight to "offer accepted." Every valid transition is tested. Every invalid transition is tested too, confirming it gets properly rejected. The system won't let your data end up in an impossible state.

### When You View the Dashboard

Every frontend component is tested with a range of data — empty states (no applications yet), single items, full lists, edge cases like extremely long company names or missing fields. The goal is to make sure the interface stays usable no matter what your data looks like.

### When AI Writes for You

The AI provider abstraction is tested to handle failures gracefully. If the AI service is slow, down, or returns garbage, Kestrel shouldn't crash — it should tell you what happened and let you continue working. The mock provider used in tests simulates these failure modes so we know the error paths actually work.


## The Layers of Verification

Not every check needs to run every time. We organize tests by how fast they are and when they matter most.

### On Every Code Change (~2 minutes)

When a developer opens a pull request, the CI pipeline kicks off immediately. This is the fast feedback loop — did I break anything obvious?

- **Lint and format check.** Catches style issues, unused imports, and common mistakes before anyone even looks at the code.
- **2,800+ unit and integration tests.** Runs the full backend test suite and the frontend test suite in parallel.
- **Migration check.** Runs database migrations up and back down to make sure schema changes are reversible.
- **API smoke test.** Starts the actual server and hits the health endpoint to confirm the app boots.
- **PII leak scan.** Scans the code diff for patterns that look like personal data — email addresses, phone numbers, API keys. If something looks like it shouldn't be in source control, the build fails.
- **Dependency audit.** Checks all Python and npm packages against known vulnerability databases.

All of this runs automatically on GitHub Actions. No human has to remember to do it.

### On Every Merge to Main

When a pull request passes all checks and gets merged, the same pipeline runs again against the main branch. This catches the rare but real scenario where two PRs individually pass but conflict when combined.

SonarCloud runs a deeper static analysis pass here too — looking for code smells, complexity hotspots, and potential bugs that individual tests might not surface. If it finds issues on new code, it posts them directly to the pull request as a comment so nothing gets buried.

### Ongoing: The Golden Sets

The golden sets deserve their own section because they're unusual for a project this size.

Most job-matching tools validate against synthetic data — fake jobs with predictable attributes. That's fast and convenient, but it doesn't catch the real-world messiness of actual job descriptions. "Fast-paced environment" could mean ten different things. A "Senior Engineer" title at a startup and a Fortune 500 company describe completely different roles.

Kestrel's golden sets contain real-world-style job descriptions across multiple career domains — technical program management, finance, design. Each job is hand-labeled into categories: dream match, strong fit, mediocre, or clear reject. Each category has an expected score band.

When the scoring algorithm changes, every golden set job gets re-scored. If a "dream match" suddenly lands in the mediocre band, the test fails. If a "reject" creeps up into the strong range, the test fails. This is the single most important guard against score regression, and it works because the labels come from human judgment, not from the algorithm being tested.

The golden sets grow over time. When we find a scoring edge case — a job that gets misjudged in a surprising way — we add it to the set so that same mistake can never recur.


## What Makes This Unusual

A few things about Kestrel's testing approach are worth calling out because they're not standard practice, especially for a solo-developer project.

### AI Writes Code, but We Verify Like Humans

A significant portion of Kestrel's code is written with AI assistance. That's efficient, but it comes with a specific risk: AI can write code that looks perfectly reasonable and is subtly wrong. It compiles, it runs, the happy path works — but an edge case fails silently.

This is why the test suite is as large as it is. When your co-developer is an AI, your test coverage isn't optional — it's your primary quality backstop.

### We Test Across Career Domains

Scoring isn't just for software engineers. The golden sets include jobs in finance, design, and technical program management. This matters because scoring heuristics that work perfectly for tech roles can fail badly for other career domains. A finance role doesn't list "Python" as a requirement — it lists "DCF modeling" and "LBO analysis." If the scoring algorithm is biased toward tech keywords, it'll underrate perfectly good finance matches.

Testing across domains is how we keep scoring honest for everyone.

### Everything Is Open Source and Free

Every quality tool in the pipeline is open source:

- **pytest** for backend testing
- **Vitest** for frontend testing
- **Ruff** for Python linting and formatting
- **ESLint** for TypeScript linting
- **SonarCloud** for static analysis (free for open-source projects)
- **GitHub Actions** for CI/CD (free for public repos)

The total cost of Kestrel's quality infrastructure is $0/month. No enterprise testing platforms, no paid static analysis tools. Just good open-source tooling, configured carefully.


## The Numbers

Here's what the quality infrastructure looks like today:

| Metric | Count |
|--------|-------|
| Backend test files | 102 |
| Frontend test files | 22 |
| Total test functions (backend) | 2,800+ |
| Golden set job profiles | 3 career domains |
| Hand-labeled golden set jobs | 20+ per domain |
| CI checks per pull request | 6 parallel jobs |
| Time to full CI pass | ~2-3 minutes |
| Monthly cost | $0 |

These numbers grow with every feature. New code requires new tests — that's a non-negotiable rule, not a suggestion.


## Why We Invest in This

"Just ship it" is tempting advice, and for many projects it's correct. Move fast, fix things in production, iterate based on user feedback.

For Kestrel, that math doesn't work.

First, Kestrel is self-hosted. When something breaks, there's no server-side hotfix — users are running their own instances. A bug that ships is a bug that every user has to wait for a release to fix, or troubleshoot themselves.

Second, Kestrel handles career data. If the scoring algorithm silently degrades, you might not notice for weeks. You'd just see fewer interesting jobs, wonder why your search wasn't going well, and maybe blame the job market. That's the worst kind of bug — the kind that hurts you without telling you.

Third, the project is maintained by a small team. Without automated quality gates, every change would require careful manual review of every possible interaction. The test suite makes it safe to move fast because the robots check what humans would miss.

Testing isn't the opposite of moving fast. It's what makes moving fast sustainable.


## How the Strategy Was Chosen

We didn't pick this testing approach by gut feel. The strategy was designed after running parallel research investigations into modern testing practices, AI-assisted development patterns, security testing, CI optimization, and cross-project quality standards. The research covered what works for solo developers specifically — not what works for a team of fifty with a dedicated QA department.

Then we chose the sanest path. Not the most sophisticated (we don't run a Kubernetes cluster for integration tests), not the most minimal (we don't skip testing and hope for the best). The goal was the most sustainable approach for one person maintaining a project long-term.

For the full technical analysis: [Testing Research](research/testing-research.md)
For raw findings with sources: [Raw Research](research/testing-raw-research.md)
For what was built, what was trimmed, and why: [Testing Strategy](testing-strategy.md)
