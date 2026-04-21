# Technology Stack

**Project:** Kestrel Onboarding Experience
**Researched:** 2026-04-19

## Recommended Stack

### CLI Wizard (Interactive Prompts)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| questionary | 2.1.1 | Interactive prompt UI (select, confirm, text, checkbox) | Best-in-class Python prompt library. Built on prompt_toolkit (same foundation as Typer). 8 prompt types including fuzzy select. MIT license. Works alongside Typer -- Typer handles command routing, questionary handles multi-step wizard UX. |
| rich | >=13.9.0 | Progress bars, formatted output, panels, tables | **Already a dependency.** Typer uses Rich internally. No new install needed. Provides spinners, progress bars, styled panels for wizard steps. |
| typer | >=0.15.0 | CLI command framework | **Already a dependency.** `kestrel init` will be a new Typer command. Questionary prompts run inside the Typer command handler. |

**Why questionary over alternatives:**
- **InquirerPy** (0.3.4): More features but unmaintained since 2023. Last commit activity stalled. questionary is actively maintained (2.1.1 released recently).
- **PyInquirer**: Abandoned. Still on prompt_toolkit 1.x. Do not use.
- **Typer's built-in `typer.prompt()`**: Too basic -- only supports single text/confirm prompts. No select lists, no multi-select, no fuzzy matching. Fine for one-off confirms but not for a 5-7 step wizard.
- **python-inquirer (magmax)**: Uses `blessed` instead of `prompt_toolkit`, creating a dependency conflict with the Typer/Rich ecosystem. Avoid.

**Confidence: HIGH** -- questionary is well-documented, stable, MIT-licensed, and the standard pairing with Typer for wizard flows.

### Resume/CV Parsing (Local, Privacy-First)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pdfplumber | 0.11.x | PDF text extraction | Best accuracy for machine-generated PDFs (which resumes almost always are). Handles tables, columns, and complex layouts. 96% table recognition rate. Visual debugging for development. Lightweight (~2MB with pdfminer.six dependency). |
| python-docx | 1.2.0 | DOCX text extraction | De facto standard for reading .docx files. Production-stable, well-maintained. Already resolved by Context7 as authoritative. |
| spaCy | 3.8.x + en_core_web_sm | NER for name, organization, location, date extraction | Industry standard for NER. The `en_core_web_sm` model is 13MB -- acceptable for a CLI tool. Extracts PERSON, ORG, GPE (location), DATE entities out of the box. Required for structured extraction beyond regex. |
| rapidfuzz | >=3.6.0 | Fuzzy matching extracted skills against Kestrel's skill taxonomy | **Already a dependency.** Use to match messy CV skill strings ("Project Mgmt") to canonical skills in the database. |

**Architecture: Two-tier parsing strategy**

```
Tier 1 - Regex (fast, zero-dependency beyond pdfplumber/python-docx):
  - Email: regex
  - Phone: regex
  - LinkedIn URL: regex
  - Section headers (Education, Experience, Skills): regex + heuristics

Tier 2 - spaCy NER (when regex isn't enough):
  - Full name: PERSON entity
  - Company names: ORG entity
  - Locations: GPE entity
  - Dates/durations: DATE entity
  - Job titles: custom patterns via spaCy EntityRuler
```

**Why this approach over alternatives:**
- **pyresparser**: Requires both spaCy AND NLTK. NLTK adds ~100MB+ of data. Unmaintained (last update 2020). Skip.
- **pyresume (wespiper)**: Too new, unproven, minimal GitHub stars. Risky for production.
- **Full spaCy-only approach**: Overkill for email/phone/URL extraction. Regex is faster and more reliable for structured patterns.
- **LLM-based parsing**: Violates the "no external API" constraint. Local LLMs are too heavy for a CLI install.
- **resume-parser (PyPI)**: Thin wrapper around pyresparser with same problems. Skip.

**Install size concern:** spaCy + en_core_web_sm adds ~150-200MB to the install. This is the heaviest new dependency. Mitigation: make it an optional dependency (`pip install kestrel-app[cv]`) so users who skip CV import don't pay the cost.

**Confidence: MEDIUM** -- The two-tier approach is sound architecture, but CV parsing accuracy varies wildly by resume format. Budget time for edge cases. The regex tier will handle 70-80% of cases; spaCy handles the rest. Some resumes (creative layouts, image-heavy) will fail gracefully.

### Web UI Tour/Walkthrough

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| react-joyride | 3.0.x | Interactive tooltip-based product tour | De facto standard for React product tours. v3 released with full React 19 support (critical -- Kestrel uses React 19). ~30% smaller bundle than v2. Named exports, hook-based API. 6.7k+ GitHub stars. MIT license. |

**Why react-joyride over alternatives:**
- **Reactour**: Simpler API but less customizable. No callback system for tracking tour completion. Fewer GitHub stars and community resources.
- **Shepherd.js (react-shepherd)**: Framework-agnostic core adds abstraction overhead. The React wrapper is thinner than Joyride's native React implementation. More suited for non-React apps that need cross-framework support.
- **NextStepjs**: Very new (2024), small community. Not enough production validation. Cool concept but risky.
- **Intro.js**: Requires commercial license for production use. Not compatible with AGPL open-source project economics.
- **Custom implementation**: Tooltip tours are deceptively complex (scroll handling, resize, z-index, focus management). Don't build from scratch.

**Confidence: HIGH** -- react-joyride v3 is the clear winner for React 19 apps. Well-maintained, feature-complete, MIT-licensed.

