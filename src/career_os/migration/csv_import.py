"""CSV migration: import applications from tracking/applications.csv.

Handles:
- Status mapping: interested→Interested, applied→Applied, discovery→Discovered,
  outreach→Interested, researching→Discovered
- Empty URLs (6 rows with no URL)
- Mixed salary formats: EUR, USD, GBP, hourly, estimated
- German-language entries (KI-Manager/in, Berater/in, etc.)
- Special characters in company names
- Missing fit scores
"""

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from career_os.models.models import ActivityLog, Application

logger = logging.getLogger(__name__)

# Status mapping from CSV values to canonical Kanban statuses (always lowercase)
STATUS_MAP: dict[str, str] = {
    "interested": "interested",
    "applied": "applied",
    "discovery": "discovered",
    "outreach": "interested",
    "researching": "discovered",
    "interviewing": "interviewing",
    "offer": "offer",
    "accepted": "accepted",
    "rejected": "rejected",
    "ghosted": "ghosted",
}

# Valid canonical statuses (lowercase)
VALID_STATUSES = {
    "discovered",
    "interested",
    "applied",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "ghosted",
}


def _map_status(raw_status: str) -> str:
    """Map CSV status to canonical Kanban status.

    Args:
        raw_status: Raw status string from CSV.

    Returns:
        Canonical status string.
    """
    normalized = raw_status.strip().lower()
    mapped = STATUS_MAP.get(normalized)
    if mapped is None:
        logger.warning(
            "Unmapped status '%s' — defaulting to 'discovered'",
            raw_status,
        )
        return "discovered"
    return mapped


def _parse_date(date_str: str) -> datetime | None:
    """Parse a date string (YYYY-MM-DD) into a timezone-aware datetime.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Timezone-aware datetime or None if empty/invalid.
    """
    date_str = date_str.strip()
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=UTC)
    except ValueError:
        logger.warning("Could not parse date '%s'", date_str)
        return None


def _parse_fit_score(score_str: str) -> float | None:
    """Parse fit score, handling empty and invalid values.

    Args:
        score_str: Score string from CSV.

    Returns:
        Float score or None.
    """
    score_str = score_str.strip()
    if not score_str:
        return None
    try:
        return float(score_str)
    except ValueError:
        logger.warning("Could not parse fit score '%s'", score_str)
        return None


def _normalize_url(url_str: str) -> str | None:
    """Normalize URL, returning None for empty strings.

    Args:
        url_str: URL string from CSV.

    Returns:
        URL string or None if empty.
    """
    url_str = url_str.strip()
    return url_str if url_str else None


def _normalize_salary(salary_str: str) -> str | None:
    """Normalize salary range, preserving the original format.

    We keep the original format (EUR/USD/GBP/hourly/estimated) as-is since
    it's human-entered and contains useful context. Normalization would lose
    information like "estimated" and currency context.

    Args:
        salary_str: Salary string from CSV.

    Returns:
        Salary string or None if empty.
    """
    salary_str = salary_str.strip()
    return salary_str if salary_str else None


def import_csv(
    db: Session,
    csv_path: str | Path,
    profile_id: int,
    *,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    """Import applications from CSV into the database.

    Args:
        db: SQLAlchemy session.
        csv_path: Path to applications.csv.
        profile_id: Profile ID to associate imported applications with.
        dry_run: If True, don't commit (for testing).

    Returns:
        Dictionary with import statistics:
        - imported: number of rows imported
        - skipped: number of rows skipped
        - warnings: list of warning messages
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    stats: dict[str, int | list[str]] = {
        "imported": 0,
        "skipped": 0,
        "warnings": [],
    }
    warnings_list: list[str] = stats["warnings"]  # type: ignore[assignment]

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # start=2 for 1-indexed + header
            try:
                # Map status
                raw_status = row.get("status", "").strip()
                status = _map_status(raw_status)
                if raw_status.lower() not in STATUS_MAP:
                    warnings_list.append(
                        f"Row {row_num}: Unmapped status '{raw_status}' → 'Discovered'"
                    )

                # Parse fields
                date_applied = _parse_date(row.get("date_applied", ""))
                fit_score = _parse_fit_score(row.get("fit_score", ""))
                url = _normalize_url(row.get("url", ""))
                salary_range = _normalize_salary(row.get("salary_range", ""))

                company = row.get("company", "").strip()
                role = row.get("role", "").strip()

                if not company or not role:
                    warnings_list.append(f"Row {row_num}: Missing company or role — skipping")
                    stats["skipped"] = int(stats["skipped"]) + 1
                    continue

                # Create application
                application = Application(
                    profile_id=profile_id,
                    company=company,
                    role=role,
                    url=url,
                    source=row.get("source", "").strip() or None,
                    status=status,
                    salary_range=salary_range,
                    contact=row.get("contact", "").strip() or None,
                    next_step=row.get("next_step", "").strip() or None,
                    notes=row.get("notes", "").strip() or None,
                    fit_score=fit_score,
                    date_applied=date_applied,
                )
                db.add(application)
                db.flush()  # Get the ID

                # Create activity log entry for the import
                log_entry = ActivityLog(
                    profile_id=profile_id,
                    application_id=application.id,
                    action="imported",
                    details=(
                        f"Imported from CSV (row {row_num}): status '{raw_status}' → '{status}'"
                    ),
                    source="csv_migration",
                )
                db.add(log_entry)

                stats["imported"] = int(stats["imported"]) + 1

                # Log edge cases
                if url is None:
                    warnings_list.append(f"Row {row_num}: Empty URL for {company} / {role}")
                if salary_range and any(c in salary_range for c in ("$", "£", "€", "/hr")):
                    # CodeQL: salary_range is from public job postings, not PII
                    logger.info("Row %d: Non-standard salary format: %s", row_num, salary_range)

            except Exception as e:
                logger.error("Row %d: Import error: %s", row_num, e)
                warnings_list.append(f"Row {row_num}: Error: {e}")
                stats["skipped"] = int(stats["skipped"]) + 1

    if not dry_run:
        db.commit()

    logger.info(
        "CSV import complete: %d imported, %d skipped, %d warnings",
        stats["imported"],
        stats["skipped"],
        len(warnings_list),
    )
    return stats
