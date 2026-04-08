# Job Application Tracking

## Files

- **applications.csv** -- Master log of all job applications
- **contacts.csv** -- Networking contacts and relationship tracking

## Application Status Values

| Status | Meaning |
|--------|---------|
| `researching` | Identified opportunity, gathering info |
| `preparing` | Tailoring resume/cover letter |
| `applied` | Application submitted |
| `screening` | Recruiter screen scheduled/completed |
| `interviewing` | In interview process |
| `offer` | Received offer |
| `negotiating` | Negotiating terms |
| `accepted` | Offer accepted |
| `rejected` | Rejected by company |
| `declined` | Declined by me |
| `ghosted` | No response after 2+ weeks |

## Fit Score (1-10)

Rate each opportunity on alignment with target role criteria:

- **9-10:** Dream role -- AI-native, high autonomy, meaningful equity, strategic work
- **7-8:** Strong fit -- most criteria met, minor compromises
- **5-6:** Decent -- pays well but may be more traditional than ideal
- **3-4:** Fallback -- bridge role, not long-term
- **1-2:** Mismatch -- applying out of desperation only

## Workflow

1. Scraper finds jobs -> review and add to `applications.csv` with status `researching`
2. Research company on Kununu, Glassdoor, Levels.fyi -> update notes and fit_score
3. Tailor resume/cover letter -> status `preparing`
4. Submit application -> status `applied`, record date
5. Track all subsequent interactions -> update status, next_step, notes
