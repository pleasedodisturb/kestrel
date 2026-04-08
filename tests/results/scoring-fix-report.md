# Scoring Fix Report -- 2026-03-27 Re-score

## Summary

- **Total jobs:** 194
- **Pre-filter rejected:** 62 (32%)
- **Pre-filter capped:** 0
- **Passed to AI scoring:** 132

## Before vs After

- **Old 10/10 scores:** 78 (was 78 out of 194 = 40%)
- **Of those 78, now rejected by pre-filter:** 33
- **Remaining for AI (from old 10s):** 45

## What Changed

### 1. Hard pre-filters added (before AI scoring)
- Title-based rejection for obviously irrelevant roles
  (accountant, sales rep, customer support, HR, legal, nurse, etc.)
- Blocked companies (Nebius, Yandex)
- Junior role detection (intern, werkstudent, junior without lead/senior)
- US-only location cap (score capped at 3 unless remote)

### 2. AI prompt rewritten to be much stricter
- Explicit HARD CAPS for each wrong-domain category (sales=MAX 1, etc.)
- Clear scoring calibration: max 2-3 per 200 at 9-10
- Candidate profile embedded directly in system prompt
- Changed from 'strict' to 'EXTREMELY strict' with explicit instructions
  to score 1 immediately for obviously wrong titles

### 3. Fallback scores lowered
- JSON parse error fallback: 5 -> 2
- API error fallback: 5 -> 2
- Keyword fallback base: 5 -> 3

## Rejection Reasons

- Rejected title pattern: 61
- Junior role: 1

## Sample: Old 10/10 Now Rejected

