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
    item_hash,
    label_matches_item,
    load_label_set,
    load_labels,
    make_record,
    render_item,
    sanitize_for_terminal,
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
    assert a["item_hash"].startswith("sha256:")
    assert a["item_hash"] != b["item_hash"], "edited text must invalidate the label"


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


# ===================================================================
# Regressions from the 2026-08-17 adversarial cross-review (codex).
# Every one of these survived a 20-mutant battery, because mutation
# testing verifies the guards you wrote, not the ones you never wrote.
# ===================================================================


def test_stale_label_does_not_count_as_labelled(tmp_path):
    """DEFECT 1: input_hash was stored and never compared.

    Labels join to items by `index`, and indices are reused whenever a label set
    is rebuilt. So a label written against "Backend Engineer" at index 1 was
    silently credited to whatever ended up at index 1 next.
    """
    log = tmp_path / "labels.jsonl"
    original = _item(1, title="Backend Engineer")
    it = iter(["y", "y"])
    ann_written = annotate([original], {}, log, reader=lambda _p: next(it))
    assert ann_written == 1

    labels = load_labels(log)
    rebuilt = _item(1, title="Sales Manager")  # same index, different posting

    assert not label_matches_item(rebuilt, labels[1]), "hash failed to notice new text"

    # The loop must re-ask rather than skip it as already done.
    it2 = iter(["n", "n"])
    written = annotate([rebuilt], labels, log, reader=lambda _p: next(it2))
    assert written == 1, "stale label was treated as still valid"
    assert cell(load_labels(log)[1]) == "drop"


def test_matching_hash_is_still_treated_as_labelled(tmp_path):
    """The other half of DEFECT 1: the gate must not re-ask everything."""
    log = tmp_path / "labels.jsonl"
    items = [_item(1)]
    it = iter(["y", "y"])
    annotate(items, {}, log, reader=lambda _p: next(it))
    labels = load_labels(log)
    assert annotate(items, labels, log, reader=lambda _p: pytest.fail("re-asked")) == 0


def test_retraction_is_durable_across_a_restart(tmp_path):
    """DEFECT 2: `b` popped the in-memory dict only; the log kept the line.

    Sequence: label item 1, go back from item 2, quit. The old code left label 1
    on disk, so the next run resurrected it and skipped the item.
    """
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2)]
    it = iter(["y", "y", "b", "q"])
    annotate(items, {}, log, reader=lambda _p: next(it))

    assert 1 not in load_labels(log), "retracted label came back after restart"


def test_retraction_then_relabel_keeps_the_new_answer(tmp_path):
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2)]
    it = iter(["y", "y", "b", "n", "y", "n", "n"])
    annotate(items, {}, log, reader=lambda _p: next(it))
    labels = load_labels(log)
    assert cell(labels[1]) == "referral_lane", "retraction ate the replacement"


def test_retracting_an_unlabelled_item_writes_no_tombstone(tmp_path):
    log = tmp_path / "labels.jsonl"
    items = [_item(1), _item(2)]
    it = iter(["s", "b", "q"])  # skip 1, back from 2, quit
    annotate(items, {}, log, reader=lambda _p: next(it))
    assert not log.exists() or log.read_text().strip() == ""


def test_terminated_corrupt_last_line_is_fatal_not_torn(tmp_path):
    """DEFECT 8: a newline-terminated malformed line was fully written.

    Calling it "torn" and discarding it hid real corruption. Only an
    UNTERMINATED final line can be an interrupted write.
    """
    log = tmp_path / "labels.jsonl"
    append_label(log, make_record(_item(1), can_win=True, wants=True))
    with log.open("a") as fh:
        fh.write('{"index": 2, "corrupt\n')  # note: terminated
    with pytest.raises(SystemExit) as exc:
        load_labels(log)
    assert "fully written" in str(exc.value)


def test_unterminated_last_line_is_still_treated_as_torn(tmp_path):
    log = tmp_path / "labels.jsonl"
    append_label(log, make_record(_item(1), can_win=True, wants=True))
    with log.open("a") as fh:
        fh.write('{"index": 2, "torn')  # no newline
    assert set(load_labels(log)) == {1}


def test_load_labels_reads_the_file_once(tmp_path, monkeypatch):
    """DEFECT 8: read_text() was called again per malformed line -> quadratic."""
    log = tmp_path / "labels.jsonl"
    for i in range(1, 6):
        append_label(log, make_record(_item(i), can_win=True, wants=True))

    calls = {"n": 0}
    real = Path.read_text

    def counting(self, *a, **k):
        if self == log:
            calls["n"] += 1
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", counting)
    load_labels(log)
    assert calls["n"] == 1, f"read the log {calls['n']} times; should be exactly once"



# ===================================================================
# Regressions from the 2026-08-18 adversarial security review (codex).
# ===================================================================


def test_hash_covers_every_displayed_field():
    """The hash must bind what the annotator SAW, not a subset of it.

    label_store.input_hash covers title|company|description and omits
    `location`, which this tool displays. A posting could move from Berlin to
    Austin and keep its label -- on a geo-eligibility tool. item_hash hashes the
    visible projection itself, so the two cannot drift apart.
    """
    base = _item()
    for field in ("title", "company", "location", "description"):
        changed = _item(**{field: "SOMETHING ELSE ENTIRELY"})
        assert item_hash(base) != item_hash(changed), (
            f"changing {field!r} left the hash unchanged, but it is rendered"
        )


