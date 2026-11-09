"""MAP-05 protective golden: AI credentials survive the full forward migration chain.

Phase 11 (Map), requirement MAP-05, decision D-10. Cut A deletes rows from the
shared ``integration_configs`` table by name, and the factory's credential read
(``career_os.ai.factory._read_credential_from_db``) swallows every error into an
empty string. A migration that emptied the AI credentials would therefore surface
only as a misleading "API key is required" error. These tests seed an
``ai_providers`` row at the revision that creates the table, upgrade to head, and
read the key back through the real reader and the real factory.

The autouse ``hermetic_db_credentials`` fixture in ``tests/conftest.py`` replaces
the reader with a stub that returns an empty string. ``REAL_READ`` is captured at
import time, before any fixture runs, and the ``migrated_db`` fixture restores it,
so these tests cannot pass vacuously through the stub.

Seeding uses raw SQL only: ``services.integrations.update_integration`` runs a live
connection test when credentials are set.
"""

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

import career_os
from career_os.ai import factory
from career_os.config import settings

# Captured at import, before the autouse fixture patches the module attribute.
REAL_READ = factory._read_credential_from_db

PKG_DIR = Path(career_os.__file__).resolve().parent
SEED_REVISION = "f7a8b9c0d1e2"
# No provider prefix and low entropy, so secret scanners have nothing to match.
FAKE_KEY = "unit-test-not-a-real-key-0001"

SEEDED = ("ai_providers", "ticktick", "calendar", "pushover", "voice", "timingsapp")
# Cut A changes this constant deliberately when it deletes a row by name.
EXPECTED_SURVIVORS = frozenset({"ai_providers", "ticktick", "calendar", "pushover", "voice"})
DELETED_BY_CHAIN = frozenset({"timingsapp"})


def _cfg(url: str) -> Config:
    """Programmatic Alembic config; never the ini file (its fileConfig() disables loggers)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(PKG_DIR / "_alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _names(db: Path) -> list[str]:
    """Return the integration_configs row names in the database."""
    with sqlite3.connect(db) as con:
        rows = con.execute("SELECT name FROM integration_configs ORDER BY name").fetchall()
    con.close()
    return [r[0] for r in rows]


@pytest.fixture
def migrated_db(tmp_path, monkeypatch) -> Path:
    """Seed integration_configs at SEED_REVISION, upgrade to head, point the app at it."""
    db = tmp_path / "map05.db"
    url = f"sqlite:///{db}"
    command.upgrade(_cfg(url), SEED_REVISION)
    con = sqlite3.connect(db)
    try:
        for name in SEEDED:
            creds = (
                {"openrouter_api_key": FAKE_KEY}
                if name == "ai_providers"
                else {"note": "synthetic"}
            )
            con.execute(
                "INSERT INTO integration_configs"
                " (name, display_name, enabled, credentials, status, created_at, updated_at)"
                " VALUES (?, ?, 1, ?, 'connected', datetime('now'), datetime('now'))",
                (name, name, json.dumps(creds)),
            )
        con.commit()
    finally:
        con.close()
    command.upgrade(_cfg(url), "head")
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(factory, "_read_credential_from_db", REAL_READ)
    # Environment wins over the database in _resolve_api_key.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return db


def test_ai_providers_key_survives_upgrade_head(migrated_db):
    """The seeded AI key is readable through the real reader after the full chain."""
    assert factory._read_credential_from_db("openrouter_api_key") == FAKE_KEY
    assert _names(migrated_db).count("ai_providers") == 1


def test_factory_builds_openrouter_with_the_seeded_key(migrated_db):
    """The factory resolves the stored key into a real provider instance."""
    provider = factory.get_ai_provider("openrouter")
    assert type(provider).__name__ == "OpenRouterProvider"
    assert provider._api_key == FAKE_KEY


def test_integration_rows_after_head(migrated_db):
    """Only the expected rows survive; the chain's own delete proves it ran over the seed."""
    names = set(_names(migrated_db))
    assert names == EXPECTED_SURVIVORS
    assert DELETED_BY_CHAIN.isdisjoint(names)


def test_seed_revision_is_meaningful(tmp_path):
    """The seed revision creates the table, and the chain has exactly one head."""
    db = tmp_path / "seed.db"
    command.upgrade(_cfg(f"sqlite:///{db}"), SEED_REVISION)
    with sqlite3.connect(db) as con:
        found = con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'integration_configs'"
        ).fetchall()
    con.close()
    heads = ScriptDirectory.from_config(_cfg(f"sqlite:///{db}")).get_heads()
    assert found == [("integration_configs",)]
    assert len(heads) == 1


def test_missing_ai_providers_row_reads_empty(migrated_db):
    """Documents today's silent failure: no row reads as an empty key, then the factory raises.

    FOUND-09 turns the silent swallow into a logged warning; this asserts only the
    return value and the raise, never log text.
    """
    con = sqlite3.connect(migrated_db)
    try:
        con.execute("DELETE FROM integration_configs WHERE name = 'ai_providers'")
        con.commit()
    finally:
        con.close()
    assert "ai_providers" not in _names(migrated_db)
    assert factory._read_credential_from_db("openrouter_api_key") == ""
    with pytest.raises(ValueError):
        factory.get_ai_provider("openrouter")
