"""Tests for the role-fit hard gate + company-prestige cap (G-1335, halo fix).

Covers findings A-D from ``docs/research/2026-07_scoring-technique-audit.md``:

- A: code-enforced cap — a wrong-role or disqualified job caps ``fit_score`` at 3
  after parsing, regardless of high dimensional scores; genuine fits unchanged.
- B/C/D: the scoring prompt scopes ``company_fit``, tiers dimensions, orders
  reason-before-score, and carries a negative reference anchor.
- Back-compat: legacy/cached/mock responses (no gate fields) leave the gate a
  no-op, and the parse path accepts the fields when present and when absent.

All validation is unit-level against the mock/deterministic providers — no paid
LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.ai.base import ROLE_FIT_GATE_PROMPT
from career_os.database import Base
from career_os.models.models import Profile
from career_os.schemas.ai import (
    ROLE_FIT_GATE_CEILING,
    ATSKeyword,
    DimensionalScores,
    RoleMatch,
    ScoreBreakdownFactor,
    ScoreResult,
    apply_role_fit_gate,
    role_fit_gate_failed,
)
from career_os.services.batch_scoring import build_batch_prompt, parse_batch_response
from career_os.services.scoring import (
    _apply_role_fit_gate,
    _average_score_results,
    _build_scoring_prompt,
    score_job,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_score_result(
    fit_score: float,
    *,
    role_match: RoleMatch | None = None,
    disqualifiers: list[str] | None = None,
    dimensional_high: bool = True,
) -> ScoreResult:
    """Build a valid ScoreResult with optionally high dimensional scores."""
    dims = 9.0 if dimensional_high else fit_score
    return ScoreResult(
        role_match=role_match,
        disqualifiers=disqualifiers or [],
        fit_score=fit_score,
        readiness_score=80.0,
        career_alignment=8.0,
        reasoning="A" * 120,
        estimated_salary="$150k-$180k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Prep note",
        score_breakdown=[
            ScoreBreakdownFactor(factor="technical_fit", contribution=3.0, description="d"),
            ScoreBreakdownFactor(factor="company_fit", contribution=2.0, description="d"),
            ScoreBreakdownFactor(factor="career", contribution=1.0, description="d"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=dims,
            seniority_alignment=dims,
            compensation_fit=dims,
            location_fit=dims,
            career_trajectory=dims,
            company_fit=dims,
        ),
        ats_keywords=[ATSKeyword(keyword="Python", category="technical", matched=True)],
        desire_score=9.0,
        desire_reasoning="Dream company",
    )


def _make_ai_response(score_result: ScoreResult) -> MagicMock:
    resp = MagicMock()
    resp.structured = score_result
    return resp


@pytest.fixture
def db_session() -> Session:
    """Fresh in-memory SQLite session with a seeded TPM profile."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_cls()
    session.add(
        Profile(id=1, name="Test User", email="t@example.com", location="Berlin", job_family="TPM")
    )
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# Pure gate function (schema layer) — finding A
# ---------------------------------------------------------------------------


class TestRoleFitGateFailed:
    """role_fit_gate_failed() truth table."""

    def test_genuine_fit_passes(self):
        assert role_fit_gate_failed(_make_score_result(8.5)) is False

    def test_explicit_same_family_passes(self):
        r = _make_score_result(8.5, role_match=RoleMatch(is_same_role_family=True, evidence="TPM"))
        assert role_fit_gate_failed(r) is False

    def test_role_mismatch_fails(self):
        r = _make_score_result(
            8.5, role_match=RoleMatch(is_same_role_family=False, evidence="SWE ≠ TPM")
        )
        assert role_fit_gate_failed(r) is True

    def test_disqualifier_fails(self):
        assert role_fit_gate_failed(_make_score_result(9.0, disqualifiers=["no work visa"])) is True

    def test_none_role_match_is_backcompat_pass(self):
        # Legacy/cached/mock rows leave role_match None → treated as a pass.
        assert role_fit_gate_failed(_make_score_result(9.9)) is False


