#!/usr/bin/env python3
"""
Validate the CareerOS Google Sheet after update.

Checks: row count vs DB, headers, statuses, scores, sort order, daily log.
Returns exit code 0 on pass, 1 on failure.

Usage:
    GOOGLE_SA_FILE=path/to/sa.json .venv/bin/python tools/validate_sheet.py
    # Or in CI with GOOGLE_SERVICE_ACCOUNT_JSON env var
"""

import os
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

try:
    import gspread
except ImportError:
    print("gspread not installed")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHEET_ID = os.getenv("SHEET_ID", "1sAeXWISdlMTk_UdJTYafQToI0G8FZcnLCATGKigjGQM")
DB_PATH = PROJECT_ROOT / "data" / "career_os.db"

EXPECTED_HEADERS = [
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
EXPECTED_LOG_HEADERS = [
    "Date",
    "Scraped",
    "Scored",
    "New (above threshold)",
    "Top Score",
    "Top Role",
    "Top Company",
    "CI Run URL",
]
VALID_STATUSES = {
    "discovered",
    "interested",
    "applied",
    "rejected",
    "closed",
    "interviewing",
    "withdrawn",
}
STATUS_ORDER = {
    "interviewing": 1,
    "applied": 2,
    "interested": 3,
    "discovered": 4,
    "rejected": 5,
    "closed": 6,
}


def get_client():
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sa_file = os.getenv("GOOGLE_SA_FILE")
    if sa_json:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(sa_json)
        tmp.close()
        client = gspread.service_account(filename=tmp.name)
        os.unlink(tmp.name)
        return client
    elif sa_file:
        return gspread.service_account(filename=sa_file)
    print("No credentials. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SA_FILE")
    sys.exit(1)


def validate():
    errors = []
    warnings = []

    client = get_client()
    sh = client.open_by_key(SHEET_ID)

    # Pipeline tab
    ws = sh.sheet1
    all_values = ws.get_all_values()
    headers = all_values[0]
    rows = all_values[1:]

    if headers != EXPECTED_HEADERS:
        errors.append(f"Pipeline headers mismatch: {headers}")
    else:
        print("OK: Pipeline headers")

    # Row count vs DB
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        db_count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        conn.close()
        if len(rows) != db_count:
            errors.append(f"Row count: sheet={len(rows)}, db={db_count}")
        else:
            print(f"OK: Row count ({len(rows)})")
    else:
        print(f"SKIP: DB not found at {DB_PATH}")

    # Empty companies
    empty = sum(1 for r in rows if not r[1].strip())
    if empty:
        warnings.append(f"{empty} rows with empty Company")

    # Status values
    bad = [r[4] for r in rows if r[4].strip().lower() not in VALID_STATUSES]
    if bad:
        errors.append(f"Invalid statuses: {bad[:5]}")
    else:
        print("OK: All statuses valid")

    # Scores
    bad_scores = []
    for r in rows:
        s = r[3].strip()
        if s:
            try:
                float(s)
            except ValueError:
                bad_scores.append(s)
    if bad_scores:
        warnings.append(f"Non-numeric scores: {bad_scores[:5]}")
    else:
        print("OK: All scores numeric")

    # Status distribution
    dist = Counter(r[4].strip().lower() for r in rows)
    print(f"OK: {dict(dist)}")

    # Sort order
    prev = 0
    sort_ok = True
    for r in rows:
        cur = STATUS_ORDER.get(r[4].strip().lower(), 7)
        if cur < prev:
            sort_ok = False
            break
        prev = cur
    if sort_ok:
        print("OK: Sort order")
    else:
        warnings.append("Sort order wrong")

    # Daily Log tab
    try:
        ws2 = sh.worksheet("Daily Log")
        log_values = ws2.get_all_values()
        if log_values[0] != EXPECTED_LOG_HEADERS:
            errors.append(f"Log headers mismatch: {log_values[0]}")
        else:
            print("OK: Daily Log headers")
        log_rows = log_values[1:]
        print(f"OK: Daily Log entries: {len(log_rows)}")
        if log_rows and log_rows[-1][0]:
            latest = log_rows[-1]
            print(f"OK: Latest: {latest[0]} - {latest[5]} @ {latest[6]}")
    except gspread.exceptions.WorksheetNotFound:
        errors.append("Daily Log tab missing")

    # Verdict
    print()
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
    if warnings:
        for w in warnings:
            print(f"WARN: {w}")

    if errors:
        print("\nFAILED")
        return 1
    elif warnings:
        print("\nPASSED (with warnings)")
        return 0
    else:
        print("\nALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(validate())
