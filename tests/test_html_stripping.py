"""Tests for the stdlib-based HTML stripping in tools/research_jobs.py.

Verifies that strip_html_tags handles normal HTML, malformed markup,
nested/unclosed tags, HTML entities, and empty input safely.
"""

import sys
from pathlib import Path

# Ensure the tools directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from research_jobs import strip_html_tags


class TestStripHtmlTags:
    """Unit tests for strip_html_tags."""

    def test_normal_paragraph(self):
        assert strip_html_tags("<p>hello</p>") == "hello"

    def test_nested_tags(self):
        html = "<div><p>hello <b>world</b></p></div>"
        assert strip_html_tags(html) == "hello world"

    def test_script_tag_removed(self):
        html = "<script>alert(1)</script>safe"
        assert strip_html_tags(html) == "safe"

    def test_malformed_script_unclosed(self):
        """Malformed/unclosed script tag - should not leak tag content."""
        html = "<script>alert(1)</script"
        result = strip_html_tags(html)
        assert "alert" not in result

    def test_style_tag_removed(self):
        html = "<style>body{color:red}</style>visible"
        assert strip_html_tags(html) == "visible"

    def test_unclosed_tag(self):
        html = "<p>hello<br>world"
        result = strip_html_tags(html)
        assert "hello" in result
        assert "world" in result

    def test_self_closing_tag(self):
        html = "line1<br/>line2"
        assert strip_html_tags(html) == "line1line2"

    def test_entities_preserved(self):
        html = "<p>5 &gt; 3 &amp; 2 &lt; 4</p>"
        result = strip_html_tags(html)
        assert "5 > 3 & 2 < 4" == result

    def test_numeric_entity_preserved(self):
        html = "&#169; 2026"
        result = strip_html_tags(html)
        assert "\u00a9 2026" == result

    def test_empty_string(self):
        assert strip_html_tags("") == ""

    def test_plain_text_passthrough(self):
        assert strip_html_tags("no tags here") == "no tags here"

    def test_attributes_stripped(self):
        html = '<a href="https://example.com" class="link">click</a>'
        assert strip_html_tags(html) == "click"

    def test_comment_stripped(self):
        html = "before<!-- comment -->after"
        assert strip_html_tags(html) == "beforeafter"

    def test_deeply_nested(self):
        html = "<div><div><div><span>deep</span></div></div></div>"
        assert strip_html_tags(html) == "deep"
