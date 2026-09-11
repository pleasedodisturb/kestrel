"""Tests for tools/check_review_trailers.py (G-1726).

Builds a throwaway git repo per test, isolated from the developer's global git
config (no hooksPath, no commit signing), and checks the patch-id binding
matrix: bound trailer passes; missing, copied and amended-after-signing fail;
merge commits are refused, empty commits skipped.
"""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_review_trailers",
    Path(__file__).parent.parent / "tools" / "check_review_trailers.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


@pytest.fixture
def repo(tmp_path: Path):
    (tmp_path / "gitconfig").write_text("")
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str, stdin: str | None = None) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=True,
            input=stdin,
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "commit.gpgsign", "false")

    def commit(name: str, content: str, msg: str, trailer: str | None = None) -> str:
        (root / name).write_text(content)
        git("add", name)
        args = ["commit", "-q", "-m", msg]
        if trailer:
            args += ["--trailer", trailer]
        git(*args)
        return git("rev-parse", "HEAD")

    def pid(sha: str) -> str:
        return _mod.patch_id(sha, root)

    base = commit("a.py", "x = 1\n", "init")
    return type(
        "R",
        (),
        {
            "root": root,
            "git": staticmethod(git),
            "commit": staticmethod(commit),
            "pid": staticmethod(pid),
            "base": base,
            "env": env,
        },
    )


def _bound_trailer(pid: str) -> str:
    return f"Reviewed-by: codex-cli-0.145.0 patch:{pid[:12]} run:0123456789ab"


class TestBinding:
    def test_bound_trailer_passes(self, repo):
        sha = repo.commit("a.py", "x = 2\n", "change")
        repo.git("commit", "--amend", "--no-edit", "--trailer", _bound_trailer(repo.pid(sha)))
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root) == []

    def test_missing_trailer_fails(self, repo):
        repo.commit("a.py", "x = 2\n", "change")
        problems = _mod.check_range(f"{repo.base}..HEAD", repo.root)
        assert len(problems) == 1
        assert "no Reviewed-by trailer with a patch: field" in problems[0]
        assert "change" in problems[0]

    def test_trailer_without_patch_field_fails(self, repo):
        repo.commit("a.py", "x = 2\n", "change", trailer="Reviewed-by: claude (code+security)")
        problems = _mod.check_range(f"{repo.base}..HEAD", repo.root)
        assert len(problems) == 1
        assert "no Reviewed-by trailer with a patch: field" in problems[0]

    def test_copied_trailer_names_another_diff(self, repo):
        first = repo.commit("a.py", "x = 2\n", "first")
        repo.commit("a.py", "x = 3\n", "second", trailer=_bound_trailer(repo.pid(first)))
        problems = _mod.check_range(f"{first}..HEAD", repo.root)
        assert len(problems) == 1
        assert "trailer names patch:" in problems[0]
        assert "amended after review, or copied trailer" in problems[0]

    def test_amend_after_signing_fails(self, repo):
        sha = repo.commit("a.py", "x = 2\n", "change")
        repo.git("commit", "--amend", "--no-edit", "--trailer", _bound_trailer(repo.pid(sha)))
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root) == []
        (repo.root / "a.py").write_text("x = 99\n")
        repo.git("commit", "-q", "-a", "--amend", "--no-edit")  # trailer kept, diff changed
        problems = _mod.check_range(f"{repo.base}..HEAD", repo.root)
        assert len(problems) == 1
        assert "trailer names patch:" in problems[0]

    def test_whitespace_only_amend_after_signing_fails(self, repo):
        """A dedent is a semantic change in Python; the default patch-id ignores it."""
        sha = repo.commit("a.py", "if ok:\n    act()\n", "guard")
        repo.git("commit", "--amend", "--no-edit", "--trailer", _bound_trailer(repo.pid(sha)))
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root) == []
        (repo.root / "a.py").write_text("if ok:\nact()\n")
        repo.git("commit", "-q", "-a", "--amend", "--no-edit")
        problems = _mod.check_range(f"{repo.base}..HEAD", repo.root)
        assert len(problems) == 1
        assert "trailer names patch:" in problems[0]

    def test_full_patch_id_in_trailer_also_matches(self, repo):
        sha = repo.commit("a.py", "x = 2\n", "change")
        repo.git(
            "commit", "--amend", "--no-edit", "--trailer", f"Reviewed-by: x patch:{repo.pid(sha)}"
        )
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root) == []


