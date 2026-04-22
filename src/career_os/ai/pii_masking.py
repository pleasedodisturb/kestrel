"""Client-side PII masking layer for AI prompts.

Detects and replaces personally identifiable information (emails, phone numbers,
LinkedIn/GitHub URLs) before text is sent to external AI providers, and restores
originals in the response content.

**Best-effort heuristic** — regex-based detection has known limitations:
- Unicode homoglyph attacks may bypass email detection.
- International phone formats may not be caught.
- Only LinkedIn/GitHub URLs are masked; other identifying URLs pass through.
- Names, addresses, and national IDs are not detected.

For higher-fidelity PII detection, consider a dedicated NER library (e.g. Presidio).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from career_os.ai.base import AIProvider, ComplexityTier
from career_os.ai.observability import update_current_span
from career_os.schemas.ai import AIFeature, AIResponse

# ---------------------------------------------------------------------------
# Regex patterns for PII categories
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # NOTE: Order matters — more specific patterns must come before greedy
    # ones (e.g. PHONE) that could match digit substrings of other types.
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    (
        "URL",
        re.compile(r"https?://(?:www\.)?(?:linkedin\.com|github\.com)/\S+"),
    ),
    # SSN: 123-45-6789 or 123 45 6789
    ("SSN", re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b")),
    # Credit card numbers: 13–19 digits with optional spaces or dashes
    (
        "CREDIT_CARD",
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    ),
    # IPv4 addresses
    (
        "IP_ADDR",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
    ),
    # US passport number: 1 uppercase letter followed by 8 digits
    ("PASSPORT", re.compile(r"\b[A-Z]\d{8}\b")),
    # PHONE last — greedy digit matching would consume other patterns' digits
    (
        "PHONE",
        re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,5}"),
    ),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class MaskMapping:
    """Bidirectional mapping between PII originals and their placeholders."""

    placeholder_to_original: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return len(self.placeholder_to_original) == 0


# ---------------------------------------------------------------------------
# PIIMasker — regex-based PII detection and masking
# ---------------------------------------------------------------------------


class PIIMasker:
    """Detect and mask PII in text using regex patterns.

    Each distinct PII value receives a unique numbered placeholder such as
    ``[EMAIL_1]``, ``[PHONE_2]``, etc.  Repeated occurrences of the same value
    reuse the same placeholder.
    """

    def mask(self, text: str) -> tuple[str, MaskMapping]:
        """Replace PII in *text* with numbered placeholders.

        Returns:
            A ``(masked_text, mapping)`` tuple.  The mapping can later be
            passed to :meth:`unmask` to restore originals.
        """
        mapping = MaskMapping()
        # Track per-category counters and a value→placeholder cache so the
        # same literal always maps to the same placeholder.
        counters: dict[str, int] = {}
        seen: dict[str, str] = {}

        for category, pattern in _PATTERNS:

            def _replacer(match: re.Match[str], _cat: str = category) -> str:
                value = match.group(0)
                if value in seen:
                    return seen[value]
                counters.setdefault(_cat, 0)
                counters[_cat] += 1
                placeholder = f"[{_cat}_{counters[_cat]}]"
                seen[value] = placeholder
                mapping.placeholder_to_original[placeholder] = value
                return placeholder

            text = pattern.sub(_replacer, text)

        return text, mapping

    def unmask(self, text: str, mapping: MaskMapping) -> str:
        """Restore original PII values from *mapping* into *text*."""
        for placeholder, original in mapping.placeholder_to_original.items():
            text = text.replace(placeholder, original)
        return text


# ---------------------------------------------------------------------------
# MaskedProvider — transparent wrapper around any AIProvider
# ---------------------------------------------------------------------------


class MaskedProvider(AIProvider):
    """Wrap an :class:`AIProvider` with automatic PII masking.

    * Masks the prompt **before** it reaches the inner provider.
    * Unmasks the ``content`` field of the response **after** receiving it.
    * Does **not** unmask ``structured`` data — score results, gap analyses,
      etc. should never contain PII.
    """

    def __init__(self, inner: AIProvider) -> None:
        self._inner = inner
        self._masker = PIIMasker()

    # -- AIProvider interface ------------------------------------------------

    @property
    def name(self) -> str:  # pragma: no cover – trivial delegation
        return self._inner.name

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        masked_prompt, mapping = self._masker.mask(prompt)
        update_current_span(
            metadata={"pii_detections": len(mapping.placeholder_to_original)}
        )
        response = await self._inner.complete(
            masked_prompt, feature=feature, context=context, tier=tier, **kwargs
        )
        return self._unmask_response(response, mapping)

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        masked_jd, jd_mapping = self._masker.mask(job_description)
        # Mask string values inside profile_data
        profile_str = json.dumps(profile_data)
        masked_profile_str, profile_mapping = self._masker.mask(profile_str)
        masked_profile = json.loads(masked_profile_str)

        # Merge both mappings for unmasking the response
        combined = MaskMapping()
        combined.placeholder_to_original.update(jd_mapping.placeholder_to_original)
        combined.placeholder_to_original.update(profile_mapping.placeholder_to_original)

        update_current_span(
            metadata={"pii_detections": len(combined.placeholder_to_original)}
        )
        response = await self._inner.score(masked_jd, masked_profile, tier=tier, **kwargs)
        return self._unmask_response(response, combined)

    # -- helpers -------------------------------------------------------------

    def _unmask_response(self, response: AIResponse, mapping: MaskMapping) -> AIResponse:
        """Return a new AIResponse with PII restored in ``content`` only."""
        if mapping.is_empty:
            return response
        return response.model_copy(
            update={"content": self._masker.unmask(response.content, mapping)},
        )
