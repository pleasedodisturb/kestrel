"""Regression tests for G-625 / GH issue #345 — textarea setter in Greenhouse JS fallback.

The React-dynamic-fields JS fallback inside ``fill_custom_questions`` (Greenhouse/
Anthropic branch) used to call ``HTMLInputElement.prototype``'s value setter on
every input — including ``<textarea>`` elements. That throws ``TypeError:
Illegal invocation`` at apply time because a setter pulled off one prototype
cannot be invoked on an instance of a different prototype. The ``||``-fallback
to ``HTMLTextAreaElement`` never fired because the descriptor on
``HTMLInputElement.prototype.value`` is always truthy.

The fix dispatches the prototype based on ``input.tagName``. These tests
inspect the source file's embedded JS string (it executes inside Playwright at
apply time, so a Python unit test cannot exercise it directly without a real
browser session). They are intentionally lightweight — the end-to-end check is
a real Greenhouse form, which is not part of CI.

Living separately from ``test_batch_apply_browser.py`` so they run even when
``config/personal.yaml`` is absent (that file skips the whole import-time
module load).
"""

from pathlib import Path


def _read_source() -> str:
    src = Path(__file__).resolve().parent.parent / "tools" / "batch_apply_browser.py"
    return src.read_text()


def test_uses_type_aware_proto_dispatch():
    """The JS must pick the prototype based on input.tagName === 'TEXTAREA'."""
    source = _read_source()
    assert "input.tagName === 'TEXTAREA'" in source, (
        "Expected type-aware setter dispatch keyed on input.tagName === 'TEXTAREA'"
    )
    assert "window.HTMLTextAreaElement.prototype" in source
    assert "window.HTMLInputElement.prototype" in source


def test_does_not_use_broken_or_fallback():
    """The old ``||`` fallback between two getOwnPropertyDescriptor calls for
    ``value.set`` must not return — it never fires for textareas and is the
    exact bug fixed by G-625."""
    source = _read_source()
    broken_chain = (
        "HTMLInputElement.prototype, 'value'\n                                        ).set ||"
    )
    assert broken_chain not in source, "Broken ||-fallback pattern from G-625 reintroduced"
