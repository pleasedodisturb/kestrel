#!/usr/bin/env python3
"""Pre-commit hook: block trivial assertions in test files.

Detects:
- assert True / assert False (completely meaningless)
- Bare assert <expr> is not None (tests existence only, not value)

Respects: # noqa: KTEST001 inline suppression for WIP stubs.
Exit code 1 = violations found (blocks commit).
"""

import re
import sys

PATTERNS = [
    (re.compile(r"^\s*assert\s+(True|False)\b"), "assert True/False is prohibited (RULE-02)"),
    (
        re.compile(r"^\s*assert\s+\w+(?:\.\w+)*(?:\[.*?\])?\s+is\s+not\s+None\s*$"),
        "bare assert-is-not-None is prohibited (RULE-03)",
    ),
]
NOQA = re.compile(r"#\s*noqa:\s*KTEST001")


def check_file(filepath):
    """Check a single file for trivial assertion violations."""
    violations = []
    try:
        with open(filepath) as f:
            for lineno, line in enumerate(f, 1):
                if NOQA.search(line):
                    continue
                for pattern, desc in PATTERNS:
                    if pattern.search(line):
                        violations.append((filepath, lineno, desc, line.rstrip()))
    except (OSError, UnicodeDecodeError):
        pass
    return violations


def main():
    """Entry point -- receives filenames from pre-commit."""
    all_violations = []
    for filepath in sys.argv[1:]:
        all_violations.extend(check_file(filepath))

    if all_violations:
        print("Trivial assertion violations found:\n")
        for path, lineno, desc, line in all_violations:
            print(f"  {path}:{lineno}: {desc}")
            print(f"    {line}\n")
        print(f"Found {len(all_violations)} violation(s).")
        print("Fix: Replace with specific value assertions.")
        print("Escape: Add '# noqa: KTEST001' for WIP stubs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
