# Kestrel - Agent Instructions

Primary agent: **Claude Code**. Workflow logic below is agent-agnostic.

For project instructions and MCP setup, see [CLAUDE.md](CLAUDE.md).

---

## Top of Mind (always remember)

- Score roles against `profile/target-roles.md` before adding
- Location scoring is configurable in `config/personal.yaml` (preferred locations, relocation preferences)
- Never delete or overwrite tracking data without explicit user confirmation

---

## Job Intake Workflow

When the user shares a job posting (URL, saved markdown file, or manual paste), follow this workflow:

### 1. Extract Structured Data

Parse the posting and extract:
- **Company**: name
- **Role**: full title
- **Location**: city/country + remote status
- **URL**: original posting link
- **Source**: linkedin / indeed / company site / etc.
- **Salary range**: if mentioned in posting
- **Estimated salary**: use the Salary Estimation Guide in `profile/target-roles.md` if not posted
- **Key requirements**: top 5 bullet points
- **Description summary**: 2-3 sentences

### 2. Score Against Profile

Score the role 1-10 against `profile/target-roles.md` and `profile/README.md`:

**High score factors (7-10):**
- Matches your defined Tier 1 or Tier 2 target roles
- Aligns with preferred location or remote-friendly
- High autonomy, strategic thinking valued
- Within or above your target compensation range
- Strong alignment with your domain interests (AI/ML, developer tools, etc.)

**Medium score factors (4-6):**
- Interesting company but role is process-heavy
- Requires relocation within your country/region
- Tier 3 / bridge role characteristics

**Low score factors (1-3):**
- Heavy PMBOK/PMO process language with no innovation component
- Requires domain experience you lack
- Requires relocation outside your preferred region
- Below your minimum compensation threshold
- No alignment with your domain interests

**Location rules (configurable in `config/personal.yaml`):**
- Preferred locations or remote: no penalty
- Within your country/region: slight penalty unless offer is exceptional
- Outside preferred region: automatic score cap at 5 unless fully remote

### 3. Add to Pipeline

Use the CLI to add the application:
```bash
career-os pipeline add \
  --company "Company" \
  --role "Role Title" \
  --url "URL" \
  --source linkedin \
  --salary-range "120-140k (estimated)" \
  --notes "AI score rationale | effort: sweet-spot" \
  --fit-score 8
```

Or via API: `POST /api/applications` with the same data + `profile_id`.

For `salary_range`: use posted salary if available, otherwise estimate per the Salary Estimation Guide in `profile/target-roles.md`. Always note "(estimated)" or "(posted)".
For `notes`: append effort flag (sweet-spot/moderate/high-intensity) after score rationale.

Status will be "discovered" initially. Update to "interested" after review.

### 4. Create Tracking Issue (optional)

If you use Linear for task tracking:
- **Title**: `[Company] Role Title`
- **Description**: Include URL, score, key requirements, and fit rationale
- **Priority**: Based on score (8-10 = Urgent, 6-7 = High, 4-5 = Normal, 1-3 = Low)
- **Status**: Backlog

If you use TickTick:
- **Title**: `[Score/10] Company - Role Title`
- **Content**: URL + score rationale
- **Priority**: Map from score (8-10 = High, 6-7 = Medium, 1-5 = Low)

### 5. Present Summary

Show the user a clean summary:
```
[Company] - Role Title
Location (remote status)
Fit Score: X/10
Salary: 120-140k (estimated) | Effort: sweet-spot
Prep: 2/5 (light prep - system design chat, brush up on X)
Rationale: one-line reason
URL: link
Added to: Pipeline + tracking
```

---

## Input Formats

- **Browser extension MD file**: User references `@path/to/saved-page.md`. Parse the markdown for job details. The "About the job" section contains the description.
- **Pasted URL**: Use WebFetch to grab content. Sign-in walls may limit data; extract what's available and ask user to supplement if needed.
- **Manual paste**: User pastes the job description text directly. Extract what you can.

---

## Batch Mode

If the user provides multiple URLs or files at once, process all of them and present a summary table at the end.

---

## Job Discovery

When the user asks to **search for jobs**, use these tools in order of preference:

| Tool | When to use |
|------|--------------|
| **tools/germany_jobs.py** | Country-specific roles (Arbeitsagentur + Arbeitnow). Run: `python tools/germany_jobs.py --keywords "TPM" --location "Frankfurt"` |
| **JobSpy MCP** | Multi-board search (Indeed, LinkedIn, Glassdoor) - requires Docker + jobspy image |
| **Himalayas MCP** | Remote-only jobs |
| **tools/scraper.py** | Fallback: `python tools/scraper.py --keywords "Product Manager"` |
| **WebSearch** | Built-in web search for ad-hoc job postings |