class TestApplyRoleFitGate:
    """apply_role_fit_gate() caps only when the gate fails."""

    def test_genuine_high_fit_unchanged(self):
        assert apply_role_fit_gate(_make_score_result(8.5)).fit_score == 8.5

    def test_role_mismatch_capped_despite_high_dimensions(self):
        r = _make_score_result(
            8.5, role_match=RoleMatch(is_same_role_family=False), dimensional_high=True
        )
        capped = apply_role_fit_gate(r)
        assert capped.fit_score == ROLE_FIT_GATE_CEILING == 3.0
        # Dimensional scores untouched — the cap only touches fit_score.
        assert capped.dimensional_scores.technical_fit == 9.0
        # Desire axis untouched — prestige stays on desire, not fit.
        assert capped.desire_score == 9.0

    def test_disqualifier_capped(self):
        r = _make_score_result(9.0, disqualifiers=["missing mandatory CPA license"])
        assert apply_role_fit_gate(r).fit_score == 3.0

    def test_already_below_ceiling_unchanged(self):
        # A mismatch that already scored low is not raised or altered.
        r = _make_score_result(2.0, role_match=RoleMatch(is_same_role_family=False))
        assert apply_role_fit_gate(r).fit_score == 2.0

    def test_backcompat_no_fields_unchanged(self):
        assert apply_role_fit_gate(_make_score_result(9.9)).fit_score == 9.9

    def test_idempotent(self):
        r = _make_score_result(8.5, role_match=RoleMatch(is_same_role_family=False))
        once = apply_role_fit_gate(r)
        assert apply_role_fit_gate(once).fit_score == once.fit_score == 3.0

    def test_service_wrapper_matches_pure(self):
        r = _make_score_result(7.7, disqualifiers=["hard location conflict"])
        assert _apply_role_fit_gate(r).fit_score == apply_role_fit_gate(r).fit_score == 3.0


# ---------------------------------------------------------------------------
# Parse path / schema back-compat — finding A
# ---------------------------------------------------------------------------


class TestParsePathBackCompat:
    """ScoreResult.model_validate accepts the new fields and defaults them."""

    BASE = {
        "fit_score": 8.0,
        "reasoning": "R" * 120,
        "estimated_salary": "$150k",
        "effort_flag": "medium",
        "prep_level": "moderate",
        "prep_notes": "n",
        "readiness_score": 80,
        "career_alignment": 8,
        "score_breakdown": [
            {"factor": "a", "contribution": 1, "description": "d"},
            {"factor": "b", "contribution": 1, "description": "d"},
            {"factor": "c", "contribution": 1, "description": "d"},
        ],
    }

    def test_absent_fields_default(self):
        # Old cached response / mock provider payload — no gate fields.
        result = ScoreResult.model_validate(self.BASE)
        assert result.role_match is None
        assert result.disqualifiers == []
        assert apply_role_fit_gate(result).fit_score == 8.0

    def test_present_fields_parse(self):
        payload = {
            **self.BASE,
            "role_match": {"is_same_role_family": False, "evidence": "SWE role, TPM candidate"},
            "disqualifiers": ["no EU work authorization"],
        }
        result = ScoreResult.model_validate(payload)
        assert result.role_match is not None
        assert result.role_match.is_same_role_family is False
        assert result.role_match.evidence == "SWE role, TPM candidate"
        assert result.disqualifiers == ["no EU work authorization"]
        assert apply_role_fit_gate(result).fit_score == 3.0

    def test_partial_role_match_defaults(self):
        # Model emits role_match with only the bool — evidence defaults to "".
        result = ScoreResult.model_validate(
            {**self.BASE, "role_match": {"is_same_role_family": True}}
        )
        assert result.role_match.evidence == ""


# ---------------------------------------------------------------------------
# Averaging carries the gate fields fail-closed — finding A + G-273 interaction
# ---------------------------------------------------------------------------


