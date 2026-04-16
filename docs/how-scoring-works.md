---
title: "How Scoring Works"
description: "A guide to how Kestrel evaluates job fit — and why it's harder than it looks"
---

# How Scoring Works

## The Problem

"Is this job a good fit?" sounds like a simple question. It's not.

Think of it like a dating app for careers. Surface-level compatibility — you both like Python! — doesn't mean deep match. Maybe you want to lead AI teams, but the role is maintaining a legacy CRUD app. The job title says "Senior Engineer" but the day-to-day is ticket triage. You'd never know from the listing alone.

And here's the thing: job descriptions are marketing copy. They're written to attract the widest possible candidate pool, not to give you an honest picture. "Fast-paced environment" could mean exciting growth or chronic understaffing. "Competitive salary" could mean anything from generous to "we'd rather not say."

Scoring tries to cut through this noise. Instead of you reading 50 job postings and hoping your gut gets it right, Kestrel breaks the evaluation into concrete dimensions, scores each one, and gives you a structured picture of how well a role aligns with what you can do and what you actually want.

It's not perfect — no automated system can fully replace human judgment. But it turns the overwhelming task of evaluating dozens of opportunities into something manageable, and it keeps getting better the more you use it.


## Two Scores, One Picture

Most job-matching tools give you a single score. Kestrel gives you two, because a single number hides an important tension: **can you do this job?** and **do you want this job?** are completely different questions.

### Fit Score (0-10)

Your Fit Score measures objective alignment. Do your skills match what they need? Is the seniority level right? Does the salary range overlap with your expectations? Would the location or remote policy work for your life?

A high fit score means you'd be a competitive candidate. It doesn't mean you'd be happy.

### Desire Score (0-10)

Your Desire Score measures subjective alignment. Does the company's mission excite you? Would this role advance your career in the direction you want? Is the team culture a match for how you like to work?

A high desire score means you'd love the role. It doesn't mean you'd get it.

### The Quadrant

The real insight comes from looking at both scores together:

```
                    Desire Score
                Low (<7)    │   High (≥7)
           ─────────────────┼──────────────────
           │                │                  │
High (≥7)  │   Safe Bet     │   Dream Job      │
Fit        │   You'd do     │   Go all in.     │
Score      │   well, but    │   Apply now,     │
           │   would you    │   prepare hard.  │
           │   be happy?    │                  │
           ─────────────────┼──────────────────
           │                │                  │
Low (<7)   │   Skip         │   Reach          │
           │   Move on,     │   Exciting, but  │
           │   no hard      │   you'd need to  │
           │   feelings.    │   close gaps.    │
           │                │                  │
           ─────────────────┴──────────────────
```

A "Safe Bet" isn't a bad outcome — sometimes stability is exactly what you need. And a "Reach" isn't hopeless — it tells you where to invest if you really want that role. The quadrant helps you make intentional decisions instead of applying to everything and hoping for the best.


## The Six Dimensions

Neither score is pulled from thin air. Each one is built from six sub-scores that examine different aspects of the match. Here's what they measure and why they matter.

### Technical Fit

Do your skills match what they need? This goes deeper than keyword matching. If a role asks for React and you have five years of Vue, that's a partial match — the mental models transfer, but there's a ramp-up. If they want Kubernetes and you've only used Docker Compose, that's a real gap, not a deal-breaker.

### Seniority Alignment

Are you the right level? You might find an amazing company, but if you're a senior engineer and they're hiring for a junior role, neither of you will be happy. You'll be bored; they'll worry you'll leave in six months. The reverse is just as tricky — a staff-level role when you have three years of experience means you'd be underwater from day one.

### Compensation Fit

Does the money work? This compares the role's stated (or estimated) salary range against your expectations. A dream job that pays 40% below your target is going to create friction, no matter how exciting the mission is.

### Location Fit

Can you actually work there? Remote-first, hybrid three days a week, on-site only — these aren't minor details. A perfect role in a city you'd never move to is a non-starter, and "remote-friendly" sometimes means "remote but you need to be in the office for quarterly planning weeks in San Francisco."

### Career Trajectory

Does this role get you where you want to go? If your goal is to move into engineering management, a deep individual-contributor role might sharpen your skills but won't build the leadership experience you need. If you want to specialize in ML, a full-stack generalist role might feel like treading water.

### Company Fit

