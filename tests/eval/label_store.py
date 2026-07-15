"""Golden-set label store for the scoring eval harness (G-1336, finding H).

Fit scoring is a *ranking* problem — so the reference we evaluate against is an
ordinal **tier/rank** label per job, not a target number. This module defines
the label schema and the input-hash that binds a label to the exact job text it
was assigned to, so a changed fixture invalidates its stale label instead of
silently mislabeling.

**Labels here are INTERIM, model-derived** — seeded from the existing golden-set
``category`` field (itself LLM-authored). They are a placeholder so the harness
runs today; the remaining step is ~60–120 **human** rank/quadrant labels (the
fixtures hold exactly 120 jobs across 6 families). Regenerate the seed with
``python -m tests.eval.generate_labels`` after editing fixtures; replace the
values with human judgments to make the κ/NDCG gate meaningful.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
LABELS_DIR = Path(__file__).resolve().parent / "labels"

LABEL_SOURCE_INTERIM = "interim-model-derived"

# Ordinal tier → relevance grade (weakest → strongest). Mirrors
# career_os.services.scoring_eval.TIER_ORDER.
TIER_TO_RELEVANCE: dict[str, int] = {"reject": 0, "mediocre": 1, "strong": 2, "dream": 3}


def input_hash(job: dict) -> str:
    """Stable hash of the load-bearing job text a label was assigned to.

    Binds a label to its exact input so an edited fixture invalidates the label
    rather than silently mislabeling. Uses title|company|description.
    """
    payload = f"{job.get('title', '')}|{job.get('company', '')}|{job.get('description', '')}"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def labels_path(fixture_name: str) -> Path:
    """Path to the label file for a given fixture filename."""
    stem = Path(fixture_name).stem
    return LABELS_DIR / f"{stem}.labels.json"


def load_fixture(fixture_name: str) -> dict:
    """Load a golden-set fixture by filename."""
    with open(FIXTURES_DIR / fixture_name) as f:
        return json.load(f)


def load_labels(fixture_name: str) -> dict:
    """Load the label file for a fixture (raises if it does not exist)."""
    with open(labels_path(fixture_name)) as f:
        return json.load(f)


def build_seed_labels(fixture_name: str) -> dict:
    """Build an interim label document from a fixture's ``category`` field."""
    data = load_fixture(fixture_name)
    labels: dict[str, dict] = {}
    for job in data["jobs"]:
        tier = job["category"]
        labels[job["id"]] = {
            "tier": tier,
            "relevance": TIER_TO_RELEVANCE[tier],
            "input_hash": input_hash(job),
        }
    return {
        "fixture": fixture_name,
        "label_source": LABEL_SOURCE_INTERIM,
        "note": (
            "INTERIM labels seeded from the golden-set `category` field (LLM-authored). "
            "NOT human ground truth. Replace `tier`/`relevance` with human rank/quadrant "
            "judgments to make the κ/NDCG gate meaningful (G-1336 follow-up)."
        ),
        "labels": labels,
    }
