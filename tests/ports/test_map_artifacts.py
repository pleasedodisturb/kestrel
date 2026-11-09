"""Real-file checks for every artefact that crosses the privacy boundary (Phase 11 Map).

Each test is a strict xfail keyed on ``ArtifactMissing``: while a crossing artefact is
absent it reports XFAIL, and once plan 11-05 crosses the file the test would XPASS
(strict), which fails the run and forces the crossing commit to remove the marker. A
file that exists but is invalid fails loudly instead of hiding as pending, because
only ``ArtifactMissing`` is an expected failure.
"""

import csv
import io
import json

import pytest

from tests.ports.boundary import (
    COUNTS_PATH,
    MANIFEST_PATH,
    PRIVATE_ROWS_PATH,
    REQUIRED_REFS,
    VERDICTS_PATH,
    ArtifactMissing,
    counts_problems,
    parse_verdict_list,
    private_rows_problems,
    require,
    verdict_problems,
)

_CROSSING = "Phase 11 plan 11-05 crosses this artefact; it removes this marker"


@pytest.mark.xfail(strict=True, raises=ArtifactMissing, reason=_CROSSING)
def test_verdict_list_is_valid_and_complete():
    """The crossed verdict list passes every rule and covers every required ref."""
    text = require(VERDICTS_PATH)
    assert verdict_problems(text) == []
    assert len(parse_verdict_list(text)) >= len(REQUIRED_REFS)


@pytest.mark.xfail(strict=True, raises=ArtifactMissing, reason=_CROSSING)
def test_arrival_counts_are_valid_aggregates():
    """The crossed counts file is a clean aggregate with at least one data row."""
    text = require(COUNTS_PATH)
    assert counts_problems(text) == []
    assert len(list(csv.reader(io.StringIO(text)))) > 1


@pytest.mark.xfail(strict=True, raises=ArtifactMissing, reason=_CROSSING)
def test_private_ledger_rows_are_anonymous():
    """The crossed private ledger rows carry anonymous ids and no paths or filenames."""
    text = require(PRIVATE_ROWS_PATH)
    assert private_rows_problems(text) == []
    assert text.count("id: P-") >= 1


@pytest.mark.xfail(strict=True, raises=ArtifactMissing, reason=_CROSSING)
def test_gate_verdict_golden_is_frozen():
    """The gate-verdict class is frozen in the manifest and its golden file exists."""
    manifest = json.loads(require(MANIFEST_PATH))
    entry = manifest["classes"]["gate_verdicts"]
    if entry["status"] == "awaiting_private_run":
        raise ArtifactMissing("gate_verdicts golden is still awaiting the private run")
    assert entry["status"] == "frozen"
    assert (MANIFEST_PATH.parent / entry["golden"]).is_file()
