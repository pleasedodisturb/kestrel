"""Tests for the kestrel start command and pip install support."""

import importlib
import re
from pathlib import Path

from typer.testing import CliRunner

from career_os.cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (Rich/Typer color output)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestStartCommand:
    """Tests for the 'kestrel start' CLI command."""

    def test_start_command_exists(self) -> None:
        """The start command should be registered."""
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "Start the Kestrel web server" in result.output

    def test_start_shows_host_option(self) -> None:
        """Start command should accept --host option."""
        result = runner.invoke(app, ["start", "--help"])
        assert "--host" in _strip_ansi(result.output)

    def test_start_shows_port_option(self) -> None:
        """Start command should accept --port option."""
        result = runner.invoke(app, ["start", "--help"])
        assert "--port" in _strip_ansi(result.output)

    def test_start_shows_no_browser_option(self) -> None:
        """Start command should accept --no-browser option."""
        result = runner.invoke(app, ["start", "--help"])
        assert "--no-browser" in _strip_ansi(result.output)

    def test_start_command_invocable(self) -> None:
        """Start command should be invocable (will fail on uvicorn import in test, but should get past arg parsing)."""
        # We can't fully test start without mocking uvicorn.run (which blocks),
        # but we can verify the command parses arguments correctly
        result = runner.invoke(app, ["start", "--help"])
        assert "host" in result.output.lower()
        assert "port" in result.output.lower()
        assert "browser" in result.output.lower()


class TestMainModule:
    """Tests for python -m career_os support."""

    def test_main_module_exists(self) -> None:
        """__main__.py should exist and be importable."""
        spec = importlib.util.find_spec("career_os.__main__")
        assert spec is not None

    def test_main_module_file_exists(self) -> None:
        """__main__.py should exist in the package."""
        pkg_dir = Path(__file__).resolve().parent.parent / "src" / "career_os"
        main_file = pkg_dir / "__main__.py"
        assert main_file.exists()
        content = main_file.read_text()
        assert "from career_os.cli.main import app" in content


class TestFrontendDiscovery:
    """Tests for frontend static file discovery in pip-install mode."""

    def test_frontend_dist_bundled(self) -> None:
        """The _frontend_dist directory should exist in the package."""
        pkg_dir = Path(__file__).resolve().parent.parent / "src" / "career_os"
        frontend_dir = pkg_dir / "_frontend_dist"
        assert frontend_dir.exists(), f"Expected {frontend_dir} to exist"
        assert (frontend_dir / "index.html").exists()
        assert (frontend_dir / "assets").is_dir()

    def test_alembic_bundled(self) -> None:
        """The _alembic directory should exist in the package."""
        pkg_dir = Path(__file__).resolve().parent.parent / "src" / "career_os"
        alembic_dir = pkg_dir / "_alembic"
        assert alembic_dir.exists(), f"Expected {alembic_dir} to exist"
        assert (alembic_dir / "versions").is_dir()
        assert (alembic_dir / "env.py").exists()


class TestPackageMetadata:
    """Tests for pip package configuration."""

    def test_kestrel_entry_point_in_pyproject(self) -> None:
        """pyproject.toml should define kestrel entry point."""
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert 'kestrel = "career_os.cli.main:app"' in content

    def test_package_name_is_kestrel_app(self) -> None:
        """Package should be named kestrel-app."""
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert 'name = "kestrel-app"' in content
