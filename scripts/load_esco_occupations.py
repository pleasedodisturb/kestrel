#!/usr/bin/env python3
"""Load the ESCO occupations pillar into the local database (G-1351).

Mirrors ``scripts/load_esco_data.py`` (the skills loader), but for *occupation*
concepts — a separate ``esco_occupations`` table, because the 4a title→occupation
axis was inert precisely when occupations were conflated with the skills cache.

Usage
-----
# Load the bundled English fixture (default — no network needed):
    python scripts/load_esco_occupations.py --fixture

# Harvest the full occupations pillar from the official ESCO API and load it:
    python scripts/load_esco_occupations.py --api

# Load from a locally downloaded ESCO occupations CSV export:
    python scripts/load_esco_occupations.py --csv /path/to/occupations_en.csv

Data source & license
---------------------
ESCO (European Skills, Competences, Qualifications and Occupations),
© European Union, https://esco.ec.europa.eu — reused under CC BY 4.0 per
Commission Decision 2011/833/EU. The bundled fixture
(``src/career_os/fixtures/esco_occupations_en.json.gz``) is a *processed,
English-only subset*: per occupation we keep concept URI, preferred label,
alternative labels, description, the ESCO occupation code, and the ISCO-08
unit group derived from that code.

Expected CSV columns (ESCO standard occupations export):
    conceptUri, preferredLabel, altLabels, description, code, iscoGroup
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# Allow running from project root without installing the package
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

FIXTURE_PATH = PROJECT_ROOT / "src" / "career_os" / "fixtures" / "esco_occupations_en.json.gz"

ESCO_SEARCH_API = (
    "https://ec.europa.eu/esco/api/search?type=occupation&language=en"
    "&full={full}&limit={limit}&offset={page}"
)


# ---------------------------------------------------------------------------
# Parsers — each yields dicts matching the ESCOOccupation columns
# ---------------------------------------------------------------------------


def _isco_from_code(code: str) -> str:
    """ISCO-08 unit group = the first segment of the ESCO code ("2166.4" -> "2166")."""
    return code.split(".")[0] if code else ""


def parse_fixture(path: Path = FIXTURE_PATH) -> list[dict]:
    """Load the bundled processed fixture."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = payload["occupations"] if isinstance(payload, dict) else payload
    logger.info("Fixture: %d occupations (%s)", len(rows), path.name)
    return rows


