"""CLI command: kestrel init -- interactive profile setup wizard."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from sqlalchemy.orm import Session

from career_os.cli.extract import (
    extract_from_text,
    extract_skills_from_text,
    read_multiline_paste,
)
from career_os.database import SessionLocal
from career_os.errors.onboarding import OnboardingError
from career_os.models.models import Profile
from career_os.models.skills import Skill
from career_os.services.onboarding import get_onboarding_status, mark_step_complete

console = Console()


def _get_session() -> Session:
    """Get a database session. Patched in tests."""
    return SessionLocal()


WIZARD_STEPS = [
    ("name", "Your name", None),
    ("location", "Your location [dim](city, country)[/dim]", None),
    (
        "job_family",
        "Target role or job family [dim](e.g. Software Engineer, Marketing Manager)[/dim]",
        None,
    ),
    ("salary_range", "Desired salary range [dim](e.g. 80000-120000)[/dim]", None),
    (
        "experience_level",
        "Experience level [dim](junior/mid/senior/lead)[/dim]",
        None,
    ),
]
TOTAL_STEPS = len(WIZARD_STEPS)  # 5

DISPLAY_NAMES = {
    "name": "Name",
    "location": "Location",
    "job_family": "Job Family",
    "salary_range": "Salary Range",
    "experience_level": "Experience Level",
}


def init(
    skip: bool = typer.Option(False, "--skip", help="Create a default profile immediately"),
    force: bool = typer.Option(False, "--force", help="Re-run init even if profile already set up"),
) -> None:
    """Interactive profile setup wizard.

    Walks through 5 skippable profile questions with progress indicators,
    optionally extracts data from pasted resume text, shows a summary table,
    confirms before saving, and marks onboarding state.
    """
    # CLI-03: Non-TTY detection
    if not sys.stdin.isatty():
        console.print(
            Panel(
                "[bold]Non-interactive environment detected.[/bold]\n\n"
                "Run with [bold cyan]kestrel init --skip[/bold cyan] to create a "
                "default profile,\nor use a terminal that supports interactive input.",
                title="Cannot run wizard",
                border_style="yellow",
            )
        )
        raise typer.Exit(0)

    db = _get_session()
    try:
        # CLI-04: --skip creates a default profile immediately
        if skip:
            profile = db.query(Profile).first()
            if profile is None:
                profile = Profile(name="Kestrel User")
                db.add(profile)
                db.flush()
            mark_step_complete(step="profile_started", via="cli", profile_id=profile.id, db=db)
            mark_step_complete(step="profile_completed", via="cli", profile_id=profile.id, db=db)
            console.print(
                "[green]check[/green] Default profile created. You can re-run "
                "[bold]kestrel init[/bold] later to fill in details."
            )
            return

        # D-14: Resume detection — skip if already completed (unless --force)
        resuming = False
        try:
            status = get_onboarding_status(profile_id=1, db=db)
            if status.profile_completed_at is not None and not force:
                console.print(
                    "[yellow]Profile already set up.[/yellow] "
                    "Use [bold]kestrel init --force[/bold] to redo."
                )
                raise typer.Exit(0)
            # D-14: Detect partially completed wizard (started but not finished)
            if status.profile_started_at and not status.profile_completed_at:
                resuming = True
        except typer.Exit:
            raise  # Re-raise Exit so it is not swallowed by the broad handler
        except Exception:
            pass  # No state yet — proceed with wizard

        # D-03: Welcome Panel
        console.print(
            Panel(
                "[bold]Kestrel[/bold]\nLet's set up your profile.",
                border_style="blue",
            )
        )

        # D-14: Welcome back message for resuming users
        if resuming:
            console.print("[dim]Welcome back! Resuming where you left off.[/dim]\n")

        # D-08: Skip tip
        console.print(
            "[dim]Tip: Press Enter to skip any question. You can re-run kestrel init later.[/dim]\n"
        )

        # Get or create Profile
        profile = db.query(Profile).first()
        if profile is None:
            profile = Profile(name="User")
            db.add(profile)
            db.flush()

        # Mark profile_started
        mark_step_complete(step="profile_started", via="cli", profile_id=profile.id, db=db)

        # CLI-05: Walk through wizard steps with step counter
        # D-14: Pre-populate defaults from existing profile when resuming
        answers: dict[str, str] = {}
        for i, (field_name, label, _default) in enumerate(WIZARD_STEPS):
            console.print(f"[bold blue]Step {i + 1}/{TOTAL_STEPS}[/bold blue]")
            existing_value = getattr(profile, field_name, None) or ""
            default = existing_value if resuming and existing_value else ""
            answer = Prompt.ask(label, default=default, console=console)
            if answer.strip():
                answers[field_name] = answer.strip()

        # D-16/PROF-02: Optional resume paste step
        extracted_skills: list[str] = []
        console.print("")  # spacing
        if Confirm.ask(
            "Want to paste resume text to auto-fill remaining fields?",
            default=False,
            console=console,
        ):
            # D-08: Paste tip
            console.print(
                "[dim]Tip: Right-click or Ctrl+V to paste. Press Enter twice when done.[/dim]"
            )
            text = read_multiline_paste(console)
            if text:
                extracted = extract_from_text(text)
                skills = extract_skills_from_text(text, db=db, top_n=10)

                # D-18: Show what was found for user review
                if extracted["emails"] or extracted["phones"] or extracted["urls"] or skills:
                    console.print("\n[bold]Found in your resume:[/bold]")
                    if extracted["emails"]:
                        console.print(f"  Email: {extracted['emails'][0]}")
                    if extracted["phones"]:
                        console.print(f"  Phone: {extracted['phones'][0]}")
                    if extracted["urls"]:
                        for url in extracted["urls"][:3]:
                            console.print(f"  URL: {url}")
                    if skills:
                        console.print(f"  Skills: {', '.join(skills[:10])}")
                    console.print("")

                    # Merge extracted data (don't overwrite user-provided answers)
                    if not answers.get("email") and extracted["emails"]:
                        answers["email"] = extracted["emails"][0]
                    extracted_skills = skills
                else:
                    console.print("[dim]No structured data found in pasted text.[/dim]")
            else:
                console.print("[dim]No text received.[/dim]")

        # D-04/PROF-03: Summary table
        table = Table(title="Profile Summary")
        table.add_column("Field", style="bold")
        table.add_column("Value")

        for field_name, _label, _default in WIZARD_STEPS:
            value = (
                answers.get(field_name)
                or getattr(profile, field_name, None)
                or "[dim]skipped[/dim]"
            )
            table.add_row(DISPLAY_NAMES.get(field_name, field_name), str(value))

        # Show extracted skills in summary if any
        if extracted_skills:
            table.add_row("Skills (from resume)", ", ".join(extracted_skills[:10]))

        console.print(table)

        # PROF-03: Confirm before save
        if not Confirm.ask("Save this profile?", default=True, console=console):
            console.print("Cancelled.")
            raise typer.Exit(0)

        # Save to Profile
        for field_name, value in answers.items():
            setattr(profile, field_name, value)
        db.commit()

        # Save extracted skills to Skill model
        if extracted_skills:
            skills_added = 0
            for skill_name in extracted_skills:
                existing = (
                    db.query(Skill)
                    .filter(
                        Skill.profile_id == profile.id,
                        Skill.name == skill_name,
                    )
                    .first()
                )
                if not existing:
                    db.add(
                        Skill(
                            profile_id=profile.id,
                            name=skill_name,
                            category="technical",  # default; normalizer refines later
                            evidence_source="resume_paste",
                        )
                    )
                    skills_added += 1
            db.commit()
            if skills_added:
                console.print(f"[green]check[/green] Added {skills_added} skills to your profile.")

        # Mark profile_completed
        mark_step_complete(step="profile_completed", via="cli", profile_id=profile.id, db=db)

        # D-12/CLI-08: Success + next step suggestion
        console.print("[green]check[/green] Profile saved!")
        console.print(
            "\n[bold]Next:[/bold] Try [bold]kestrel pipeline list[/bold] to see your job matches."
        )
        # D-08: Re-run tip
        console.print("[dim]Tip: Run kestrel init again anytime to update your profile.[/dim]")

    except OnboardingError as exc:
        console.print(f"[red]Error:[/red] {exc.user_message}")
        console.print(f"[dim]{exc.resolution}[/dim]")
        raise typer.Exit(1) from exc
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Unexpected error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        db.close()
