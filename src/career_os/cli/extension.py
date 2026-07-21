"""CLI commands for browser-extension pairing (Phase 0 / G-1390).

`kestrel extension pair` surfaces the current pairing code so the user can read it
from their own running instance and type it into the extension's options page once.
This is the chosen bootstrap surface (a future web-UI panel can render the same
code): possession of the code proves local access to the instance, and submitting
it to POST /api/extension/pair mints the extension's dedicated token.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from career_os.config import settings
from career_os.services.extension_pairing import current_pairing_code

console = Console()

extension_app = typer.Typer(
    name="extension",
    help="Browser-extension pairing",
    no_args_is_help=True,
)


@extension_app.command("pair")
def pair() -> None:
    """Print the current pairing code for the browser extension."""
    code = current_pairing_code()
    window_minutes = settings.extension_pairing_window_seconds // 60

    console.print(
        Panel(
            f"[bold cyan]{code}[/bold cyan]\n\n"
            f"Enter this code in the Kestrel browser extension's options page to\n"
            f"pair it with this instance. The code is valid for about "
            f"[bold]{window_minutes} minute(s)[/bold]; run this command again for a\n"
            f"fresh one. Pairing mints a dedicated token stored by the extension —\n"
            f"it never uses or reveals your AUTH_API_KEY.",
            title="[bold]Extension Pairing Code[/bold]",
            border_style="cyan",
        )
    )