What's the company actually like? Stage matters — a Series A startup and a Fortune 500 company are completely different work experiences, even for the same job title. Industry matters too: if you care about healthcare but the company sells ad tech, that misalignment shows up in daily motivation.


## Score Bands

Here's what the numbers mean in plain language, so you're not just staring at a 6.4 wondering if that's good or bad.

**9-10: Dream fit.** You'd be a top candidate and love the role. Everything aligns — skills, seniority, compensation, trajectory. These are rare, so when they show up, act fast.

**7-8: Strong.** You're competitive. There might be minor gaps — maybe you haven't used one of their core tools, or the salary is at the low end of your range — but nothing that preparation can't bridge.

**5-6: Moderate.** Real gaps exist, but you have transferable skills. You could make a case for yourself, especially with a strong cover letter or a referral, but you'll be stretching.

**3-4: Weak.** This would be a major pivot. The role asks for things you don't have yet, and closing those gaps would take significant time. Not impossible, but you should go in with eyes open.

**1-2: Skip.** This is a fundamentally different career path. No amount of interview prep bridges the gap between, say, a marketing coordinator and a systems architect.

A 7 doesn't mean the job is bad — it means you're competitive but there are gaps to prepare for. Use the sub-scores to find exactly where those gaps are, then decide if they're worth closing.


## Red Flags

Before any AI scoring happens, Kestrel runs a set of pattern-matching checks on the job posting itself. These catch warning signs that no amount of skill-matching can fix.

**Ghost jobs.** The same role reposted five or more times. The company might not actually be hiring — they could be collecting resumes for future openings or satisfying an internal policy that requires external postings.

**Stale postings.** Still active after 60+ days. Either the hiring process is glacially slow (a signal in itself) or the role was filled and nobody took the listing down.

**Vague responsibilities.** "Other duties as assigned" is a red flag when it dominates the description. A role that can't clearly articulate what you'd do probably hasn't figured that out internally either.

**Staffing agencies in disguise.** The posting looks like a direct hire, but the actual employer is a staffing firm. Not inherently bad, but good to know before you invest time.

**Unrealistic requirements.** Ten years of experience for a junior title. Five years of a framework that's existed for three. These signal a disconnected hiring process.

**Missing salary in mandatory-disclosure states.** Some jurisdictions require salary ranges on postings. When they're absent, it suggests the company is either unaware of the law or hoping you won't notice.

Think of red flags as the fine print detector — they catch things you might miss when you're excited about a role.


## How Scoring Learns

Kestrel's scoring isn't static. It adapts to you.

When you look at a score and think "that's too high" or "that's too low," you can tell Kestrel. Maybe it scored a DevRel role at 8 because your skills match, but you know from experience that you don't enjoy public speaking enough to thrive in that kind of position. That correction matters.

After you've provided enough feedback — roughly ten corrections — Kestrel starts injecting your calibration examples into future scoring prompts. Instead of scoring from scratch every time, it learns what "good fit" means for you specifically. Your feedback becomes part of the scoring context, nudging future evaluations toward your actual preferences.

This also means scoring weights aren't one-size-fits-all. A software engineering role emphasizes technical skills more heavily (around 35% of the overall score), while a Developer Relations role gives more weight to culture and communication fit (around 25%). The weighting adjusts based on job family, so a perfect score for a backend engineer looks different from a perfect score for a product manager.

The more you use it, the sharper it gets.


## What Scoring Can't Do

Scoring is powerful, but it has real limitations, and pretending otherwise would be dishonest.

**Culture fit is guesswork.** A job description can hint at culture — "we value work-life balance" or "we move fast and break things" — but those are self-reported signals, not reality. You won't know the actual culture until you talk to people who work there.

**Salary estimates are rough.** When a posting doesn't include compensation, Kestrel estimates based on market data. That's better than nothing, but it's not insider information. The real number could be significantly different.

**Networking isn't factored in.** A referral from a friend at the company can matter more than any skill match. Scoring doesn't know about your professional network or personal connections.

**The JD might not reflect the actual role.** Some of the best jobs have mediocre descriptions, and some of the worst have polished ones. The posting is a starting point, not the full picture.

**Short descriptions get penalized.** Small companies and startups often write brief, informal job postings. Less text means fewer signals, which means lower confidence in scoring. A low score here might reflect limited information, not a bad match.

Scoring is a compass, not a GPS. It points you in the right direction, but you still need to talk to people, ask hard questions, and trust your own judgment when something feels off.
