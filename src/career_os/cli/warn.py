"""CLI commands for WARN Act data management (Epic 9 / G-277).

Usage:
    kestrel warn-update              # update all default states
    kestrel warn-update --states CA,NY,WA
    kestrel warn-update --state CA --state NY
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from career_os.database import SessionLocal
from career_os.services.warn_data import DEFAULT_STATES, _is_warnscraper_available, load_warn_data

console = Console()

_DEFAULT_STATES_HELP = (
    "Two-letter state abbreviation to fetch (repeatable). Defaults to: " + ", ".join(DEFAULT_STATES)
)

warn_app = typer.Typer(
    name="warn",
    help="WARN Act layoff data — download and manage filings from state portals.",
    no_args_is_help=True,
)


@warn_app.command("update")
def update(
    states: list[str] = typer.Option(
        None,
        "--state",
        "-s",
        help=_DEFAULT_STATES_HELP,
    ),
) -> None:
    """Download WARN Act filings from state government portals.

    Fetches current WARN data for the specified states (or all default states)
    and stores results in the local database. Run weekly to keep data fresh.

    Requires the warn-scraper package:
        pip install "kestrel-app[warn]"
    """
    if not _is_warnscraper_available():
        console.print(
            "[bold red]warn-scraper is not installed.[/bold red]\n"
            "Install it with:\n"
            '    pip install "kestrel-app[warn]"\n'
            "or:\n"
            "    pip install warn-scraper"
        )
        raise typer.Exit(code=1)

    target_states = [s.upper() for s in states] if states else DEFAULT_STATES

    console.print(
        f"[bold]Fetching WARN Act data for {len(target_states)} state(s):[/bold] "
        + ", ".join(target_states)
    )

    with SessionLocal() as db:
        results = load_warn_data(db, states=target_states)
        db.commit()

    # Summary table
    table = Table(title="WARN Data Update Results", show_header=True)
    table.add_column("State", style="bold")
    table.add_column("Filings", justify="right")
    table.add_column("Status")

    total = 0
    for state in target_states:
        count = results.get(state, 0)
        if count == -1:
            table.add_row(state, "—", "[red]failed[/red]")
        else:
            table.add_row(state, str(count), "[green]ok[/green]")
            total += count

    console.print(table)
    console.print(f"\n[bold green]Done.[/bold green] Total filings processed: {total}")


@warn_app.command("list-states")
def list_states() -> None:
    """Show the default states tracked for WARN Act data."""
    console.print("[bold]Default WARN Act states:[/bold]")
    for state in DEFAULT_STATES:
        console.print(f"  {state}")
