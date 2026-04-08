"""Career OS CLI — main entry point."""

from __future__ import annotations

import asyncio
import json as json_mod
import re
from datetime import UTC, datetime

import typer
import typer.core as typer_core
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy.orm import Session

from career_os.database import SessionLocal
from career_os.models.models import (
    ActivityLog,
    Application,
    FollowUp,
    Profile,
)
from career_os.schemas.applications import ApplicationStatus, is_valid_transition

console = Console()

app = typer.Typer(
    name="career",
    help="Career OS — AI-Powered Job Search & Career Strategy Platform",
    no_args_is_help=True,
)

# Pipeline subcommand group
pipeline_app = typer.Typer(
    name="pipeline",
    help="Manage your job application pipeline.",
    no_args_is_help=True,
)
app.add_typer(pipeline_app, name="pipeline")

# Skills subcommand group
skills_app = typer.Typer(
    name="skills",
    help="Manage your skills inventory and gap analysis.",
    no_args_is_help=True,
)
app.add_typer(skills_app, name="skills")

# Goals subcommand group
goals_app = typer.Typer(
    name="goals",
    help="Track your career goals and progress.",
    invoke_without_command=True,
)
app.add_typer(goals_app, name="goals")

# Interview-prep subcommand group (uses Click Group to handle both
# `career interview-prep <id>` and `career interview-prep stories <subcmd>`)


class InterviewPrepGroup(typer_core.TyperGroup):
    """Custom Typer group that dispatches numeric args as application IDs."""

    def parse_args(self, ctx, args: list[str]) -> list[str]:
        """If first arg is a number, treat as 'generate <id>'."""
        if args and args[0].isdigit():
            args = ["generate"] + args
        return super().parse_args(ctx, args)


interview_prep_app = typer.Typer(
    name="interview-prep",
    cls=InterviewPrepGroup,
    help="Interview preparation: topics, questions, checklist, and STAR stories.",
    no_args_is_help=True,
)
app.add_typer(interview_prep_app, name="interview-prep")

# Stories sub-subcommand group under interview-prep
stories_app = typer.Typer(
    name="stories",
    help="Manage STAR stories for interview preparation.",
    invoke_without_command=True,
)
interview_prep_app.add_typer(stories_app, name="stories")

# Contacts subcommand group (M6)
from career_os.cli.contacts import contacts_app  # noqa: E402

app.add_typer(contacts_app, name="contacts")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_session() -> Session:
    """Get a database session. Patched in tests to use in-memory DB."""
    return SessionLocal()


def _get_default_profile(db: Session) -> Profile:
    """Get the default profile (id=1). Raise if missing."""
    profile = db.query(Profile).filter(Profile.id == 1).first()
    if profile is None:
        console.print("[red]Error:[/red] No default profile found. Run the migration first.")
        raise typer.Exit(code=1)
    return profile


# ---------------------------------------------------------------------------
# career pipeline list
# ---------------------------------------------------------------------------


