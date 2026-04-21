---
title: "How CI/CD Works"
description: "What happens between writing code and running your own Kestrel instance — and why it matters"
---

# How CI/CD Works

## The Journey of Code

You've probably installed software before. Download, double-click, done. But have you ever wondered what happens between someone writing code and you running it?

Think of it like a restaurant kitchen. A chef (the developer) creates a recipe (writes code). But before it reaches your table, it goes through a process: the recipe gets reviewed, the ingredients get checked for quality, the dish gets plated, and a server brings it to you. If any step fails — bad ingredient, wrong temperature, dropped plate — you never see the mistake.

That's what CI/CD does for software. CI stands for *Continuous Integration* (checking the code) and CD stands for *Continuous Delivery* (getting it to you). It's the invisible kitchen that turns raw code into the app you use.

For Kestrel specifically, this matters because Kestrel is *self-hosted* — you run it on your own machine or server. So the "kitchen" needs to be really good, because we can't fix a bad dish after it's on your table. You'd have to wait for us to cook a new one and update manually.

---

## The Three Checkpoints

Every piece of code that goes into Kestrel passes through three checkpoints before it can become part of a release:

### Checkpoint 1: Does It Work?

When a developer (or an AI assistant — Kestrel is built with AI help) writes new code and submits it for review, automated checks run immediately:

- **Does it follow the rules?** Every project has coding standards — like grammar rules for code. A tool called a *linter* checks that the code is formatted consistently and doesn't contain common mistakes.

- **Do the tests pass?** Kestrel has hundreds of automated tests. Each one asks a specific question: "If I create a job application with these details, does the scoring engine produce the right result?" "If I send this API request, does the server respond correctly?" These tests run in under 2 minutes.

- **Is it secure?** Automated scanners check for known vulnerabilities in the code and its dependencies. Think of it as checking that all your kitchen ingredients haven't been recalled.

- **Did anything leak?** A special scanner checks that no personal information, passwords, or API keys accidentally ended up in the code. This is like checking that a letter you're mailing doesn't have your credit card number written on the envelope.

If any of these fail, the code can't move forward. The developer fixes the issue and tries again.

### Checkpoint 2: Is It Ready to Ship?

Once the code passes all checks, it gets merged into the main codebase. But that doesn't make it a release yet. Changes accumulate — bug fixes, new features, improvements — until there's enough to justify a new version.

Kestrel uses something called *conventional commits*: every code change has a label that says what kind of change it is. `feat:` means a new feature. `fix:` means a bug fix. `docs:` means documentation was updated.

A bot reads these labels and automatically prepares a release draft:

```
Version 0.4.0

New Features:
- Expanded scoring to work with finance and design roles
- Added new AI provider options

Bug Fixes:
- Fixed scoring inconsistency with profile-aware wrapping
- Corrected golden set test categorizations
```

The developer reviews this draft and decides when to publish it. This is a deliberate choice — we don't auto-release because self-hosted users need time to plan their upgrades.

### Checkpoint 3: Can You Get It?

When a release is published, the code needs to be packaged in ways you can actually use:

- **Docker image** — The most common way to run Kestrel. The entire app (backend + frontend) gets built into a single container image. It's like a meal kit — everything pre-measured, pre-prepped, ready to cook in one pot.

- **Python package (pip)** — For users who want to install Kestrel as a Python tool. Published to PyPI, the Python Package Index.

- **npm package** — A convenience wrapper that installs the Python package using Node.js tooling.

All three are published automatically when a release is tagged. You don't need to build anything yourself.

---

## How Self-Hosting Works

When you self-host Kestrel, you're running it on a server you control. Here's what a typical setup looks like:

```
Your Server
┌─────────────────────────────────────┐
│                                     │
│  Kestrel (the app)                  │
│  ├── Backend: finds and scores jobs │
│  ├── Frontend: the web UI you see   │
│  └── Database: your job data        │
│                                     │
│  + Backup system (automatic)        │
│  + Health monitor (checks it's up)  │
│                                     │
└─────────────────────────────────────┘
```

### Your Data Stays Yours

This is the whole point of self-hosting. Your job applications, scores, contacts, and career goals live on *your* server, not ours. The database is a single file (SQLite) — you could copy it to a USB drive if you wanted to.

A backup system called Litestream continuously copies your database changes to cloud storage, so if your server has a bad day, your data is safe. Think of it like your phone automatically backing up photos — you don't think about it, but it's always happening.

### Updating Kestrel

When a new version comes out, updating is:

```bash
docker compose pull        # Download the new version
docker compose up -d       # Restart with the new version
```

That's two commands. The database migrates automatically — new tables get created, old data gets preserved. If something goes wrong, you can roll back to the previous version just as easily.

### What About the Mobile App?

A mobile app is planned for a future release. It will connect to your self-hosted Kestrel server — think of it as a remote control for your instance. The app would get updates through the app store (Apple/Google), and some updates could be pushed instantly without waiting for app store review. Stay tuned for updates on the [roadmap](https://github.com/pleasedodisturb/kestrel/wiki/Roadmap).

---

## Why This Matters to You

You might be thinking: "I just want to search for jobs. Why should I care about CI/CD?"

Fair question. Here's why it matters:

**Reliability.** Every feature you use was tested hundreds of times before it reached you. The scoring engine that tells you a job is a "dream job"? That's been validated against real job data, checked for bias across industries, and tested with edge cases. The CI pipeline catches mistakes that humans miss.

**Security.** Your career data is sensitive — where you're applying, your salary expectations, your skills gaps. The automated security scanning ensures no version of Kestrel ships with known vulnerabilities or accidental data leaks.

**Transparency.** Kestrel is open source. Every automated check, every test, every security scan is visible in the GitHub repository. You can see exactly what standards the code is held to. The CI configuration files are just text files you can read.

**Predictability.** When you update Kestrel, you can read the changelog and know exactly what changed. No surprises, no mystery features, no "we updated and now it's different." The conventional commit system ensures every change is categorized and documented.

---

## The Numbers

Some concrete facts about Kestrel's quality pipeline:

- **12 automated workflows** check every code change
- **100+ backend tests** validate the API, scoring, and data layer
- **20+ frontend tests** validate the web interface
- **6 security scanners** check for vulnerabilities, secrets, and supply chain risks
- **Every release** is built for both Intel and ARM processors (runs on regular servers and Apple Silicon)
- **Zero manual steps** between "release approved" and "packages published"

All of this runs automatically. The developer's job is to write good code and decide when to ship. The pipeline handles the rest.

---

## Glossary

Some terms you might encounter:

| Term | What It Means |
|------|---------------|
| **CI** | Continuous Integration — automatically testing code when it's submitted |
| **CD** | Continuous Delivery — automatically packaging and publishing tested code |
| **Docker** | A way to package an app so it runs the same everywhere (like a shipping container for software) |
| **Pipeline** | The sequence of automated checks that code goes through |
| **Linting** | Checking code for style and formatting consistency |
| **SAST** | Static Application Security Testing — scanning code for security issues without running it |
| **SemVer** | Semantic Versioning — version numbers like 1.2.3 where each number means something (major.minor.patch) |
| **OTA** | Over-The-Air — updating a mobile app without going through the app store |

---

*Want to see the pipeline in action? Check the [Actions tab](https://github.com/pleasedodisturb/kestrel/actions) in the GitHub repository — every run is public.*
