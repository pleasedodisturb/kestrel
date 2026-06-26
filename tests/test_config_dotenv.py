"""Tests for the .env backfill in career_os.config (G-1217, ported from Eyas).

config.py calls load_dotenv(override=False) at import so that .env values land
in os.environ even for consumers that read os.getenv directly (e.g. the tools/
pipeline) rather than as pydantic Settings fields — without clobbering real
environment variables set by tests, CI, or containers.
"""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch


def test_config_calls_load_dotenv_with_override_false():
    """Reimporting config invokes load_dotenv(override=False) exactly once."""
    import career_os.config as cfg

    # Patch the source (dotenv.load_dotenv) so the module's
    # `from dotenv import load_dotenv` binds the mock on reload.
    with patch("dotenv.load_dotenv") as mock_ld:
        importlib.reload(cfg)
        mock_ld.assert_called_once_with(override=False)

    # Restore real module state for any later tests in the session.
    importlib.reload(cfg)


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
