"""Tests for tools/annotate.py.

Three properties carry weight here.

BLINDNESS. ``render_item`` must be incapable of showing a filter-derived field,
even when one is handed to it. This is asserted by feeding it an item whose
``_hidden`` block is deliberately stuffed with anchoring values and checking
none of them appear in the rendered string. The projection is an allow-list, so
a field added upstream is invisible until someone adds it here on purpose.

TWO AXES, NEVER MERGED. The stored record keeps ``can_win_cold`` and ``wants``
as separate booleans. The four-cell name is derived for reporting only. If a
future change stores the cell instead of the pair, the referral lane (want, no
win) becomes unrecoverable, so there is a test pinning the pair.

RESUMABILITY. The log is append-only JSONL replayed last-wins. Tests cover a
clean resume, a re-label superseding an earlier one, and a torn final line from
a kill mid-write, which must be discarded rather than crash or corrupt.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from annotate import (  # noqa: E402
    VISIBLE_FIELDS,
    annotate,
    append_label,
    cell,
    load_labels,
    make_record,
    render_item,
    visible_projection,
)


def _item(index: int = 1, **over) -> dict:
    base = {
        "index": index,
        "title": "Senior Product Engineer",
        "company": "Acme GmbH",
        "location": "Berlin, Germany",
        "description": "We build things. " * 10,
        "_hidden": {
            "job_id": 4242,
            "url": "https://example.test/4242",
            "stratum": "KEEP",
            "geo_class": "home_relocate",
            "fit_score": 9.7,
            "remote": True,
            "repeat": False,
            "repeat_of": None,
        },
    }
    base.update(over)
    return base


def _reader(answers):
    it = iter(answers)

    def read(_prompt):
        return next(it)

    return read


# ------------------------------------------------------------------ blindness


def test_render_cannot_show_a_filter_derived_field():
    out = render_item(_item(), 1, 10)
    for anchor in ("4242", "KEEP", "home_relocate", "9.7", "geo_class", "fit_score", "stratum"):
        assert anchor not in out, f"{anchor!r} rendered to the annotator"


def test_visible_projection_is_an_allow_list():
    item = _item()
    item["surprise_new_score"] = 8.8  # something a future change might add
    projected = visible_projection(item)
    assert set(projected) <= set(VISIBLE_FIELDS)
    assert "surprise_new_score" not in projected
    assert "_hidden" not in projected


def test_blindness_guard_is_falsifiable():
    """Prove the render test can fail: put an anchor where it would be shown."""
    leaked = _item(title="Senior Product Engineer (fit 9.7, home_relocate)")
    out = render_item(leaked, 1, 10)
    assert "home_relocate" in out, "the render assertion would not have caught a leak"


def test_hidden_block_cannot_influence_rendering():
    """The projection must be load-bearing, not decorative.

    Mutation testing caught that the earlier blindness test passed even when
    `visible_projection` was removed from the render path, because the template
    happens to read only four keys -- so dropping the projection changed nothing
    observable. The template's field selection was doing all the work, and the
    projection would only have started mattering once someone added a field to
    the template.

    This pins the projection directly: `_hidden` keys that SHADOW visible field
    names must not reach the output. Merging `_hidden` over the item (the exact
    careless edit) makes this fail, while the template-only defence does not
    catch it.
    """
    shadowed = {
        "index": 1,
        "title": "",
        "company": "",
        "location": "",
        "description": "",
        "_hidden": {
            "title": "LEAKED TITLE",
            "company": "LEAKED COMPANY",
            "location": "LEAKED LOCATION",
            "description": "LEAKED DESCRIPTION",
        },
    }
    out = render_item(shadowed, 1, 1)
    for leaked in ("LEAKED TITLE", "LEAKED COMPANY", "LEAKED LOCATION", "LEAKED DESCRIPTION"):
        assert leaked not in out, (
            f"{leaked!r} reached the annotator: _hidden was merged into the "
            "render input instead of being projected away"
        )


# -------------------------------------------------------------- the two axes


@pytest.mark.parametrize(
    "can_win,wants,expected",
    [
        (True, True, "apply_now"),
        (False, True, "referral_lane"),
        (True, False, "fallback"),
        (False, False, "drop"),
    ],
)
def test_four_cells(can_win, wants, expected):
    assert cell(make_record(_item(), can_win=can_win, wants=wants)) == expected


def test_record_stores_the_pair_not_the_cell():
    """The referral lane is only recoverable while the axes stay separate."""
    rec = make_record(_item(), can_win=False, wants=True)
    assert rec["can_win_cold"] is False
    assert rec["wants"] is True
    assert "cell" not in rec and "verdict" not in rec and "go" not in rec


def test_record_binds_the_label_to_the_job_text():
    a = make_record(_item(), can_win=True, wants=True)
    b = make_record(_item(title="Different Title"), can_win=True, wants=True)
    assert a["input_hash"].startswith("sha256:")
    assert a["input_hash"] != b["input_hash"], "edited text must invalidate the label"


# ----------------------------------------------------------- resume / durability


def test_labels_survive_and_resume(tmp_path):
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2), _item(3)]

    written = annotate(items, {}, log, reader=_reader(["y", "y", "n", "y", "q"]))
    assert written == 2

    labels = load_labels(log)
    assert set(labels) == {1, 2}
    assert cell(labels[2]) == "referral_lane"

    # Second session picks up exactly where the first stopped.
    written2 = annotate(items, labels, log, reader=_reader(["n", "n"]))
    assert written2 == 1
    assert set(load_labels(log)) == {1, 2, 3}


def test_relabel_supersedes_last_wins(tmp_path):
    log = tmp_path / "labels.jsonl"
    append_label(log, make_record(_item(1), can_win=True, wants=True))
    append_label(log, make_record(_item(1), can_win=False, wants=True))
    labels = load_labels(log)
    assert len(labels) == 1
    assert cell(labels[1]) == "referral_lane"


def test_torn_final_line_is_discarded_not_fatal(tmp_path, capsys):
    log = tmp_path / "labels.jsonl"
    append_label(log, make_record(_item(1), can_win=True, wants=True))
    with log.open("a") as fh:
        fh.write('{"index": 2, "can_win_c')  # killed mid-write
    labels = load_labels(log)
    assert set(labels) == {1}
    assert "discarded torn final line" in capsys.readouterr().err


def test_corruption_that_is_not_the_last_line_is_fatal(tmp_path):
    """A torn line can only be last. Anything else is real damage; do not guess."""
    log = tmp_path / "labels.jsonl"
    log.write_text('{"index": 1, "broken\n{"index": 2, "can_win_cold": true, "wants": true}\n')
    with pytest.raises(SystemExit) as exc:
        load_labels(log)
    assert "corrupt" in str(exc.value)


def test_missing_log_is_an_empty_resume(tmp_path):
    assert load_labels(tmp_path / "nothing.jsonl") == {}


# ------------------------------------------------------------------ navigation


def test_skip_leaves_the_item_unlabelled(tmp_path):
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2)]
    annotate(items, {}, log, reader=_reader(["s", "y", "y"]))
    labels = load_labels(log)
    assert set(labels) == {2}, "a skipped item must not be recorded as a decision"


def test_back_reopens_the_previous_item(tmp_path):
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2)]
    # label 1, then on item 2 go back, re-label 1 differently, then label 2
    annotate(items, {}, log, reader=_reader(["y", "y", "b", "n", "y", "y", "n"]))
    labels = load_labels(log)
    assert cell(labels[1]) == "referral_lane", "the re-label did not supersede"
    assert cell(labels[2]) == "fallback"


def test_quit_is_clean(tmp_path):
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2)]
    written = annotate(items, {}, log, reader=_reader(["q"]))
    assert written == 0
    assert load_labels(log) == {}


def test_invalid_input_reprompts_rather_than_crashing(tmp_path, capsys):
    log = tmp_path / "labels.jsonl"
    written = annotate([_item(1)], {}, log, reader=_reader(["maybe", "?", "y", "y"]))
    assert written == 1
    assert "expected one of" in capsys.readouterr().out
