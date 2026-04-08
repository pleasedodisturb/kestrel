#!/usr/bin/env python3
"""Render a markdown cover letter into a polished A4 PDF via HTML + Playwright.

Matches the CV design language: Inter font, electric blue accent, proper margins.

Usage:
    python tools/render_cover_letter_html.py cv/applications/jetbrains-ai-developer-advocate/cover-letter.md
    python tools/render_cover_letter_html.py --all   # render all application folders
"""

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def md_to_html_content(md_text: str) -> tuple[str, str, str]:
    """Parse cover letter markdown into (header_html, subject_line, body_html)."""
    lines = md_text.strip().split("\n")

    # Extract header info (first few lines before ---)
    header_lines = []
    subject = ""
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("**Re:"):
            subject = stripped.replace("**Re:", "").replace("**", "").strip()
            continue
        if stripped == "---":
            body_start = i + 1
            if subject:
                break
            continue
        if (
            not subject
            and stripped
            and not stripped.startswith("**")
            and not stripped.startswith("March")
            and not stripped.startswith("---")
        ):
            header_lines.append(stripped)

    # Parse header
    name = header_lines[0] if header_lines else ""
    contact_info = header_lines[1] if len(header_lines) > 1 else ""

    # Find the date
    date_line = ""
    for line in lines[:10]:
        if re.match(
            r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d",
            line.strip(),
        ):
            date_line = line.strip()
            break

    # Build body HTML from remaining lines
    body_lines = lines[body_start:]
    body_html = ""
    in_list = False
    in_roles_list = False

    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                body_html += "</ul>\n"
                in_list = False
            if in_roles_list:
                body_html += "</ol>\n"
                in_roles_list = False
            body_html += '<div style="height: 6px;"></div>\n'
            continue

        # Centered decorative divider (lines that are just "+")
        if stripped == "+":
            body_html += '<div class="section-break"><span class="divider-symbol">&#x2022;&ensp;&#x2022;&ensp;&#x2022;</span></div>\n'
            continue

        # Bold text
        stripped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)

        # Links
        stripped = re.sub(r"\(?(https?://[^\s\)]+)\)?", r'<a href="\1">\1</a>', stripped)

        # Numbered list items (role links)
        if re.match(r"^\d+\.", stripped):
            if not in_roles_list:
                body_html += '<ol class="roles-list">\n'
                in_roles_list = True
            item = re.sub(r"^\d+\.\s*", "", stripped)
            body_html += f"  <li>{item}</li>\n"
            continue

        # Bullet points
        if stripped.startswith("- "):
            if not in_list:
                body_html += '<ul class="body-list">\n'
                in_list = True
            body_html += f"  <li>{stripped[2:]}</li>\n"
            continue

        if in_list:
            body_html += "</ul>\n"
            in_list = False
        if in_roles_list:
            body_html += "</ol>\n"
            in_roles_list = False

        body_html += f"<p>{stripped}</p>\n"

    if in_list:
        body_html += "</ul>\n"
    if in_roles_list:
        body_html += "</ol>\n"

    header_html = f"""
    <div class="cl-name">{name}</div>
    <div class="cl-contact">{contact_info}</div>
    <div class="cl-date">{date_line}</div>
    """

    return header_html, subject, body_html


