"""Tests for tools/open_question_probe.py (shared open-Q detection).

Adds tools/ to sys.path so the module imports directly (tools-test convention).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import open_question_probe as oqp


def _fake_client(questions):
    c = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"questions": questions}
    resp.raise_for_status.return_value = None
    c.get.return_value = resp
    return c


_STD = [
    {"label": "First Name", "required": True, "fields": [{"type": "input_text"}]},
    {"label": "Email", "required": True, "fields": [{"type": "input_text"}]},
    {
        "label": "Resume/CV",
        "required": True,
        "fields": [{"type": "input_file"}, {"type": "textarea"}],
    },
    {
        "label": "Cover Letter",
        "required": False,
        "fields": [{"type": "input_file"}, {"type": "textarea"}],
    },
    {"label": "LinkedIn Profile", "required": False, "fields": [{"type": "input_text"}]},
]


def test_standard_form_has_no_open_questions():
    r = oqp.probe_greenhouse("acme", "1", client=_fake_client(_STD))
    assert r["checked"] is True
    assert r["has_open_questions"] is False


def test_required_essay_flagged():
    qs = _STD + [
        {
            "label": "Why do you want to work here?",
            "required": True,
            "fields": [{"type": "textarea"}],
        }
    ]
    r = oqp.probe_greenhouse("acme", "1", client=_fake_client(qs))
    assert r["has_open_questions"] is True
    assert any("Why do you want" in e for e in r["essay_labels"])


def test_optional_essay_not_flagged():
    qs = _STD + [{"label": "Anything else?", "required": False, "fields": [{"type": "textarea"}]}]
    r = oqp.probe_greenhouse("acme", "1", client=_fake_client(qs))
    assert r["has_open_questions"] is False


def test_standard_textarea_not_essay():
    # "How did you hear about us" is standard even as a textarea.
    qs = _STD + [
        {"label": "How did you hear about us?", "required": True, "fields": [{"type": "textarea"}]}
    ]
    r = oqp.probe_greenhouse("acme", "1", client=_fake_client(qs))
    assert r["has_open_questions"] is False


def test_unknown_source_returns_unchecked():
    r = oqp.probe_open_questions("https://jobs.lever.co/x/123", "lever")
    assert r["checked"] is False


def test_essay_prompt_containing_standard_word_flagged():
    # "Name a project ..." contains "name" but is a required textarea essay.
    for label in [
        "Name a project you're proud of and why",
        "What's your favorite website and why?",
        "Describe your ideal work location",
    ]:
        qs = _STD + [{"label": label, "required": True, "fields": [{"type": "textarea"}]}]
        r = oqp.probe_greenhouse("acme", "1", client=_fake_client(qs))
        assert r["has_open_questions"] is True, f"{label!r} should be an essay"