class TestAverageCarriesGate:
    def test_mismatch_from_either_pass_propagates(self):
        clean = _make_score_result(6.0, role_match=RoleMatch(is_same_role_family=True))
        mismatch = _make_score_result(5.0, role_match=RoleMatch(is_same_role_family=False))
        merged = _average_score_results(clean, mismatch)
        assert merged.role_match is not None
        assert merged.role_match.is_same_role_family is False
        # Gate then caps the averaged score.
        assert apply_role_fit_gate(merged).fit_score == 3.0

    def test_disqualifiers_unioned(self):
        a = _make_score_result(6.0, disqualifiers=["no visa"])
        b = _make_score_result(5.0, disqualifiers=["seniority off by 2 levels", "no visa"])
        merged = _average_score_results(a, b)
        assert set(merged.disqualifiers) == {"no visa", "seniority off by 2 levels"}

    def test_both_clean_stays_clean(self):
        a = _make_score_result(6.0, role_match=RoleMatch(is_same_role_family=True))
        b = _make_score_result(5.0, role_match=RoleMatch(is_same_role_family=True))
        merged = _average_score_results(a, b)
        assert merged.role_match.is_same_role_family is True
        assert apply_role_fit_gate(merged).fit_score == merged.fit_score == 5.5

    def test_backcompat_none_both(self):
        merged = _average_score_results(_make_score_result(6.0), _make_score_result(5.0))
        assert merged.role_match is None
        assert merged.disqualifiers == []


# ---------------------------------------------------------------------------
# End-to-end through score_job (production path) — finding A
# ---------------------------------------------------------------------------


class TestScoreJobGate:
    @pytest.mark.asyncio
    async def test_wrong_role_capped_end_to_end(self, db_session: Session):
        """A high-scoring wrong-role dream-company job persists fit_score ≤ 3."""
        result = _make_score_result(
            8.7, role_match=RoleMatch(is_same_role_family=False, evidence="SRE role, TPM candidate")
        )
        provider = AsyncMock()
        provider.score.return_value = _make_ai_response(result)

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored = await score_job(
                db_session,
                profile_id=1,
                job_description="Site Reliability Engineer at a famous AI lab",
                job_title="Senior SRE",
                job_company="Anthropic",
            )

        assert scored.fit_score <= 3.0
        # Capped below the borderline zone → no wasteful second pass.
        assert provider.score.call_count == 1

    @pytest.mark.asyncio
    async def test_disqualified_capped_end_to_end(self, db_session: Session):
        result = _make_score_result(9.2, disqualifiers=["requires active TS/SCI clearance"])
        provider = AsyncMock()
        provider.score.return_value = _make_ai_response(result)

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = False
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored = await score_job(
                db_session,
                profile_id=1,
                job_description="TPM role requiring an active security clearance",
                job_title="TPM",
                job_company="DefenseCorp",
            )

        assert scored.fit_score <= 3.0

    @pytest.mark.asyncio
    async def test_genuine_fit_unchanged_end_to_end(self, db_session: Session):
        """A genuine same-family fit is not capped."""
        result = _make_score_result(
            8.5, role_match=RoleMatch(is_same_role_family=True, evidence="TPM ↔ TPM")
        )
        provider = AsyncMock()
        provider.score.return_value = _make_ai_response(result)

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = False
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored = await score_job(
                db_session,
                profile_id=1,
                job_description="Technical Program Manager, AI Platform",
                job_title="TPM",
                job_company="Anthropic",
            )

        assert scored.fit_score == 8.5

    @pytest.mark.asyncio
    async def test_backcompat_no_gate_fields_end_to_end(self, db_session: Session):
        """A provider that omits gate fields (legacy/mock) scores normally."""
        result = _make_score_result(8.5)  # role_match=None, disqualifiers=[]
        provider = AsyncMock()
        provider.score.return_value = _make_ai_response(result)

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = False
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored = await score_job(
                db_session,
                profile_id=1,
                job_description="Some role",
                job_title="TPM",
                job_company="Startup",
            )

        assert scored.fit_score == 8.5


# ---------------------------------------------------------------------------
# Batch path (daily scan) applies the gate — finding A
# ---------------------------------------------------------------------------


