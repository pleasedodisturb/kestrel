"""Seed / refresh interim golden-set labels (G-1336, finding H).

Run after editing the golden-set fixtures to regenerate the interim label files
from the ``category`` field:

    python -m tests.eval.generate_labels

This only SEEDS placeholder labels — human rank/quadrant labels are the
remaining step and should overwrite the generated values.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

from tests.eval.label_store import LABELS_DIR, build_seed_labels


def regenerate_all() -> list[Path]:
    """Regenerate label files for every ``scoring_golden_set*.json`` fixture."""
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    written: list[Path] = []
    for path in sorted(glob.glob(str(fixtures_dir / "scoring_golden_set*.json"))):
        fixture_name = Path(path).name
        doc = build_seed_labels(fixture_name)
        out = LABELS_DIR / f"{Path(fixture_name).stem}.labels.json"
        with open(out, "w") as f:
            json.dump(doc, f, indent=2, sort_keys=True)
            f.write("\n")
        written.append(out)
    return written


if __name__ == "__main__":
    for p in regenerate_all():
        print(f"wrote {p}")