def build_cover_letter_html(md_text: str) -> str:
    """Build full HTML document for cover letter."""
    header_html, subject, body_html = md_to_html_content(md_text)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cover Letter</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  @page {{
    size: A4;
    margin: 96px 0;
  }}

  @page:first {{
    margin: 0;
  }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 10pt;
    line-height: 1.65;
    color: #111111;
    -webkit-font-smoothing: antialiased;
    background: #fff;
  }}

  .page {{
    width: 210mm;
    min-height: 297mm;
    padding: 48px 72px 48px 72px;
    position: relative;
  }}


  /* Header */
  .cl-header {{
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 2px solid #0066FF;
  }}

  .cl-name {{
    font-size: 20pt;
    font-weight: 700;
    color: #0A0A0A;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin-bottom: 4px;
  }}

  .cl-contact {{
    font-size: 8.5pt;
    color: #6B7280;
    margin-bottom: 8px;
  }}

  .cl-date {{
    font-size: 8.5pt;
    color: #6B7280;
  }}

  /* Subject line */
  .cl-subject {{
    font-size: 11pt;
    font-weight: 600;
    color: #0066FF;
    margin-bottom: 20px;
  }}

  /* Body */
  .cl-body {{
    font-size: 9.5pt;
    line-height: 1.6;
    color: #1c1c1c;
  }}

  .cl-body p {{
    margin-bottom: 10px;
    orphans: 4;
    widows: 4;
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  .section-break {{
    text-align: center;
    margin: 10px 0;
    line-height: 1;
  }}

  .section-break .divider-symbol {{
    color: #0066FF;
    opacity: 0.35;
    font-size: 8pt;
    letter-spacing: 2px;
  }}

  .cl-body strong {{
    font-weight: 600;
    color: #0A0A0A;
  }}

  .cl-body a {{
    color: #0066FF;
    text-decoration: none;
    font-size: 8pt;
    word-break: break-all;
  }}

  .cl-body .roles-list {{
    margin: 8px 0 12px 0;
    padding-left: 20px;
  }}

  .cl-body .roles-list li {{
    margin-bottom: 4px;
    font-size: 9pt;
  }}

  .cl-body .body-list {{
    list-style: none;
    padding: 0;
    margin: 8px 0 12px 0;
  }}

  .cl-body .body-list li {{
    padding-left: 16px;
    position: relative;
    margin-bottom: 10px;
    font-size: 9.5pt;
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  .cl-body .body-list li:last-child {{
    margin-bottom: 0;
  }}

  .cl-body .body-list li::before {{
    content: '';
    position: absolute;
    left: 0;
    top: 7px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #0066FF;
    opacity: 0.6;
  }}

  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .page {{ width: 100%; min-height: auto; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="cl-header">
    {header_html}
  </div>
  <div class="cl-subject">Re: {subject}</div>
  <div class="cl-body">
    {body_html}
  </div>
</div>
</body>
</html>"""


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Convert HTML to PDF using Playwright."""
    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('file://{html_path.resolve()}', {{ waitUntil: 'networkidle' }});
    await page.pdf({{
        path: '{pdf_path.resolve()}',
        format: 'A4',
        printBackground: true,
        margin: {{ top: '0', right: '0', bottom: '0', left: '0' }}
    }});
    await browser.close();
}})();
"""
    js_path = html_path.parent / "_render_cl.cjs"
    js_path.write_text(script, encoding="utf-8")

    try:
        # Try cv/ dir first (has playwright installed), then project root
        cv_dir = PROJECT_ROOT / "cv"
        node_modules = (
            cv_dir / "node_modules"
            if (cv_dir / "node_modules").exists()
            else PROJECT_ROOT / "node_modules"
        )

        result = subprocess.run(
            ["node", str(js_path.resolve())],
            capture_output=True,
            text=True,
            cwd=str(cv_dir) if (cv_dir / "node_modules").exists() else str(PROJECT_ROOT),
            env={
                "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin",
                "NODE_PATH": str(node_modules),
            },
        )
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return False
        return True
    finally:
        js_path.unlink(missing_ok=True)


def render_one(md_path: Path):
    """Render a single cover letter."""
    md_text = md_path.read_text(encoding="utf-8")
    html_content = build_cover_letter_html(md_text)

    html_path = md_path.with_suffix(".html")
    pdf_path = md_path.with_suffix(".pdf")

    html_path.write_text(html_content, encoding="utf-8")
    print(f"  HTML: {html_path}")

    if html_to_pdf(html_path, pdf_path):
        print(f"  PDF:  {pdf_path}")
        html_path.unlink(missing_ok=True)  # cleanup temp HTML
    else:
        print(f"  PDF failed — HTML kept at {html_path}")


def main():
    if "--all" in sys.argv:
        apps_dir = PROJECT_ROOT / "cv" / "applications"
        for folder in sorted(apps_dir.iterdir()):
            md = folder / "cover-letter.md"
            if md.exists():
                print(f"Rendering {folder.name}...")
                render_one(md)
        return

    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            md_path = Path(arg)
            if md_path.exists():
                print(f"Rendering {md_path.name}...")
                render_one(md_path)
            else:
                print(f"Not found: {md_path}")


if __name__ == "__main__":
    main()
