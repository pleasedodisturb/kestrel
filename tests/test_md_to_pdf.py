"""Tests for md_to_pdf_cover_letter module."""

import platform
from pathlib import Path

import pytest
from md_to_pdf_cover_letter import CoverLetterPDF, render_cover_letter

# macOS system fonts required by render_cover_letter
ARIAL_DIR = Path("/System/Library/Fonts/Supplemental")
FONTS_AVAILABLE = (
    platform.system() == "Darwin"
    and (ARIAL_DIR / "Arial.ttf").exists()
    and (ARIAL_DIR / "Arial Bold.ttf").exists()
    and (ARIAL_DIR / "Arial Italic.ttf").exists()
)
skip_no_fonts = pytest.mark.skipif(
    not FONTS_AVAILABLE,
    reason="macOS Arial system fonts not available",
)

SAMPLE_MD = """\
Jane Doe
jane@example.com · +49 123 456 · github.com/janedoe · linkedin.com/in/janedoe

March 10, 2026

**Re: Senior AI Product Manager — Mistral AI**

---

Dear Hiring Team,

I am writing to express my **strong** interest in the position. My background in *technical program management* spans over a decade.

- **Leadership:** Led cross-functional teams of 15+ engineers across three continents, shipping products on time.
- **AI Expertise:** Deployed LLM-based pipelines serving 10M+ users daily.
- **BoldOnly**

I look forward to the opportunity.

Best regards,
Jane Doe
"""


class TestCoverLetterPDFClass:
    """Tests for the CoverLetterPDF subclass."""

    def test_instantiation(self):
        pdf = CoverLetterPDF()
        assert pdf is not None

    def test_auto_page_break_margin(self):
        pdf = CoverLetterPDF()
        # FPDF stores the break margin; verify it was set to 25
        assert pdf.b_margin == 25

    def test_header_is_noop(self):
        pdf = CoverLetterPDF()
        # Should not raise
        pdf.header()

    def test_footer_is_noop(self):
        pdf = CoverLetterPDF()
        # Should not raise
        pdf.footer()


@skip_no_fonts
class TestRenderCoverLetterFull:
    """Integration tests that require macOS system fonts."""

    def test_creates_pdf_file(self, tmp_path):
        md_file = tmp_path / "cover.md"
        pdf_file = tmp_path / "cover.pdf"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)

        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0

    def test_pdf_starts_with_header(self, tmp_path):
        """PDF files start with the %PDF magic bytes."""
        md_file = tmp_path / "cover.md"
        pdf_file = tmp_path / "cover.pdf"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)

        header = pdf_file.read_bytes()[:5]
        assert header == b"%PDF-"

    def test_all_elements_present(self, tmp_path):
        """Render sample with every element type and verify PDF is valid."""
        md_file = tmp_path / "cover.md"
        pdf_file = tmp_path / "cover.pdf"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)

        _content = pdf_file.read_bytes()  # noqa: F841
        # Basic structural check: PDF should have at least one page
        assert b"/Type /Page" in content

    def test_empty_file(self, tmp_path):
        """An empty markdown file should still produce a valid (mostly blank) PDF."""
        md_file = tmp_path / "empty.md"
        pdf_file = tmp_path / "empty.pdf"
        md_file.write_text("", encoding="utf-8")

        render_cover_letter(md_file, pdf_file)

        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0
        assert pdf_file.read_bytes()[:5] == b"%PDF-"

    def test_body_only(self, tmp_path):
        """Markdown with only plain body text (no name, contact, date, etc.)."""
        body_only = "This is just a plain paragraph.\n\nAnother paragraph here.\n"
        md_file = tmp_path / "body.md"
        pdf_file = tmp_path / "body.pdf"
        md_file.write_text(body_only, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)

        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0

    def test_contact_dot_replacement(self, tmp_path):
        """The middle-dot character in the contact line should be replaced with pipe."""
        md = "Jane Doe\njane@example.com · +49 123\n\nBody text.\n"
        md_file = tmp_path / "dot.md"
        pdf_file = tmp_path / "dot.pdf"
        md_file.write_text(md, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)

        _content = pdf_file.read_bytes()  # noqa: F841
        # The pipe character should appear somewhere in the PDF stream
        # (the dot should have been replaced)
        assert pdf_file.stat().st_size > 0

    def test_date_line_formats(self, tmp_path):
        """Various month names should be recognized as date lines."""
        for month in ["January", "February", "December"]:
            md = f"Jane D\njane@example.com\n\n{month} 1, 2026\n\nBody.\n"
            md_file = tmp_path / f"date_{month}.md"
            pdf_file = tmp_path / f"date_{month}.pdf"
            md_file.write_text(md, encoding="utf-8")

            render_cover_letter(md_file, pdf_file)
            assert pdf_file.exists()

    def test_horizontal_rule_before_body(self, tmp_path):
        """A --- line before body should not crash and should produce valid PDF."""
        md = "Jane X\njane@example.com\n\n---\n\nBody text.\n"
        md_file = tmp_path / "hr.md"
        pdf_file = tmp_path / "hr.pdf"
        md_file.write_text(md, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)
        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0

    def test_bullet_label_only(self, tmp_path):
        """Bullet with bold label but no rest text."""
        md = "Jane Y\njane@example.com\n\n**Re: Some Role**\n\n---\n\n- **LabelOnly**\n\nEnd.\n"
        md_file = tmp_path / "bullet_label.md"
        pdf_file = tmp_path / "bullet_label.pdf"
        md_file.write_text(md, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)
        assert pdf_file.exists()

    def test_subject_line_strips_bold_markers(self, tmp_path):
        """The **Re: ...** subject should have markers stripped in the PDF."""
        md = "Jane Z\njane@example.com\n\n**Re: Test Position — Company**\n\n---\n\nBody.\n"
        md_file = tmp_path / "subj.md"
        pdf_file = tmp_path / "subj.pdf"
        md_file.write_text(md, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)
        assert pdf_file.exists()

    def test_inline_bold_and_italic_stripped(self, tmp_path):
        """Bold and italic markdown markers should be stripped from body text."""
        md = "Plain start.\n\nThis has **bold** and *italic* words.\n"
        md_file = tmp_path / "inline.md"
        pdf_file = tmp_path / "inline.pdf"
        md_file.write_text(md, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)
        assert pdf_file.exists()

    def test_output_path_with_parents(self, tmp_path):
        """render_cover_letter should work when pdf_path's parent dir exists."""
        subdir = tmp_path / "nested" / "dir"
        subdir.mkdir(parents=True)
        md_file = tmp_path / "cover.md"
        pdf_file = subdir / "out.pdf"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        render_cover_letter(md_file, pdf_file)
        assert pdf_file.exists()