| Title | Company | Old Score | Action |
|-------|---------|-----------|--------|
| Compensation Analyst | BHG Financial | 10 | REJECTED |
| Mid Market Customer Account Manager | Iterable | 10 | REJECTED |
| Senior Accountant | Blink Health | 10 | REJECTED |
| Sales & Business Development Director | NEAR Foundation | 10 | REJECTED |
| Smart Contract Engineer SVM | Veda Tech Labs | 10 | REJECTED |
| Financial Crimes Analyst I | Dave | 10 | REJECTED |
| Affiliate Marketing & Partnerships Lead | Material Bank | 10 | REJECTED |
| 58134729590 Marketing Operations & Execution Lead | Activate Talent | 10 | REJECTED |
| Customer Support Specialist | HighLevel | 10 | REJECTED |
| Sales Development Representative | Ping Identity | 10 | REJECTED |
| Technical Account Manager | Rithum | 10 | REJECTED |
| Global Head of AML & Regulatory Compliance | Kraken | 10 | REJECTED |
| Head of AML & CTF Compliance (PCF-52) | Kraken | 10 | REJECTED |
| Account Manager, Monetize | Liftoff | 10 | REJECTED |
| Sr. Technical Artist | Fortis Games | 10 | REJECTED |
| Customer Support Team Lead | Paddle | 10 | REJECTED |
| Buyer Support Team Lead | Paddle | 10 | REJECTED |
| Manager, Employee Relations | Remote | 10 | REJECTED |
| Account Executive, Mid-Market | DACH | Deel | 10 | REJECTED |
| Benefits Manager | Deel | 10 | REJECTED |
| Junior Account Manager | Automat-it | 10 | REJECTED |
| Senior Automation Quality Assurance Engineer | Automat-it | 10 | REJECTED |
| HR Specialist | Automat-it | 10 | REJECTED |
| Senior Manager, Clinical Trial Management | Precision Medicine Group | 10 | REJECTED |
| Salesforce Developer | UCAS | 10 | REJECTED |
| Salesforce Administrator (App Builder) | UCAS | 10 | REJECTED |
| Head of Food Assurance Services | SGS | 10 | REJECTED |
| Onboarding Technician | Nextiva | 10 | REJECTED |
| Affiliate Marketing Manager | Hello There Collective | 10 | REJECTED |
|  Growth Manager | Maps Platform (Remote in Europe) | MapTiler | 10 | REJECTED |
| Accounts Payable & Finance Operations Specialist ( | EverAI | 10 | REJECTED |
| Head of Support | OnTheGoSystems | 10 | REJECTED |
| Community & Support Specialist - EST Time Zone (Co | IFTTT | 10 | REJECTED |

## Sample: Correctly Passed (Good Roles)

| Title | Company | Old Score | Action |
|-------|---------|-----------|--------|
| Application-Engineer/-Manager/in | NTT DATA Deutschland SE | 5 | PASS |
| KI-Engineer | NTT DATA Deutschland SE | 5 | PASS |
| Senior Sales Engineer | Harness | 10 | PASS |
| Systems Engineer (f/m/d), Hybrid | KLA | 10 | PASS |
| Senior Developer Backend Search CD+E | Ubiminds | 10 | PASS |
| Lead Security Engineer | Copia Automation | 10 | PASS |
| Fire Protection Engineer | Skillcloud HCM | 7 | PASS |
| Senior Frontend Engineer Frontend Platform | Vannevar | 8 | PASS |
| Research Engineer | Turing | 9 | PASS |
| Lead Front End Software Engineer | Callibrity | 7 | PASS |
| Security Engineer II Canada | NerdWallet | 9 | PASS |
| GenAI Senior Integrated Designer | Brandtech+ | 7 | PASS |
| Product Manager Growth | 12Go Asia | 10 | PASS |
| Senior Product Manager Core Infrastructure | Mesh | 10 | PASS |
| Forward Deployed Engineer VoIP | Parloa | 9 | PASS |
| Senior Staff Software Engineer AI Customer Operati | Monzo | 8 | PASS |
| Go To Market Engineer | TestGorilla | 10 | PASS |
| Senior Staff Engineer Product Security | Faire | 10 | PASS |
| Principal Machine Learning Engineer | Attentive | 8 | PASS |
| Senior Engineering Manager, Design | GitLab | 10 | PASS |
| Founding Software Engineer – Agentic Systems | Veriff | 10 | PASS |
| AI Agents Solutions Architect – Finance | Kraken | 10 | PASS |
| Engineering Director | Precision Medicine Group | 10 | PASS |
| Senior Backend Engineer(Golang) – PerfectScale by  | DoiT International | 10 | PASS |
| House Engineering Manager -Cloud Diagrams | DoiT International | 10 | PASS |
| Senior Backend Engineer (Elixir) | Remote | 10 | PASS |
| Senior Backend Engineer | Remote | 10 | PASS |
| Senior DevOps Engineer | Docplanner | 10 | PASS |
| Solutions Engineer, EMEA – SELECT by DoiT | DoiT International | 10 | PASS |
| Scene Service Product Engineer II | ESRI | 10 | PASS |
| Data Engineer, 80-100% (f/m/x), remote | comparis.ch | 10 | PASS |
| Lead Frontend Engineer | FINN | 10 | PASS |
| Principal Software Engineer | LawnStarter | 10 | PASS |
| Senior Software Engineer | Cue | 9 | PASS |
| (Senior) AI Solutions Engineer | Aktor AI | 10 | PASS |
| Full-Stack Developer (Junior) | LeadUp AI | 10 | PASS |
| Senior Product Manager - Endpoint Management & Pat | Action1 | 9 | PASS |
| Senior Frontend Engineer (React / Next.js) — Full- | Knack | 10 | PASS |
| Full-Stack PHP Developer  | OnTheGoSystems | 10 | PASS |
| Product Manager - Enterprise (PRISE) | Magicschool Ai | 9 | PASS |
| Senior Full Stack Developer (Kotlin, Vue.js) (Remo | Smart Working Solutions | 9 | PASS |
| Senior Product Manager (Data Products) | G2 | 10 | PASS |
| Product Manager, AI | Wing Assistant | 10 | PASS |
| Head of Engineering | Lemon.io | 10 | PASS |
|  Java Developer - AI (Backend) | CloudDevs | 10 | PASS |
| Senior Product Designer (Typeform Ai) | Typeform | 10 | PASS |
| Senior Firmware Engineer | Sanctuary Computer | 9 | PASS |
| Frontend Developer | C4Media | 9 | PASS |
| Senior Frontend Engineer | Level | 10 | PASS |
