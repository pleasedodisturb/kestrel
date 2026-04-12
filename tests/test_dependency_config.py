"""Tests for dependency management configuration files (G-246).

Validates that the config files introduced for automated dependency
tracking are well-formed and follow project conventions.
"""

import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# G-247: Renovate Bot configuration
# ---------------------------------------------------------------------------


class TestRenovateConfig:
    """Validate renovate.json structure and policy."""

    @pytest.fixture()
    def config(self):
        with open(PROJECT_ROOT / "renovate.json") as f:
            return json.load(f)

    def test_renovate_json_is_valid_json(self):
        """renovate.json parses without error."""
        with open(PROJECT_ROOT / "renovate.json") as f:
            json.load(f)

    def test_extends_recommended(self, config):
        assert "config:recommended" in config.get("extends", [])

    def test_has_schedule(self, config):
        assert "schedule" in config
        assert len(config["schedule"]) > 0

    def test_has_timezone(self, config):
        assert config.get("timezone") == "Europe/Berlin"

    def test_has_package_rules(self, config):
        rules = config.get("packageRules", [])
        assert len(rules) >= 2, "Need at least Python and Node rules"

    def test_major_updates_not_automerged(self, config):
        """Major version bumps must require manual review."""
        major_rules = [
            r for r in config.get("packageRules", []) if "major" in r.get("matchUpdateTypes", [])
        ]
        assert len(major_rules) > 0, "No rule for major updates"
        for rule in major_rules:
            assert rule.get("automerge") is False, "Major updates must not automerge"

    def test_pr_concurrent_limit(self, config):
        limit = config.get("prConcurrentLimit", 999)
        assert limit <= 10, "PR flood protection: limit should be reasonable"

    def test_ignores_legacy_requirements_txt(self, config):
        ignored = config.get("ignorePaths", [])
        assert "requirements.txt" in ignored, (
            "requirements.txt is legacy — Renovate should ignore it"
        )


# ---------------------------------------------------------------------------
# G-248: Socket.dev configuration
# ---------------------------------------------------------------------------


class TestSocketConfig:
    """Validate .socket.yml structure and policy."""

    @pytest.fixture()
    def config(self):
        with open(PROJECT_ROOT / ".socket.yml") as f:
            return yaml.safe_load(f)

    def test_socket_yml_is_valid_yaml(self):
        with open(PROJECT_ROOT / ".socket.yml") as f:
            yaml.safe_load(f)

    def test_has_issue_rules(self, config):
        assert "issueRules" in config

    def test_typosquatting_is_error(self, config):
        assert config["issueRules"].get("typosquatting") == "error"

    def test_install_scripts_is_error(self, config):
        assert config["issueRules"].get("installScripts") == "error"

    def test_protestware_is_error(self, config):
        assert config["issueRules"].get("protestware") == "error"

    def test_github_app_enabled(self, config):
        app = config.get("githubApp", {})
        assert app.get("enabled") is True
        assert app.get("pullRequestAlertsEnabled") is True


# ---------------------------------------------------------------------------
# G-249: pip-audit-ignore
# ---------------------------------------------------------------------------


class TestPipAuditIgnore:
    """Validate .pip-audit-ignore file."""

    def test_file_exists(self):
        assert (PROJECT_ROOT / ".pip-audit-ignore").exists()

    def test_entries_have_comments(self):
        """Every non-empty, non-comment line should have a trailing comment."""
        with open(PROJECT_ROOT / ".pip-audit-ignore") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                assert "#" in stripped, (
                    f"Entry '{stripped.split()[0]}' should have a comment "
                    "explaining why it's suppressed"
                )


# ---------------------------------------------------------------------------
# G-250: python-jobspy compatibility
# ---------------------------------------------------------------------------


class TestJobSpyCompat:
    """Verify python-jobspy import and API surface."""

    def test_scrape_jobs_importable(self):
        from jobspy import scrape_jobs  # noqa: F401

    def test_scrape_jobs_signature_has_required_params(self):
        import inspect

        from jobspy import scrape_jobs

        params = list(inspect.signature(scrape_jobs).parameters.keys())
        for required in ("site_name", "search_term", "location", "results_wanted"):
            assert required in params, f"Missing expected param: {required}"


# ---------------------------------------------------------------------------
# G-249: CI workflow structure
# ---------------------------------------------------------------------------


class TestCIWorkflow:
    """Validate CI workflow has required security steps."""

    @pytest.fixture()
    def ci_content(self):
        ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        return ci_path.read_text()

    def test_pip_audit_step_exists(self, ci_content):
        assert "pip-audit" in ci_content

    def test_npm_audit_step_exists(self, ci_content):
        assert "npm audit" in ci_content

    def test_npm_audit_signatures_step_exists(self, ci_content):
        assert "npm audit signatures" in ci_content

    def test_pii_check_step_exists(self, ci_content):
        assert "PII" in ci_content or "pii" in ci_content.lower()
