"""In-package ESCO occupations fixture consumer (G-1351 Phase B).

Loads the bundled ESCO occupations pillar fixture
(``career_os.fixtures/esco_occupations_en.json.gz``) via ``importlib.resources``
so that a pip/wheel install — which has no ``scripts/`` directory — can still
populate the ``esco_occupations`` table. Fixes the 4a "inert axis" failure mode:
without an in-package consumer, the occupation matcher (Phase B's crux,
``occupation_matcher.py``) would have no taxonomy to match against on a wheel
install, since ``scripts/load_esco_occupations.py`` is not shipped in the wheel.

Mirrors ``scripts/load_esco_occupations.py``'s parse/insert shape (NOT imported
from here — that module lives in ``scripts/``, which is absent in wheels) and
``career_os.migration.demo_seed``'s ``importlib.resources`` fixture-load
precedent.
"""

from __future__ import annotations

import gzip
import json
import logging
from importlib.resources import files

from sqlalchemy.orm import Session

from career_os.models.esco import ESCOOccupation

logger = logging.getLogger(__name__)

FIXTURE_PACKAGE = "career_os.fixtures"
FIXTURE_NAME = "esco_occupations_en.json.gz"


def load_bundled_occupations() -> list[dict]:
    """Load the bundled ESCO occupations fixture via ``importlib.resources``.

    Works under an installed wheel (no filesystem path relative to ``scripts/``
    required) as well as an editable install. Returns a list of row dicts with
    keys: ``concept_uri``, ``preferred_label``, ``alt_labels``, ``description``,
    ``occupation_code``, ``isco_group`` — matching the ``ESCOOccupation`` columns.
    """
    fixture_path = files(FIXTURE_PACKAGE).joinpath(FIXTURE_NAME)
    with fixture_path.open("rb") as fh:
        raw = gzip.decompress(fh.read())
    payload = json.loads(raw.decode("utf-8"))
    rows = payload["occupations"] if isinstance(payload, dict) else payload
    logger.info("Loaded %d occupations from bundled fixture %s", len(rows), FIXTURE_NAME)
    return rows


def count_occupations(db: Session) -> int:
    """Return the current row count of ``esco_occupations``."""
    return db.query(ESCOOccupation).count()


def populate_occupations(db: Session, *, force: bool = False) -> dict:
    """Populate ``esco_occupations`` from the bundled fixture. Idempotent.

    * Empty table: inserts every valid fixture row (dedup on ``concept_uri``;
      rows with a blank ``concept_uri`` or ``preferred_label`` are skipped),
      commits once, and returns
      ``{"inserted": N, "skipped": M, "already_loaded": False}``.
    * Populated table, ``force=False``: does nothing (no fixture re-read) and
      returns ``{"inserted": 0, "skipped": <existing count>, "already_loaded": True}``.
    * Populated table, ``force=True``: re-scans the fixture and inserts only
      genuinely-missing rows (dedup against existing ``concept_uri`` values) —
      never duplicates existing rows.

    Does NOT create tables — the Alembic migration (and the test
    ``create_all``) owns that; this function only queries and inserts.
    """
    existing_count = count_occupations(db)
    if existing_count > 0 and not force:
        return {"inserted": 0, "skipped": existing_count, "already_loaded": True}

    rows = load_bundled_occupations()

    # Single pre-loaded set of existing URIs avoids N per-row queries.
    existing_uris = {uri for (uri,) in db.query(ESCOOccupation.concept_uri).all()}

    inserted = 0
    skipped = 0
    seen_in_batch: set[str] = set()

    for row in rows:
        uri = (row.get("concept_uri") or "").strip()
        label = (row.get("preferred_label") or "").strip()
        if not uri or not label:
            skipped += 1
            continue
        if uri in existing_uris or uri in seen_in_batch:
            skipped += 1
            continue
        seen_in_batch.add(uri)
        db.add(
            ESCOOccupation(
                concept_uri=uri,
                preferred_label=label,
                alt_labels=row.get("alt_labels") or None,
                description=row.get("description") or None,
                occupation_code=row.get("occupation_code") or None,
                isco_group=row.get("isco_group") or None,
            )
        )
        inserted += 1

    db.commit()
    logger.info("populate_occupations: inserted=%d skipped=%d (force=%s)", inserted, skipped, force)
    return {"inserted": inserted, "skipped": skipped, "already_loaded": False}
