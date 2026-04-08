# Job Search Tools, Frameworks & Resources (2025-2026)

> Comprehensive research for someone targeting TPM/Product/AI roles in Germany (Frankfurt) or remote positions in Europe.

---

## Table of Contents

1. [Job Tracking Tools](#1-job-tracking-tools)
2. [Job Scraping & Aggregation](#2-job-scraping--aggregation-tools)
3. [Resume/CV Optimization](#3-resumecv-optimization-tools)
4. [Networking & Outreach](#4-networking--outreach-tools)
5. [Interview Preparation](#5-interview-preparation-tools)
6. [Salary Research](#6-salary-research-tools)
7. [GitHub Repos & Automation Frameworks](#7-github-repos--automation-frameworks)
8. [Germany/EU-Specific Resources](#8-germanyeu-specific-resources)

---

## 1. Job Tracking Tools

### SaaS Platforms

| Tool | Pricing | Key Features | Best For |
|------|---------|-------------|----------|
| **[Teal](https://tealhq.com)** | Free / $29/mo | Resume builder, ATS scanner, job tracker, Chrome extension (40+ sites), autofill | Budget-conscious, resume-heavy workflows |
| **[Huntr](https://huntr.co)** | Free (100 jobs) / $40/mo | Kanban board, Chrome extension, match scoring, analytics | Visual organizers, power users |
| **[JobPilot](https://jobpilotapp.com)** | Free / Pro $9/mo | Universal autofill across 20+ boards, tracking, 95% form fill rate | High-volume applicants |
| **[Careerflow](https://careerflow.ai)** | Free / $19.99/mo | LinkedIn profile optimization, job tracker, AI resume tools | LinkedIn-centric job searches |
| **[Scale.jobs](https://scale.jobs)** | $199-$1,099 (one-time) | AI + human-assisted applications, ATS-optimized docs | Premium, hands-off approach |
| **[ApplyArc](https://applyarc.com)** | Free / Paid | Job tracking, application management | Huntr alternative seekers |
| **[TrackJobs](https://trackjobs.co)** | Free / Paid | Centralized application tracking | Simplicity-focused users |

### Open Source Job Trackers

| Project | Tech Stack | Stars | Key Features |
|---------|-----------|-------|-------------|
| **[JobSync](https://github.com/gsync/jobsync)** | Next.js, Shadcn UI, Prisma | ~230 | Self-hosted, AI resume review, job matching, analytics, privacy-first. Demo: demo.jobsync.ca |
| **[job_tracker](https://github.com/tgaeta/job_tracker)** | Ruby on Rails | — | Original open-source job tracker |
| **[JobTracker-Pro](https://github.com/ZhanLiQxQ/JobTracker-Pro)** | Frontend + Backend + AI Service | — | Multi-component with AI features |
| **[ai-job-tracker](https://github.com/lbwalton/ai-job-tracker)** | — | — | Application + follow-up tracking (MIT) |
| **[asthana-16/job-tracker](https://github.com/asthana-16/job-tracker)** | Node.js (Express) | — | Full-stack with 600+ commits |
| **[AppTracker](https://github.com/YiSun88/AppTracker)** | Client-Server | — | Developer-focused application tracker |

---

## 2. Job Scraping & Aggregation Tools

### Open Source Scrapers

| Project | Tech | Stars | Supported Boards |
|---------|------|-------|-----------------|
| **[JobSpy (python-jobspy)](https://github.com/cullenwatson/JobSpy)** | Python | Very Popular (126k+ monthly PyPI downloads) | LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, Bayt, Naukri, BDJobs |
| **[jobspy-api](https://github.com/rainmanjam/jobspy-api)** | Python, FastAPI, Docker | — | Wraps JobSpy with auth + rate limiting |
| **[AIHawk](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk)** | Python | 29,000+ | LinkedIn (auto-apply with AI form-filling) |
| **[Job-apply-AI-agent](https://github.com/imon333/Job-apply-AI-agent)** | Python, n8n, Selenium, OpenAI | ~86 | LinkedIn, Indeed, StepStone — auto CV/cover letter generation |
| **[LinkedIn Job Hunting Assistant](https://github.com/brightdata/linkedin-job-hunting-assistant)** | Python | — | LinkedIn (via Bright Data API) + OpenAI scoring |
| **[Agentic Job Scout](https://github.com/logsv/agentic-jobscout)** | Python, Docker | — | Agentic job search with test coverage |

### Commercial APIs & Services

| Service | Coverage | Pricing |
|---------|----------|---------|
| **[Apify - Job Search Engines](https://apify.com/nextapi/job-search-engines)** | LinkedIn, Indeed, Glassdoor, ZipRecruiter, regional boards | $0.003/job |
| **[Apify - Jobs Scraper All-in-One](https://apify.com/globalapi/jobs-scraper-all-in-one)** | LinkedIn, Indeed, Glassdoor, ZipRecruiter, Monster + 30 countries | Pay-per-use |
| **[ScraperAPI](https://scraperapi.com)** | Any site (200M+ proxies, 150+ countries) | Subscription |
| **[Bright Data](https://brightdata.com)** | LinkedIn Job Listings API + structured datasets | Enterprise pricing |

### Installation: JobSpy (Recommended Open Source)

```bash
pip install -U python-jobspy
```

```python
from jobspy import scrape_jobs

jobs = scrape_jobs(
    site_name=["indeed", "linkedin", "glassdoor"],
    search_term="Technical Program Manager",
    location="Frankfurt, Germany",
    results_wanted=50,
    hours_old=72,
    country_indeed="Germany"
)
print(f"Found {len(jobs)} jobs")
jobs.to_csv("tpm_jobs_frankfurt.csv", index=False)
```

---

## 3. Resume/CV Optimization Tools

### AI Resume Builders

| Tool | Best For | Pricing |
|------|---------|---------|
| **[Teal](https://tealhq.com)** | Fast, tailored ATS-friendly resumes | Free / Premium |
| **[Rezi](https://rezi.ai)** | Keyword optimization, ATS targeting | Free / Paid |
| **[Jobscan](https://jobscan.co)** | Improving existing resumes with AI scoring | Free scans / $49.95/mo |
| **[Kickresume](https://kickresume.com)** | Fast AI content generation | Free / Paid |
| **[Text2Resume](https://text2resume.com)** | Enterprise-grade optimization (67% more callbacks reported) | Paid |
| **[Enhancv](https://enhancv.com)** | Guided writing with AI suggestions | Free / Paid |
| **[Novorésumé](https://novoresume.com)** | Polished structure + guided flow | Free / Paid |
| **[VisualCV](https://visualcv.com)** | Analytics + performance tracking on resumes | Free / Paid |
| **[Canva](https://canva.com)** | Design-focused, visually appealing resumes | Free / Pro |
| **Microsoft Copilot** | Free AI-powered resume optimization in browser | Free |

### ATS Tips for TPM/Product Roles

- Use exact keywords from the job description (e.g., "Agile", "Scrum", "roadmap", "stakeholder management", "cross-functional")
- Quantify impact: "Led 3 cross-functional teams", "Reduced delivery time by 30%"
- Avoid graphics/tables/columns that confuse ATS parsers
- Use standard section headings: Experience, Education, Skills, Certifications

---

## 4. Networking & Outreach Tools

### Personal CRMs for Job Seekers

| Tool | Features | Pricing |
|------|---------|---------|
| **[Dex](https://getdex.com)** | Network organizer, interaction tracking, follow-up reminders, LinkedIn/Twitter/iCloud sync | Free / Paid |
| **[FireApp](https://usefireapp.com)** | Contact + company + opportunity CRM, LinkedIn/Gmail/Zapier integration, visual pipeline | Paid |
| **[Apollo.io](https://apollo.io)** | 275M+ contacts, email finder, sequences, A/B testing, AI intent scoring | Free (50 credits) / $49/mo |
| **[Vocus.io](https://vocus.io)** | Gmail mass email, automated follow-ups, GDPR/CCPA compliant | Paid |

### LinkedIn Automation (Within Safe Limits)

**Safe daily limits (2025):**
- Connection requests: 10-20/day
- Messages: 50-100/day
- Profile views: <80/day (free accounts)
- Weekly cap: ~50 connection requests

**Recommended approach:**
1. 30-day warm-up with manual activity first
2. Use cloud-based tools (safer than browser extensions): Expandi, Zopto, Skylead
3. Personalize every message with profile-specific details
4. Scale activity by 20-30% weekly maximum
5. Monitor acceptance/reply rates as compliance signals

### Email Finder Extensions

| Tool | Contact Database | Key Feature |
|------|-----------------|-------------|
| **Apollo.io** | 275M+ contacts | Chrome extension on LinkedIn profiles |
| **Lusha** | — | Direct dials + emails |
| **RocketReach** | — | Verified professional emails |
| **Hunter.io** | — | Domain-based email finder |
| **ContactOut** | — | LinkedIn email extraction |

---

## 5. Interview Preparation Tools

### AI Mock Interviews

| Platform | Best For | Pricing |
|----------|---------|---------|
| **[Revarta](https://revarta.com)** | Behavioral mastery, leadership questions | $49/mo or $149/90 days |
| **[MocklyAI](https://trymockly.ai)** | Realistic simulations (behavioral + coding + system design) | Free trial |
| **[Mockstar](https://mockstar.co)** | Comprehensive analytics (pace, filler words, eye contact), STAR coaching | Paid |
| **[Exponent](https://tryexponent.com)** | Product management, software engineering, data roles | Subscription |
| **[Pramp](https://pramp.com)** | Free peer-to-peer mock interviews | Free |
| **[Interviewing.io](https://interviewing.io)** | Premium technical coaching by FAANG engineers | $225+/session |

### Technical Interview Prep

| Resource | Focus Area |
|----------|-----------|
| **[LeetCode](https://leetcode.com)** | Coding challenges, SQL, system design |
| **[Exponent](https://tryexponent.com)** | PM interviews, system design, estimation |
| **[Grokking the System Design Interview](https://designgurus.io)** | System design deep dives |
| **[InterviewBit](https://interviewbit.com)** | Coding + system design |
| **[Cracking the PM Interview](https://amazon.com)** | Book: PM-specific interview framework |

### TPM-Specific Interview Tips

- **Technical depth**: Be ready to discuss system architecture, APIs, CI/CD, cloud infrastructure
- **Program management**: STAR stories about managing cross-functional timelines, risks, dependencies
- **Stakeholder management**: Examples of influencing without authority
- **Metrics-driven**: Showcase data-driven decision making
- **Germany-specific**: Be prepared for more structured, thorough interview processes (often 4-6 rounds)

---

## 6. Salary Research Tools

### Global Platforms

| Tool | Coverage | Strengths |
|------|----------|----------|
| **[Levels.fyi](https://levels.fyi)** | Global (strong US/EU tech) | Total compensation breakdowns (base + stock + bonus), 245K+ data points, company leaderboards for Germany |
| **[Glassdoor](https://glassdoor.com)** | Global | Salary + company reviews + interview experiences |
| **[Blind](https://teamblind.com)** | US/Global tech | Anonymous verified compensation sharing |
| **[Payscale](https://payscale.com)** | Global | Cost-of-living adjustments, industry benchmarks |
| **[Comparably](https://comparably.com)** | US/Global | Culture + compensation data |

### Germany/EU-Specific

| Tool | Coverage | Key Data |
|------|----------|----------|
| **[Kununu](https://kununu.com)** | Germany, Austria, Switzerland (DACH) | 15M+ employer reviews, salary check tool, gender pay gap insights, 125K+ job listings |
| **[StepStone Salary Report](https://stepstone.de)** | Germany | 1M+ salary data points. 2025 median: €45,800. Engineers: €58,500. Management consultants: €58,250 |
| **[Ravio](https://ravio.com)** | 50+ European countries | 900+ roles in Germany, 2026 benchmarks. Germany annual salary increase: +5%. Hiring rate: +29.8% |
| **[Gehalt.de](https://gehalt.de)** | Germany | Detailed German salary calculator by role, experience, city |
| **[Destatis](https://destatis.de)** | Germany | Official government statistics on earnings |

### Frankfurt Salary Context (2025)

- Frankfurt is one of Germany's highest-paying cities (financial hub)
- Tech/Product roles typically 10-20% above national median
- TPM roles in Germany: €70,000-€110,000+ depending on seniority and company
- EU Pay Transparency Directive (mandatory by mid-2026) will increase salary visibility

---

## 7. GitHub Repos & Automation Frameworks

### Most Notable Repos

| Repository | Stars | Description |
|-----------|-------|-------------|
| **[AIHawk (Jobs_Applier_AI_Agent)](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk)** | 29,000+ | Automated LinkedIn job applications with AI. Fills forms, generates responses, attaches resumes. Featured in TechCrunch, Wired. Python, AGPL-3.0. |
| **[JobSpy (python-jobspy)](https://github.com/cullenwatson/JobSpy)** | Very Popular | Multi-board job scraper (LinkedIn, Indeed, Glassdoor, etc.). 126K+ monthly PyPI downloads. Python, MIT. |
| **[JobSync](https://github.com/gsync/jobsync)** | ~230 | Self-hosted job tracker with AI career assistance. Next.js + Prisma. |
| **[Job-apply-AI-agent](https://github.com/imon333/Job-apply-AI-agent)** | ~86 | End-to-end automation: scrape → generate CV/cover letter → auto-apply. Python + n8n + Selenium + OpenAI. Supports StepStone (Germany!). |
| **[LinkedIn Job Hunting Assistant](https://github.com/brightdata/linkedin-job-hunting-assistant)** | — | Bright Data + OpenAI for AI-scored LinkedIn job matching. Python. |
| **[Job Search Automations](https://github.com/dev-dull/job-search-automations)** | — | Gemini-powered cover letter generation + job qualification assessment. |
| **[Agentic Job Scout](https://github.com/logsv/agentic-jobscout)** | — | Agentic job search with Docker support. |
| **[jobspy-api](https://github.com/rainmanjam/jobspy-api)** | — | FastAPI wrapper for JobSpy with auth + rate limiting. Docker-ready. |

### Recommended Stack for DIY Automation

```
Job Discovery:     python-jobspy (scraping) + Apify APIs (backup)
AI Processing:     OpenAI/Claude API (resume tailoring, cover letters, job scoring)
Tracking:          JobSync (self-hosted) or Notion/Airtable
Orchestration:     n8n (open source) or Make/Zapier (SaaS)
Notifications:     Email alerts, Telegram/Slack bots
Data Storage:      PostgreSQL + CSV exports
```

---

## 8. Germany/EU-Specific Resources

### Job Boards for TPM/Product/AI Roles

| Board | Focus | Notes |
|-------|-------|-------|
| **[StepStone.de](https://stepstone.de)** | Germany's largest job board | Strong for corporate/enterprise TPM roles |
| **[LinkedIn Jobs](https://linkedin.com/jobs)** | Global, strong in Germany | Best for networking + applying, set location to Frankfurt |
| **[Remote Rocketship](https://remoterocketship.com)** | Remote roles in Europe | 30 TPM roles, 113 PM roles in Germany, 536 PM roles EU-wide |
| **[Top Remote Jobs EU](https://topremotejobs.eu)** | Remote EU positions | 146 product management roles with salary data |
| **[Kununu Jobs](https://kununu.com/de/jobs)** | Germany (DACH) | 125K+ listings with employer reviews attached |
| **[XING](https://xing.com)** | DACH region | Strong German professional network (LinkedIn alternative) |
| **[Arbeitnow](https://arbeitnow.com)** | Germany, visa-sponsored roles | English-friendly job board for Germany |
| **[Germany Is Calling](https://germanyiscalling.com)** | Expats targeting Germany | English-speaking tech roles |
| **[Berlin Startup Jobs](https://berlinstartupjobs.com)** | Berlin startup ecosystem | Many remote-flexible roles |
| **[Working in Germany (Make it in Germany)](https://make-it-in-germany.com)** | Government portal | Official job + visa information |

### Germany-Specific Tips

- **Language**: Many TPM roles in Frankfurt (finance hub) require German B2 +, but international companies and remote roles are often English-only
- **Visa**: EU Blue Card for non-EU nationals; salary threshold ~€45,300 (general) or lower for shortage occupations
- **Contract culture**: German employment contracts are very structured; expect 6-month probation, 13th salary common in finance
- **Notice periods**: Standard 3 months after probation in many German companies
- **Works council (Betriebsrat)**: Large companies have employee representation that influences hiring

### Recommended Workflow for Frankfurt/Remote EU

```
1. DISCOVER:   JobSpy scraping (StepStone, LinkedIn, Indeed DE) + Remote Rocketship
2. TRACK:      JobSync (self-hosted) or Teal/Huntr (SaaS)
3. OPTIMIZE:   Teal or Rezi for ATS resume + AI cover letters
4. NETWORK:    Dex CRM + LinkedIn warm outreach (10-20 connections/day)
5. RESEARCH:   Levels.fyi + Kununu + StepStone salary report
6. PREPARE:    Exponent (PM interviews) + MocklyAI (behavioral) + Pramp (free)
7. AUTOMATE:   n8n workflows to glue scraping → scoring → alerting
```

---

## Summary & Top Picks

### If You Pick Just One Per Category

| Category | Top Pick | Why |
|----------|---------|-----|
| **Job Tracking** | **Teal** (SaaS) / **JobSync** (self-hosted) | Best value; Teal has resume tools built in |
| **Job Scraping** | **python-jobspy** | MIT license, 126K+ downloads, covers all major boards |
| **Resume Optimization** | **Teal + Rezi** | Teal for tailoring, Rezi for ATS keyword optimization |
| **Networking** | **Dex** | Purpose-built personal CRM for job seekers |
| **Interview Prep** | **Exponent** (PM/TPM) + **Pramp** (free) | Exponent for PM-specific prep, Pramp for free coding |
| **Salary Research** | **Levels.fyi** (tech TC) + **Kununu** (Germany) | Best combo for Frankfurt tech compensation data |
| **Automation** | **AIHawk** (LinkedIn auto-apply) + **JobSpy** (scraping) | Most starred, most battle-tested open source tools |

### Key Trends in 2025-2026

1. **AI agents are mainstream** — Tools like AIHawk (29K+ stars) show demand for autonomous job application agents
2. **ATS optimization is table stakes** — Every serious tool now includes keyword matching and ATS scoring
3. **Multi-tool stacks win** — No single tool covers everything; effective job seekers combine 3-4 tools
4. **Privacy matters** — Self-hosted tools like JobSync are gaining traction
5. **EU Pay Transparency** — By mid-2026, German companies must publish salary ranges (game-changer for negotiation)
6. **AI/ML roles boom** — Highest-paid SWE track per Levels.fyi 2025 report
7. **Return to office trend** — +12% YoY increase in office-based roles, making location (Frankfurt) more relevant

---

*Research compiled: February 2026*
