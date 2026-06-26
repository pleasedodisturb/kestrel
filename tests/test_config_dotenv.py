"""Tests for the .env backfill in career_os.config (G-1217, ported from Eyas).

config.py calls load_dotenv(override=False) at import so that .env values land
in os.environ even for consumers that read os.getenv directly (e.g. the tools/
pipeline) rather than as pydantic Settings fields — without clobbering real
environment variables set by tests, CI, or containers.

These tests deliberately avoid importlib.reload(career_os.config): reloading
the module rebuilds the global `settings` singleton and desyncs it from every
module that did `from career_os.config import settings`, which silently breaks
unrelated tests (e.g. preset propagation). The import-time wiring is verified
statically instead; the override=False contract is verified behaviorally.
"""

from __future__ import annotations

import inspect
import os


def test_config_wires_load_dotenv_with_override_false():
    """config.py calls load_dotenv(override=False) at import (static check)."""
    import career_os.config as cfg

    # load_dotenv is imported into the module namespace...
    assert hasattr(cfg, "load_dotenv")
    # ...and invoked with override=False at import time.
    source = inspect.getsource(cfg)
    assert "load_dotenv(override=False)" in source


def test_override_false_respects_existing_env(tmp_path, monkeypatch):
    """The override=False contract: a real env var wins over the .env value."""
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("KESTREL_TEST_DOTENV_VAR=from_file\n")
    monkeypatch.setenv("KESTREL_TEST_DOTENV_VAR", "from_env")

    load_dotenv(env_file, override=False)

    assert os.environ["KESTREL_TEST_DOTENV_VAR"] == "from_env"


def test_override_false_backfills_missing_env(tmp_path, monkeypatch):
    """When the var is absent from the environment, the .env value backfills it."""
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("KESTREL_TEST_DOTENV_BACKFILL=from_file\n")
    monkeypatch.delenv("KESTREL_TEST_DOTENV_BACKFILL", raising=False)

    load_dotenv(env_file, override=False)

    assert os.environ["KESTREL_TEST_DOTENV_BACKFILL"] == "from_file"
