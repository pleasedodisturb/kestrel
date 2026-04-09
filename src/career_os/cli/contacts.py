"""CLI commands for Networking CRM (M6) — contacts, interactions, linking."""

from __future__ import annotations

import json as json_mod

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from career_os.database import SessionLocal
from career_os.schemas.contacts import (
    ContactApplicationCreate,
    ContactCreate,
    ContactUpdate,
    InteractionCreate,
)
from career_os.services.contacts import (
    ApplicationNotFoundError,
    ContactNotFoundError,
    DuplicateLinkError,
    archive_contact,
    create_contact,
    create_interaction,
    get_contact,
    get_contacts_by_company,
    link_contact_to_application,
    list_contacts,
    list_interactions,
    unlink_contact_from_application,
    update_contact,
)

console = Console()

contacts_app = typer.Typer(
    name="contacts",
    help="Manage your professional network — contacts, interactions, referrals.",
    no_args_is_help=True,
)

DEFAULT_PROFILE_ID = 1


@contacts_app.command("add")
def add(
    name: str = typer.Option(..., "--name", help="Contact name"),
    company: str | None = typer.Option(None, "--company", help="Company name"),
    role: str | None = typer.Option(None, "--role", help="Their role/title"),
    email: str | None = typer.Option(None, "--email", help="Email address"),
    linkedin: str | None = typer.Option(None, "--linkedin", help="LinkedIn URL"),
    phone: str | None = typer.Option(None, "--phone", help="Phone number"),
    type_: str = typer.Option("other", "--type", help="Relationship type"),
    warmth: str = typer.Option("cold", "--warmth", help="Connection strength: cold/warm/hot"),
    source: str | None = typer.Option(None, "--source", help="How you met"),
    notes: str | None = typer.Option(None, "--notes", help="Notes"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Add a new contact to your network."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    db = SessionLocal()
    try:
        contact = create_contact(
            db,
            ContactCreate(
                profile_id=profile_id,
                name=name,
                company=company,
                role=role,
                email=email,
                linkedin_url=linkedin,
                phone=phone,
                relationship_type=type_,
                warmth=warmth,
                source=source,
                notes=notes,
                tags=tag_list,
            ),
        )
        console.print(
            f"[green]✓[/green] Created contact [bold]{contact.name}[/bold] (ID: {contact.id})"
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("list")
def list_cmd(
    company: str | None = typer.Option(None, "--company", help="Filter by company"),
    type_: str | None = typer.Option(None, "--type", help="Filter by relationship type"),
    warmth: str | None = typer.Option(None, "--warmth", help="Filter by warmth"),
    needs_follow_up: bool = typer.Option(
        False, "--needs-follow-up", help="Show overdue follow-ups"
    ),
    search: str | None = typer.Option(None, "--search", help="Search name/company/notes"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """List contacts with optional filters."""
    db = SessionLocal()
    try:
        contacts, total = list_contacts(
            db,
            profile_id=profile_id,
            company=company,
            relationship_type=type_,
            warmth=warmth,
            needs_follow_up=needs_follow_up,
            search=search,
        )
        if not contacts:
            console.print("[dim]No contacts found.[/dim]")
            return

        table = Table(title=f"Contacts ({total})")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Name", style="bold")
        table.add_column("Company")
        table.add_column("Type")
        table.add_column("Warmth")
        table.add_column("Referral")
        table.add_column("Last Contact", style="dim")

        for c in contacts:
            warmth_style = {"hot": "red", "warm": "yellow", "cold": "blue"}.get(c.warmth, "")
            last = c.last_contacted_at.strftime("%Y-%m-%d") if c.last_contacted_at else "—"
            table.add_row(
                str(c.id),
                c.name,
                c.company or "—",
                c.relationship_type,
                f"[{warmth_style}]{c.warmth}[/{warmth_style}]" if warmth_style else c.warmth,
                c.referral_status or "—",
                last,
            )

        console.print(table)
    finally:
        db.close()


def _build_contact_info(contact) -> str:  # noqa: ANN001
    """Build a rich-formatted info string for a contact detail panel."""
    dash = "\u2014"

    tags = ""
    if contact.tags:
        try:
            tag_list = json_mod.loads(contact.tags)
            tags = ", ".join(tag_list)
        except (json_mod.JSONDecodeError, TypeError):
            tags = contact.tags

    last_contacted = (
        contact.last_contacted_at.strftime("%Y-%m-%d %H:%M") if contact.last_contacted_at else dash
    )
    next_follow_up = contact.next_follow_up.strftime("%Y-%m-%d") if contact.next_follow_up else dash

    return (
        f"[bold]{contact.name}[/bold]\n"
        f"Company: {contact.company or dash}\n"
        f"Role: {contact.role or dash}\n"
        f"Email: {contact.email or dash}\n"
        f"LinkedIn: {contact.linkedin_url or dash}\n"
        f"Phone: {contact.phone or dash}\n"
        f"Type: {contact.relationship_type}\n"
        f"Warmth: {contact.warmth}\n"
        f"Referral Status: {contact.referral_status or dash}\n"
        f"Source: {contact.source or dash}\n"
        f"Tags: {tags or dash}\n"
        f"Last Contacted: {last_contacted}\n"
        f"Next Follow-up: {next_follow_up}\n"
        f"Notes: {contact.notes or dash}"
    )


@contacts_app.command("show")
def show(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Show contact details."""
    db = SessionLocal()
    try:
        contact = get_contact(db, contact_id, profile_id=profile_id)
        info = _build_contact_info(contact)
        console.print(Panel(info, title=f"Contact #{contact.id}"))
    except ContactNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("update")
def update_cmd(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    name: str | None = typer.Option(None, "--name"),
    company: str | None = typer.Option(None, "--company"),
    role: str | None = typer.Option(None, "--role"),
    warmth: str | None = typer.Option(None, "--warmth"),
    referral_status: str | None = typer.Option(None, "--referral-status"),
    notes: str | None = typer.Option(None, "--notes"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Update a contact's fields."""
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if company is not None:
        update_data["company"] = company
    if role is not None:
        update_data["role"] = role
    if warmth is not None:
        update_data["warmth"] = warmth
    if referral_status is not None:
        update_data["referral_status"] = referral_status
    if notes is not None:
        update_data["notes"] = notes

    if not update_data:
        console.print("[yellow]No fields to update.[/yellow]")
        return

    db = SessionLocal()
    try:
        contact = update_contact(
            db, contact_id, ContactUpdate(**update_data), profile_id=profile_id
        )
        console.print(
            f"[green]✓[/green] Updated contact [bold]{contact.name}[/bold] (ID: {contact.id})"
        )
    except ContactNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("archive")
def archive_cmd(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Archive (soft-delete) a contact."""
    db = SessionLocal()
    try:
        contact = archive_contact(db, contact_id, profile_id=profile_id)
        console.print(f"[green]✓[/green] Archived contact [bold]{contact.name}[/bold]")
    except ContactNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("log")
def log_cmd(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    type_: str = typer.Option(
        ...,
        "--type",
        help="Interaction type: email/call/coffee/linkedin_message/intro/referral_submission",
    ),
    direction: str = typer.Option("outbound", "--direction", help="inbound or outbound"),
    notes: str | None = typer.Option(None, "--notes", help="Interaction notes"),
    subject: str | None = typer.Option(None, "--subject", help="Subject line"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Log an interaction with a contact."""
    db = SessionLocal()
    try:
        interaction = create_interaction(
            db,
            contact_id,
            InteractionCreate(
                interaction_type=type_,
                direction=direction,
                notes=notes,
                subject=subject,
            ),
            profile_id=profile_id,
        )
        console.print(
            f"[green]✓[/green] Logged {interaction.interaction_type} ({interaction.direction}) — ID: {interaction.id}"
        )
    except ContactNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("history")
def history_cmd(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Show interaction history for a contact."""
    db = SessionLocal()
    try:
        interactions = list_interactions(db, contact_id, profile_id=profile_id)
        if not interactions:
            console.print("[dim]No interactions recorded.[/dim]")
            return

        table = Table(title="Interaction History")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Type")
        table.add_column("Direction")
        table.add_column("Subject")
        table.add_column("Date", style="dim")

        for i in interactions:
            table.add_row(
                str(i.id),
                i.interaction_type,
                i.direction,
                i.subject or "—",
                i.occurred_at.strftime("%Y-%m-%d %H:%M") if i.occurred_at else "—",
            )

        console.print(table)
    except ContactNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("link")
def link_cmd(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    application_id: int = typer.Argument(..., help="Application ID"),
    role: str = typer.Option(
        "referrer",
        "--role",
        help="Contact's role: referrer/recruiter/hiring_manager/interviewer/insider",
    ),
    notes: str | None = typer.Option(None, "--notes"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Link a contact to an application."""
    db = SessionLocal()
    try:
        link = link_contact_to_application(
            db,
            contact_id,
            ContactApplicationCreate(application_id=application_id, role=role, notes=notes),
            profile_id=profile_id,
        )
        console.print(
            f"[green]✓[/green] Linked contact {contact_id} → application {application_id} as {link.role}"
        )
    except (ContactNotFoundError, ApplicationNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    except DuplicateLinkError as e:
        console.print(f"[yellow]Warning:[/yellow] {e}")
    finally:
        db.close()


@contacts_app.command("unlink")
def unlink_cmd(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    application_id: int = typer.Argument(..., help="Application ID"),
) -> None:
    """Unlink a contact from an application."""
    db = SessionLocal()
    try:
        unlink_contact_from_application(db, contact_id, application_id)
        console.print(
            f"[green]✓[/green] Unlinked contact {contact_id} from application {application_id}"
        )
    except ContactNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        db.close()


@contacts_app.command("at")
def at_company(
    company: str = typer.Argument(..., help="Company name"),
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Show contacts at a company — "who do I know at Mistral?" """
    db = SessionLocal()
    try:
        contacts = get_contacts_by_company(db, company, profile_id=profile_id)
        if not contacts:
            console.print(f"[dim]No contacts found at {company}.[/dim]")
            return

        table = Table(title=f"Contacts at {company}")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Type")
        table.add_column("Warmth")

        for c in contacts:
            table.add_row(str(c.id), c.name, c.role or "—", c.relationship_type, c.warmth)

        console.print(table)
    finally:
        db.close()


@contacts_app.command("follow-ups")
def follow_ups_cmd(
    profile_id: int = typer.Option(DEFAULT_PROFILE_ID, "--profile-id", hidden=True),
) -> None:
    """Show contacts with overdue follow-ups."""
    db = SessionLocal()
    try:
        contacts, total = list_contacts(db, profile_id=profile_id, needs_follow_up=True)
        if not contacts:
            console.print("[dim]No overdue follow-ups.[/dim]")
            return

        table = Table(title=f"Overdue Follow-ups ({total})")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Name", style="bold")
        table.add_column("Company")
        table.add_column("Due", style="red")
        table.add_column("Last Contact", style="dim")

        for c in contacts:
            due = c.next_follow_up.strftime("%Y-%m-%d") if c.next_follow_up else "—"
            last = c.last_contacted_at.strftime("%Y-%m-%d") if c.last_contacted_at else "—"
            table.add_row(str(c.id), c.name, c.company or "—", due, last)

        console.print(table)
    finally:
        db.close()