### Web UI Onboarding Patterns (No Additional Libraries)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Tailwind CSS | >=4.2.1 | Welcome screens, empty states, progress indicators | **Already a dependency.** All onboarding UI (welcome modal, empty state cards, progress stepper) should be built with existing Tailwind + custom components. No additional UI library needed. |
| lucide-react | >=1.0.0 | Icons for onboarding steps, empty states | **Already a dependency.** Provides all icons needed for welcome screens and empty state illustrations. |
| TanStack React Query | >=5.x | Onboarding state persistence via API | **Already a dependency.** Track onboarding completion status server-side. |

**Why no additional libraries for web onboarding UI:**
- Welcome screens and empty states are simple layout components -- Tailwind handles this perfectly.
- Progress steppers are 50-100 lines of custom code with Tailwind. No need for a stepper library.
- "Do it later" signposting is routing + conditional rendering -- already covered by React Router.
- Adding more dependencies for simple UI patterns increases bundle size and maintenance burden for no gain.

**Confidence: HIGH** -- These are standard UI patterns. The existing stack handles them without additions.

## Supporting Libraries (Already Present, Leveraged for Onboarding)

| Library | Already In | Purpose for Onboarding |
|---------|-----------|----------------------|
| rich | Backend | CLI wizard formatting, progress bars, error panels |
| typer | Backend | `kestrel init` command registration |
| rapidfuzz | Backend | Fuzzy-match extracted CV skills to Kestrel taxonomy |
| pydantic | Backend | Validation schemas for parsed CV data |
| tailwindcss | Frontend | All onboarding UI styling |
| lucide-react | Frontend | Onboarding icons and illustrations |
| react-router-dom | Frontend | Onboarding flow routing, redirect after completion |
| @tanstack/react-query | Frontend | Onboarding state API calls |

## Full New Dependency List

### Backend (Python)

```bash
# Core new dependencies
pip install questionary pdfplumber python-docx

# Optional heavy dependency for CV NER (recommended)
pip install spacy
python -m spacy download en_core_web_sm
```

**pyproject.toml additions:**
```toml
# In [project.dependencies] -- lightweight, always installed
"questionary>=2.1.0",
"pdfplumber>=0.11.0",
"python-docx>=1.1.0",

# In [project.optional-dependencies]
cv = [
    "spacy>=3.7.0",
]
```

### Frontend (npm)

```bash
cd frontend
npm install react-joyride@^3.0.0
```

**Total new dependencies: 4** (questionary, pdfplumber, python-docx, react-joyride) + 1 optional (spaCy).

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CLI prompts | questionary | InquirerPy | Unmaintained since 2023, activity stalled |
| CLI prompts | questionary | typer.prompt() | Too basic -- no select lists, no multi-select |
| CLI prompts | questionary | python-inquirer | Uses blessed (not prompt_toolkit), dependency conflict |
| PDF parsing | pdfplumber | PyPDF2/pypdf | Worse text extraction from complex layouts |
| PDF parsing | pdfplumber | pdfminer.six | Lower-level API, pdfplumber wraps it with better DX |
| PDF parsing | pdfplumber | pymupdf (fitz) | GPL licensed -- incompatible with distribution concerns |
| DOCX parsing | python-docx | docx2txt | Abandoned, no table support, minimal features |
| NER | spaCy | NLTK | 100MB+ data download, worse NER accuracy, slower |
| NER | spaCy | transformers (HuggingFace) | Massive install size (1GB+), overkill for resume NER |
| React tour | react-joyride v3 | Reactour | Less customizable, weaker callback system |
| React tour | react-joyride v3 | Shepherd.js | Framework-agnostic overhead, thinner React wrapper |
| React tour | react-joyride v3 | Intro.js | Commercial license required for production |
| Onboarding UI | Tailwind (existing) | Chakra UI / Radix | Adding a component library for 3-4 screens is overkill |

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| **PyInquirer** | Abandoned. Stuck on prompt_toolkit 1.x. Known bugs. |
| **pyresparser** | Requires NLTK + spaCy together. Unmaintained since 2020. |
| **resume-parser (PyPI)** | Thin wrapper around pyresparser. Same problems. |
| **Intro.js** | Commercial license for production. Not compatible with open-source project. |
| **Any external API resume parser** (Affinda, Eden AI, etc.) | Violates privacy constraint. CV data must never leave the user's machine. |
| **pymupdf/fitz** | GPL-licensed. Legal risk for AGPL project distribution. Use pdfplumber instead. |
| **textract** | Requires system-level dependencies (antiword, etc.). Hostile to non-dev users. |
| **NLTK for NER** | Massive download, worse accuracy than spaCy, slower inference. |
| **Full transformer models** | 1GB+ install for marginally better NER. Not worth it for resume parsing. |

## Sources

- [questionary PyPI](https://pypi.org/project/questionary/) -- v2.1.1, MIT license
- [questionary GitHub](https://github.com/tmbo/questionary) -- active maintenance
- [pdfplumber GitHub](https://github.com/jsvine/pdfplumber) -- v0.11.x, MIT license
- [python-docx docs](https://python-docx.readthedocs.io/) -- v1.2.0
- [spaCy models](https://spacy.io/models) -- en_core_web_sm ~13MB
- [react-joyride npm](https://www.npmjs.com/package/react-joyride) -- v3.0.2, React 19 support
- [react-joyride v3 docs](https://react-joyride.com/docs/new-in-v3) -- migration guide
- [InquirerPy GitHub](https://github.com/kazhala/InquirerPy) -- for comparison (unmaintained)
- [Intro.js pricing](https://introjs.com/) -- commercial license required