class TestMergesAndEmpty:
    def test_merge_commit_is_refused_even_when_both_parents_are_signed(self, repo):
        """Fourth reviewer run: a merge was skipped, so a conflict resolution could
        carry code no reviewer saw. Rebase instead."""
        repo.git("checkout", "-q", "-b", "feat")
        sha = repo.commit("b.py", "y = 1\n", "feature")
        repo.git("commit", "--amend", "--no-edit", "--trailer", _bound_trailer(repo.pid(sha)))
        repo.git("checkout", "-q", "main")
        m = repo.commit("c.py", "z = 1\n", "main work")
        repo.git("commit", "--amend", "--no-edit", "--trailer", _bound_trailer(repo.pid(m)))
        repo.git("checkout", "-q", "feat")
        repo.git("merge", "-q", "--no-edit", "main")
        problems = _mod.check_range(f"{repo.base}..HEAD", repo.root)
        assert len(problems) == 1
        assert "merge commit in the PR range" in problems[0]
        assert "rebase" in problems[0]

    def test_empty_commit_is_skipped(self, repo):
        repo.git("commit", "-q", "--allow-empty", "-m", "retrigger CI")
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root) == []

    def test_empty_range_is_ok(self, repo):
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root) == []


class TestExempt:
    def test_exempt_shas_are_skipped_but_other_commits_are_still_checked(self, repo):
        """Fifth reviewer run: a per-PR bot skip let a human commit on a bot branch
        through. The exemption is per commit, decided by the caller (CI: GitHub
        attribution + verification), and everything else is still checked."""
        bot = repo.commit("a.py", "x = 2\n", "deps: bump something")  # unsigned, "bot"
        human = repo.commit("a.py", "x = 3\n", "human tweak on the bot branch")  # unsigned
        problems = _mod.check_range(f"{repo.base}..HEAD", repo.root, exempt={bot})
        assert len(problems) == 1
        assert "human tweak" in problems[0]
        assert "deps: bump" not in problems[0]
        assert _mod.check_range(f"{repo.base}..HEAD", repo.root, exempt={bot, human}) == []

    def test_exemption_does_not_cover_a_merge_commit(self, repo):
        """Sixth reviewer run: the exempt check ran before the merge check."""
        repo.git("checkout", "-q", "-b", "feat")
        repo.commit("b.py", "y = 1\n", "feature")
        repo.git("checkout", "-q", "main")
        main_work = repo.commit("c.py", "z = 1\n", "main work")
        repo.git("checkout", "-q", "feat")
        repo.git("merge", "-q", "--no-edit", "main")
        merge = repo.git("rev-parse", "HEAD")
        # merge^1..merge = main's commit + the merge; exempt both, only the merge is refused
        problems = _mod.check_range(f"{merge}^1..{merge}", repo.root, exempt={merge, main_work})
        assert len(problems) == 1
        assert "merge commit in the PR range" in problems[0]

    def test_cli_exempt_flag(self, repo, monkeypatch, capsys):
        monkeypatch.chdir(repo.root)
        bot = repo.commit("a.py", "x = 2\n", "deps: bump")
        assert _mod.main(["--base", repo.base, "--head", bot, "--exempt", bot]) == 0
        assert "exempt (verified bot commit)" in capsys.readouterr().out
        assert _mod.main(["--base", repo.base, "--head", bot, "--exempt"]) == 1


class TestCli:
    def test_main_exit_codes_and_report(self, repo, capsys, monkeypatch):
        monkeypatch.chdir(repo.root)
        repo.commit("a.py", "x = 2\n", "unsigned")
        assert _mod.main([f"{repo.base}..HEAD"]) == 1
        out = capsys.readouterr().out
        assert "unsigned" in out
        assert "review-push sign" in out
        assert _mod.main(["--base", repo.base, "--head", repo.base]) == 0
        assert "review trailers OK" in capsys.readouterr().out

    def test_main_requires_a_range(self, repo, monkeypatch):
        monkeypatch.chdir(repo.root)
        with pytest.raises(SystemExit):
            _mod.main([])
