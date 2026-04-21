"""Unit tests for .claude/hooks/check-trivial-assertions.py hook script."""

import importlib.util
import tempfile
from pathlib import Path

# Load module with hyphens in filename via importlib
_spec = importlib.util.spec_from_file_location(
    "check_trivial_assertions",
    Path(__file__).parent.parent / ".claude" / "hooks" / "check-trivial-assertions.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
check_file = _mod.check_file


class TestCheckFile:
    """Tests for check_file() function."""

    def _write_temp(self, content: str) -> str:
        """Write content to a temp file and return path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            return f.name

    def test_detects_assert_true(self):
        path = self._write_temp("def test_x():\n    assert True\n")
        violations = check_file(path)
        assert len(violations) == 1
        assert "assert True/False" in violations[0][2]

    def test_detects_assert_false(self):
        path = self._write_temp("def test_x():\n    assert False\n")
        violations = check_file(path)
        assert len(violations) == 1
        assert "assert True/False" in violations[0][2]

    def test_detects_bare_is_not_none(self):
        path = self._write_temp("def test_x():\n    assert result is not None\n")
        violations = check_file(path)
        assert len(violations) == 1
        assert "is-not-None" in violations[0][2]

    def test_ignores_noqa_suppressed_line(self):
        path = self._write_temp("def test_x():\n    assert True  # noqa: KTEST001\n")
        violations = check_file(path)
        assert len(violations) == 0

    def test_no_violations_in_clean_file(self):
        path = self._write_temp(
            "def test_x():\n    assert result == 42\n    assert name == 'foo'\n"
        )
        violations = check_file(path)
        assert len(violations) == 0

    def test_compound_assertion_not_flagged(self):
        """assert x is not None and x.value == 5 is NOT bare (has more on the line)."""
        path = self._write_temp("def test_x():\n    assert result is not None and result > 0\n")
        violations = check_file(path)
        assert len(violations) == 0

    def test_handles_nonexistent_file(self):
        violations = check_file("/nonexistent/path/file.py")
        assert len(violations) == 0

    def test_returns_correct_line_numbers(self):
        content = "# comment\ndef test_x():\n    x = 1\n    assert True\n"
        path = self._write_temp(content)
        violations = check_file(path)
        assert len(violations) == 1
        assert violations[0][1] == 4  # line 4

    def test_multiple_violations_in_one_file(self):
        content = "def test_a():\n    assert True\ndef test_b():\n    assert result is not None\n"
        path = self._write_temp(content)
        violations = check_file(path)
        assert len(violations) == 2
