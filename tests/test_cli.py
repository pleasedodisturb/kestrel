"""Tests for the Typer CLI skeleton."""

from typer.testing import CliRunner

from career_os.cli.main import app

runner = CliRunner()


def test_career_help() -> None:
    """career --help exits 0 and shows help text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Career OS" in result.output


def test_pipeline_subcommand_present() -> None:
    """career --help lists pipeline as a subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pipeline" in result.output


def test_pipeline_help() -> None:
    """career pipeline --help exits 0 and shows pipeline commands."""
    result = runner.invoke(app, ["pipeline", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "add" in result.output
    assert "update" in result.output
    assert "stats" in result.output
    assert "follow-ups" in result.output


def test_pipeline_list() -> None:
    """career pipeline list exits 0."""
    result = runner.invoke(app, ["pipeline", "list"])
    assert result.exit_code == 0


def test_pipeline_stats() -> None:
    """career pipeline stats exits 0."""
    result = runner.invoke(app, ["pipeline", "stats"])
    assert result.exit_code == 0


def test_pipeline_follow_ups() -> None:
    """career pipeline follow-ups exits 0."""
    result = runner.invoke(app, ["pipeline", "follow-ups"])
    assert result.exit_code == 0
    assert "caught up" in result.output.lower() or "follow" in result.output.lower()