Score all results against `profile/target-roles.md` and present a table. User picks which to add via job-intake.

---

## Application Preparation Toolkit

### RenderCV - Tailored CV Generation (PRIMARY method)

**RenderCV** generates LaTeX-quality typeset PDFs from YAML. This is the canonical CV pipeline.

**Canonical source:** `cv/cv.yaml` - RenderCV v2.6 format. ALL facts (education, dates, experience, skills) come from this file. NEVER invent or hallucinate data.

**Base CV build:**
```bash
cd cv && rendercv render cv.yaml
```

**Tailored CVs (per role):**
```bash
.venv/bin/python tools/render_tailored_cvs.py
```
This script:
1. Loads `cv/cv.yaml` as base
2. Replaces the summary section with a role-specific tailored summary
3. Renders via RenderCV and copies PDF to `cv/applications/[company]-[role]/`

**To add a new role:** Edit `ROLES` dict in `tools/render_tailored_cvs.py` with:
- `filename`: output PDF name (no extension)
- `summary`: tailored summary paragraph for that specific role

**Key rules:**
- All dates, education, and experience facts come from `cv/cv.yaml` only
- Never invent or hallucinate data not present in the canonical source

### Cover Letter PDF Generation

Cover letters are written manually in markdown, then converted to PDF.

**Markdown source:** `cv/applications/[company]-[role]/cover-letter.md`

**PDF generation:**
```bash
.venv/bin/python tools/md_to_pdf_cover_letter.py
```
Uses fpdf2 with Arial TTF fonts for Unicode support. Handles:
- Name header (bold, navy)
- Contact line
- Date
- Subject line (bold, navy, starts with `**Re:`)
- Body paragraphs
- Bullet points with `- **Label** rest of text` format (bold label + full-width flow)

**To add a new cover letter:** Add directory name to `dirs` list in `tools/md_to_pdf_cover_letter.py`

**Cover letter voice and style:**
- Write in the user's authentic voice - direct, specific, no corporate fluff
- Read profile docs (`profile/`) before writing to match tone
- Every claim must be backed by specific evidence from profile docs or `cv/cv.yaml`
- Name gaps honestly

### CV Forge MCP (on-demand)

Application preparation tools. Use ONLY for:
- `parse_job_requirements(...)` - structured JD extraction (useful)
- `generate_email_template(...)` - email drafts (decent starting point)
- `generate_cover_letter(...)` - AVOID, produces generic output. Write manually instead.
- `generate_cv(...)` - AVOID, use RenderCV instead (better typography, correct data)

### Workflow: Tailored Application

When the user provides a job URL and wants a **tailored application**:
1. Fetch full JD (WebFetch or Lever/Greenhouse API)
2. `parse_job_requirements(...)` - structured extraction
3. Read ALL profile docs (`profile/README.md`, voice/identity docs, capability docs, `cv/cv.yaml`)
4. Write cover letter manually in markdown and save to `cv/applications/[company]-[role]/cover-letter.md`
5. Add role to `tools/render_tailored_cvs.py` and run to generate tailored CV PDF
6. Add dir to `tools/md_to_pdf_cover_letter.py` and run to generate cover letter PDF
7. Run job-intake to add to tracking

**Output per role in `cv/applications/[company]-[role]/`:**
- `cover-letter.md` - markdown source (editable)
- `cover-letter.pdf` - generated PDF
- `[name]-[company]-cv.pdf` - tailored RenderCV PDF

---

## Project Context

- **Profile (identity & voice)**: `profile/README.md`, voice/identity docs in `profile/`
- **Profile (evidence)**: capability digests, strengths summaries in `profile/`
- **Profile (strategy)**: `profile/target-roles.md`, `profile/narrative.md`
- **CV source**: `cv/cv.yaml` - CANONICAL source of truth for all dates, education, experience
- **CV build tools**: `tools/render_tailored_cvs.py` (RenderCV per-role), `tools/md_to_pdf_cover_letter.py` (cover letter PDF)
- **Applications**: `cv/applications/[company]-[role]/` - each folder has cover-letter.md, cover-letter.pdf, CV PDF

---

## Safety

- Before any destructive action (delete, overwrite, bulk changes), ask for explicit confirmation
- Never modify `profile/target-roles.md` without user approval
- Never invent or hallucinate data not present in `cv/cv.yaml`
