"""CLI commands for browser-extension pairing (Phase 0 / G-1390, hardened G-1391).

`kestrel extension pair` MINTS a fresh single-use pairing code the user reads from
their own running instance and types into the extension's options page once. Each
invocation generates a new random code (invalidating any previous one) and persists
only its hash + a short expiry; submitting the code to POST /api/extension/pair
consumes it and mints the extension's dedicated token. Possession of the code proves
local access to the instance.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from career_os.config import settings
from career_os.services.extension_pairing import mint_pairing_code

console = Console()

extension_app = typer.Typer(
    name="extension",
    help="Browser-extension pairing",
    no_args_is_help=True,
)


@extension_app.command("pair")
def pair() -> None:
    """Mint and print a fresh single-use pairing code for the browser extension."""
    code = mint_pairing_code()
    ttl_minutes = max(1, settings.extension_pairing_ttl_seconds // 60)

    console.print(
        Panel(
            f"[bold cyan]{code}[/bold cyan]\n\n"
            f"Enter this code in the Kestrel browser extension's options page to\n"
            f"pair it with this instance. The code is [bold]single-use[/bold] and expires in\n"
            f"about [bold]{ttl_minutes} minute(s)[/bold]; run this command again for a fresh one.\n"
            f"Pairing mints a dedicated token stored by the extension — it never\n"
            f"uses or reveals your AUTH_API_KEY.",
            title="[bold]Extension Pairing Code[/bold]",
            border_style="cyan",
        )
    )