@pipeline_app.command("list")
def pipeline_list(
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
) -> None:
    """List all applications in the pipeline."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)
        query = db.query(Application).filter(
            Application.profile_id == profile.id,
            Application.archived_at.is_(None),
        )

        if status:
            query = query.filter(Application.status.ilike(status))

        # Newest first
        query = query.order_by(Application.created_at.desc())
        applications = query.all()

        if not applications:
            if status:
                console.print(f"[yellow]No matching applications with status '{status}'.[/yellow]")
            else:
                console.print("[yellow]No applications in the pipeline yet.[/yellow]")
            return

        table = Table(title="Pipeline Applications")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Company", style="bold")
        table.add_column("Role")
        table.add_column("Status")
        table.add_column("Score", justify="right")
        table.add_column("Date")

        for app_obj in applications:
            score_str = f"{app_obj.fit_score:.1f}" if app_obj.fit_score is not None else "—"
            created = app_obj.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            date_str = created.strftime("%Y-%m-%d") if created else "—"

            table.add_row(
                str(app_obj.id),
                app_obj.company,
                app_obj.role,
                app_obj.status,
                score_str,
                date_str,
            )

        console.print(table)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# career pipeline add
# ---------------------------------------------------------------------------


@pipeline_app.command("add")
def pipeline_add(
    company: str = typer.Option(..., "--company", "-c", help="Company name"),
    role: str = typer.Option(..., "--role", "-r", help="Role title"),
    url: str = typer.Option("", "--url", "-u", help="Job posting URL"),
    source: str = typer.Option("manual", "--source", help="Source of the job posting"),
) -> None:
    """Add a new application to the pipeline."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)

        app_obj = Application(
            profile_id=profile.id,
            company=company,
            role=role,
            url=url if url else None,
            source=source,
            status="discovered",
        )
        db.add(app_obj)
        db.flush()

        # Activity log
        log = ActivityLog(
            profile_id=profile.id,
            application_id=app_obj.id,
            action="created",
            details=f"Created application for {company} — {role}",
            source="cli",
        )
        db.add(log)
        db.commit()
        db.refresh(app_obj)

        console.print(
            f"[green]✓[/green] Added application [bold]#{app_obj.id}[/bold]: "
            f"{company} — {role} (status: discovered)"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# career pipeline update
# ---------------------------------------------------------------------------


@pipeline_app.command("update")
def pipeline_update(
    app_id: int = typer.Argument(..., help="Application ID"),
    status: str | None = typer.Option(None, "--status", "-s", help="New status"),
    notes: str | None = typer.Option(None, "--notes", "-n", help="Update notes"),
) -> None:
    """Update an existing application."""
    if status is None and notes is None:
        console.print("[red]Error:[/red] Provide at least --status or --notes.")
        raise typer.Exit(code=1)

    db = _get_session()
    try:
        profile = _get_default_profile(db)
        app_obj = (
            db.query(Application)
            .filter(
                Application.id == app_id,
                Application.profile_id == profile.id,
                Application.archived_at.is_(None),
            )
            .first()
        )
        if app_obj is None:
            console.print(f"[red]Error:[/red] Application {app_id} not found.")
            raise typer.Exit(code=1)

        changed = []

        if status:
            # Validate status value
            try:
                ApplicationStatus(status.lower())
            except ValueError:
                valid = ", ".join(s.value for s in ApplicationStatus)
                console.print(
                    f"[red]Error:[/red] Invalid status '{status}'. Valid statuses: {valid}"
                )
                raise typer.Exit(code=1) from None

            old_status = app_obj.status.lower()
            new_status = status.lower()

            if old_status != new_status:
                if not is_valid_transition(old_status, new_status):
                    console.print(
                        f"[red]Error:[/red] Cannot transition from "
                        f"'{old_status}' to '{new_status}'."
                    )
                    raise typer.Exit(code=1)

                app_obj.status = new_status
                changed.append(f"status → {new_status}")

                # Log status change
                log = ActivityLog(
                    profile_id=app_obj.profile_id,
                    application_id=app_obj.id,
                    action="status_changed",
                    details=f"Status changed from '{old_status}' to '{new_status}'",
                    source="cli",
                )
                db.add(log)

                # Set date_applied if transitioning to applied
                if new_status == "applied" and app_obj.date_applied is None:
                    app_obj.date_applied = datetime.now(UTC)

        if notes is not None:
            app_obj.notes = notes
            changed.append("notes")

            log = ActivityLog(
                profile_id=app_obj.profile_id,
                application_id=app_obj.id,
                action="updated",
                details="Updated fields: notes",
                source="cli",
            )
            db.add(log)

        db.commit()
        db.refresh(app_obj)

        changes_str = ", ".join(changed) if changed else "notes"
        console.print(
            f"[green]✓[/green] Updated application [bold]#{app_id}[/bold] "
            f"({app_obj.company}): {changes_str}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# career pipeline stats
# ---------------------------------------------------------------------------


@pipeline_app.command("stats")
def pipeline_stats() -> None:
    """Show pipeline statistics."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)

        applications = (
            db.query(Application)
            .filter(
                Application.profile_id == profile.id,
                Application.archived_at.is_(None),
            )
            .all()
        )

        total = len(applications)

        # Per-status counts
        status_counts: dict[str, int] = {}
        scores: list[float] = []
        company_counts: dict[str, int] = {}

        for app_obj in applications:
            s = app_obj.status.lower()
            status_counts[s] = status_counts.get(s, 0) + 1

            if app_obj.fit_score is not None:
                scores.append(app_obj.fit_score)

            company_counts[app_obj.company] = company_counts.get(app_obj.company, 0) + 1

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        # Top companies by count (top 5)
        top_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Date range
        dates = [a.created_at for a in applications if a.created_at is not None]
        if dates:
            earliest = min(dates)
            latest = max(dates)
            if earliest.tzinfo is None:
                earliest = earliest.replace(tzinfo=UTC)
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=UTC)
            date_range = f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}"
        else:
            date_range = "—"

        console.print()
        console.print("[bold]Pipeline Statistics[/bold]")
        console.print(f"  Total applications: {total}")
        console.print(f"  Average fit score:  {avg_score}")
        console.print(f"  Date range:         {date_range}")
        console.print()

        # Status breakdown
        console.print("[bold]Status Breakdown[/bold]")
        for s in ApplicationStatus:
            count = status_counts.get(s.value, 0)
            if count > 0:
                console.print(f"  {s.value:<15} {count}")

        console.print()

        # Top companies
        console.print("[bold]Top Companies[/bold]")
        if top_companies:
            for company, count in top_companies:
                console.print(f"  {company:<25} {count} application(s)")
        else:
            console.print("  —")

        console.print()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# career pipeline follow-ups
# ---------------------------------------------------------------------------


@pipeline_app.command("follow-ups")
def pipeline_follow_ups() -> None:
    """List due and overdue follow-ups."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)
        now = datetime.now(UTC)

        # Get only due/overdue incomplete follow-ups (due_date <= now)
        follow_ups = (
            db.query(FollowUp)
            .join(Application)
            .filter(
                FollowUp.profile_id == profile.id,
                FollowUp.completed_at.is_(None),
                FollowUp.due_date <= now,
            )
            .order_by(FollowUp.due_date.asc())
            .all()
        )

        if not follow_ups:
            console.print("[green]🎉 You're all caught up! No pending follow-ups.[/green]")
            return

        table = Table(title="Follow-Ups")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Company", style="bold")
        table.add_column("Role")
        table.add_column("Type")
        table.add_column("Due Date")
        table.add_column("Status")
        table.add_column("Notes")

        for fu in follow_ups:
            app_obj = fu.application
            due = fu.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)

            days_diff = (due - now).days
            if days_diff < 0:
                status_str = f"[red]🔴 {abs(days_diff)}d overdue[/red]"
            else:
                status_str = "[yellow]⚠️ Due today[/yellow]"

            table.add_row(
                str(fu.id),
                app_obj.company if app_obj else "—",
                app_obj.role if app_obj else "—",
                fu.follow_up_type,
                due.strftime("%Y-%m-%d"),
                status_str,
                fu.notes or "—",
            )

        console.print(table)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# career skills list
# ---------------------------------------------------------------------------


@skills_app.command("list")
def skills_list(
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (technical/domain/soft/tools)",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Filter by evidence source",
    ),
) -> None:
    """List all skills in the inventory."""
    from career_os.services.skills import list_skills

    db = _get_session()
    try:
        profile = _get_default_profile(db)
        skills, total = list_skills(
            db,
            profile.id,
            category=category,
            source=source,
            page_size=500,
        )

        if not skills:
            if category or source:
                console.print("[yellow]No matching skills found with the given filters.[/yellow]")
            else:
                console.print(
                    "[yellow]No skills in the inventory yet. "
                    "Import from CV or add manually.[/yellow]"
                )
            return

        table = Table(title="Skills Inventory")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Name", style="bold")
        table.add_column("Category")
        table.add_column("Proficiency")
        table.add_column("Source")

        for skill in skills:
            table.add_row(
                str(skill.id),
                skill.name,
                skill.category,
                skill.proficiency,
                skill.evidence_source,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {total} skill(s)[/dim]")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# career skills gaps
# ---------------------------------------------------------------------------


@skills_app.command("gaps")
def skills_gaps(
    application: int | None = typer.Option(
        None,
        "--application",
        "-a",
        help="Application ID for per-job gap report",
    ),
    aggregate: bool = typer.Option(
        False,
        "--aggregate",
        help="Show cross-application gap summary",
    ),
    severity: str | None = typer.Option(
        None,
        "--severity",
        help="Filter gaps by severity (critical/nice-to-have/bonus)",
    ),
) -> None:
    """Show skill gaps for an application or aggregate across all applications."""
    from career_os.services.gap_analysis import (
        ApplicationNotFoundError,
        MissingRequirementsError,
        aggregate_gaps,
        analyze_gaps,
    )

    if not application and not aggregate:
        console.print("[red]Error:[/red] Provide --application <id> or --aggregate.")
        raise typer.Exit(code=1)

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        if aggregate:
            _show_aggregate_gaps(db, profile.id, aggregate_gaps)
        else:
            _show_application_gaps(
                db,
                profile.id,
                application,
                severity,
                analyze_gaps,
                ApplicationNotFoundError,
                MissingRequirementsError,
            )
    finally:
        db.close()


def _show_application_gaps(
    db: Session,
    profile_id: int,
    application_id: int,
    severity_filter: str | None,
    analyze_fn,
    not_found_err,
    missing_reqs_err,
) -> None:
    """Display gap report for a specific application."""
    try:
        result = analyze_fn(db, application_id, profile_id)
    except not_found_err:
        console.print(f"[red]Error:[/red] Application {application_id} not found.")
        raise typer.Exit(code=1) from None
    except missing_reqs_err:
        console.print(
            f"[red]Error:[/red] Job requirements not yet parsed for application {application_id}."
        )
        raise typer.Exit(code=1) from None

    console.print(f"\n[bold]Gap Analysis: {result['company']} — {result['role']}[/bold]")

    score = result["readiness_score"]
    if score >= 80:
        score_style = "green"
    elif score >= 50:
        score_style = "yellow"
    else:
        score_style = "red"
    console.print(f"Readiness Score: [{score_style}]{score:.1f}%[/{score_style}]")
    console.print(
        f"Total requirements: {result['total_requirements']}, Gaps: {result['gaps_count']}\n"
    )

    gaps = result["gaps"]
    if severity_filter:
        gaps = [g for g in gaps if g["severity"] == severity_filter]

    if not gaps:
        console.print("[green]✓ No gaps found (or all filtered out).[/green]")
        return

    table = Table(title="Skill Gaps")
    table.add_column("Skill", style="bold")
    table.add_column("Required")
    table.add_column("Current")
    table.add_column("Severity")
    table.add_column("Distance", justify="right")

    for gap in gaps:
        current = gap["current_level"] or "[dim]missing[/dim]"
        sev = gap["severity"]
        if sev == "critical":
            sev_str = f"[red]{sev}[/red]"
        elif sev == "nice-to-have":
            sev_str = f"[yellow]{sev}[/yellow]"
        else:
            sev_str = f"[dim]{sev}[/dim]"

        dist = gap["distance"]
        if dist >= 3:
            dist_str = f"[red]{dist}[/red]"
        elif dist >= 2:
            dist_str = f"[yellow]{dist}[/yellow]"
        else:
            dist_str = str(dist)

        table.add_row(
            gap["skill_name"],
            gap["required_level"],
            current,
            sev_str,
            dist_str,
        )

    console.print(table)


def _show_aggregate_gaps(db: Session, profile_id: int, aggregate_fn) -> None:
    """Display cross-application gap summary."""
    result = aggregate_fn(db, profile_id)

    if not result["gaps"]:
        console.print(
            "[yellow]No gaps found across applications. "
            "Either no applications have parsed requirements, "
            "or your skills cover all requirements.[/yellow]"
        )
        return

    console.print(
        f"\n[bold]Aggregate Gap Analysis[/bold] "
        f"({result['total_applications_analyzed']} application(s) analyzed)\n"
    )

    table = Table(title="Cross-Application Gaps (ranked by frequency)")
    table.add_column("Skill", style="bold")
    table.add_column("Frequency", justify="right")
    table.add_column("Avg Severity")
    table.add_column("Avg Distance", justify="right")
    table.add_column("Applications")

    for gap in result["gaps"]:
        freq = gap["frequency"]
        sev = gap["avg_severity"]
        if sev == "critical":
            sev_str = f"[red]{sev}[/red]"
        elif sev == "nice-to-have":
            sev_str = f"[yellow]{sev}[/yellow]"
        else:
            sev_str = f"[dim]{sev}[/dim]"

        app_ids = ", ".join(str(i) for i in gap["application_ids"])

        table.add_row(
            gap["skill_name"],
            str(freq),
            sev_str,
            f"{gap['avg_distance']:.1f}",
            app_ids,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# career goals (list + show)
# ---------------------------------------------------------------------------


@goals_app.callback(invoke_without_command=True)
def goals_list(ctx: typer.Context) -> None:
    """List all career goals with progress."""
    if ctx.invoked_subcommand is not None:
        return

    from career_os.services.goals import get_progress, list_goals

    db = _get_session()
    try:
        profile = _get_default_profile(db)
        goals, total = list_goals(db, profile.id, status="active")

        if not goals:
            console.print(
                "[yellow]No career goals defined yet. Create goals via the web UI or API.[/yellow]"
            )
            return

        table = Table(title="Career Goals")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Title", style="bold")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Target Date")
        table.add_column("Progress", justify="right")

        for goal in goals:
            # Get progress for each goal
            try:
                progress_data = get_progress(db, goal.id, profile.id)
                progress_pct = progress_data["overall_progress"]
                progress_str = f"{progress_pct:.1f}%"
            except Exception:
                progress_str = "—"

            target = goal.target_date
            if target:
                if target.tzinfo is None:
                    target = target.replace(tzinfo=UTC)
                target_str = target.strftime("%Y-%m-%d")
            else:
                target_str = "—"

            status = goal.status
            if status == "completed":
                status_str = f"[green]{status}[/green]"
            elif status == "paused":
                status_str = f"[yellow]{status}[/yellow]"
            elif status == "abandoned":
                status_str = f"[dim]{status}[/dim]"
            else:
                status_str = status

            table.add_row(
                str(goal.id),
                goal.title,
                goal.goal_type,
                status_str,
                target_str,
                progress_str,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {total} goal(s)[/dim]")
    finally:
        db.close()


@goals_app.command("show")
def goals_show(
    goal_id: int = typer.Argument(..., help="Goal ID to show reality map for"),
) -> None:
    """Show reality map for a specific career goal."""
    from career_os.services.goals import GoalNotFoundError, get_reality_map

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        try:
            result = get_reality_map(db, goal_id, profile.id)
        except GoalNotFoundError:
            console.print(f"[red]Error:[/red] Goal {goal_id} not found.")
            raise typer.Exit(code=1) from None

        console.print(f"\n[bold]Reality Map: {result['title']}[/bold]")
        console.print(f"Type: {result['goal_type']}")

        overall = result["overall_progress"]
        if overall >= 80:
            progress_style = "green"
        elif overall >= 50:
            progress_style = "yellow"
        else:
            progress_style = "red"
        console.print(f"Overall Progress: [{progress_style}]{overall:.1f}%[/{progress_style}]\n")

        for dim in result["dimensions"]:
            pct = dim["progress_pct"]
            if pct >= 80:
                pct_style = "green"
            elif pct >= 50:
                pct_style = "yellow"
            else:
                pct_style = "red"

            content = (
                f"Current: {dim['current_state']}\n"
                f"Required: {dim['required_state']}\n"
                f"Delta: {dim['delta']}\n"
                f"Progress: [{pct_style}]{pct:.1f}%[/{pct_style}]"
            )
            console.print(Panel(content, title=f"[bold]{dim['dimension'].title()}[/bold]"))

    finally:
        db.close()


# ---------------------------------------------------------------------------
# career coach
# ---------------------------------------------------------------------------


@app.command("coach")
def coach() -> None:
    """Get top coaching suggestions with effort estimates."""
    from career_os.services.coaching import get_coaching_suggestions

    db = _get_session()
    try:
        profile = _get_default_profile(db)
        result = get_coaching_suggestions(db, profile.id)

        suggestions = result["suggestions"]
        focus_area = result.get("focus_area")

        if not suggestions:
            console.print(
                "[green]🎉 No coaching suggestions right now. "
                "Add applications, skills, and goals to get personalized advice.[/green]"
            )
            return

        if focus_area:
            console.print(f"\n[bold]Focus Area:[/bold] {focus_area}\n")

        # Show top 5 suggestions
        top_suggestions = suggestions[:5]

        table = Table(title="Top Coaching Suggestions")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Action", style="bold", max_width=60)
        table.add_column("Hours", justify="right")
        table.add_column("Weeks", justify="right")
        table.add_column("Difficulty")

        for i, cs in enumerate(top_suggestions, start=1):
            hours_str = f"{cs.hours:.0f}h" if cs.hours else "—"
            weeks_str = f"{cs.weeks:.1f}w" if cs.weeks else "—"
            difficulty = cs.difficulty or "—"

            if difficulty == "high":
                diff_str = f"[red]{difficulty}[/red]"
            elif difficulty == "medium":
                diff_str = f"[yellow]{difficulty}[/yellow]"
            else:
                diff_str = f"[green]{difficulty}[/green]"

            table.add_row(
                str(i),
                cs.action,
                hours_str,
                weeks_str,
                diff_str,
            )

        console.print(table)
        top_count = len(top_suggestions)
        total_count = result["total"]
        console.print(f"\n[dim]Showing top {top_count} of {total_count} suggestion(s)[/dim]")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async helpers for discovery & scoring (CLI runs sync, services are async)
# ---------------------------------------------------------------------------


def _run_discovery_async(
    db: Session,
    profile_id: int,
    *,
    keywords: list[str] | None = None,
    locations: list[str] | None = None,
    trigger: str = "cli",
) -> dict:
    """Run async discovery from a sync context. Patched in tests."""
    from career_os.services.discovery import run_discovery

    return asyncio.run(
        run_discovery(
            db,
            profile_id,
            keywords=keywords,
            locations=locations,
            trigger=trigger,
        )
    )


def _run_score_async(
    db: Session,
    profile_id: int,
    job_description: str,
    *,
    job_url: str | None = None,
):
    """Run async scoring from a sync context. Patched in tests."""
    from career_os.services.scoring import score_job

    return asyncio.run(
        score_job(
            db,
            profile_id,
            job_description,
            job_url=job_url,
        )
    )


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"^https?://"  # scheme
    r"[^\s/$.?#]"  # at least one non-special char
    r"[^\s]*$",  # rest
    re.IGNORECASE,
)


def _is_valid_url(url: str) -> bool:
    """Check if a string looks like a valid HTTP/HTTPS URL."""
    return bool(_URL_RE.match(url.strip()))


# ---------------------------------------------------------------------------
# career discover
# ---------------------------------------------------------------------------


@app.command("discover")
def discover(
    keywords: str | None = typer.Option(
        None,
        "--keywords",
        "-k",
        help="Search keywords (comma-separated)",
    ),
    location: str | None = typer.Option(
        None,
        "--location",
        "-l",
        help="Location to search",
    ),
    schedule: str | None = typer.Option(
        None,
        "--schedule",
        help="Configure scheduled runs (e.g. 'weekly')",
    ),
    output: str = typer.Option(
        "table",
        "--output",
        "-o",
        help="Output format: table or json",
    ),
) -> None:
    """Run a job discovery sweep or configure scheduled runs."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)

        # Parse keywords
        kw_list: list[str] | None = None
        if keywords:
            kw_list = [k.strip() for k in keywords.split(",") if k.strip()]

        loc_list: list[str] | None = None
        if location:
            loc_list = [location.strip()]

        # Handle --schedule: create/update search profile instead of running
        if schedule:
            _handle_schedule(db, profile.id, schedule, kw_list, loc_list, output)
            return

        # Run the discovery sweep
        try:
            result = _run_discovery_async(
                db,
                profile.id,
                keywords=kw_list,
                locations=loc_list,
                trigger="cli",
            )
        except Exception as exc:
            console.print(f"[red]Error:[/red] Discovery failed: {exc}")
            raise typer.Exit(code=1) from None

        # Fetch all discovered jobs for this profile, ranked by score
        from career_os.models.discovery import DiscoveredJob

        jobs = (
            db.query(DiscoveredJob)
            .filter(DiscoveredJob.profile_id == profile.id)
            .order_by(DiscoveredJob.fit_score.desc().nullslast())
            .all()
        )

        if output == "json":
            _discover_output_json(jobs, result)
            return

        # Show sweep summary (table mode only)
        console.print(
            f"\n[bold]Discovery Sweep Complete[/bold]\n"
            f"  Sources queried: {', '.join(result.get('sources_queried', [])) or '—'}\n"
            f"  Total found:     {result['total_found']}\n"
            f"  New jobs:        {result['new_jobs']}\n"
            f"  Duplicates:      {result['duplicates']}"
        )

        if result.get("warnings"):
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in result["warnings"]:
                console.print(f"  ⚠ {w['source']}: {w['error']}")

        if not jobs:
            console.print("\n[yellow]No discovered jobs to display.[/yellow]")
            return

        _discover_output_table(jobs)

    finally:
        db.close()


def _discover_output_table(jobs) -> None:
    """Print discovered jobs as a Rich table."""
    table = Table(title="Discovered Jobs (ranked by score)")
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Company")
    table.add_column("Score", justify="right")
    table.add_column("Source")
    table.add_column("Salary")

    for job in jobs:
        score_str = f"{job.fit_score:.1f}" if job.fit_score is not None else "—"
        sources = json_mod.loads(job.sources) if job.sources else []
        source_str = ", ".join(sources) if sources else "—"
        salary_str = job.salary_range or "—"

        table.add_row(
            str(job.id),
            job.title,
            job.company,
            score_str,
            source_str,
            salary_str,
        )

    console.print()
    console.print(table)


def _discover_output_json(jobs, sweep_result: dict) -> None:
    """Print discovered jobs as JSON."""
    data = {
        "sweep": {
            "run_id": sweep_result["run_id"],
            "total_found": sweep_result["total_found"],
            "new_jobs": sweep_result["new_jobs"],
            "duplicates": sweep_result["duplicates"],
            "sources_queried": sweep_result.get("sources_queried", []),
        },
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "url": j.url,
                "fit_score": j.fit_score,
                "salary_range": j.salary_range,
                "remote": j.remote,
                "sources": json_mod.loads(j.sources) if j.sources else [],
                "posted_at": j.posted_at.isoformat() if j.posted_at else None,
            }
            for j in jobs
        ],
    }
    # Print raw JSON (no Rich formatting for parseable output)
    typer.echo(json_mod.dumps(data, indent=2))


def _handle_schedule(
    db: Session,
    profile_id: int,
    schedule: str,
    keywords: list[str] | None,
    locations: list[str] | None,
    output: str,
) -> None:
    """Create or update a scheduled search profile."""
    from datetime import timedelta

    from career_os.services.discovery import create_search_profile

    if schedule.lower() not in ("weekly", "daily"):
        console.print(
            f"[red]Error:[/red] Unsupported schedule '{schedule}'. Use 'weekly' or 'daily'."
        )
        raise typer.Exit(code=1)

    cadence = schedule.lower()
    # Compute next_run based on cadence
    now = datetime.now(UTC)
    next_run = now + timedelta(days=1) if cadence == "daily" else now + timedelta(weeks=1)

    name = f"CLI scheduled ({schedule})"
    if keywords:
        name += f" — {', '.join(keywords)}"

    sp = create_search_profile(
        db,
        profile_id,
        {
            "name": name,
            "keywords": keywords or [],
            "locations": locations or [],
            "remote_only": False,
            "sources": [],
            "cadence": cadence,
            "next_run": next_run,
        },
    )

    next_run_str = next_run.strftime("%Y-%m-%d %H:%M UTC")
    if output == "json":
        data = {
            "id": sp.id,
            "name": sp.name,
            "schedule": cadence,
            "cadence": cadence,
            "is_active": sp.is_active,
            "next_run": next_run.isoformat(),
        }
        typer.echo(json_mod.dumps(data, indent=2))
    else:
        console.print(
            f"\n[green]✓[/green] Scheduled {cadence} discovery "
            f"(profile #{sp.id}: [bold]{sp.name}[/bold])\n"
            f"  Keywords:  {', '.join(keywords) if keywords else '—'}\n"
            f"  Locations: {', '.join(locations) if locations else '—'}\n"
            f"  Status:    [green]Active[/green]\n"
            f"  Next run:  {next_run_str}"
        )


# ---------------------------------------------------------------------------
# career score <url>
# ---------------------------------------------------------------------------


def _fetch_url_content(url: str) -> str | None:
    """Fetch URL content and extract text. Returns None on failure."""
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CareerOS/1.0)",
                "Accept": "text/html,application/xhtml+xml,text/plain",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(500_000)  # Limit to 500KB
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            text = raw.decode(charset, errors="replace")

            # Strip HTML tags for a rough text extraction
            if "html" in content_type.lower() or text.strip().startswith("<"):
                _flags = re.DOTALL | re.IGNORECASE
                text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=_flags)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=_flags)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()

            return text[:10_000] if text else None  # Limit to 10k chars
    except Exception:
        return None


@app.command("score")
def score(
    url: str = typer.Argument(..., help="Job posting URL to score"),
    output: str = typer.Option(
        "table",
        "--output",
        "-o",
        help="Output format: table or json",
    ),
) -> None:
    """Score a single job posting against your profile."""
    # Validate URL
    if not url or not _is_valid_url(url):
        console.print(
            f"[red]Error:[/red] Invalid URL '{url}'. Provide a valid http:// or https:// URL."
        )
        raise typer.Exit(code=1)

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        if output != "json":
            console.print(f"[dim]Scoring job posting: {url}[/dim]")

        # Fetch real content from the URL
        if output != "json":
            console.print("[dim]Fetching job posting content...[/dim]")
        fetched_content = _fetch_url_content(url)

        if fetched_content and len(fetched_content.strip()) > 50:
            job_description = fetched_content
            if output != "json":
                console.print(f"[dim]Fetched {len(fetched_content)} chars of content.[/dim]")
        else:
            # Fallback: use URL as minimal description
            job_description = (
                f"Job posting at {url}\n\n"
                f"(Unable to fetch full posting — scoring based on URL and profile match)"
            )
            if output != "json":
                console.print(
                    "[yellow]Could not fetch posting content. "
                    "Scoring with limited information.[/yellow]"
                )

        try:
            scored = _run_score_async(
                db,
                profile.id,
                job_description,
                job_url=url,
            )
        except Exception as exc:
            console.print(f"[red]Error:[/red] Scoring failed: {exc}")
            raise typer.Exit(code=1) from None

        if output == "json":
            _score_output_json(scored)
        else:
            _score_output_table(scored)

    finally:
        db.close()


def _score_output_table(scored) -> None:
    """Print score breakdown as a formatted panel."""
    # Color code fit score
    fit = scored.fit_score
    if fit >= 8:
        fit_style = "green"
    elif fit >= 6:
        fit_style = "yellow"
    else:
        fit_style = "red"

    # Color code readiness score
    readiness = scored.readiness_score
    if readiness >= 80:
        ready_style = "green"
    elif readiness >= 50:
        ready_style = "yellow"
    else:
        ready_style = "red"

    # Build breakdown section if available
    breakdown_lines = ""
    breakdown_data = getattr(scored, "score_breakdown", None)
    if breakdown_data:
        # Handle both JSON string and list of dicts/objects
        if isinstance(breakdown_data, str):
            try:
                breakdown_data = json_mod.loads(breakdown_data)
            except (json_mod.JSONDecodeError, TypeError):
                breakdown_data = []
        if breakdown_data:
            breakdown_lines = "\n[bold]Score Factors:[/bold]\n"
            for factor in breakdown_data:
                if isinstance(factor, dict):
                    name = factor.get("factor", "")
                    contrib = factor.get("contribution", 0)
                    desc = factor.get("description", "")
                else:
                    name = getattr(factor, "factor", "")
                    contrib = getattr(factor, "contribution", 0)
                    desc = getattr(factor, "description", "")
                sign = "+" if contrib >= 0 else ""
                color = "green" if contrib >= 0 else "red"
                breakdown_lines += f"  [{color}]{sign}{contrib:.1f}[/{color}] {name}: {desc}\n"

    console.print()
    console.print(
        Panel(
            f"[bold]Fit Score:[/bold]        [{fit_style}]{fit:.1f} / 10[/{fit_style}]\n"
            f"[bold]Readiness:[/bold]        [{ready_style}]{readiness:.1f}%[/{ready_style}]\n"
            f"[bold]Career Alignment:[/bold] {scored.career_alignment:.1f} / 10\n"
            f"{breakdown_lines}\n"
            f"[bold]Estimated Salary:[/bold] {scored.estimated_salary or '—'}\n"
            f"[bold]Effort Level:[/bold]     {scored.effort_flag}\n"
            f"[bold]Prep Level:[/bold]       {scored.prep_level}\n"
            f"\n"
            f"[bold]Reasoning:[/bold]\n{scored.reasoning}\n"
            f"\n"
            f"[bold]Prep Notes:[/bold]\n{scored.prep_notes or '—'}",
            title="[bold]Score Breakdown[/bold]",
        )
    )


def _score_output_json(scored) -> None:
    """Print score breakdown as JSON."""
    # Parse score_breakdown from JSON string if needed
    breakdown = getattr(scored, "score_breakdown", None)
    if isinstance(breakdown, str):
        try:
            breakdown = json_mod.loads(breakdown)
        except (json_mod.JSONDecodeError, TypeError):
            breakdown = []
    elif breakdown and hasattr(breakdown[0], "model_dump"):
        breakdown = [f.model_dump() for f in breakdown]

    data = {
        "fit_score": scored.fit_score,
        "readiness_score": scored.readiness_score,
        "career_alignment": scored.career_alignment,
        "score_breakdown": breakdown or [],
        "reasoning": scored.reasoning,
        "estimated_salary": scored.estimated_salary,
        "effort_flag": scored.effort_flag,
        "prep_level": scored.prep_level,
        "prep_notes": scored.prep_notes,
    }
    typer.echo(json_mod.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# career market
# ---------------------------------------------------------------------------


@app.command("market")
def market(
    output: str = typer.Option(
        "table",
        "--output",
        "-o",
        help="Output format: table or json",
    ),
) -> None:
    """Show market intelligence summary (salary trends, skills, hiring, positioning)."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)

        from career_os.services.market import (
            get_hiring_patterns,
            get_market_positioning,
            get_salary_trends,
            get_skill_trends,
        )

        salary_data = get_salary_trends(db, profile.id)
        skill_data = get_skill_trends(db, profile.id)
        hiring_data = get_hiring_patterns(db, profile.id)
        positioning_data = get_market_positioning(db, profile.id)

        # Check if any data exists
        has_data = (
            salary_data.get("trends")
            or skill_data.get("skills")
            or hiring_data.get("companies")
            or positioning_data.get("positions")
        )

        if not has_data:
            console.print(
                "[yellow]No market data available. "
                "Run `career discover` first to populate market intelligence.[/yellow]"
            )
            return

        if output == "json":
            _market_output_json(salary_data, skill_data, hiring_data, positioning_data)
        else:
            _market_output_table(salary_data, skill_data, hiring_data, positioning_data)

    finally:
        db.close()


def _market_output_table(salary_data, skill_data, hiring_data, positioning_data) -> None:
    """Print market intelligence as Rich tables."""
    # Section 1: Salary Trends
    console.print("\n[bold]📊 Salary Trends[/bold]")
    if salary_data.get("trends"):
        table = Table()
        table.add_column("Role", style="bold")
        table.add_column("P25", justify="right")
        table.add_column("Median", justify="right")
        table.add_column("P75", justify="right")
        table.add_column("Sample", justify="right", style="dim")

        for t in salary_data["trends"]:
            table.add_row(
                t["role"],
                f"€{t['p25']:,.0f}",
                f"€{t['median']:,.0f}",
                f"€{t['p75']:,.0f}",
                str(t["sample_size"]),
            )
        console.print(table)
    else:
        console.print("  [dim]No salary data available.[/dim]")

    # Section 2: Skill Demand Trends
    console.print("\n[bold]🔥 Skill Demand Trends[/bold]")
    if skill_data.get("skills"):
        table = Table()
        table.add_column("Skill", style="bold")
        table.add_column("Mentions", justify="right")
        table.add_column("% of Postings", justify="right")
        table.add_column("Trend")

        for s in skill_data["skills"][:10]:  # Top 10
            trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}.get(s["trend_direction"], "—")
            table.add_row(
                s["skill_name"],
                str(s["mention_count"]),
                f"{s['percentage_of_postings']:.1f}%",
                trend_icon,
            )
        console.print(table)
    else:
        console.print("  [dim]No skill trend data available.[/dim]")

    # Section 3: Hiring Patterns
    console.print("\n[bold]🏢 Company Hiring Patterns[/bold]")
    if hiring_data.get("companies"):
        table = Table()
        table.add_column("Company", style="bold")
        table.add_column("Active", justify="right")
        table.add_column("Velocity", justify="right")
        table.add_column("Roles")

        for c in hiring_data["companies"][:10]:  # Top 10
            roles_str = ", ".join(c["roles_trending"][:3])
            if len(c["roles_trending"]) > 3:
                roles_str += f" (+{len(c['roles_trending']) - 3} more)"

            table.add_row(
                c["company"],
                str(c["active_postings_count"]),
                f"{c['posting_velocity']:.1f}/wk",
                roles_str,
            )
        console.print(table)
    else:
        console.print("  [dim]No hiring pattern data available.[/dim]")

    # Section 4: Market Positioning
    console.print("\n[bold]🎯 Market Positioning[/bold]")
    if positioning_data.get("positions"):
        table = Table()
        table.add_column("Role Type", style="bold")
        table.add_column("Match %", justify="right")
        table.add_column("Roles Analyzed", justify="right", style="dim")

        for p in positioning_data["positions"]:
            if p["match_percentage"] >= 70:
                pct_style = "green"
            elif p["match_percentage"] >= 40:
                pct_style = "yellow"
            else:
                pct_style = "red"

            table.add_row(
                p["role_type"],
                f"[{pct_style}]{p['match_percentage']:.1f}%[/{pct_style}]",
                str(p["total_roles_analyzed"]),
            )
        console.print(table)
    else:
        console.print("  [dim]No positioning data available.[/dim]")

    console.print()


