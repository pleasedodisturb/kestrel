"""Tests for the release hold on main (FOUND-11, G-2040).

While a ``.release-hold`` marker sits at the repo root, the Release Please
workflow must not open a release PR or cut a release. The guard is a step
that looks for the marker, and every later step runs only when that step
said the hold is off.

The Install phase deletes the marker in the commit that sets Release-As
2.0.0. ``test_marker_is_committed_and_says_who_removes_it`` goes in that same
commit; the other tests stay, because the guard itself stays.
"""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release-please.yml"
MARKER = PROJECT_ROOT / ".release-hold"
GUARD_CONDITION = "steps.hold.outputs.held == 'false'"


@pytest.fixture()
def steps() -> list[dict]:
    """Steps of the single release-please job, in workflow order."""
    with open(WORKFLOW) as f:
        workflow = yaml.safe_load(f)
    return workflow["jobs"]["release-please"]["steps"]


def _hold_index(steps: list[dict]) -> int:
    """Position of the guard step; fails the test when there is none."""
    matches = [i for i, step in enumerate(steps) if step.get("id") == "hold"]
    assert len(matches) == 1, "release-please job needs exactly one step with id 'hold'"
    return matches[0]


def _run_guard(script: str, workdir: Path) -> str:
    """Run the guard step's script in ``workdir`` and return what it wrote to GITHUB_OUTPUT."""
    output = workdir / "github_output.txt"
    output.write_text("")
    env = {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(output)}
    subprocess.run(["bash", "-e", "-c", script], cwd=workdir, env=env, check=True, timeout=20)
    return output.read_text()


def test_guard_step_runs_after_a_checkout(steps):
    """The guard reads a file from the repo, so a checkout has to come first."""
    hold = _hold_index(steps)
    checkouts = [
        i
        for i, step in enumerate(steps)
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    assert checkouts, "no checkout step: the guard would look at an empty workspace"
    assert min(checkouts) < hold
    assert steps[min(checkouts)].get("with", {}).get("persist-credentials") is False


def test_every_step_after_the_guard_is_conditional_on_it(steps):
    """Nothing after the guard may run unless the guard said the hold is off."""
    hold = _hold_index(steps)
    later = steps[hold + 1 :]
    assert later, "no steps after the guard: the workflow would never release"
    for step in later:
        name = step.get("name") or step.get("uses")
        assert step.get("if") == GUARD_CONDITION, f"step {name!r} is not gated on the hold"


def test_release_please_action_sits_behind_the_guard(steps):
    """The action that opens release PRs and cuts releases comes after the guard."""
    hold = _hold_index(steps)
    actions = [
        i
        for i, step in enumerate(steps)
        if str(step.get("uses", "")).startswith("googleapis/release-please-action@")
    ]
    assert len(actions) == 1
    assert actions[0] > hold


def test_guard_reports_held_when_the_marker_exists(steps, tmp_path):
    """With the marker present the guard writes held=true, so gated steps skip."""
    (tmp_path / ".release-hold").write_text("hold\n")
    written = _run_guard(steps[_hold_index(steps)]["run"], tmp_path)
    assert written.splitlines() == ["held=true"]


def test_guard_reports_not_held_when_the_marker_is_absent(steps, tmp_path):
    """Without the marker the guard writes held=false, the only value that releases."""
    written = _run_guard(steps[_hold_index(steps)]["run"], tmp_path)
    assert written.splitlines() == ["held=false"]


def test_marker_is_committed_and_says_who_removes_it():
    """The hold is active: the marker exists and names the phase that lifts it."""
    assert MARKER.is_file(), ".release-hold is missing, so releases are not held"
    text = MARKER.read_text()
    assert "Install" in text
    assert "2.0.0" in text
