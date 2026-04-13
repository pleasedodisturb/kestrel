"""Tests for the PII masking layer (career_os.ai.pii_masking)."""

from __future__ import annotations

import pytest

from career_os.ai.base import AIProvider
from career_os.ai.pii_masking import MaskedProvider, MaskMapping, PIIMasker
from career_os.schemas.ai import AIFeature, AIResponse, ScoreResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def masker() -> PIIMasker:
    return PIIMasker()


# ---------------------------------------------------------------------------
# PIIMasker — mask()
# ---------------------------------------------------------------------------


class TestMaskEmail:
    def test_single_email(self, masker: PIIMasker) -> None:
        text = "Contact me at alice@example.com for details."
        masked, mapping = masker.mask(text)
        assert "alice@example.com" not in masked
        assert "[EMAIL_1]" in masked
        assert mapping.placeholder_to_original["[EMAIL_1]"] == "alice@example.com"

    def test_multiple_emails(self, masker: PIIMasker) -> None:
        text = "From bob@corp.io to carol@test.org"
        masked, mapping = masker.mask(text)
        assert "[EMAIL_1]" in masked
        assert "[EMAIL_2]" in masked
        assert len(mapping.placeholder_to_original) == 2

    def test_duplicate_email_reuses_placeholder(self, masker: PIIMasker) -> None:
        text = "Send to me@x.com and again me@x.com"
        masked, mapping = masker.mask(text)
        assert masked.count("[EMAIL_1]") == 2
        assert len(mapping.placeholder_to_original) == 1


class TestMaskPhone:
    def test_international_phone(self, masker: PIIMasker) -> None:
        text = "Call +49 170 1234567 anytime."
        masked, _ = masker.mask(text)
        assert "+49 170 1234567" not in masked
        assert "[PHONE_1]" in masked

    def test_us_phone(self, masker: PIIMasker) -> None:
        text = "Reach me at (555) 123-4567."
        masked, _ = masker.mask(text)
        assert "(555) 123-4567" not in masked
        assert "[PHONE_1]" in masked


class TestMaskURL:
    def test_linkedin_url(self, masker: PIIMasker) -> None:
        text = "Profile: https://www.linkedin.com/in/johndoe"
        masked, _ = masker.mask(text)
        assert "linkedin.com" not in masked
        assert "[URL_1]" in masked

    def test_github_url(self, masker: PIIMasker) -> None:
        text = "Code at https://github.com/johndoe/repo"
        masked, _ = masker.mask(text)
        assert "github.com" not in masked
        assert "[URL_1]" in masked

    def test_non_target_url_not_masked(self, masker: PIIMasker) -> None:
        text = "See https://docs.python.org/3/ for info."
        masked, mapping = masker.mask(text)
        assert "https://docs.python.org/3/" in masked
        assert mapping.is_empty


class TestMaskSSN:
    def test_ssn_with_dashes(self, masker: PIIMasker) -> None:
        text = "SSN: 123-45-6789"
        masked, mapping = masker.mask(text)
        assert "123-45-6789" not in masked
        assert "[SSN_1]" in masked
        assert mapping.placeholder_to_original["[SSN_1]"] == "123-45-6789"

    def test_ssn_with_spaces(self, masker: PIIMasker) -> None:
        text = "Social: 123 45 6789"
        masked, mapping = masker.mask(text)
        assert "123 45 6789" not in masked
        assert any("SSN" in k for k in mapping.placeholder_to_original)


class TestMaskCreditCard:
    def test_16_digit_card(self, masker: PIIMasker) -> None:
        text = "Card: 4111111111111111"
        masked, mapping = masker.mask(text)
        assert "4111111111111111" not in masked
        assert any("CREDIT_CARD" in k for k in mapping.placeholder_to_original)

    def test_card_with_spaces(self, masker: PIIMasker) -> None:
        text = "Visa: 4111 1111 1111 1111"
        masked, _ = masker.mask(text)
        assert "4111 1111 1111 1111" not in masked

    def test_card_with_dashes(self, masker: PIIMasker) -> None:
        text = "Card: 4111-1111-1111-1111"
        masked, _ = masker.mask(text)
        assert "4111-1111-1111-1111" not in masked


class TestMaskIPAddress:
    def test_ipv4_address(self, masker: PIIMasker) -> None:
        text = "Server at 192.168.1.100 is up."
        masked, mapping = masker.mask(text)
        assert "192.168.1.100" not in masked
        assert any("IP_ADDR" in k for k in mapping.placeholder_to_original)

    def test_loopback(self, masker: PIIMasker) -> None:
        text = "Localhost: 127.0.0.1"
        masked, _ = masker.mask(text)
        assert "127.0.0.1" not in masked

    def test_rejects_invalid_octets(self, masker: PIIMasker) -> None:
        text = "Not an IP: 999.999.999.999"
        _, mapping = masker.mask(text)
        assert not any("IP_ADDR" in k for k in mapping.placeholder_to_original)


class TestMaskPassport:
    def test_us_passport(self, masker: PIIMasker) -> None:
        text = "Passport: C12345678"
        masked, mapping = masker.mask(text)
        assert "C12345678" not in masked
        assert any("PASSPORT" in k for k in mapping.placeholder_to_original)

    def test_lowercase_not_matched(self, masker: PIIMasker) -> None:
        text = "Code: c12345678"
        _, mapping = masker.mask(text)
        assert not any("PASSPORT" in k for k in mapping.placeholder_to_original)


