"""Tests for dependency management configuration files (G-246).

Validates that the config files introduced for automated dependency
tracking are well-formed and follow project conventions.
"""

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# G-1277: Dependabot is the single update bot (Renovate removed — the app
# was never installed, so renovate.json was dead config)
# ---------------------------------------------------------------------------


class TestDependabotConfig:
    """Validate .github/dependabot.yml structure and policy."""

    @pytest.fixture()
    def config(self):
        with open(PROJECT_ROOT / ".github" / "dependabot.yml") as f:
            return yaml.safe_load(f)

    def test_renovate_config_is_gone(self):
        """renovate.json must not resurface — Dependabot is the single bot."""
        assert not (PROJECT_ROOT / "renovate.json").exists(), (
            "renovate.json found — removed in G-1277 because the Renovate app "
            "was never installed; keep Dependabot as the single update bot"
        )

    def test_dependabot_yml_is_valid_yaml(self):
        with open(PROJECT_ROOT / ".github" / "dependabot.yml") as f:
            yaml.safe_load(f)

    def test_covers_all_ecosystems(self, config):
        """pip, npm, github-actions and docker must all get update PRs."""
        ecosystems = {u["package-ecosystem"] for u in config["updates"]}
        assert {"pip", "npm", "github-actions", "docker"} <= ecosystems

    def test_pr_flood_protection(self, config):
        for update in config["updates"]:
            limit = update.get("open-pull-requests-limit", 5)
            assert limit <= 10, f"{update['package-ecosystem']}: PR limit {limit} too high"

    def test_runtime_version_guards(self, config):
        """Runtime images must not auto-bump (G-1288: python 3.14 slipped
        through automerge as a semver-minor). Policy from retired
        renovate.json: Python 3.11, Node 22 LTS — upgrades are deliberate."""
        docker = next(u for u in config["updates"] if u["package-ecosystem"] == "docker")
        ignored = {i["dependency-name"] for i in docker.get("ignore", [])}
        assert {"python", "node"} <= ignored, (
            "docker ecosystem must ignore python/node runtime bumps"
        )
        npm = next(u for u in config["updates"] if u["package-ecosystem"] == "npm")
        npm_ignored = {i["dependency-name"] for i in npm.get("ignore", [])}
        assert "@types/node" in npm_ignored, "@types/node majors must track the pinned Node runtime"

    def test_dockerfile_runtime_is_python_311(self):
        """The runtime base image tracks the project's pinned Python.

        Accepts an optional @sha256 digest pin (G-1412 supply-chain
        hardening) — the policy being guarded is the 3.11-slim tag itself.
        """
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
        assert re.search(
            r"^FROM python:3\.11-slim(@sha256:[0-9a-f]{64})? AS runtime$",
            dockerfile,
            flags=re.MULTILINE,
        ), (
            "Runtime image must stay on python:3.11-slim until the deliberate "
            "upgrade ticket (G-1289) lands"
        )


class TestAutomergeWorkflow:
    """Validate the Dependabot automerge workflow policy (G-1277)."""

    @pytest.fixture()
    def content(self):
        path = PROJECT_ROOT / ".github" / "workflows" / "dependabot-automerge.yml"
        return path.read_text()

    @pytest.fixture()
    def config(self):
        path = PROJECT_ROOT / ".github" / "workflows" / "dependabot-automerge.yml"
        with open(path) as f:
            return yaml.safe_load(f)

    def test_gates_on_pr_author_not_actor(self, config):
        """Must gate on the PR author (event payload), not spoofable actor."""
        condition = config["jobs"]["automerge"]["if"]
        assert "github.event.pull_request.user.login" in condition
        assert "github.actor" not in condition, (
            "github.actor reflects the run trigger (spoofable) — zizmor bot-conditions"
        )

    def test_only_patch_and_minor_automerge(self, content):
        """Major version bumps must never be auto-merged."""
        assert "semver-patch" in content
        assert "semver-minor" in content
        assert "semver-major" not in content, "Major bumps must stay manual — most likely to break"

    def test_uses_auto_flag_so_ci_gates_merge(self, content):
        """--auto defers the merge until required status checks pass."""
        assert "--auto" in content


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
