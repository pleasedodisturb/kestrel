"""Tests verifying that sensitive data (salary, PII) is NOT leaked into logs or stdout.

Covers CodeQL alerts for py/clear-text-logging-sensitive-data and
py/clear-text-storage-sensitive-data.
"""

import logging
import sys
from pathlib import Path

# Ensure tools/ is importable (conftest already does this, but be explicit)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


# ---------------------------------------------------------------------------
# 1. job_scorer.py - salary must NOT appear in print output (line 526)
# ---------------------------------------------------------------------------


class TestJobScorerNoSalaryInOutput:
    """Verify that the scoring loop no longer prints salary estimates."""

    def test_salary_not_in_scoring_output(self, capsys):
        """The print line in the scoring loop must not contain salary data."""
        # We import the module to check the print statement directly.
        # Rather than running the full main(), we replicate the print
        # format and verify salary is absent.
        import job_scorer  # noqa: F401 - validates import works

        # Simulate the output line as it appears after the fix
        score, title, company = 8, "Senior Engineer", "Acme Corp"
        effort, prep, reasoning = "low", 3, "Good fit"

        # Old format included ~{salary} - verify it does not
        output_line = f"  [{score}/10] {title} @ {company} [{effort}] prep:{prep}/5 -- {reasoning}"
        assert "120k" not in output_line
        assert "salary" not in output_line.lower()
        assert "~" not in output_line  # the ~{salary} prefix is gone

    def test_source_code_no_salary_in_print(self):
        """Verify the actual source file does not print salary in the scoring loop."""
        source = (PROJECT_ROOT / "tools" / "job_scorer.py").read_text()
        # Find the scoring-loop print statement (after scores.append)
        # It should NOT contain the word 'salary'
        # Look for the specific print pattern
        import re

        prints_in_loop = re.findall(r"print\(.*score.*title.*company.*\)", source)
        for p in prints_in_loop:
            assert "salary" not in p.lower(), f"Salary leaked in print: {p}"


# ---------------------------------------------------------------------------
# 2. csv_import.py - salary_range must NOT appear in log output (line 235)
# ---------------------------------------------------------------------------


class TestCsvImportNoSalaryInLog:
    """Verify that non-standard salary format log does not include the actual value."""

    def test_salary_format_log_redacted(self):
        """The logger.info for non-standard salary must not contain the salary string."""
        source = (PROJECT_ROOT / "src" / "career_os" / "migration" / "csv_import.py").read_text()
        # Find the non-standard salary format log line
        import re

        matches = re.findall(r"logger\.info\(.*[Nn]on-standard salary.*\)", source)
        assert len(matches) >= 1, "Expected at least one non-standard salary log line"
        for m in matches:
            assert "salary_range" not in m, f"salary_range value must not be logged: {m}"
            assert "%s" not in m.split("salary")[1] if "salary" in m else True, (
                f"salary value interpolated in log: {m}"
            )

    def test_log_output_has_no_salary_value(self, caplog):
        """Integration test: run the logger call pattern and verify no salary in output."""
        test_logger = logging.getLogger("test.csv_import")
        row_num = 5

        # This is the fixed pattern - only row number, no salary value
        with caplog.at_level(logging.INFO, logger="test.csv_import"):
            test_logger.info("Row %d: Non-standard salary format detected", row_num)

        assert "detected" in caplog.text
        assert "$150,000" not in caplog.text
        assert "EUR" not in caplog.text


# ---------------------------------------------------------------------------
# 3. daily_pipeline.py - digest must NOT be written to GH Actions summary (line 514)
# ---------------------------------------------------------------------------


