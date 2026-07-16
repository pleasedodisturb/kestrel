"""Golden-set agreement eval on the REAL production scorer (G-1336, finding H).

Marked ``@pytest.mark.eval`` so it runs as a separate (nightly) CI job, not the
fast unit run. Every metric here comes from ``career_os.services.scoring.score_job``
driven by the deterministic MockProvider — the real production path, zero paid
LLM calls (see ``tests/eval/run_scoring.py``).

The gate is a *delta vs a frozen baseline* with tolerance bands, not a brittle
absolute threshold: it detects when a change to the production scoring pipeline
moves κ/NDCG, without flapping on nondeterminism (the mock is deterministic).

Honesty note: with the mock provider these κ values hover near 0 (hash scores
are uncorrelated with the interim labels). They become real *quality* signal
only once the labels are human and a real reference model is run — see
``tests/eval/label_store.py``. The infra, metric math, and regression gate are
what ship here.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from career_os.services.scoring_eval import spread_collapsed
from tests.eval.harness import check_label_freshness, compute_agreement
from tests.eval.run_scoring import make_memory_session, score_fixture

pytestmark = pytest.mark.eval

FIXTURE_NAMES = sorted(
    Path(p).name
    for p in glob.glob(
        str(Path(__file__).resolve().parent.parent / "fixtures" / "scoring_golden_set*.json")
    )
)

BASELINE = json.loads((Path(__file__).resolve().parent / "baseline_metrics.json").read_text())

# Tolerance bands for the delta-vs-baseline gate.
KAPPA_TOLERANCE = 0.15
NDCG_TOLERANCE = 0.15
# Spread (finding F): std-dev may drift this far from baseline before we call it
# a distribution shift. Wider than κ/NDCG because std-dev is a coarser statistic.
SPREAD_STDDEV_TOLERANCE = 1.0


@pytest.fixture()
def db_session():
    """In-memory DB with a seeded profile (fresh per test)."""
    session = make_memory_session()
    yield session
    session.close()


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_label_freshness(fixture_name):
    """Every labeled job still matches its stored input hash (no stale labels)."""
    stale = check_label_freshness(fixture_name)
    assert not stale, (
        f"{fixture_name}: labels are stale for {stale} — the fixture text changed. "
        f"Re-label (human) or reseed with `python -m tests.eval.generate_labels`."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
async def test_agreement_within_baseline_band(fixture_name, db_session):
    """κ / NDCG@5 on the real scorer stay within tolerance of the frozen baseline."""
    scored = await score_fixture(db_session, fixture_name)
    agreement = compute_agreement(fixture_name, scored)

    # Metrics are well-formed.
    assert -1.0 <= agreement["kappa"] <= 1.0
    assert 0.0 <= agreement["ndcg@5"] <= 1.0
    assert agreement["n"] == BASELINE["metrics"][fixture_name]["n"]

    base = BASELINE["metrics"][fixture_name]
    kappa_delta = abs(agreement["kappa"] - base["kappa"])
    ndcg_delta = abs(agreement["ndcg@5"] - base["ndcg@5"])

    assert kappa_delta <= KAPPA_TOLERANCE, (
        f"{fixture_name}: weighted κ drifted {kappa_delta:.3f} from baseline "
        f"{base['kappa']:.3f} (now {agreement['kappa']:.3f}, tolerance {KAPPA_TOLERANCE}). "
        f"If intentional, regenerate with `python -m tests.eval.generate_baseline`."
    )
    assert ndcg_delta <= NDCG_TOLERANCE, (
        f"{fixture_name}: NDCG@5 drifted {ndcg_delta:.3f} from baseline "
        f"{base['ndcg@5']:.3f} (now {agreement['ndcg@5']:.3f}, tolerance {NDCG_TOLERANCE}). "
        f"If intentional, regenerate with `python -m tests.eval.generate_baseline`."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
async def test_spread_not_collapsed_and_within_baseline(fixture_name, db_session):
    """Score spread stays healthy (finding F): not collapsed + std-dev near baseline.

    A judge whose distribution flattens/clusters has stopped discriminating.
    We gate two ways: an absolute anti-collapse guard (std-dev floor / mode-share
    ceiling) that fails a genuinely degenerate distribution, and a delta-vs-baseline
    guard on std-dev that catches a silent narrowing before it fully collapses.
    """
    scored = await score_fixture(db_session, fixture_name)
    spread = compute_agreement(fixture_name, scored)["spread"]

    # Well-formed spread metrics.
    assert spread["stddev"] >= 0.0
    assert spread["entropy"] >= 0.0
    assert 0.0 <= spread["mode_share"] <= 1.0

    # Absolute anti-collapse guard.
    assert not spread_collapsed(spread), (
        f"{fixture_name}: score distribution collapsed — stddev={spread['stddev']:.3f}, "
        f"mode_share={spread['mode_share']:.3f}. The judge stopped discriminating."
    )

    # Delta-vs-baseline guard on std-dev.
    base_spread = BASELINE["metrics"][fixture_name]["spread"]
    stddev_delta = abs(spread["stddev"] - base_spread["stddev"])
    assert stddev_delta <= SPREAD_STDDEV_TOLERANCE, (
        f"{fixture_name}: score std-dev drifted {stddev_delta:.3f} from baseline "
        f"{base_spread['stddev']:.3f} (now {spread['stddev']:.3f}, tolerance "
        f"{SPREAD_STDDEV_TOLERANCE}). If intentional, regenerate the baseline."
    )


@pytest.mark.asyncio
async def test_scorer_is_deterministic_under_mock(db_session):
    """Two runs of the same fixture give identical scores (baseline can't flap)."""
    first = await score_fixture(db_session, FIXTURE_NAMES[0])
    second_db = make_memory_session()
    try:
        second = await score_fixture(second_db, FIXTURE_NAMES[0])
    finally:
        second_db.close()
    assert first == second


@pytest.mark.asyncio
async def test_exercises_real_batch_path(db_session):
    """The batch entrypoint scores real DiscoveredJob rows via the production path."""
    from career_os.models.discovery import DiscoveredJob
    from career_os.models.models import Profile
    from career_os.services.scoring import batch_score_discovery

    profile = db_session.get(Profile, 1)
    profile.job_family = "TPM"
    profile.location = "Remote"
    db_session.commit()

    for i in range(3):
        db_session.add(
            DiscoveredJob(
                profile_id=1,
                title=f"Technical Program Manager {i}",
                company=f"Acme {i}",
                location="Remote",
                description="Own cross-functional AI infrastructure programs. Python, cloud.",
                url=f"https://example.com/job/{i}",
                title_normalized=f"technical program manager {i}",
                company_normalized=f"acme {i}",
                location_normalized="remote",
            )
        )
    db_session.commit()

    result = await batch_score_discovery(db_session, 1)
    assert result["scored_count"] == 3
    assert all(0.0 <= s.fit_score <= 10.0 for s in result["scores"])
