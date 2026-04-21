"""Golden set regression tests for scoring band drift detection.

Validates that the scoring pipeline produces fit_scores within expected bands
for 6 diverse job families (TPM, finance, design, healthcare, legal, product)
using a DeterministicScoringMockProvider.

Per D-01: 6 diverse job families
Per D-02: band ranges, not exact scores
Per D-03: any band violation fails immediately (-x in CI)
Per D-04/D-09: real scoring pipeline with deterministic mock provider
Per D-11: excluded from default pytest run via addopts marker exclusion
"""

from __future__ import annotations

import pytest

from career_os.services.scoring import score_job

from .conftest import load_golden_set

# ---------------------------------------------------------------------------
# Helper: parametrize over jobs in a golden set fixture
# ---------------------------------------------------------------------------


def _job_ids(fixture_filename: str) -> list[str]:
    """Return a list of job IDs from a golden set fixture for parametrize."""
    data = load_golden_set(fixture_filename)
    return [job["id"] for job in data["jobs"]]


def _job_by_id(fixture_filename: str, job_id: str) -> dict:
    """Return a single job dict from a golden set fixture by its ID."""
    data = load_golden_set(fixture_filename)
    for job in data["jobs"]:
        if job["id"] == job_id:
            return job
    msg = f"Job {job_id} not found in {fixture_filename}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# TPM (scoring_golden_set.json)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGoldenSetTPM:
    """Golden set regression for TPM job family (20 jobs)."""

    FIXTURE = "scoring_golden_set.json"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("job_id", _job_ids("scoring_golden_set.json"))
    async def test_scoring_band(self, db_session, golden_set_provider, job_id):
        """Score falls within expected band for TPM golden set job."""
        job = _job_by_id(self.FIXTURE, job_id)
        low, high = job["expected_band"]

        scored = await score_job(
            db_session,
            profile_id=1,
            job_description=job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )

        assert low <= scored.fit_score <= high, (
            f"TPM job {job_id} ({job['title']}): fit_score {scored.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
        assert scored.fit_score >= 0.0
        assert scored.fit_score <= 10.0


# ---------------------------------------------------------------------------
# Finance (scoring_golden_set_finance.json)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGoldenSetFinance:
    """Golden set regression for Financial Analyst job family (20 jobs)."""

    FIXTURE = "scoring_golden_set_finance.json"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("job_id", _job_ids("scoring_golden_set_finance.json"))
    async def test_scoring_band(self, db_session, golden_set_provider, job_id):
        """Score falls within expected band for Finance golden set job."""
        job = _job_by_id(self.FIXTURE, job_id)
        low, high = job["expected_band"]

        scored = await score_job(
            db_session,
            profile_id=1,
            job_description=job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )

        assert low <= scored.fit_score <= high, (
            f"Finance job {job_id} ({job['title']}): fit_score {scored.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
        assert scored.fit_score >= 0.0
        assert scored.fit_score <= 10.0


# ---------------------------------------------------------------------------
# Design (scoring_golden_set_design.json)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGoldenSetDesign:
    """Golden set regression for UX Designer job family (20 jobs)."""

    FIXTURE = "scoring_golden_set_design.json"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("job_id", _job_ids("scoring_golden_set_design.json"))
    async def test_scoring_band(self, db_session, golden_set_provider, job_id):
        """Score falls within expected band for Design golden set job."""
        job = _job_by_id(self.FIXTURE, job_id)
        low, high = job["expected_band"]

        scored = await score_job(
            db_session,
            profile_id=1,
            job_description=job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )

        assert low <= scored.fit_score <= high, (
            f"Design job {job_id} ({job['title']}): fit_score {scored.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
        assert scored.fit_score >= 0.0
        assert scored.fit_score <= 10.0


# ---------------------------------------------------------------------------
# Healthcare (scoring_golden_set_healthcare.json)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGoldenSetHealthcare:
    """Golden set regression for Healthcare Administration job family (20 jobs)."""

    FIXTURE = "scoring_golden_set_healthcare.json"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("job_id", _job_ids("scoring_golden_set_healthcare.json"))
    async def test_scoring_band(self, db_session, golden_set_provider, job_id):
        """Score falls within expected band for Healthcare golden set job."""
        job = _job_by_id(self.FIXTURE, job_id)
        low, high = job["expected_band"]

        scored = await score_job(
            db_session,
            profile_id=1,
            job_description=job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )

        assert low <= scored.fit_score <= high, (
            f"Healthcare job {job_id} ({job['title']}): fit_score {scored.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
        assert scored.fit_score >= 0.0
        assert scored.fit_score <= 10.0


# ---------------------------------------------------------------------------
# Legal (scoring_golden_set_legal.json)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGoldenSetLegal:
    """Golden set regression for Legal job family (20 jobs)."""

    FIXTURE = "scoring_golden_set_legal.json"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("job_id", _job_ids("scoring_golden_set_legal.json"))
    async def test_scoring_band(self, db_session, golden_set_provider, job_id):
        """Score falls within expected band for Legal golden set job."""
        job = _job_by_id(self.FIXTURE, job_id)
        low, high = job["expected_band"]

        scored = await score_job(
            db_session,
            profile_id=1,
            job_description=job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )

        assert low <= scored.fit_score <= high, (
            f"Legal job {job_id} ({job['title']}): fit_score {scored.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
        assert scored.fit_score >= 0.0
        assert scored.fit_score <= 10.0


# ---------------------------------------------------------------------------
# Product Management (scoring_golden_set_product.json)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGoldenSetProduct:
    """Golden set regression for Product Management job family (20 jobs)."""

    FIXTURE = "scoring_golden_set_product.json"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("job_id", _job_ids("scoring_golden_set_product.json"))
    async def test_scoring_band(self, db_session, golden_set_provider, job_id):
        """Score falls within expected band for Product golden set job."""
        job = _job_by_id(self.FIXTURE, job_id)
        low, high = job["expected_band"]

        scored = await score_job(
            db_session,
            profile_id=1,
            job_description=job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )

        assert low <= scored.fit_score <= high, (
            f"Product job {job_id} ({job['title']}): fit_score {scored.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
        assert scored.fit_score >= 0.0
        assert scored.fit_score <= 10.0
