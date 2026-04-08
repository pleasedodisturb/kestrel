#!/usr/bin/env python3
"""Convert markdown cover letters to clean PDF format."""

import re
from pathlib import Path

from fpdf import FPDF


class CoverLetterPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        pass

    def footer(self):
        pass


def render_cover_letter(md_path: Path, pdf_path: Path):
    text = md_path.read_text(encoding="utf-8")
    lines = text.strip().split("\n")

    pdf = CoverLetterPDF()

    # Register Unicode fonts (Arial)
    font_dir = "/System/Library/Fonts/Supplemental"
    pdf.add_font("Arial", "", f"{font_dir}/Arial.ttf", uni=True)
    pdf.add_font("Arial", "B", f"{font_dir}/Arial Bold.ttf", uni=True)
    pdf.add_font("Arial", "I", f"{font_dir}/Arial Italic.ttf", uni=True)

    pdf.add_page()
    pdf.set_margins(25, 20, 25)
    pdf.set_y(20)

    # Use Unicode Arial
    name_font = ("Arial", "B", 18)
    contact_font = ("Arial", "", 9)
    date_font = ("Arial", "", 10)
    body_font = ("Arial", "", 10.5)
    bold_font = ("Arial", "B", 10.5)
    subject_font = ("Arial", "B", 11)

    i = 0
    in_body = False
    in_bullets = False

    while i < len(lines):
        line = lines[i].strip()

        # Skip horizontal rules
        if line == "---":
            if not in_body:
                # Draw a thin line after contact/date section
                pdf.set_draw_color(0, 102, 255)
                pdf.line(25, pdf.get_y() + 2, 185, pdf.get_y() + 2)
                pdf.ln(6)
            i += 1
            continue

        # Name (first line)
        if i == 0 and line.startswith(line.split()[0]) and len(line.split()) <= 3:
            pdf.set_font(*name_font)
            pdf.set_text_color(0, 102, 255)
            pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            i += 1
            continue

        # Contact line
        if "@" in line and not in_body and not in_body:
            pdf.set_font(*contact_font)
            pdf.set_text_color(80, 80, 80)
            # Replace unicode dot
            clean = line.replace("·", "|")
            pdf.cell(0, 5, clean, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
            i += 1
            continue

        # Date line
        if re.match(
            r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d",
            line,
        ):
            pdf.set_font(*date_font)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
            i += 1
            continue

        # Subject line (bold, starts with **Re:)
        if line.startswith("**Re:"):
            in_body = True
            clean = line.replace("**", "")
            pdf.set_font(*subject_font)
            pdf.set_text_color(0, 102, 255)
            pdf.cell(0, 6, clean, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
            i += 1
            continue

        # Empty line = paragraph break
        if line == "":
            if in_bullets:
                in_bullets = False
            pdf.ln(3)
            i += 1
            continue

        # Bullet points
        if line.startswith("- **"):
            in_bullets = True
            match = re.match(r"^- \*\*(.+?)\*\*\s*(.*)", line)
            if match:
                label = match.group(1)
                rest = match.group(2)
                pdf.set_text_color(30, 30, 30)
                # Strip any remaining markdown from rest
                rest = re.sub(r"\*\*(.+?)\*\*", r"\1", rest)

                indent = 30  # bullet indent from left
                bullet_str = "\u2022  "

                # Measure pieces
                pdf.set_font(*bold_font)
                bullet_w = pdf.get_string_width(bullet_str)
                label_w = pdf.get_string_width(label + " ")

                # Available width for first line after bullet+label
                page_w = pdf.w - pdf.r_margin - indent
                first_line_remaining = page_w - bullet_w - label_w

                if rest and first_line_remaining < 40:
                    # Not enough room — put label on its own line, rest below
                    pdf.set_x(indent)
                    pdf.set_font(*bold_font)
                    pdf.cell(bullet_w, 5.5, bullet_str)
                    pdf.cell(label_w, 5.5, label)
                    pdf.ln(5.5)
                    pdf.set_font(*body_font)
                    pdf.set_x(indent + bullet_w)
                    pdf.multi_cell(page_w - bullet_w, 5.5, rest, new_x="LMARGIN", new_y="NEXT")
                elif rest:
                    # Enough room — split rest into what fits on first line vs overflow
                    pdf.set_x(indent)
                    pdf.set_font(*bold_font)
                    pdf.cell(bullet_w, 5.5, bullet_str)
                    pdf.cell(label_w, 5.5, label)

                    # Word-wrap rest manually for first line
                    pdf.set_font(*body_font)
                    words = rest.split()
                    first_line_words = []
                    overflow_words = []
                    running_w = 0
                    filled = False
                    for w in words:
                        ww = pdf.get_string_width(w + " ")
                        if not filled and running_w + ww <= first_line_remaining:
                            first_line_words.append(w)
                            running_w += ww
                        else:
                            filled = True
                            overflow_words.append(w)

                    if first_line_words:
                        pdf.cell(0, 5.5, " ".join(first_line_words), new_x="LMARGIN", new_y="NEXT")
                    else:
                        pdf.ln(5.5)

                    if overflow_words:
                        pdf.set_x(indent + bullet_w)
                        pdf.multi_cell(
                            page_w - bullet_w,
                            5.5,
                            " ".join(overflow_words),
                            new_x="LMARGIN",
                            new_y="NEXT",
                        )
                else:
                    # Label only, no rest
                    pdf.set_x(indent)
                    pdf.set_font(*bold_font)
                    pdf.cell(bullet_w, 5.5, bullet_str)
                    pdf.cell(0, 5.5, label, new_x="LMARGIN", new_y="NEXT")

                pdf.ln(1)
            i += 1
            continue

        # Numbered list items (role links) — left-aligned, not justified
        if re.match(r"^\d+\.", line):
            in_body = True
            pdf.set_font(*body_font)
            pdf.set_text_color(30, 30, 30)
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            clean = re.sub(r"\(already applied: ", "(applied: ", clean)
            pdf.set_x(30)
            pdf.multi_cell(
                pdf.w - pdf.r_margin - 30, 5.5, clean, new_x="LMARGIN", new_y="NEXT", align="L"
            )
            pdf.ln(0.5)
            i += 1
            continue

        # Regular body text
        in_body = True
        pdf.set_text_color(30, 30, 30)

        clean = line
        # Check if line is entirely bold (section header like **Roles I'm interested in:**)
        bold_line_match = re.match(r"^\*\*(.+?)\*\*$", clean)
        if bold_line_match:
            pdf.set_font(*bold_font)
            pdf.multi_cell(
                0, 5.5, bold_line_match.group(1), new_x="LMARGIN", new_y="NEXT", align="L"
            )
            i += 1
            continue

        pdf.set_font(*body_font)
        # Strip inline bold/italic markers
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", clean)
        clean = re.sub(r"\*(.+?)\*", r"\1", clean)

        pdf.multi_cell(0, 5.5, clean, new_x="LMARGIN", new_y="NEXT")
        i += 1

    pdf.output(str(pdf_path))
    print(f"  Created: {pdf_path}")


def main():
    base = Path(__file__).resolve().parent.parent / "cv" / "applications"
    dirs = [
        "mistral-ai-deployment-strategist",
        "plain-sr-product-engineer-ai",
        "jetbrains-pm-bonsai",
        "n8n-sr-developer-advocate",
        "mongodb-technical-project-manager",
        "shopware-ai-native-tpm",
        "shopware-ai-native-pm",
        "deepl-sr-technical-pm-ai",
        "ashby-sr-swe-product-eng",
        "attio-product-engineer",
        "mistral-tpm-science-ops",
        "mistral-tpm-engineering",
        "gitlab-sr-tpm-cto",
        "huggingface-ai-ml-pm",
    ]

    for d in dirs:
        md_path = base / d / "cover-letter.md"
        pdf_path = base / d / "cover-letter.pdf"
        if md_path.exists():
            print(f"Converting {d}...")
            render_cover_letter(md_path, pdf_path)
        else:
            print(f"  SKIP: {md_path} not found")


if __name__ == "__main__":
    main()
