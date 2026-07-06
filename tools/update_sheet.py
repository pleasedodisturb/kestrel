#!/usr/bin/env python3
"""
Update the Kestrel pipeline Google Sheet with pipeline data and daily scan log.

Usage:
    # From CI (uses GOOGLE_SERVICE_ACCOUNT_JSON env var):
    .venv/bin/python tools/update_sheet.py

    # Locally (uses JSON file):
    GOOGLE_SA_FILE=path/to/sa.json .venv/bin/python tools/update_sheet.py

    # With daily log entry:
    .venv/bin/python tools/update_sheet.py --log-entry '{"scraped":196,"scored":48,"top_score":9,"top_role":"Sr PM AI","top_company":"Boostlingo"}'

Environment:
    GOOGLE_SERVICE_ACCOUNT_JSON  - JSON string of service account creds (CI)
    GOOGLE_SA_FILE               - Path to service account JSON file (local)
    SHEET_ID                     - Google Sheet ID (required; your own spreadsheet)
    CI_RUN_URL                   - GitHub Actions run URL for daily log
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import gspread
except ImportError:
    print("gspread not installed. Run: pip install gspread")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Target spreadsheet is per-user config — no personal default is committed.
SHEET_ID = os.getenv("SHEET_ID")
DB_PATH = PROJECT_ROOT / "data" / "career_os.db"


def get_client():
    """Authenticate with Google Sheets API."""
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sa_file = os.getenv("GOOGLE_SA_FILE")

    if sa_json:
        # CI mode: write JSON string to temp file
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(sa_json)
        tmp.close()
        client = gspread.service_account(filename=tmp.name)
        os.unlink(tmp.name)
        return client
    elif sa_file:
        return gspread.service_account(filename=sa_file)
    else:
        # Try default location
        default_path = PROJECT_ROOT / "secrets" / "google-sa.json"
        if default_path.exists():
            return gspread.service_account(filename=str(default_path))
        print("No Google service account credentials found.")
        print("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SA_FILE")
        sys.exit(1)


def update_pipeline_tab(sh):
    """Refresh the Pipeline tab with current DB data."""
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH} - skipping pipeline tab (CI mode)")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    rows = list(
        c.execute("""
        SELECT id, company, role, fit_score, status, salary_range, source, url,
               created_at, updated_at, notes
        FROM applications
        ORDER BY
            CASE status
                WHEN 'interviewing' THEN 1
                WHEN 'applied' THEN 2
                WHEN 'interested' THEN 3
                WHEN 'discovered' THEN 4
                WHEN 'rejected' THEN 5
                WHEN 'closed' THEN 6
                ELSE 7
            END,
            COALESCE(fit_score, 0) DESC
    """)
    )
    conn.close()

    ws = sh.sheet1
    headers = [
        "ID",
        "Company",
        "Role",
        "Score",
        "Status",
        "Location",
        "Salary",
        "Source",
        "URL",
        "Date Added",
        "Last Updated",
        "Notes",
    ]

    data = [headers]
    for r in rows:
        rid, company, role, score, status, salary, source, url, created, updated, notes = r
        data.append(
            [
                rid,
                company or "",
                role or "",
                score if score else "",
                status or "",
                "",  # location not in DB schema
                salary or "",
                source or "",
                url or "",
                (created or "")[:10],
                (updated or "")[:10],
                (notes or "")[:150],
            ]
        )

    # Clear old data and write fresh
    ws.clear()
    ws.update(values=data, range_name=f"A1:L{len(data)}")

    # Format header
    ws.format(
        "A1:L1",
        {
            "textFormat": {
                "bold": True,
                "foregroundColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
            },
            "backgroundColor": {"red": 0.15, "green": 0.35, "blue": 0.75},
            "horizontalAlignment": "CENTER",
        },
    )
    ws.freeze(rows=1)

    return len(data) - 1  # exclude header


def update_daily_log(sh, entry: dict):
    """Append a row to the Daily Log tab."""
    try:
        ws = sh.worksheet("Daily Log")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Daily Log", rows=500, cols=10)
        ws.update(
            values=[
                [
                    "Date",
                    "Scraped",
                    "Scored",
                    "New (above threshold)",
                    "Top Score",
                    "Top Role",
                    "Top Company",
                    "CI Run URL",
                ]
            ],
            range_name="A1:H1",
        )
        ws.format(
            "A1:H1",
            {
                "textFormat": {
                    "bold": True,
                    "foregroundColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
                },
                "backgroundColor": {"red": 0.15, "green": 0.35, "blue": 0.75},
            },
        )
        ws.freeze(rows=1)

    row = [
        entry.get("date", datetime.now().strftime("%Y-%m-%d")),
        entry.get("scraped", ""),
        entry.get("scored", ""),
        entry.get("new_above_threshold", ""),
        entry.get("top_score", ""),
        entry.get("top_role", ""),
        entry.get("top_company", ""),
        entry.get("ci_run_url", os.getenv("CI_RUN_URL", "")),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return row


def update_review_queue(sh, scored_path: Path):
    """Update the Review Queue tab from scored JSON (flagged items only)."""
    if not scored_path.exists():
        print(f"Scored JSON not found: {scored_path} - skipping review queue")
        return 0

    import json as _json

    jobs = _json.loads(scored_path.read_text())
    flagged = [j for j in jobs if j.get("review_flag")]

    if not flagged:
        print("No review-flagged jobs found")
        return 0

    try:
        ws = sh.worksheet("Review Queue")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Review Queue", rows=500, cols=10)

    headers = [
        "Date",
        "Company",
        "Role",
        "Score",
        "Review Reason",
        "Location",
        "Salary",
        "Source",
        "URL",
    ]

    # Clear and rewrite (keep as rolling list, newest on top)
    existing = ws.get_all_values()
    existing_rows = existing[1:] if len(existing) > 1 else []

    today = datetime.now().strftime("%Y-%m-%d")
    new_rows = []
    for j in flagged:
        new_rows.append(
            [
                today,
                j.get("company", "")[:30],
                j.get("title", "")[:50],
                j.get("fit_score", ""),
                j.get("review_reason", "")[:100],
                j.get("location", ""),
                j.get("estimated_salary", ""),
                j.get("source", ""),
                j.get("url", ""),
            ]
        )

    # New items on top, then existing
    all_data = [headers] + new_rows + existing_rows
    ws.clear()
    ws.update(values=all_data, range_name=f"A1:I{len(all_data)}")
    ws.format(
        "A1:I1",
        {
            "textFormat": {
                "bold": True,
                "foregroundColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
            },
            "backgroundColor": {"red": 0.6, "green": 0.3, "blue": 0.1},
            "horizontalAlignment": "CENTER",
        },
    )
    ws.freeze(rows=1)

    print(f"Review Queue updated: {len(new_rows)} new flagged, {len(existing_rows)} existing")
    return len(new_rows)


def main():
    parser = argparse.ArgumentParser(description="Update Kestrel pipeline Google Sheet")
    parser.add_argument("--log-entry", help="JSON string with daily log data")
    parser.add_argument("--scored-json", help="Path to scored JSON for review queue")
    parser.add_argument("--pipeline-only", action="store_true", help="Only update pipeline tab")
    parser.add_argument("--log-only", action="store_true", help="Only append daily log")
    args = parser.parse_args()

    if not SHEET_ID:
        print("SHEET_ID env var is required (your own Google Sheet ID).")
        sys.exit(1)

    client = get_client()
    sh = client.open_by_key(SHEET_ID)
    print(f"Connected to: {sh.title}")

    if not args.log_only:
        count = update_pipeline_tab(sh)
        print(f"Pipeline tab updated: {count} rows")

    if args.log_entry and not args.pipeline_only:
        entry = json.loads(args.log_entry)
        row = update_daily_log(sh, entry)
        print(f"Daily log appended: {row}")

    # Update review queue from scored JSON
    if args.scored_json:
        scored_path = Path(args.scored_json)
    else:
        # Default: today's scored file
        today = datetime.now().strftime("%Y-%m-%d")
        scored_path = PROJECT_ROOT / "tracking" / f"scraped_scored_{today}.json"

    if scored_path.exists() and not args.pipeline_only:
        review_count = update_review_queue(sh, scored_path)
        if review_count:
            print(f"Review Queue: {review_count} wildcards flagged")

    print(f"Sheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    main()