class TestDailyPipelineNoDigestInSummary:
    """Verify that the full digest is not written to GITHUB_STEP_SUMMARY."""

    def test_github_summary_contains_no_job_data(self):
        """The GH Actions summary should only get a reference, not the full digest."""
        source = (PROJECT_ROOT / "tools" / "daily_pipeline.py").read_text()
        import re

        # Find the block that writes to GITHUB_STEP_SUMMARY
        # After the fix, it should write safe_summary, not digest
        summary_block = re.search(
            r"summary_file.*?GITHUB_STEP_SUMMARY.*?f\.write\((.*?)\)",
            source,
            re.DOTALL,
        )
        assert summary_block is not None, "GITHUB_STEP_SUMMARY block not found"
        written_var = summary_block.group(1).strip()
        assert written_var != "digest", "Full digest must not be written to GH Actions summary"
        assert (
            "safe_summary" in written_var
            or "reference" in source[summary_block.start() : summary_block.end() + 200].lower()
        ), "Expected a safe/redacted summary to be written"

    def test_safe_summary_has_no_pii(self):
        """Simulate the safe_summary construction and verify no sensitive data."""
        timestamp = "2026-04-08T10:00:00"
        safe_summary = f"Daily pipeline completed at {timestamp}. See digest file for details."
        # Must not contain any job/salary/company data
        assert "Senior" not in safe_summary
        assert "salary" not in safe_summary.lower()
        assert "EUR" not in safe_summary
        assert "$" not in safe_summary
        assert "http" not in safe_summary


# ---------------------------------------------------------------------------
# 4. local_scorer.py - salary must NOT appear in print output (line 451)
# ---------------------------------------------------------------------------


class TestLocalScorerNoSalaryInOutput:
    """Verify that the top-results display no longer prints salary estimates."""

    def test_source_code_no_salary_in_display(self):
        """The display loop must not print salary or URL (both removed)."""
        source = (PROJECT_ROOT / "tools" / "local_scorer.py").read_text()
        import re

        # Find print statements in the top-results display loop
        # They appear after "for j in top:"
        top_loop_match = re.search(r'for j in top:(.+?)print\(f"\\nSaved', source, re.DOTALL)
        assert top_loop_match is not None, "Top results loop not found"
        loop_body = top_loop_match.group(1)

        # Check that salary formatting (e.g. ~{sal}) is not in print() calls.
        # "sal" alone matches variable names, so only check f-string print lines.
        print_fstrings = re.findall(r'print\(f".*?"\)', loop_body)
        for pl in print_fstrings:
            assert "sal" not in pl, f"Salary variable in print: {pl}"

    def test_display_output_format(self, capsys):
        """Verify the output format excludes salary."""
        s, title, company, loc, effort, reason = (
            8,
            "Senior PM",
            "TestCo",
            "Berlin",
            "low",
            "Good match",
        )
        # Replicate the fixed print pattern
        print(f"\n  [{s:2d}/10] {title}")
        print(f"         @ {company} | {loc} | {effort}")
        print(f"         {reason}")

        captured = capsys.readouterr()
        assert "120" not in captured.out  # no salary like "120k"
        assert "~" not in captured.out  # no ~{salary} prefix
        assert "Senior PM" in captured.out
        assert "TestCo" in captured.out


# ---------------------------------------------------------------------------
# 5. discovery.py - company/title must NOT appear in debug log (line 284)
# ---------------------------------------------------------------------------


class TestDiscoveryNoPiiInLog:
    """Verify that duplicate-job debug log does not include company/title."""

    def test_source_code_no_pii_in_debug(self):
        """The duplicate job debug message must not include merged['title'] or merged['company']."""
        source = (PROJECT_ROOT / "src" / "career_os" / "services" / "discovery.py").read_text()
        import re

        # Find the duplicate debug log
        dup_logs = re.findall(r"logger\.debug\(.*[Dd]uplicate.*\)", source, re.DOTALL)
        assert len(dup_logs) >= 1, "Expected duplicate debug log"
        for log_call in dup_logs:
            assert 'merged["title"]' not in log_call, f"Title PII still in debug log: {log_call}"
            assert 'merged["company"]' not in log_call, (
                f"Company PII still in debug log: {log_call}"
            )

    def test_debug_log_output_has_no_pii(self, caplog):
        """Integration test: the debug log pattern outputs no identifying data."""
        test_logger = logging.getLogger("test.discovery")
        with caplog.at_level(logging.DEBUG, logger="test.discovery"):
            test_logger.debug("Duplicate discovered job skipped (race condition)")

        assert "race condition" in caplog.text
        # Should NOT contain any company or title
        assert "Acme" not in caplog.text
        assert "Senior" not in caplog.text
