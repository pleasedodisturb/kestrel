"""Unit tests for .claude/hooks/check-test-assertions.py hook script."""

import importlib.util
import tempfile
from pathlib import Path

# Load module with hyphens in filename via importlib
_spec = importlib.util.spec_from_file_location(
    "check_test_assertions",
    Path(__file__).parent.parent / ".claude" / "hooks" / "check-test-assertions.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
count_assertions = _mod.count_assertions


class TestCountAssertions:
    """Tests for count_assertions() function."""

    def _write_temp(self, content: str) -> str:
        """Write content to a temp file and return path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            return f.name

    def test_counts_single_assertion(self):
        path = self._write_temp("def test_x():\n    assert 1 == 1\n")
        counts = count_assertions(path)
        assert "test_x" in counts
        assert counts["test_x"] == 1

    def test_counts_multiple_assertions(self):
        path = self._write_temp(
            "def test_x():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n"
        )
        counts = count_assertions(path)
        assert counts["test_x"] == 3

    def test_counts_zero_assertions(self):
        path = self._write_temp("def test_x():\n    pass\n")
        counts = count_assertions(path)
        assert counts["test_x"] == 0

    def test_ignores_non_test_functions(self):
        path = self._write_temp(
            "def helper():\n    assert True\ndef test_x():\n    assert 1 == 1\n"
        )
        counts = count_assertions(path)
        assert "helper" not in counts
        assert counts == {"test_x": 1}

    def test_handles_multiple_test_functions(self):
        content = (
            "def test_a():\n    assert 1 == 1\n\n"
            "def test_b():\n    assert 2 == 2\n    assert 3 == 3\n"
        )
        path = self._write_temp(content)
        counts = count_assertions(path)
        assert counts == {"test_a": 1, "test_b": 2}

    def test_handles_async_test_functions(self):
        path = self._write_temp("async def test_async():\n    assert 1 == 1\n    assert 2 == 2\n")
        counts = count_assertions(path)
        assert "test_async" in counts
        assert counts["test_async"] == 2

    def test_handles_syntax_error(self):
        path = self._write_temp("def test_x(\n    broken syntax\n")
        counts = count_assertions(path)
        assert counts == {}

    def test_handles_nonexistent_file(self):
        counts = count_assertions("/nonexistent/path/file.py")
        assert counts == {}

    def test_handles_empty_file(self):
        path = self._write_temp("")
        counts = count_assertions(path)
        assert counts == {}
