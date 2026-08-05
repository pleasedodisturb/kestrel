"""Blind-set gates for the geo engine (G-1474): differential, P/R, integrity.

Three gates over the scrubbed 277-item Frankfurt-preset reference set
(``fixtures/README.md``):

1. **Differential** — the generic engine + ``FRANKFURT_PROFILE`` must reproduce
   the frozen Eyas class assignment on every item. This is the acceptance
   criterion for the port: byte-identical behaviour, not "close enough".
2. **Precision/recall floor** — the joint role+geo KEEP decision must hold the
   set's measured quality (thresholds read from the reference file, published
   Eyas numbers: 93.6% recall / 74.6% precision). ``role_keep`` is frozen in
   the reference because only the GEO engine was ported.
3. **Fixture integrity** — the scrub gate stays alive: the committed fixture
   must keep matching zero PII/tracking patterns, and the provenance log's
   ``SCRUB-PROOF: PASS`` line cannot be quietly dropped.

All eval-marked: excluded from the fast unit run, executed by the dedicated
"Geo blind-set gate" CI step.
"""

from __future__ import annotations

import pytest

from career_os.services.geo.classifier import ALL_CLASSES, ELIGIBLE_CLASSES, MAYBE_CLASSES
from career_os.services.geo.presets import FRANKFURT_PROFILE
from tests.eval.geo.replay import (
    FIXTURES,
    classify,
    load_items,
    load_judgements,
    load_reference,
    scrub_patterns,
)

pytestmark = pytest.mark.eval


# ---------------------------------------------------------------------------
# 1. Differential gate: generic engine == frozen Eyas reference, all 277 items.
# ---------------------------------------------------------------------------


def test_differential_matches_frozen_eyas_reference():
    """Every item classifies to exactly the frozen ``generic_class``."""
    items = load_items()
    reference = load_reference()["items"]

    mismatches = [
        (item["id"], reference[item["id"]]["generic_class"], got, item["location"], item["title"])
        for item in items
        if (got := classify(item, FRANKFURT_PROFILE)) != reference[item["id"]]["generic_class"]
    ]
    detail = "\n".join(
        f"  {item_id}: reference={want} generic={got} location={location!r} title={title!r}"
        for item_id, want, got, location, title in mismatches[:10]
    )
    assert not mismatches, (
        f"{len(mismatches)}/{len(items)} items diverge from the frozen Eyas reference "
        f"(first 10 shown):\n{detail}"
    )


# ---------------------------------------------------------------------------
# 2. Precision/recall floor on the joint role+geo KEEP decision.
# ---------------------------------------------------------------------------


def test_precision_recall_hold_published_floor():
    """Recall/precision on the blind set must hold the thresholds frozen in the reference."""
    items = load_items()
    judgements = load_judgements()
    reference = load_reference()
    thresholds = reference["thresholds"]

    keep_classes = ELIGIBLE_CLASSES | MAYBE_CLASSES
    keep = [
        item
        for item in items
        if reference["items"][item["id"]]["role_keep"]
        and classify(item, FRANKFURT_PROFILE) in keep_classes
    ]
    total_go = sum(1 for item in items if judgements[item["id"]]["verdict"] == "GO")
    go_kept = sum(1 for item in keep if judgements[item["id"]]["verdict"] == "GO")

    recall = go_kept / total_go if total_go else 0.0
    precision = go_kept / len(keep) if keep else 0.0

    assert recall >= thresholds["recall"], (
        f"recall {recall:.1%} fell below the {thresholds['recall']:.0%} floor "
        f"(Eyas published 93.6% on this set; kept {go_kept}/{total_go} GO items)"
    )
    assert precision >= thresholds["precision"], (
        f"precision {precision:.1%} fell below the {thresholds['precision']:.0%} floor "
        f"(Eyas published 74.6% on this set; {go_kept} GO of {len(keep)} kept)"
    )


# ---------------------------------------------------------------------------
# 3. Fixture integrity: counts, id consistency, live PII scan, provenance.
# ---------------------------------------------------------------------------


def test_fixture_counts_and_id_consistency():
    """277 items, ids fully aligned across all three files, classes all known."""
    items = load_items()
    judgements = load_judgements()
    reference = load_reference()

    assert len(items) == 277
    item_ids = {item["id"] for item in items}
    assert item_ids == set(judgements) == set(reference["items"])
    assert set(reference["class_map"].values()) <= ALL_CLASSES
    for entry in reference["items"].values():
        assert entry["generic_class"] in ALL_CLASSES
        assert entry["generic_class"] == reference["class_map"][entry["eyas_class"]]

    assert not (FIXTURES / "answer_key.json").exists(), (
        "answer_key.json must never ship — it carries per-item application URLs"
    )


def test_fixture_carries_no_pii_or_tracking_urls():
    """Re-run the scrub pattern set over the committed fixture files.

    This keeps the PII gate alive after the one-time scrub: a future fixture
    edit (or regeneration) that reintroduces an identifier or a tracking URL
    fails here, on every CI eval run.
    """
    blob = (FIXTURES / "blind_items.json").read_text(encoding="utf-8") + (
        FIXTURES / "judgements.json"
    ).read_text(encoding="utf-8")

    hits = {
        label: pattern.findall(blob)
        for label, pattern in scrub_patterns().items()
        if pattern.search(blob)
    }
    assert not hits, f"scrub gate: committed fixture matches PII/tracking patterns: {sorted(hits)}"


def test_generation_log_provenance_intact():
    """The provenance record cannot be quietly dropped or downgraded."""
    log = (FIXTURES / "GENERATION_LOG.md").read_text(encoding="utf-8")
    assert "SCRUB-PROOF: PASS" in log, (
        "GENERATION_LOG.md lost its SCRUB-PROOF: PASS line — the fixture's scrub "
        "provenance is no longer auditable; regenerate via generate_reference.py"
    )
    assert "Items differing | 0" in log, (
        "GENERATION_LOG.md no longer records the zero-diff behaviour-neutrality proof"
    )