def test_hash_covers_fields_added_to_the_visible_set():
    """By construction, not by a hand-maintained list."""
    shown = set(VISIBLE_FIELDS) - {"index"}
    hashed_input = {k: v for k, v in visible_projection(_item()).items() if k != "index"}
    assert set(hashed_input) == shown & set(hashed_input.keys() | shown)


def test_index_alone_does_not_change_the_hash():
    """Position in the set is not a property of the posting."""
    assert item_hash(_item(index=1)) == item_hash(_item(index=99))


def test_hidden_block_does_not_change_the_hash():
    a = _item()
    b = _item()
    b["_hidden"] = {**b["_hidden"], "fit_score": 0.0, "stratum": "DROP"}
    assert item_hash(a) == item_hash(b), "filter output must not affect the binding"


def test_delimiter_collision_is_gone():
    """Concatenating fields with a bare separator makes boundaries ambiguous.

    The fields must be ADJACENT in whatever order a naive join would use, or the
    test does not actually construct a collision. An earlier version of this
    test picked non-adjacent fields, so reverting to a pipe-join left it green.
    Sorted key order is company, description, location, title -- so moving the
    boundary between `company` and `description` is the real collision.
    """
    x = _item(company="A|B", description="D")
    y = _item(company="A", description="B|D")
    assert item_hash(x) != item_hash(y), (
        "distinct postings share a hash: field boundaries are ambiguous"
    )


def test_control_characters_are_stripped_before_display():
    """Untrusted scraped text must not be able to repaint the terminal.

    This is a blindness defect, not a cosmetic one: a posting that can clear the
    screen or reposition the cursor can hide part of itself or forge content,
    corrupting the label while every string-level blindness test stays green.
    """
    evil = _item(description="visible\x1b[2J\x1b[H hidden\rOVERWRITE\x07")
    out = render_item(evil, 1, 1)
    for bad in ("\x1b", "\r", "\x07"):
        assert bad not in out, f"{bad!r} reached the terminal"
    assert "visible" in out and "hidden" in out, "real text was destroyed, not just controls"


def test_sanitizer_keeps_newlines_and_tabs():
    """They carry real layout in a job description."""
    assert sanitize_for_terminal("a\nb\tc") == "a\nb\tc"


def test_sanitizer_strips_c1_range():
    assert "\x9b" not in sanitize_for_terminal("a\x9bb")


def test_labels_log_is_created_private(tmp_path):
    """It records private judgements about named employers."""
    import stat
    log = tmp_path / "labels.jsonl"
    append_label(log, make_record(_item(1), can_win=True, wants=True))
    mode = stat.S_IMODE(log.stat().st_mode)
    assert mode == 0o600, f"labels log is {oct(mode)}, expected 0o600"


def test_annotate_refuses_a_set_calibrate_would_reject(tmp_path):
    """The 15th defect: two readers, one file, different verdicts.

    annotate.load_label_set checked only that `items` and `_meta` existed, while
    calibrate ran a stricter validator. A set whose items lacked `_hidden`
    annotated perfectly and was then categorically rejected at calibration --
    an hour of labelling wasted, with no warning at the time.

    Both readers must now refuse the same file, and annotate must refuse it
    BEFORE anything is displayed or recorded.
    """
    import json as _json
    ls = tmp_path / "ls.json"
    ls.write_text(_json.dumps({"_meta": {}, "items": [
        {"index": 1, "title": "Engineer", "company": "Ex",
         "location": "Berlin", "description": "looks fine."}]}))   # no _hidden
    with pytest.raises(SystemExit) as exc:
        load_label_set(ls)
    assert "_hidden" in str(exc.value)


def test_both_readers_agree_on_the_same_file(tmp_path):
    """Explicitly pin the agreement, not just each side's behaviour."""
    import json as _json

    import calibrate as cal
    ls = tmp_path / "ls.json"
    lab = tmp_path / "l.jsonl"
    lab.write_text(_json.dumps({"index": 1, "item_hash": "x",
                                "can_win_cold": True, "wants": True}) + "\n")
    ls.write_text(_json.dumps({"_meta": {}, "items": [
        {"index": 1, "title": "E", "company": "C",
         "location": "L", "description": "d"}]}))
    annotate_refused = calibrate_refused = False
    try:
        load_label_set(ls)
    except SystemExit:
        annotate_refused = True
    try:
        cal.load_inputs(ls, lab)
    except SystemExit:
        calibrate_refused = True
    assert annotate_refused == calibrate_refused, (
        "the two readers disagree about the same label set"
    )


def test_bidi_and_zero_width_are_stripped():
    """Not C0/C1, so the codepoint filter missed them entirely.

    A right-to-left override can make a line render as something other than what
    it says -- the same forgery risk as an escape sequence, reached differently.
    """
    for ch in ("‮", "‭", "​", "‍", "﻿", "⁦"):
        assert ch not in sanitize_for_terminal(f"a{ch}b"), f"{ch!r} survived"
    assert sanitize_for_terminal("a‮b") == "ab", "surrounding text was damaged"


def test_sanitizer_keeps_ordinary_non_ascii():
    """Stripping must not mangle real postings: umlauts, CJK, emoji."""
    for good in ("Müller", "東京", "Zürich", "naïve", "café"):
        assert sanitize_for_terminal(good) == good
