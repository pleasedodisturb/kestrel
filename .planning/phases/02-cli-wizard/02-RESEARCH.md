# Phase 2: CLI Wizard - Research

**Researched:** 2026-04-20
**Domain:** Python CLI (Typer + Rich), interactive prompts, regex extraction, ESCO skill matching
**Confidence:** HIGH

## Summary

Phase 2 builds `kestrel init` (interactive profile wizard) and `kestrel doctor` (health check) as top-level Typer commands. The entire implementation is CLI-only with direct DB access — no HTTP API, no web UI. All required libraries (Typer 0.24.1, Rich 15.0.0, rapidfuzz 3.14.5) are already installed and used elsewhere in the codebase. The existing CLI test pattern (CliRunner + monkeypatched `_get_session`) is well-established and supports `input=` for simulating interactive prompts.

The key challenge is testing interactive multi-step prompts with Rich's `Prompt` class through Typer's CliRunner, which pipes stdin. Rich Prompt reads from stdin by default but needs the `console` parameter set correctly for testing. The existing `console = Console()` in `cli/main.py` should be shared with the init module.

**Primary recommendation:** Build `cli/init.py` and `cli/doctor.py` as new modules registered on the main `app`. Use `rich.prompt.Prompt.ask()` / `Confirm.ask()` for all interaction. Test via CliRunner with `input=` providing newline-separated answers.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Use `rich.prompt` (Prompt, Confirm, IntPrompt) for all interactive questions
- D-02: Empty Enter = skip (default values shown in brackets)
- D-03: Rich Panel welcome banner before questions start
- D-04: Summary table + confirm after collecting all answers (PROF-03)
- D-05: Rich Progress bar for step indicator (CLI-05)
- D-06: `kestrel init` and `kestrel doctor` are top-level commands on the main app — new file `cli/init.py`
- D-07: Direct DB access via `SessionLocal()` — no HTTP API calls
- D-08: Inline terminal tips at key moments
- D-09: First-run detection via onboarding state (query OnboardingState for default profile)
- D-10: First-run message is a Rich Panel
- D-11: Typer callback on main app for first-run check (non-blocking)
- D-12: Context-aware next-step suggestions after each CLI action (CLI-08)
- D-13: Update onboarding state per step (profile_started, profile_completed)
- D-14: Resume from last step on re-run
- D-15: Basic regex patterns for extraction (email, phone, URLs, skills via rapidfuzz)
- D-16: Optional step after guided questions for paste-text extraction
- D-17: ESCO taxonomy for skill matching (existing taxonomy + rapidfuzz)
- D-18: Double-Enter to finish multiline paste
- D-19: Local-only health checks (Python version, DB connection, migrations, profile, demo data)
- D-20: Pass/fail checklist output for doctor command

