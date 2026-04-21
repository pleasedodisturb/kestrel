#!/usr/bin/env python3
"""Claude Code Stop hook: enforce minimum assertions per test function.

Checks staged test files and rejects if any test function has fewer than
2 assert statements. This is an agent-specific constraint (D-09) that
ensures Claude doesn't write shallow tests.

Exit code 2 = violations found (blocks Claude Code Stop event).
Exit code 0 = all clear.
"""

import ast
import subprocess
import sys


def get_staged_test_files():
    """Get test files that are staged for commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [
        f
        for f in result.stdout.strip().split("\n")
        if f and f.startswith("tests/") and f.endswith(".py") and "test_" in f
    ]


def count_assertions(filepath):
    """Count assert statements per test function in a file."""
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        return {}

    results = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            count = sum(1 for child in ast.walk(node) if isinstance(child, ast.Assert))
            results[node.name] = count
    return results


def main():
    """Entry point -- check staged test files for assertion minimums."""
    test_files = get_staged_test_files()

    # Fast path: no staged test files, nothing to check
    if not test_files:
        sys.exit(0)

    violations = []
    for filepath in test_files:
        counts = count_assertions(filepath)
        for func_name, count in counts.items():
            if count < 2:
                violations.append(
                    f"  {filepath}::{func_name} has {count} assertion(s), minimum is 2"
                )

    if violations:
        print("Test assertion count violations:", file=sys.stderr)
        print("", file=sys.stderr)
        for v in violations:
            print(v, file=sys.stderr)
        print("", file=sys.stderr)
        print(
            f"Found {len(violations)} test function(s) with fewer than 2 assertions.",
            file=sys.stderr,
        )
        print("Fix: Add meaningful assertions that verify behavior.", file=sys.stderr)
        sys.exit(2)  # Exit code 2 blocks the Stop event

    sys.exit(0)


if __name__ == "__main__":
    main()
