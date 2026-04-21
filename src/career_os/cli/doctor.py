"""CLI command: kestrel doctor -- local health check."""

from __future__ import annotations

import platform
import sys

import typer
from rich.console import Console
from sqlalchemy import text

from career_os.database import SessionLocal
from career_os.models.models import Profile

console = Console()


def _get_session():
    """Get a database session. Patched in tests."""
    return SessionLocal()


def _check_python_version() -> tuple[bool, str, str]:
    """Check Python >= 3.11. Returns (passed, label, resolution)."""
    version = platform.python_version()
    major, minor = sys.version_info[:2]
    if major >= 3 and minor >= 11:
        return True, f"Python {version}", ""
    return False, f"Python {version}", "Kestrel requires Python 3.11+. Install from python.org"


def _check_db_connection() -> tuple[bool, str, str]:
    """Check database is connectable."""
    try:
        db = _get_session()
        db.execute(text("SELECT 1"))
        db.close()
        return True, "Database connected", ""
    except Exception:
        return False, "Database connection failed", "Check database configuration"


def _check_migrations() -> tuple[bool, str, str]:
    """Check that database tables exist (proxy for migrations applied)."""
    try:
        db = _get_session()
        # If we can query the profiles table, migrations have been applied
        db.execute(text("SELECT COUNT(*) FROM profiles"))
        db.close()
        return True, "Migrations applied", ""
    except Exception:
        return (
            False,
            "Migrations not applied",
            "Run `alembic upgrade head` to apply database migrations",
        )


def _check_profile_exists() -> tuple[bool, str, str]:
    """Check default profile exists."""
    try:
        db = _get_session()
        profile = db.query(Profile).filter(Profile.id == 1).first()
        db.close()
        if profile:
            return True, f"Default profile: {profile.name}", ""
        return False, "No default profile", "Run `kestrel init` to create your profile"
    except Exception:
        return False, "Profile check failed", "Run `kestrel init` to create your profile"


def _check_demo_data() -> tuple[bool, str, str]:
    """Check if demo data is present. Auto-seeds if missing (D-03)."""
    try:
        from career_os.migration.demo_seed import seed_demo_data
        from career_os.models.models import Application, Profile

        db = _get_session()
        demo_count = db.query(Application).filter(Application.is_demo.is_(True)).count()
        if demo_count > 0:
            db.close()
            return True, f"Demo data present ({demo_count} jobs)", ""

        # D-03: Auto-fix -- seed demo data
        profile = db.query(Profile).first()
        if profile:
            count = seed_demo_data(db, profile_id=profile.id)
            db.close()
            return True, f"Demo data restored ({count} jobs)", ""

        db.close()
        return False, "Demo data missing (no profile)", "Run `kestrel init` first"
    except Exception:
        return False, "Demo data check failed", "Run `kestrel init` to set up"


_CHECKS = [
    ("Python version", _check_python_version),
    ("Database connection", _check_db_connection),
    ("Migrations", _check_migrations),
    ("Default profile", _check_profile_exists),
    ("Demo data", _check_demo_data),
]


def doctor() -> None:
    """Run local health checks and display a pass/fail checklist."""
    console.print("\n[bold]Kestrel Doctor[/bold] -- Health Check\n")

    passed = 0
    total = len(_CHECKS)
    any_failed = False

    for _name, check_fn in _CHECKS:
        try:
            ok, label, resolution = check_fn()
        except Exception:
            ok = False
            label = f"{_name} check error"
            resolution = "An unexpected error occurred"

        if ok:
            console.print(f"  [green]check[/green] {label}")
            passed += 1
        else:
            console.print(f"  [red]X[/red] {label}")
            if resolution:
                console.print(f"        {resolution}")
            any_failed = True

    console.print(f"\n  {passed}/{total} checks passed\n")

    if any_failed:
        raise typer.Exit(code=1)