def _market_output_json(salary_data, skill_data, hiring_data, positioning_data) -> None:
    """Print market intelligence as JSON."""
    data = {
        "salary_trends": salary_data.get("trends", []),
        "skill_trends": skill_data.get("skills", []),
        "hiring_patterns": hiring_data.get("companies", []),
        "positioning": positioning_data.get("positions", []),
    }
    typer.echo(json_mod.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Async helpers for research & interview prep (CLI runs sync, services async)
# ---------------------------------------------------------------------------


def _run_research_async(
    db: Session,
    company_name: str,
    profile_id: int,
    company_url: str | None = None,
):
    """Run async company research from a sync context. Patched in tests."""
    from career_os.services.company_research import research_company

    return asyncio.run(
        research_company(
            db,
            company_name=company_name,
            profile_id=profile_id,
            company_url=company_url,
        )
    )


def _run_interview_prep_async(
    db: Session,
    application_id: int,
    profile_id: int,
):
    """Run async interview prep from a sync context. Patched in tests."""
    from career_os.services.interview_prep import get_or_create_interview_prep

    return asyncio.run(
        get_or_create_interview_prep(
            db,
            application_id=application_id,
            profile_id=profile_id,
        )
    )


# ---------------------------------------------------------------------------
# career research <company>
# ---------------------------------------------------------------------------


@app.command("research")
def research(
    company: str = typer.Argument(..., help="Company name to research"),
    url: str | None = typer.Option(None, "--url", "-u", help="Company website URL for enrichment"),
) -> None:
    """Run full company research and output a structured report."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)

        console.print(f"[dim]Researching {company}...[/dim]")

        try:
            report = _run_research_async(
                db,
                company_name=company,
                profile_id=profile.id,
                company_url=url,
            )
        except Exception as exc:
            console.print(f"[red]Error:[/red] Research failed: {exc}")
            raise typer.Exit(code=1) from None

        # Render structured report
        _render_research_report(report)

    finally:
        db.close()


def _render_research_report(report) -> None:
    """Render a CompanyResearchReport as a formatted Rich output."""

    console.print(f"\n[bold]📋 Company Research: {report.company_name}[/bold]\n")

    # Industry segment + employee count
    if report.industry_segment:
        console.print(f"[bold]Industry:[/bold] {report.industry_segment}")
    if report.employee_count:
        console.print(f"[bold]Employees:[/bold] {report.employee_count}")
    if report.ats_platform:
        console.print(f"[bold]ATS Platform:[/bold] {report.ats_platform}")
    console.print()

    # Tech Stack
    console.print("[bold]🔧 Tech Stack[/bold]")
    ts = report.tech_stack
    has_tech = any([ts.frontend, ts.backend, ts.infrastructure, ts.analytics])
    if has_tech:
        if ts.frontend:
            console.print(f"  Frontend:       {', '.join(ts.frontend)}")
        if ts.backend:
            console.print(f"  Backend:        {', '.join(ts.backend)}")
        if ts.infrastructure:
            console.print(f"  Infrastructure: {', '.join(ts.infrastructure)}")
        if ts.analytics:
            console.print(f"  Analytics:      {', '.join(ts.analytics)}")
    else:
        console.print("  [dim]No data found[/dim]")
    console.print()

    # Funding
    console.print("[bold]💰 Funding[/bold]")
    f = report.funding
    has_funding = any([f.stage, f.total_raised, f.lead_investor])
    if has_funding:
        if f.stage:
            console.print(f"  Stage:          {f.stage}")
        if f.total_raised:
            console.print(f"  Total Raised:   {f.total_raised}")
        if f.lead_investor:
            console.print(f"  Lead Investor:  {f.lead_investor}")
        if f.last_round_date:
            console.print(f"  Last Round:     {f.last_round_date}")
    else:
        console.print("  [dim]No data found[/dim]")
    console.print()

    # Glassdoor / Culture
    console.print("[bold]⭐ Glassdoor & Culture[/bold]")
    g = report.glassdoor
    has_glassdoor = any([g.overall_rating, g.ceo_approval, g.culture_keywords])
    if has_glassdoor:
        if g.overall_rating is not None:
            console.print(f"  Overall Rating: {g.overall_rating:.1f}/5.0")
        if g.ceo_approval is not None:
            console.print(f"  CEO Approval:   {g.ceo_approval}%")
        if g.work_life_balance is not None:
            console.print(f"  Work-Life Bal:  {g.work_life_balance:.1f}/5.0")
        if g.culture_keywords:
            console.print(f"  Culture:        {', '.join(g.culture_keywords)}")
    else:
        console.print("  [dim]No data found[/dim]")
    console.print()

    # Values Alignment
    console.print("[bold]🎯 Values Alignment[/bold]")
    va = report.values_alignment
    score = va.score
    if score >= 8:
        score_style = "green"
    elif score >= 5:
        score_style = "yellow"
    else:
        score_style = "red"
    console.print(f"  Score: [{score_style}]{score:.1f}/10[/{score_style}]")
    console.print(f"  {va.rationale}")
    console.print()

    # Hiring Patterns
    console.print("[bold]📈 Hiring Patterns[/bold]")
    hp = report.hiring_patterns
    has_hiring = any([hp.active_postings, hp.posting_velocity, hp.top_departments])
    if has_hiring:
        if hp.active_postings is not None:
            console.print(f"  Active Postings:  {hp.active_postings}")
        if hp.posting_velocity:
            console.print(f"  Posting Velocity: {hp.posting_velocity}")
        if hp.top_departments:
            console.print(f"  Top Departments:  {', '.join(hp.top_departments)}")
    else:
        console.print("  [dim]No data found[/dim]")
    console.print()

    # Warnings
    if report.warnings:
        console.print("[yellow]⚠ Warnings[/yellow]")
        for w in report.warnings:
            console.print(f"  ⚠ {w.source}: {w.error}")
        console.print()


# ---------------------------------------------------------------------------
# career interview-prep <application_id> (default command)
# ---------------------------------------------------------------------------


@interview_prep_app.command("generate")
def interview_prep_generate(
    application_id: int = typer.Argument(..., help="Application ID to prepare for"),
) -> None:
    """Generate interview preparation for an application."""
    db = _get_session()
    try:
        profile = _get_default_profile(db)

        # Check application exists
        app_obj = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.profile_id == profile.id,
                Application.archived_at.is_(None),
            )
            .first()
        )
        if app_obj is None:
            console.print(f"[red]Error:[/red] Application {application_id} not found.")
            raise typer.Exit(code=1)

        console.print(
            f"[dim]Generating interview prep for {app_obj.company} — {app_obj.role}...[/dim]"
        )

        try:
            prep = _run_interview_prep_async(
                db,
                application_id=application_id,
                profile_id=profile.id,
            )
        except Exception as exc:
            console.print(f"[red]Error:[/red] Interview prep failed: {exc}")
            raise typer.Exit(code=1) from None

        _render_interview_prep(prep)

    finally:
        db.close()


def _render_interview_prep(prep) -> None:
    """Render an InterviewPrepResponse as Rich output."""

    console.print(f"\n[bold]🎤 Interview Prep: {prep.company} — {prep.role}[/bold]\n")

    # Progress summary
    progress = prep.progress_percentage
    completed = prep.completed_items
    total = prep.total_items
    if progress >= 80:
        p_style = "green"
    elif progress >= 50:
        p_style = "yellow"
    else:
        p_style = "red"
    console.print(
        f"Progress: [{p_style}]{progress:.1f}%[/{p_style}] "
        f"({completed}/{total} items) | "
        f"Est. prep time: {prep.total_prep_hours:.1f}h"
    )

    # Research prompt
    if prep.research_prompt:
        console.print(f"\n[yellow]⚠ {prep.research_prompt}[/yellow]")

    console.print()

    # Topics
    if prep.topics:
        table = Table(title="Topics")
        table.add_column("Topic", style="bold")
        table.add_column("Relevance")
        table.add_column("Difficulty")
        table.add_column("Source", style="dim")

        for t in prep.topics:
            rel = t.relevance
            if rel == "high":
                rel_str = f"[red]{rel}[/red]"
            elif rel == "medium":
                rel_str = f"[yellow]{rel}[/yellow]"
            else:
                rel_str = f"[dim]{rel}[/dim]"

            diff = t.difficulty
            if diff == "high":
                diff_str = f"[red]{diff}[/red]"
            elif diff == "medium":
                diff_str = f"[yellow]{diff}[/yellow]"
            else:
                diff_str = f"[dim]{diff}[/dim]"

            table.add_row(t.topic, rel_str, diff_str, t.source or "—")

        console.print(table)
        console.print()

    # Questions
    if prep.questions:
        table = Table(title="Practice Questions")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Question", style="bold", max_width=70)
        table.add_column("Category")
        table.add_column("Difficulty")

        for i, q in enumerate(prep.questions, start=1):
            diff = q.difficulty
            if diff == "high":
                diff_str = f"[red]{diff}[/red]"
            elif diff == "medium":
                diff_str = f"[yellow]{diff}[/yellow]"
            else:
                diff_str = f"[dim]{diff}[/dim]"

            table.add_row(str(i), q.question, q.category, diff_str)

        console.print(table)
        console.print()

    # Checklist
    if prep.checklist:
        table = Table(title="Prep Checklist")
        table.add_column("", justify="center", width=3)
        table.add_column("Item", style="bold", max_width=60)
        table.add_column("Time", justify="right")
        table.add_column("Priority")

        for item in prep.checklist:
            check = "[green]✓[/green]" if item.completed else "○"

            priority = item.priority
            if priority == "high":
                pri_str = f"[red]{priority}[/red]"
            elif priority == "medium":
                pri_str = f"[yellow]{priority}[/yellow]"
            else:
                pri_str = f"[dim]{priority}[/dim]"

            table.add_row(
                check,
                item.item,
                f"{item.time_minutes}m",
                pri_str,
            )

        console.print(table)

        total_mins = prep.total_prep_minutes
        console.print(
            f"\n[dim]Total estimated prep time: {total_mins // 60}h {total_mins % 60}m[/dim]"
        )

    console.print()


# ---------------------------------------------------------------------------
# career interview-prep stories (list / add / view / edit)
# ---------------------------------------------------------------------------


@stories_app.callback(invoke_without_command=True)
def stories_list_default(ctx: typer.Context) -> None:
    """List all STAR stories with titles, skills, and usage count."""
    if ctx.invoked_subcommand is not None:
        return

    from career_os.models.skills import JobRequirement
    from career_os.models.star_stories import StarStory

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        stories = (
            db.query(StarStory)
            .filter(StarStory.profile_id == profile.id)
            .order_by(StarStory.created_at.desc())
            .all()
        )

        if not stories:
            console.print(
                "[yellow]No STAR stories yet. "
                "Add one with: career interview-prep stories add[/yellow]"
            )
            return

        # Build a mapping of story → usage count (how many applications match)
        # by checking skill tags overlap with job requirements
        all_requirements = (
            db.query(JobRequirement).filter(JobRequirement.profile_id == profile.id).all()
        )
        # Group requirements by application_id for counting
        app_requirements: dict[int, set[str]] = {}
        for req in all_requirements:
            app_requirements.setdefault(req.application_id, set()).add(
                req.skill_name.lower().strip()
            )

        table = Table(title="STAR Stories")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Title", style="bold")
        table.add_column("Skills")
        table.add_column("Used", justify="right")
        table.add_column("Created")

        for story in stories:
            tags = story.get_skill_tags_list()
            tags_str = ", ".join(tags) if tags else "—"
            tags_lower = {t.lower().strip() for t in tags}

            # Count applications where this story's tags match any requirement
            usage_count = 0
            for _app_id, req_skills in app_requirements.items():
                if tags_lower & req_skills:
                    usage_count += 1

            created = story.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            date_str = created.strftime("%Y-%m-%d") if created else "—"

            table.add_row(str(story.id), story.title, tags_str, str(usage_count), date_str)

        console.print(table)
        console.print(f"\n[dim]Total: {len(stories)} story(ies)[/dim]")
    finally:
        db.close()


@stories_app.command("add")
def stories_add(
    title: str = typer.Option(..., "--title", "-t", help="Story title"),
    situation: str = typer.Option(..., "--situation", "-s", help="STAR: Situation"),
    task: str = typer.Option(..., "--task", help="STAR: Task"),
    action: str = typer.Option(..., "--action", "-a", help="STAR: Action"),
    result: str = typer.Option(..., "--result", "-r", help="STAR: Result"),
    tags: str = typer.Option("", "--tags", help="Comma-separated skill tags"),
) -> None:
    """Add a new STAR story."""
    from career_os.models.star_stories import StarStory

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        skill_tags = ",".join(t.strip() for t in tags.split(",") if t.strip()) if tags else ""

        story = StarStory(
            profile_id=profile.id,
            title=title,
            situation=situation,
            task=task,
            action=action,
            result=result,
            skill_tags=skill_tags,
        )
        db.add(story)
        db.commit()
        db.refresh(story)

        console.print(f"[green]✓[/green] Created STAR story [bold]#{story.id}[/bold]: {title}")
        if skill_tags:
            console.print(f"  Skills: {skill_tags}")
    finally:
        db.close()


@stories_app.command("view")
def stories_view(
    story_id: int = typer.Argument(..., help="Story ID to view"),
) -> None:
    """View a single STAR story in detail."""
    from career_os.models.star_stories import StarStory

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        story = (
            db.query(StarStory)
            .filter(
                StarStory.id == story_id,
                StarStory.profile_id == profile.id,
            )
            .first()
        )
        if story is None:
            console.print(f"[red]Error:[/red] STAR story {story_id} not found.")
            raise typer.Exit(code=1)

        tags = story.get_skill_tags_list()
        tags_str = ", ".join(tags) if tags else "—"

        content = (
            f"[bold]Situation:[/bold]\n{story.situation}\n\n"
            f"[bold]Task:[/bold]\n{story.task}\n\n"
            f"[bold]Action:[/bold]\n{story.action}\n\n"
            f"[bold]Result:[/bold]\n{story.result}\n\n"
            f"[bold]Skills:[/bold] {tags_str}"
        )
        console.print(Panel(content, title=f"[bold]{story.title}[/bold]"))
    finally:
        db.close()


@stories_app.command("edit")
def stories_edit(
    story_id: int = typer.Argument(..., help="Story ID to edit"),
    title: str | None = typer.Option(None, "--title", "-t", help="New title"),
    situation: str | None = typer.Option(None, "--situation", "-s", help="New situation"),
    task: str | None = typer.Option(None, "--task", help="New task"),
    action: str | None = typer.Option(None, "--action", "-a", help="New action"),
    result: str | None = typer.Option(None, "--result", "-r", help="New result"),
    tags: str | None = typer.Option(None, "--tags", help="New comma-separated skill tags"),
) -> None:
    """Edit an existing STAR story."""
    from career_os.models.star_stories import StarStory

    # Check at least one field provided
    if all(v is None for v in [title, situation, task, action, result, tags]):
        console.print(
            "[red]Error:[/red] Provide at least one field to update "
            "(--title, --situation, --task, --action, --result, --tags)."
        )
        raise typer.Exit(code=1)

    db = _get_session()
    try:
        profile = _get_default_profile(db)

        story = (
            db.query(StarStory)
            .filter(
                StarStory.id == story_id,
                StarStory.profile_id == profile.id,
            )
            .first()
        )
        if story is None:
            console.print(f"[red]Error:[/red] STAR story {story_id} not found.")
            raise typer.Exit(code=1)

        changed = []
        if title is not None:
            story.title = title
            changed.append("title")
        if situation is not None:
            story.situation = situation
            changed.append("situation")
        if task is not None:
            story.task = task
            changed.append("task")
        if action is not None:
            story.action = action
            changed.append("action")
        if result is not None:
            story.result = result
            changed.append("result")
        if tags is not None:
            story.skill_tags = ",".join(t.strip() for t in tags.split(",") if t.strip())
            changed.append("tags")

        db.commit()
        db.refresh(story)

        console.print(
            f"[green]✓[/green] Updated STAR story [bold]#{story.id}[/bold] ({', '.join(changed)})"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Server start command
# ---------------------------------------------------------------------------


@app.command("start")
def start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8100, "--port", "-p", help="Port number"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
) -> None:
    """Start the Kestrel web server.

    Runs database migrations, then starts the FastAPI server.
    Opens your browser to the dashboard automatically.
    """
    import subprocess
    import sys
    import threading
    import time
    import webbrowser

    console.print(Panel.fit("[bold]Kestrel[/bold] - Starting up...", border_style="blue"))

    # Ensure data directory exists
    from pathlib import Path

    data_dir = Path.home() / ".kestrel" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Set DATABASE_URL if not already set (default to ~/.kestrel/data/)
    import os

    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = f"sqlite:///{data_dir}/career_os.db"

    # Run migrations
    console.print("  Running database migrations...", style="dim")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            console.print(f"  [yellow]Migration warning:[/yellow] {result.stderr.strip()[:200]}")
        else:
            console.print("  [green]OK[/green] Database ready")
    except Exception as e:
        console.print(f"  [yellow]Migration skipped:[/yellow] {e}")

    # Open browser after a short delay
    if not no_browser:

        def _open_browser() -> None:
            time.sleep(2)
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=_open_browser, daemon=True).start()

    console.print(f"  Dashboard: [link]http://localhost:{port}[/link]")
    console.print("  Press Ctrl+C to stop\n")

    # Start uvicorn
    import uvicorn

    uvicorn.run(
        "career_os.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    app()
