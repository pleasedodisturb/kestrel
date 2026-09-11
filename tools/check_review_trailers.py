#!/usr/bin/env python3
"""Verify that every PR commit's Reviewed-by trailer is bound to its own diff (G-1726).

The local pre-push gate (terminal-craft ``review-push``) stores a reviewer record
per ``git patch-id`` and signs each commit with::

    Reviewed-by: <reviewer> patch:<12 hex of git patch-id --verbatim> run:<id>

CI cannot see the local record, but it can check the binding: the ``patch:``
value must equal the patch-id of the commit it sits on, computed with the same
algorithm and the same pinned diff options as the signer (``--verbatim``, so
whitespace counts; see ``DIFF_ARGS``). That catches a trailer copied from
another commit, a commit amended after it was signed, and a commit pushed with
no trailer from any path the local hook does not cover (cloud runs, other
machines).

Empty commits have no diff and are skipped. Merge commits are refused: their own
diff is empty too, but a conflict resolution can carry code that neither parent
had and no reviewer saw. PR branches are rebased, not merged into.

Usage::

    python tools/check_review_trailers.py <base>..<head>
    python tools/check_review_trailers.py --base <sha> --head <sha>

Exit 1 with one line per offending commit; exit 0 when every checked commit is bound.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PATCH_TOKEN_RE = re.compile(r"\bpatch:([0-9a-f]{12,40})\b")

# Byte-identical diff on the signer's machine and here, whatever the local git
# config says. KEEP IN SYNC with terminal-craft scripts/hooks/review-push.
DIFF_ARGS = [
    "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
    "-c", "diff.suppressBlankEmpty=false", "-c", "core.quotePath=true",
    "diff-tree", "-p", "--root", "--no-commit-id", "--no-color", "--no-ext-diff",
    "--no-textconv", "--no-renames", "--diff-algorithm=myers", "-U3",
    "--inter-hunk-context=0", "--indent-heuristic", "--full-index",
]  # fmt: skip


def _git(*args: str, cwd: Path | None = None, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True, input=stdin
    ).stdout


def is_merge(sha: str, cwd: Path | None = None) -> bool:
    return len(_git("rev-list", "--parents", "-n", "1", sha, cwd=cwd).split()) > 2


def patch_id(sha: str, cwd: Path | None = None) -> str:
    """Content identity of a commit's diff; '' for merges and empty commits.

    ``--verbatim`` (git >= 2.39), not ``--stable``: the default patch-id ignores
    whitespace, so a signed commit could be amended by dedenting a line out of
    an ``if`` and keep its id. Whitespace is content here. Must match the
    algorithm ``review-push`` uses to sign.
    """
    if is_merge(sha, cwd):
        return ""
    diff = _git(*DIFF_ARGS, sha, cwd=cwd)
    if not diff.strip():
        return ""
    out = _git("patch-id", "--verbatim", cwd=cwd, stdin=diff).strip()
    return out.split()[0] if out else ""


def trailer_patch_tokens(sha: str, cwd: Path | None = None) -> list[str]:
    out = _git("log", "-1", "--format=%(trailers:key=Reviewed-by,valueonly)", sha, cwd=cwd)
    return [tok for line in out.splitlines() for tok in PATCH_TOKEN_RE.findall(line)]


def check_commits(
    commits: list[str], cwd: Path | None = None, exempt: set[str] | None = None
) -> list[str]:
    """Return one problem line per commit whose trailer is missing or names another diff.

    ``exempt`` holds full SHAs the caller has established were produced by a
    bot (in CI: GitHub attributes the author to a Bot account AND the commit is
    GitHub-verified, so a forged author email does not qualify). The exemption
    is per commit, not per PR: a human commit pushed onto a Dependabot branch
    is still checked.
    """
    problems: list[str] = []
    exempt = exempt or set()
    for sha in commits:
        subject = _git("log", "-1", "--format=%s", sha, cwd=cwd).strip()
        if is_merge(sha, cwd):
            # A merge has no diff of its own to bind, and a conflict resolution
            # can introduce code that exists in neither parent and that no
            # reviewer saw. Refuse rather than skip; rebase gives every change
            # a normal, signable commit. Checked BEFORE the bot exemption: a
            # merge is refused whoever made it.
            problems.append(
                f"{sha[:10]} {subject}: merge commit in the PR range -- a conflict resolution "
                f"would bypass review; rebase onto the base branch instead"
            )
            continue
        if sha in exempt:
            print(f"  exempt (verified bot commit): {sha[:10]} {subject}")
            continue
        pid = patch_id(sha, cwd)
        if not pid:
            continue  # empty commit: nothing to review
        tokens = trailer_patch_tokens(sha, cwd)
        if not tokens:
            problems.append(f"{sha[:10]} {subject}: no Reviewed-by trailer with a patch: field")
        elif not any(pid.startswith(tok) for tok in tokens):
            problems.append(
                f"{sha[:10]} {subject}: trailer names patch:{tokens[-1][:12]} but the diff is "
                f"patch:{pid[:12]} (amended after review, or copied trailer)"
            )
    return problems


def check_range(spec: str, cwd: Path | None = None, exempt: set[str] | None = None) -> list[str]:
    commits = _git("rev-list", "--reverse", spec, cwd=cwd).split()
    return check_commits(commits, cwd, exempt)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("range", nargs="?", help="rev range, e.g. origin/main..HEAD")
    ap.add_argument("--base")
    ap.add_argument("--head")
    ap.add_argument(
        "--exempt",
        nargs="*",
        default=[],
        metavar="SHA",
        help="full SHAs of commits GitHub attributes to a verified bot; skipped",
    )
    args = ap.parse_args(argv)
    if args.base and args.head:
        spec = f"{args.base}..{args.head}"
    elif args.range:
        spec = args.range
    else:
        ap.error("give a range or --base/--head")
    problems = check_range(spec, exempt=set(args.exempt))
    if problems:
        print("Reviewed-by trailers not bound to their commits:")
        for p in problems:
            print(f"  - {p}")
        print(
            "\nSign with `review-push sign` (terminal-craft, G-1725); it binds the trailer to "
            "the commit's git patch-id, so amend-after-review and copied trailers fail here."
        )
        return 1
    print(f"review trailers OK for {spec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