### Claude's Discretion
- Internal service function signatures for wizard steps
- Exact regex patterns for email/phone/URL extraction
- Progress bar styling and positioning (Rich Progress API)
- How to integrate first-run callback without interfering with existing commands
- Test fixture approach for wizard tests (mock stdin, capture stdout)
- Error message wording for specific failure scenarios

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | First-run next-steps message | D-09/D-10/D-11: Typer callback checks OnboardingState, shows Rich Panel |
| CLI-02 | `kestrel init` interactive wizard | D-01/D-06: rich.prompt on cli/init.py, registered on main app |
| CLI-03 | Non-TTY detection with --non-interactive guidance | sys.stdin.isatty() check at wizard start |
| CLI-04 | `kestrel init --skip` creates default profile | Flag on init command, creates Profile with defaults |
| CLI-05 | Progress indicator ("Step 2/5") | D-05: Rich Progress bar |
| CLI-06 | `kestrel doctor` health check | D-19/D-20: cli/doctor.py with pass/fail checklist |
| CLI-07 | Errors include what/why/what-to-do | OnboardingError hierarchy + Rich formatting, no stack traces |
| CLI-08 | Suggested next command after each action | D-12: Per-command next-step hint |
| PROF-01 | 5-7 guided questions (name, location, roles, salary, skills, experience) | Maps to Profile model fields: name, location, job_family + new fields if needed |
| PROF-02 | Paste resume text with regex extraction | D-15/D-16/D-17/D-18: regex + rapidfuzz + ESCO |
| PROF-03 | Extracted data shown for confirmation | D-04: Rich Table summary + Confirm |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Interactive prompts | CLI (terminal) | — | User input/output is exclusively terminal |
| Profile data persistence | Database / Storage | — | SQLAlchemy ORM writes to SQLite |
| Onboarding state tracking | Database / Storage | — | OnboardingState model from Phase 1 |
| Resume text extraction | CLI (terminal) | — | Regex + rapidfuzz run in-process, no API |
| Health checks (doctor) | CLI (terminal) | Database / Storage | Probes local DB, Python, migrations |
| First-run detection | CLI (terminal) | Database / Storage | Callback queries DB on every CLI invocation |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.24.1 | CLI framework, command registration | Already used for all CLI commands [VERIFIED: pip show] |
| rich | 15.0.0 | Prompt, Confirm, Panel, Table, Progress | Already used throughout CLI [VERIFIED: pip show] |
| rapidfuzz | 3.14.5 | Fuzzy skill matching against ESCO | Already used in skill_normalizer.py [VERIFIED: pip show] |
| sqlalchemy | (installed) | ORM for Profile, OnboardingState | Core DB layer [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | — | Email/phone/URL regex extraction | Resume paste parsing |
| sys (stdlib) | — | isatty() check for non-TTY detection | CLI-03 |
| platform (stdlib) | — | Python version check in doctor | CLI-06 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rich.prompt | questionary | Would add a dependency; rich.prompt is zero-cost and matches existing patterns |
| Manual step tracking | tqdm | Overkill; Rich Progress already available |

**Installation:**
```bash
# No new dependencies required — all already in pyproject.toml
```

## Architecture Patterns

### System Architecture Diagram

```
User types `kestrel init`
    |
    v
[Typer Main App] --callback--> [First-Run Check]
    |                              |
    |                              v
    |                         Query OnboardingState
    |                              |
    |                         if incomplete: print Panel hint
    |
    v
[cli/init.py: init_command()]
    |
    +--- Non-TTY check (sys.stdin.isatty())
    |         +-- if False: exit with --non-interactive guidance
    |
    +--- --skip flag check
    |         +-- if True: create default profile, mark steps complete, exit
    |
    +--- Resume detection (D-14)
    |         +-- query OnboardingState -> skip completed steps
    |
    +--- Welcome Panel (D-03)
    |
    +--- Step 1-N: Guided Questions (rich.prompt.Prompt.ask)
    |         |    Progress bar advances per step
    |         |    Empty Enter = skip (default value used)
    |         |    mark_step_complete("profile_started") on first answer
    |         |
    |         v
    +--- Optional: Paste Resume Text (D-16)
    |         |    Double-Enter to finish multiline
    |         |    Regex: email, phone, URLs
    |         |    rapidfuzz + ESCO: skill keywords
    |         |    Merge with existing answers
    |         |
    |         v
    +--- Summary Table + Confirm (D-04 / PROF-03)
    |         |    If rejected: re-run wizard
    |         |
    |         v
    +--- Save to Profile (DB write)
    |
    +--- mark_step_complete("profile_completed")
    |
    +--- Next-step suggestion: "Try `kestrel pipeline list`"


User types `kestrel doctor`
    |
    v
[cli/doctor.py: doctor_command()]
    |
    +-- Check Python version >= 3.11
    +-- Check DB connection (SessionLocal())
    +-- Check migrations applied (alembic current)
    +-- Check default profile exists
    +-- Check demo data present
         |
         v
    Pass/fail checklist output (check / X + resolution)
```

### Recommended Project Structure
```
src/career_os/cli/
+-- main.py          # Add first-run callback + import init/doctor
+-- init.py          # NEW: kestrel init wizard
+-- doctor.py        # NEW: kestrel doctor health check
+-- contacts.py      # Existing
+-- warn.py          # Existing
```

### Pattern 1: Interactive Prompt with Skip-on-Empty
**What:** Use `rich.prompt.Prompt.ask()` with `default=""` so pressing Enter returns empty string (treated as skip)
**When to use:** Every wizard question (PROF-01)
**Example:**
```python
from rich.prompt import Prompt, Confirm

# Skippable question with shown default
name = Prompt.ask("[bold]Your name[/bold]", default="", console=console)
if not name:
    name = None  # treat as skipped

# Location with hint
location = Prompt.ask(
    "[bold]Your location[/bold] [dim](city, country)[/dim]",
    default="",
    console=console,
)
```
[VERIFIED: rich 15.0.0 installed, Prompt.ask signature confirmed via import test]

### Pattern 2: Multiline Paste with Double-Enter Termination
**What:** Read lines until two consecutive empty lines (D-18)
**When to use:** Resume text paste (PROF-02)
**Example:**
```python
def read_multiline_paste(console: Console) -> str:
    """Read multiline input terminated by double-Enter."""
    console.print("[dim]Paste your resume text below (press Enter twice when done):[/dim]")
    lines: list[str] = []
    empty_count = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
            lines.append(line)
        else:
            empty_count = 0
            lines.append(line)
    return "\n".join(lines).strip()
```
[ASSUMED: double-Enter pattern is standard for CLI multiline input]

### Pattern 3: Typer Callback for First-Run Detection
**What:** Register a callback on the main app that runs before any command
**When to use:** CLI-01 first-run message
**Example:**
```python
@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Run first-run check before any command."""
    # Don't check for init/doctor commands or --help
    if ctx.invoked_subcommand in ("init", "doctor"):
        return
    if ctx.resilient_parsing:  # --help/completion
        return

    db = _get_session()
    try:
        from career_os.services.onboarding import get_onboarding_status
        status = get_onboarding_status(profile_id=1, db=db)
        if not status.is_complete:
            console.print(Panel(
                "[bold]Welcome to Kestrel![/bold]\n"
                "Run [bold]kestrel init[/bold] to set up your profile.",
                border_style="blue",
            ))
    except Exception:
        pass  # Don't block normal commands if DB isn't ready
    finally:
        db.close()
```
[VERIFIED: Typer 0.24.1 supports @app.callback(); existing goals_app uses this pattern]

### Pattern 4: Progress Bar for Step Indicator
**What:** Rich Progress with a simple task showing "Step X/N"
**When to use:** CLI-05 step indicator
**Example:**
```python
from rich.progress import Progress, BarColumn, TextColumn

TOTAL_STEPS = 5

with Progress(
    TextColumn("[bold blue]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    console=console,
) as progress:
    task = progress.add_task("Setting up profile", total=TOTAL_STEPS)
    # After each question:
    progress.advance(task)
    progress.update(task, description=f"Step {completed}/{TOTAL_STEPS}")
```
[VERIFIED: Rich 15.0.0 has Progress, BarColumn, TextColumn — already imported in codebase elsewhere]

### Anti-Patterns to Avoid
- **Blocking on first-run check:** Never make the callback raise or exit — it's advisory only (D-11 says non-blocking)
- **Raw input() without Rich:** Always use `rich.prompt.Prompt.ask()` for styled prompts; only use raw `input()` for multiline paste where Rich can't handle line-by-line
- **HTTP calls from CLI:** Direct DB access only (D-07). Never import or call API routes from CLI commands
- **Nested Typer subgroup for init:** D-06 says top-level commands. Use `@app.command("init")` not a subgroup

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy skill matching | Custom Levenshtein | rapidfuzz + existing `skill_normalizer.py` | 14K ESCO entries, edge cases, threshold tuning already done |
| Email regex | Simple `@` check | Standard RFC-aware regex | False positives/negatives on edge cases |
| Terminal prompts | Custom input loops | `rich.prompt.Prompt` / `Confirm` | Handles keyboard interrupt, styling, defaults |
| Step progress tracking | Custom counter | `rich.progress.Progress` | Live update, styling, proper terminal handling |
| DB session management | Context managers | Existing `_get_session()` + try/finally | Matches all existing CLI commands exactly |

**Key insight:** This phase adds zero new dependencies. Every building block exists in the codebase already — the work is composition and UX polish, not infrastructure.

## Common Pitfalls

### Pitfall 1: Rich Prompt Breaks in CliRunner Tests
**What goes wrong:** `Prompt.ask()` reads from sys.stdin but CliRunner captures differently; tests hang or get empty input
**Why it happens:** Rich Prompt uses its own Console's input method, which may not respect CliRunner's input piping
**How to avoid:** Pass `console=console` to Prompt.ask() AND ensure the test CliRunner is initialized without `mix_stderr=False`. Alternatively, mock `rich.prompt.Prompt.ask` in tests to return predetermined answers. The CliRunner `input=` param works with Click's `click.prompt()` but Rich's Prompt bypasses Click — test strategy should mock at the Prompt level.
**Warning signs:** Tests hang waiting for input, or receive empty strings

### Pitfall 2: Callback Breaks no_args_is_help
**What goes wrong:** Adding `@app.callback()` changes Typer's help behavior — `kestrel` with no args may no longer show help
**Why it happens:** Typer callbacks can override the `invoke_without_command` behavior
**How to avoid:** Keep `no_args_is_help=True` on the app, and ensure the callback doesn't consume the invocation. Set `invoke_without_command=False` on the callback explicitly if needed. Test `kestrel --help` and `kestrel` (no args) after adding callback.
**Warning signs:** Running `kestrel` alone either shows the first-run panel with no help, or errors

### Pitfall 3: Profile Row Missing on Fresh Install
**What goes wrong:** `kestrel init` tries to update Profile(id=1) but it doesn't exist yet on a fresh install
**Why it happens:** Default profile is created by migration/seeder, but fresh DB has no rows
**How to avoid:** The wizard must CREATE a profile if none exists, not just UPDATE. Check `db.query(Profile).first()` — if None, create one. Similarly for OnboardingState (already handled by service layer's lazy creation).
**Warning signs:** IntegrityError or "No default profile" on first run

### Pitfall 4: Double-Enter Detection with CliRunner Input
**What goes wrong:** CliRunner's `input=` parameter sends all input at once, making double-Enter detection unreliable
**Why it happens:** CliRunner doesn't simulate real-time typing; it pipes the full string
**How to avoid:** In test input strings, include `\n\n` for the double-Enter terminator. The `read_multiline_paste` function processes line-by-line from stdin regardless of source.
**Warning signs:** Paste function never terminates in tests, or terminates too early

### Pitfall 5: Onboarding State Query Fails Before Migration
**What goes wrong:** First-run callback queries OnboardingState table that doesn't exist pre-migration
**Why it happens:** User runs `kestrel` before `alembic upgrade head`
**How to avoid:** Wrap the onboarding state query in a broad try/except. If it fails (table missing), assume fresh install and show the "run `kestrel init`" message. Doctor command should detect this case.
**Warning signs:** OperationalError "no such table: onboarding_state" on first invocation

## Code Examples

### Testing Interactive CLI Commands
```python
# Source: existing tests/test_cli.py pattern + CliRunner docs
from typer.testing import CliRunner
from unittest.mock import patch

runner = CliRunner()

def test_init_wizard_happy_path(db_session):
    """kestrel init collects answers and saves profile."""
    # Mock Prompt.ask to return predetermined answers
    answers = iter(["Alice", "Berlin", "Software Engineer", "80000-120000", "Python, TypeScript", "senior"])

    with patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)):
        with patch("career_os.cli.init.Confirm.ask", return_value=True):
            result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Profile saved" in result.output or "✓" in result.output
```
[VERIFIED: CliRunner supports `input=` param; mocking pattern standard for Rich prompt testing]

### Regex Extraction Patterns
```python
import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
URL_RE = re.compile(r"https?://[^\s<>\"']+")

def extract_from_text(text: str) -> dict:
    """Extract structured data from pasted resume text."""
    return {
        "emails": EMAIL_RE.findall(text),
        "phones": PHONE_RE.findall(text),
        "urls": URL_RE.findall(text),
    }
```
[ASSUMED: regex patterns cover common formats; edge cases will need iteration]

### Skill Extraction via ESCO + rapidfuzz
```python
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session
from career_os.models.esco import ESCOSkill

SKILL_MATCH_THRESHOLD = 80.0  # Lower than normalizer's 85 for broader recall

def extract_skills_from_text(text: str, db: Session, top_n: int = 10) -> list[str]:
    """Find skill mentions in text by fuzzy-matching against ESCO taxonomy."""
    # Split text into candidate tokens (2-4 word ngrams)
    words = text.split()
    candidates = set()
    for n in range(1, 4):
        for i in range(len(words) - n + 1):
            candidates.add(" ".join(words[i:i+n]))

    # Load ESCO labels
    all_skills = db.query(ESCOSkill.preferred_label).all()
    labels = [s.preferred_label for s in all_skills]

    # Match each candidate against taxonomy
    matched = set()
    for candidate in candidates:
        result = process.extractOne(candidate, labels, scorer=fuzz.WRatio, score_cutoff=SKILL_MATCH_THRESHOLD)
        if result:
            matched.add(result[0])

    return sorted(matched)[:top_n]
```
[VERIFIED: rapidfuzz API matches existing skill_normalizer.py usage; ESCO table has ~14K entries]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| questionary for CLI prompts | rich.prompt (built into Rich) | Rich 13+ | No extra dependency, consistent styling |
| click.prompt() | rich.prompt.Prompt.ask() | Typer 0.12+ | Rich styling, better defaults handling |
| Manual profile YAML editing | Interactive wizard | This phase | Non-developer accessible |

**Deprecated/outdated:**
- `questionary` library: Still works but adds unnecessary dependency when Rich has prompt built-in
- `InquirerPy`: Fork of python-inquirer, heavy; Rich.prompt covers all needed patterns

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Double-Enter is discoverable for non-developers | Patterns | May need explicit "press Enter twice" with visual cue |
| A2 | Mocking Prompt.ask() is cleaner than CliRunner input= for Rich | Testing | May need hybrid approach |
| A3 | ESCO skill matching on n-grams will perform acceptably for ~14K entries | Code Examples | Could be slow; may need caching or pre-filtering |
| A4 | Profile(id=1) won't exist on fresh install | Pitfall 3 | If migration creates it, code would be different |

## Open Questions (RESOLVED)

1. **Profile creation vs update on fresh install** — RESOLVED
   - What we know: `_get_default_profile()` assumes Profile(id=1) exists (errors if not)
   - What's unclear: Does any migration seed a default profile? Or does `kestrel init` need to CREATE it?
   - Recommendation: Init wizard should create Profile if none exists, matching Phase 1's assumption that first PATCH creates OnboardingState lazily
   - **Resolution:** Plan 03 Task 1 implements CREATE-if-not-exists: `profile = db.query(Profile).first()` — if None, creates `Profile(name="User")` and flushes. This matches the lazy-creation pattern from Phase 1.

2. **Rich Progress bar vs simple text indicator** — RESOLVED
   - What we know: D-05 says "Rich Progress bar for step indicator"
   - What's unclear: Should it be a persistent live-updating bar (which conflicts with Prompt.ask mid-step) or just a text update between steps?
   - Recommendation: Print a styled "Step 2/5" text between questions rather than a live Progress bar, since Progress context managers conflict with interactive prompts. Use Progress only for non-interactive steps (like skill matching).
   - **Resolution:** Plan 03 Task 1 uses styled text `"[bold blue]Step {i+1}/{TOTAL_STEPS}[/bold blue]"` between questions. Rich Progress context managers conflict with interactive Prompt.ask, so text-based indicator is correct per D-05 intent.

3. **How to handle `kestrel init` re-run when profile already complete** — RESOLVED
   - What we know: D-14 says resume from last incomplete step
   - What's unclear: What if ALL steps are complete? Re-run from scratch? Show "already complete" message?
   - Recommendation: If complete, show "Profile already set up. Run `kestrel init --force` to re-do." (or just re-run wizard with existing values as defaults)
   - **Resolution:** Plan 03 Task 1 implements: if `profile_completed_at` is set and `--force` not passed, print "Profile already set up. Use --force to redo." and exit. The `--force` flag re-runs the wizard with existing values as defaults.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_cli_init.py tests/test_cli_doctor.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | First-run message shown | unit | `pytest tests/test_cli_init.py::test_first_run_message -x` | Wave 0 |
| CLI-02 | Interactive wizard runs | unit | `pytest tests/test_cli_init.py::test_init_happy_path -x` | Wave 0 |
| CLI-03 | Non-TTY detection | unit | `pytest tests/test_cli_init.py::test_non_tty_exits -x` | Wave 0 |
| CLI-04 | --skip creates default | unit | `pytest tests/test_cli_init.py::test_init_skip -x` | Wave 0 |
| CLI-05 | Progress indicator | unit | `pytest tests/test_cli_init.py::test_step_indicator -x` | Wave 0 |
| CLI-06 | kestrel doctor | unit | `pytest tests/test_cli_doctor.py::test_doctor_all_pass -x` | Wave 0 |
| CLI-07 | Error formatting | unit | `pytest tests/test_cli_init.py::test_error_no_stacktrace -x` | Wave 0 |
| CLI-08 | Next-step suggestions | unit | `pytest tests/test_cli_init.py::test_next_step_suggestion -x` | Wave 0 |
| PROF-01 | 5-7 guided questions | unit | `pytest tests/test_cli_init.py::test_all_questions_asked -x` | Wave 0 |
| PROF-02 | Resume paste extraction | unit | `pytest tests/test_cli_init.py::test_resume_extraction -x` | Wave 0 |
| PROF-03 | Confirmation before save | unit | `pytest tests/test_cli_init.py::test_confirmation_shown -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_cli_init.py tests/test_cli_doctor.py -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before /gsd-verify-work

### Wave 0 Gaps
- [ ] `tests/test_cli_init.py` — covers CLI-01 through CLI-08, PROF-01 through PROF-03
- [ ] `tests/test_cli_doctor.py` — covers CLI-06
- [ ] `tests/test_resume_extraction.py` — covers PROF-02 regex + skill matching in isolation

## Project Constraints (from CLAUDE.md)

- Every piece of code must have unit tests (written alongside, not after)
- Python: Ruff lint + format (line-length=100, select E/F/I/UP/B/SIM)
- Conventional commit format: `feat(G-392): description`
- Commit after every logical unit of work
- Push after committing on non-main branches
- Direct DB access pattern: `_get_session()` + try/finally with `db.close()`
- Run tests after writing to confirm they pass

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/career_os/cli/main.py` — all CLI patterns verified
- Codebase inspection: `src/career_os/services/onboarding.py` — service layer API verified
- Codebase inspection: `src/career_os/services/skill_normalizer.py` — rapidfuzz usage verified
- pip show: Rich 15.0.0, Typer 0.24.1, rapidfuzz 3.14.5 installed

### Secondary (MEDIUM confidence)
- CliRunner `input=` parameter — confirmed via inspect.signature

### Tertiary (LOW confidence)
- Rich Prompt behavior in CliRunner piped stdin (A2) — needs empirical validation in tests

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed and used in codebase
- Architecture: HIGH — follows exact patterns from existing 2000+ line CLI
- Pitfalls: MEDIUM — testing interactive prompts is the main uncertainty

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (stable domain, no fast-moving dependencies)