class TestMaskMultiplePIITypes:
    def test_mixed_pii(self, masker: PIIMasker) -> None:
        text = "Email alice@example.com, call +49 170 1234567, see https://linkedin.com/in/alice"
        masked, mapping = masker.mask(text)
        assert "[EMAIL_1]" in masked
        assert "[PHONE_1]" in masked
        assert "[URL_1]" in masked
        assert len(mapping.placeholder_to_original) == 3

    def test_all_pii_types_in_one_text(self, masker: PIIMasker) -> None:
        text = (
            "Email alice@example.com, call +1 555-123-4567, "
            "see https://linkedin.com/in/alice, SSN 111-22-3333, "
            "card 4111111111111111, IP 10.0.0.1, passport A12345678."
        )
        _, mapping = masker.mask(text)
        categories = {k.split("_")[0].lstrip("[") for k in mapping.placeholder_to_original}
        assert "EMAIL" in categories
        assert "SSN" in categories
        assert "IP" in categories
        assert "PASSPORT" in categories


# ---------------------------------------------------------------------------
# PIIMasker — unmask()
# ---------------------------------------------------------------------------


class TestUnmask:
    def test_round_trip(self, masker: PIIMasker) -> None:
        original = "Reach alice@example.com or +1-555-123-4567"
        masked, mapping = masker.mask(original)
        restored = masker.unmask(masked, mapping)
        assert restored == original

    def test_unmask_with_empty_mapping(self, masker: PIIMasker) -> None:
        text = "No PII here at all."
        result = masker.unmask(text, MaskMapping())
        assert result == text


# ---------------------------------------------------------------------------
# No-PII passthrough
# ---------------------------------------------------------------------------


class TestNoPII:
    def test_no_pii_returns_unchanged(self, masker: PIIMasker) -> None:
        text = "This text has no personal information whatsoever."
        masked, mapping = masker.mask(text)
        assert masked == text
        assert mapping.is_empty


# ---------------------------------------------------------------------------
# MaskedProvider
# ---------------------------------------------------------------------------


class _StubProvider(AIProvider):
    """Minimal stub that echoes the prompt back as content."""

    @property
    def name(self) -> str:
        return "stub"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        **kwargs: object,
    ) -> AIResponse:
        # Echo the (possibly masked) prompt so tests can inspect it.
        return AIResponse(content=prompt, provider=self.name, feature=feature)

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        return AIResponse(
            content="scored",
            provider=self.name,
            feature=AIFeature.score,
            structured=ScoreResult(
                fit_score=7.5,
                reasoning="Good fit",
                estimated_salary="100k-120k",
                effort_flag="medium",
                prep_level="moderate",
                prep_notes="Review basics",
                readiness_score=75.0,
                career_alignment=8.0,
                score_breakdown=[
                    {"factor": "skills", "contribution": 2.0, "description": "Strong skills"},
                    {"factor": "experience", "contribution": 1.5, "description": "Good exp"},
                    {"factor": "culture", "contribution": 1.0, "description": "Culture match"},
                ],
            ),
        )


class TestMaskedProviderComplete:
    @pytest.mark.asyncio
    async def test_prompt_is_masked_before_inner(self) -> None:
        stub = _StubProvider()
        provider = MaskedProvider(stub)
        resp = await provider.complete("Email alice@example.com for info")
        # The stub echoes the prompt — if masking worked the echo contains the
        # placeholder, but the wrapper unmasks it before returning.
        assert "alice@example.com" in resp.content
        assert "[EMAIL_1]" not in resp.content

    @pytest.mark.asyncio
    async def test_no_pii_passthrough(self) -> None:
        stub = _StubProvider()
        provider = MaskedProvider(stub)
        resp = await provider.complete("Tell me about Python")
        assert resp.content == "Tell me about Python"

    @pytest.mark.asyncio
    async def test_name_delegates(self) -> None:
        stub = _StubProvider()
        provider = MaskedProvider(stub)
        assert provider.name == "stub"


class _RecordingProvider(_StubProvider):
    """Stub that records the job_description passed to score()."""

    def __init__(self) -> None:
        self.last_jd: str | None = None

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        self.last_jd = job_description
        return await super().score(job_description, profile_data, **kwargs)


class TestMaskedProviderScore:
    @pytest.mark.asyncio
    async def test_score_masks_pii_in_job_description(self) -> None:
        """PII in job_description should be masked before reaching the inner provider."""
        inner = _RecordingProvider()
        provider = MaskedProvider(inner)
        await provider.score("Contact alice@example.com to apply", {"profile": "data"})
        assert inner.last_jd is not None
        assert "alice@example.com" not in inner.last_jd
        assert "[EMAIL_1]" in inner.last_jd

    @pytest.mark.asyncio
    async def test_score_preserves_structured_data(self) -> None:
        stub = _StubProvider()
        provider = MaskedProvider(stub)
        resp = await provider.score("job desc with alice@example.com", {"profile": "data"})
        # Structured data untouched
        assert resp.structured is not None
        assert isinstance(resp.structured, ScoreResult)
        assert resp.structured.fit_score == 7.5