class TestBatchGate:
    def _item(self, job_id: str, fit: float, **extra) -> dict:
        base = {
            "job_id": job_id,
            "fit_score": fit,
            "reasoning": "R" * 120,
            "estimated_salary": "$150k",
            "effort_flag": "medium",
            "prep_level": "moderate",
            "prep_notes": "n",
            "readiness_score": 80,
            "career_alignment": 8,
            "score_breakdown": [
                {"factor": "a", "contribution": 1, "description": "d"},
                {"factor": "b", "contribution": 1, "description": "d"},
                {"factor": "c", "contribution": 1, "description": "d"},
            ],
        }
        base.update(extra)
        return base

    def test_batch_caps_role_mismatch(self):
        import json

        items = [
            self._item("1", 9.0, role_match={"is_same_role_family": False, "evidence": "SWE"}),
            self._item("2", 8.5),  # genuine, no gate fields
        ]
        parsed = parse_batch_response(json.dumps(items), ["1", "2"])
        assert parsed["1"].fit_score == 3.0
        assert parsed["2"].fit_score == 8.5

    def test_batch_caps_disqualifier_positional(self):
        import json

        # No job_id fields → positional mapping path.
        items = [
            self._item("", 9.0, disqualifiers=["no visa"]),
            self._item("", 7.0),
        ]
        for it in items:
            del it["job_id"]
        parsed = parse_batch_response(json.dumps(items), ["10", "20"])
        assert parsed["10"].fit_score == 3.0
        assert parsed["20"].fit_score == 7.0

    def test_batch_prompt_instructs_gate(self):
        prompt, _ = build_batch_prompt(
            [{"id": 1, "title": "SWE", "company": "X", "description": "desc"}],
            {"job_family": "TPM", "location": "Berlin"},
        )
        assert "role_match" in prompt
        assert "is_same_role_family" in prompt
        assert "disqualifiers" in prompt
        assert "capped at 3" in prompt


# ---------------------------------------------------------------------------
# Prompt guardrail content — findings B, C, D (lives in the provider preamble)
# ---------------------------------------------------------------------------


class TestPromptGuardrails:
    """The guardrails ship in ai.base.ROLE_FIT_GATE_PROMPT (provider preamble)."""

    def test_emits_gate_fields(self):
        p = ROLE_FIT_GATE_PROMPT
        assert "role_match" in p
        assert "is_same_role_family" in p
        assert "disqualifiers" in p

    def test_reason_before_score_and_weakness(self):
        # Finding C: reason-before-score + required against/weakness note.
        p = ROLE_FIT_GATE_PROMPT.lower()
        assert "reason before you score" in p
        assert "against" in p
        assert "reject" in p

    def test_company_fit_scoped_and_capped(self):
        # Finding B: company_fit = culture/values/size only, ±1, prestige → desire.
        p = ROLE_FIT_GATE_PROMPT
        assert "±1" in p
        assert "culture" in p.lower()
        assert "prestige" in p.lower()
        assert "desire" in p.lower()

    def test_dimension_tiers_present(self):
        # Finding B: primary technical + seniority, minor capped company_fit.
        p = ROLE_FIT_GATE_PROMPT.lower()
        assert "primary" in p
        assert "technical_fit" in p
        assert "seniority_alignment" in p

    def test_negative_and_positive_anchors(self):
        # Finding D: a strong-company/wrong-role negative anchor + a genuine high.
        p = ROLE_FIT_GATE_PROMPT.lower()
        assert "negative" in p
        assert "positive" in p

    def test_cap_ceiling_documented(self):
        assert "capped at 3" in ROLE_FIT_GATE_PROMPT.lower()

    def test_guard_absent_from_build_scoring_prompt(self):
        # Golden-set stability invariant: _build_scoring_prompt must NOT carry the
        # guard (the deterministic golden mock hashes its output). The guard
        # reaches real models via the provider preamble instead.
        prompt = _build_scoring_prompt(
            job_description="A job",
            job_title="Senior SRE",
            job_company="Anthropic",
            profile_data={"name": "T", "location": "Berlin", "job_family": "TPM", "weights": {}},
        )
        assert "is_same_role_family" not in prompt
        assert "anti-halo" not in prompt.lower()

    @pytest.mark.asyncio
    async def test_provider_score_prepends_guard(self):
        """A representative provider (Mistral) prepends the gate preamble to its
        score prompt so real models receive it."""
        from career_os.ai.mistral_provider import MistralProvider

        provider = MistralProvider(api_key="test-key")
        captured: dict = {}

        async def _fake_complete(prompt, **kwargs):
            captured["prompt"] = prompt
            return MagicMock(structured=None)

        with patch.object(provider, "complete", side_effect=_fake_complete):
            await provider.score(
                job_description="Some job description",
                profile_data={"job_family": "TPM"},
            )

        assert captured["prompt"].startswith(ROLE_FIT_GATE_PROMPT)
        assert "is_same_role_family" in captured["prompt"]
