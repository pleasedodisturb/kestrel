"""Verify that npm dependencies have no known vulnerabilities.

This test runs `npm audit` against all package directories and fails if any
high or critical severity advisory is found, unless the advisory is in the
ALLOWLIST below with a documented not-applicable rationale.
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
    PROJECT_ROOT / "extension",
]

# Advisories assessed as not-applicable, scoped per package dir so a masked
# advisory here never hides the same advisory somewhere a fix exists. Every
# entry MUST carry: the GHSA id, why it does not apply, and when to re-review.
# Remove an entry as soon as a forward-patched version exists.
ALLOWLIST: dict[str, dict[str, str]] = {
    "frontend": {
        # react-router "RSC Mode CSRF Bypass" — affects 7.12.0-8.2.0 with NO
        # forward patch (npm audit's only "fix" is a downgrade to 7.11.0).
        # The vulnerable code path is React Server Components / server
        # actions; this frontend is a plain Vite SPA on BrowserRouter (zero
        # RSC usage, verified G-1412 2026-07-27). Re-review when react-router
        # publishes a forward patch; then bump and drop this entry.
        "GHSA-qwww-vcr4-c8h2": "RSC-mode only; non-RSC BrowserRouter SPA (G-1412)",
    },
    "extension": {
        # brace-expansion unbounded-expansion DoS via wxt -> web-ext-run ->
        # multimatch -> minimatch@3 -> brace-expansion@1.x. Only patched
        # version is 5.0.8 (no 1.x backport); forcing 5.0.8 under minimatch@3
        # breaks its CJS API (verified: "expand is not a function",
        # G-1412 2026-07-27). Dev-time build tooling only, glob input is our
        # own config — not attacker-reachable. Re-review when web-ext-run or
        # multimatch move to minimatch >= 10.0.3.
        "GHSA-mh99-v99m-4gvg": "no-fix-available; dev-only wxt chain, self-controlled globs (G-1412)",
    },
}


def _advisories(audit: dict) -> dict[str, str]:
    """Extract {GHSA id: 'severity pkg title'} for high/critical advisories.

    npm audit --json nests advisory objects in each package's `via` list;
    transitive entries are plain strings referencing the parent package, so
    counting unique advisory ids (not per-package totals) avoids double
    counting one advisory across its dependents.
    """
    found: dict[str, str] = {}
    for pkg, info in audit.get("vulnerabilities", {}).items():
        for via in info.get("via", []):
            if not isinstance(via, dict):
                continue
            if via.get("severity") not in ("high", "critical"):
                continue
            ghsa = (via.get("url") or "").rsplit("/", 1)[-1] or f"unknown:{pkg}"
            found[ghsa] = f"{via.get('severity')} {pkg}: {via.get('title')}"
    return found


@pytest.mark.parametrize("pkg_dir", NPM_DIRS, ids=lambda p: p.name)
def test_npm_audit_no_high_or_critical(pkg_dir: Path):
    """Run npm audit and assert zero non-allowlisted high/critical advisories."""
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
    found = _advisories(audit)
    allowed = ALLOWLIST.get(pkg_dir.name, {})
    actionable = {g: desc for g, desc in found.items() if g not in allowed}

    assert not actionable, (
        f"{pkg_dir.name}: non-allowlisted high/critical advisories: {actionable}. "
        f"Run `npm audit --prefix {pkg_dir}` for details; fix, or add a "
        f"documented not-allowlisted entry to ALLOWLIST in this file."
    )
