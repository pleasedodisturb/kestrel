# CareerOS Pricing Strategy

## Philosophy

Don't sell food to the hungry. Job seekers are under financial pressure - charging them monthly while they're unemployed is extractive. The tool should be free when you need it most, and you give back when you're on the other side.

## Model: Open Core + "I Got The Job" + Marketplace

### Tier 1: Free Forever (Self-Hosted)

- Full CLI + web UI
- All scrapers, scorers, trackers, auto-apply tools
- Local AI scoring (Ollama, local LLMs)
- SQLite database, full data ownership
- MIT licensed, fork it, modify it, redistribute it
- Community support (GitHub Issues, Discord)

### Tier 2: Hosted Cloud ($15-30/mo)

- career-os.dev - one-click signup, zero setup
- Managed AI scoring (OpenRouter, Claude, GPT-4o)
- Cloud sync across devices
- Daily automated pipeline runs
- Email/Pushover notifications
- Priority support

### Tier 3: "I Got The Job" Donation

- Voluntary one-time payment when you land a role through CareerOS
- Suggested: $50-100 (or 0.1% of first year salary)
- Publicly celebrate on a "Wall of Wins" (opt-in)
- Donors get a badge, early access to new features, and a voice in roadmap
- No guilt, no enforcement - purely honor system
- If even 5% of active users donate $75 avg, this sustains development

### Tier 4: Pipe Store (Marketplace)

Community-built plugins, sold or free:

**Free pipes (community):**
- Country-specific job board scrapers (Arbeitsagentur, Arbeitnow, StepStone, Xing)
- ATS connectors (Ashby, Greenhouse, Lever, Workday, Workable)
- CV templates by industry
- Scoring profiles by role type

**Paid pipes (developer ecosystem):**
- Premium ATS automation (LinkedIn Easy Apply, multi-form batch apply)
- AI interview prep (mock interviews with feedback)
- Salary negotiation assistant
- Network/referral tracker with LinkedIn integration
- Company culture analyzer (Glassdoor + Blind + Kununu aggregation)

**Developer monetization:**
- Stripe Connect integration for pipe developers
- 80/20 revenue split (developer keeps 80%)
- Publish to pipe store with one command

### Tier 5: Enterprise / Outplacement

- Companies buy CareerOS for their laid-off employees
- White-labeled, pre-configured, bulk licensing
- Outplacement firms integrate it into their services
- $500-2000 per seat depending on support level
- This is where the real money is - companies have budgets, individuals don't

## Why This Works

1. **Zero barrier to entry** - MIT license, self-host, no credit card needed
2. **Moral alignment** - free when you're hurting, pay when you're thriving
3. **Viral loop** - "I got the job using CareerOS" is the best marketing possible
4. **Enterprise anchor** - outplacement is a real budget line item at every company doing layoffs
5. **Developer ecosystem** - pipe store creates network effects, community builds what we can't
6. **Trust through transparency** - open source means people see exactly what happens with their data

## Revenue Projections (Conservative)

Assuming 10k active users after 12 months:

| Stream | Users/Buyers | Price | Monthly |
|--------|-------------|-------|---------|
| Hosted cloud | 500 (5%) | $20/mo | $10,000 |
| "I Got The Job" | 50/mo (0.5%) | $75 avg | $3,750 |
| Pipe Store | 20 paid pipes | $200/mo avg | $4,000 (CareerOS 20%) = $800 |
| Enterprise | 2 companies | $5,000/yr | $833 |
| **Total** | | | **$15,383/mo** |

At 50k users (achievable if the product is good and open source):
- Hosted: $50k/mo
- Donations: $18.75k/mo
- Pipe Store: $4k/mo
- Enterprise: $8.3k/mo
- **Total: ~$81k/mo**

## Inspiration

- **Screenpipe** - MIT open source + paid desktop app + pipe store marketplace
- **n8n** - open source + commercial cloud ($2.5B valuation)
- **Hugging Face** - open models + commercial inference/hosting
- **Wikipedia** - donation model that actually works at scale
- **Godot Engine** - pure open source, donation-funded, beloved

## Anti-Patterns (What We Won't Do)

- No FOMO pricing or escalating costs
- No gating core features behind paywalls
- No selling user data, ever
- No dark patterns in the donation flow
- No "free trial then surprise invoice"
- No LinkedIn scraping that violates ToS (we scrape job boards, not profiles)