def parse_occupations_csv(content: str) -> list[dict]:
    """Parse an official ESCO occupations CSV export."""
    reader = csv.DictReader(io.StringIO(content))
    rows: list[dict] = []
    for rec in reader:
        uri = (rec.get("conceptUri") or "").strip()
        if not uri:
            continue
        code = (rec.get("code") or "").strip()
        rows.append(
            {
                "concept_uri": uri,
                "preferred_label": (rec.get("preferredLabel") or "").strip(),
                # ESCO CSVs separate altLabels with newlines already
                "alt_labels": (rec.get("altLabels") or "").strip(),
                "description": (rec.get("description") or "").strip(),
                "occupation_code": code,
                "isco_group": (rec.get("iscoGroup") or "").strip() or _isco_from_code(code),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# API harvest (the bundled fixture was produced this way)
# ---------------------------------------------------------------------------


def _get_json(url: str, tries: int = 3) -> dict | None:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                return None
            time.sleep(1.5**attempt)
    return None


def _api_record_to_row(rec: dict) -> dict:
    code = rec.get("code") or ""
    desc = (rec.get("description") or {}).get("en")
    if isinstance(desc, dict):
        desc = desc.get("literal", "")
    return {
        "concept_uri": rec.get("uri", ""),
        "preferred_label": (rec.get("preferredLabel") or {}).get("en") or rec.get("title", ""),
        "alt_labels": "\n".join((rec.get("alternativeLabel") or {}).get("en") or []),
        "description": desc or "",
        "occupation_code": code,
        "isco_group": _isco_from_code(code),
    }


def harvest_from_api(page_size: int = 20) -> list[dict]:
    """Harvest every occupation concept from the ESCO search API.

    NB the API's ``offset`` parameter is a PAGE INDEX, not a row offset.
    A few records 500 the server when serialized with ``full=true``; on a failed
    page we retry its rows one at a time and skip (with a log line) only the
    poisonous record rather than losing the page.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    page = 0
    total: int | None = None
    consecutive_failed_pages = 0
    max_consecutive_failed_pages = 5

    def _add(rec: dict) -> None:
        uri = rec.get("uri", "")
        if uri and uri not in seen:
            seen.add(uri)
            rows.append(_api_record_to_row(rec))

    while total is None or page * page_size < total:
        # Without this bound, an API outage loops forever: `total` never gets
        # set, every page falls into the row-by-row fallback, and page += 1
        # marches on. Five failed pages in a row = the API is down, not one
        # poisonous record.
        if consecutive_failed_pages >= max_consecutive_failed_pages:
            raise RuntimeError(
                f"ESCO API: {consecutive_failed_pages} consecutive pages failed "
                f"(harvested {len(rows)} so far) — aborting instead of looping. "
                "Retry later or use --csv with a manual download."
            )
        data = _get_json(ESCO_SEARCH_API.format(full="true", limit=page_size, page=page))
        if data is None:
            recovered = 0
            for sub in range(page_size):
                row_idx = page * page_size + sub
                single = _get_json(ESCO_SEARCH_API.format(full="true", limit=1, page=row_idx))
                if single is None:
                    lite = _get_json(ESCO_SEARCH_API.format(full="false", limit=1, page=row_idx))
                    info = (
                        lite["_embedded"]["results"][0]
                        if lite and lite["_embedded"]["results"]
                        else {}
                    )
                    logger.warning(
                        "Skipping unserializable occupation row %d: %s (%s)",
                        row_idx,
                        info.get("title"),
                        info.get("uri"),
                    )
                    continue
                for rec in single["_embedded"]["results"]:
                    _add(rec)
                recovered += 1
                time.sleep(0.1)
            # a poisoned page recovers most rows (one bad record); a DEAD page
            # recovers none — only the latter counts toward the outage bail-out
            consecutive_failed_pages = 0 if recovered else consecutive_failed_pages + 1
            page += 1
            continue

        consecutive_failed_pages = 0
        total = data["total"]
        for rec in data["_embedded"]["results"]:
            _add(rec)
        page += 1
        if page % 25 == 0:
            logger.info("  page %d: %d/%d", page, len(rows), total)
        time.sleep(0.15)

    logger.info("Harvested %d occupations (API total %s)", len(rows), total)
    return rows


# ---------------------------------------------------------------------------
# DB load — mirrors load_esco_data.load_skills_into_db
# ---------------------------------------------------------------------------


def load_occupations_into_db(rows: list[dict], db_url: str | None = None) -> dict[str, int]:
    """Insert occupation rows, skipping ones whose concept_uri already exists.

    Builds its OWN engine from ``db_url`` (mirroring the skills loader) — the
    earlier env-var approach was a silent no-op whenever ``career_os.config``
    was already imported (pydantic-settings reads env at instantiation), sending
    rows to the app database instead, and it disposed the shared global engine.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if db_url is None:
        from career_os.config import settings

        db_url = settings.database_url

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Ensure tables exist (same as the skills loader): create_all only creates
    # missing tables, never alters existing ones, so a migrated DB is untouched.
    import career_os.models.esco  # noqa: F401 — registers models with Base
    from career_os.database import Base

    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    from career_os.models.esco import ESCOOccupation

    db = session_factory()
    counts = {"inserted": 0, "skipped": 0, "errors": 0}
    now = datetime.now(UTC)

    try:
        for row in rows:
            uri = (row.get("concept_uri") or "").strip()
            if not uri or not (row.get("preferred_label") or "").strip():
                counts["errors"] += 1
                continue
            if db.query(ESCOOccupation).filter(ESCOOccupation.concept_uri == uri).first():
                counts["skipped"] += 1
                continue
            db.add(
                ESCOOccupation(
                    concept_uri=uri,
                    preferred_label=row["preferred_label"],
                    alt_labels=row.get("alt_labels") or None,
                    description=row.get("description") or None,
                    occupation_code=row.get("occupation_code") or None,
                    isco_group=row.get("isco_group") or None,
                    created_at=now,
                )
            )
            counts["inserted"] += 1
            if counts["inserted"] % 500 == 0:
                db.commit()
                logger.info("  %d occupations inserted...", counts["inserted"])
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error loading occupations: %s", exc)
        counts["errors"] += 1
    finally:
        db.close()
        engine.dispose()

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Load the ESCO occupations pillar into the Kestrel database."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--fixture",
        action="store_true",
        help="Load the bundled English fixture (default source, no network).",
    )
    group.add_argument(
        "--api",
        action="store_true",
        help="Harvest the full occupations pillar from the ESCO API and load it.",
    )
    group.add_argument(
        "--csv",
        metavar="PATH",
        help="Path to a locally downloaded ESCO occupations CSV export.",
    )
    parser.add_argument(
        "--db-url",
        help="SQLAlchemy database URL. Defaults to app-configured database.",
    )
    args = parser.parse_args()

    if args.fixture:
        rows = parse_fixture()
    elif args.api:
        rows = harvest_from_api()
    else:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            logger.error("CSV file not found: %s", csv_path)
            sys.exit(1)
        rows = parse_occupations_csv(csv_path.read_text(encoding="utf-8-sig"))
        logger.info("Parsed %d occupations from %s", len(rows), csv_path)

    counts = load_occupations_into_db(rows, db_url=args.db_url)
    logger.info(
        "Done. inserted=%d  skipped=%d  errors=%d",
        counts["inserted"],
        counts["skipped"],
        counts["errors"],
    )


if __name__ == "__main__":
    main()
