"""Verify that npm dependencies have no known vulnerabilities.

This test runs `npm audit` against all package directories and fails
if any high or critical severity vulnerability is found.
"""

import json
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

NPM_DIRS = [
    PROJECT_ROOT / "frontend",
    PROJECT_ROOT / "worker",
    PROJECT_ROOT / "dashboard",
]


@pytest.mark.parametrize("pkg_dir", NPM_DIRS, ids=lambda p: p.name)
def test_npm_audit_no_high_or_critical(pkg_dir: Path):
    """Run npm audit and assert zero high/critical vulnerabilities."""
    if not (pkg_dir / "package-lock.json").exists():
        pytest.skip(f"No package-lock.json in {pkg_dir.name}")

    result = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=str(pkg_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )

    audit = json.loads(result.stdout)
    vulns = audit.get("metadata", {}).get("vulnerabilities", {})
    high = vulns.get("high", 0)
    critical = vulns.get("critical", 0)

    assert high + critical == 0, (
        f"{pkg_dir.name}: {high} high + {critical} critical vulnerabilities found. "
        f"Run `npm audit --prefix {pkg_dir}` for details."
    )
