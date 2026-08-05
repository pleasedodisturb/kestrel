"""Config-driven geographic vocabulary for the geo-eligibility engine.

A :class:`GeoProfile` carries every region-specific regex the classifier
consults. The engine itself (``career_os.services.geo.classifier``) contains
NO home-region vocabulary: swapping the profile swaps the geography. A field
left as ``None`` simply never matches, so partial profiles are valid.

Two builders are provided, both compiling every pattern exactly once at
construction time (never inside a classify call):

- :func:`build_profile` — compile explicit pattern strings (used by the
  shipped presets in ``career_os.services.geo.presets``).
- :meth:`GeoProfile.from_home_tokens` — build a profile from a flat token
  vocabulary (used to drive the engine from user configuration).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# Pan-region vocabulary used by ``from_home_tokens`` when the caller allows
# pan-region remote postings. Deliberately region-agnostic: these tokens mean
# "open to everyone" no matter where home is.
_PAN_REGION_WIDE = r"\b(?:global(?:ly)?|worldwide|anywhere|international)\b"
_PAN_REGION_REMOTE_PHRASE = (
    r"(?:work[ \-]from[ \-]anywhere|remote[ ,\-]*(?:global(?:ly)?|worldwide|anywhere)|"
    r"(?:global(?:ly)?|worldwide|anywhere)[ ,\-]*remote)"
)


@dataclass(frozen=True)
class GeoProfile:
    """Immutable bundle of compiled geographic patterns for one candidate.

    Every field except ``name`` is a compiled ``re.Pattern`` or ``None``.
    A ``None`` field never matches — required for partial profiles.
    """

    name: str
    # Commute belt: reachable without moving house. Ranking only, never a filter.
    home_local: re.Pattern[str] | None = None
    # Home country and its cities: a move, but no visa.
    home_country: re.Pattern[str] | None = None
    # Onsite locations reachable without a work visa (freedom-of-movement region).
    visa_free_region: re.Pattern[str] | None = None
    # Bare pan-region tokens that are eligible on their own ("global", "anywhere").
    visa_free_wide: re.Pattern[str] | None = None
    # Remote-region phrasings ("remote - <region>", "anywhere in <region>").
    visa_free_remote_phrase: re.Pattern[str] | None = None
    # Onsite locations that require a work visa; kept distinct so the burden
    # stays visible to the caller.
    visa_required: re.Pattern[str] | None = None
    # Explicitly ineligible places.
    foreign: re.Pattern[str] | None = None
    # Tokens that rescue a multi-region posting ("EMEA/AMER"-shaped strings).
    eligible_region: re.Pattern[str] | None = None
    # Market-naming tokens in a title ("(AMER)", ", Korea") that bind first.
    title_region_foreign: re.Pattern[str] | None = None

    @classmethod
    def from_home_tokens(
        cls,
        name: str,
        home_tokens: Iterable[str],
        *,
        home_local_tokens: Iterable[str] = (),
        visa_required_tokens: Iterable[str] = (),
        extra_foreign_tokens: Iterable[str] = (),
        allow_pan_region_remote: bool = True,
    ) -> GeoProfile:
        """Build a profile from a flat token vocabulary.

        ``home_tokens``, ``allow_pan_region_remote`` and ``extra_foreign_tokens``
        map 1:1 onto the user-facing geo configuration keys.
        ``home_local_tokens`` and ``visa_required_tokens`` are code-level
        parameters only. Tokens are ``re.escape``-d and joined into a
        word-boundary alternation, so a hostile token cannot inject regex
        metacharacters or a catastrophic pattern.

        When ``home_local_tokens`` is empty, ``home_local`` mirrors
        ``home_country`` (every home hit counts as local). The ``foreign``
        pattern is the shared public geography list OR'd with
        ``extra_foreign_tokens``, minus any token already claimed by a
        home/local/visa-required vocabulary.
        """
        # Imported lazily: presets.py imports build_profile from this module,
        # so a module-level import here would be circular.
        from career_os.services.geo.presets import PUBLIC_GEOGRAPHY_TOKENS

        home = _normalize_tokens(home_tokens)
        local = _normalize_tokens(home_local_tokens)
        visa_required = _normalize_tokens(visa_required_tokens)
        extra_foreign = _normalize_tokens(extra_foreign_tokens)

        reserved = set(home) | set(local) | set(visa_required)
        foreign_tokens = [t for t in PUBLIC_GEOGRAPHY_TOKENS if t.lower() not in reserved]
        foreign_tokens.extend(t for t in extra_foreign if t not in reserved)

        home_country = _compile_tokens(home)
        home_local = _compile_tokens(local) if local else home_country

        if allow_pan_region_remote:
            visa_free_wide = re.compile(_PAN_REGION_WIDE, re.IGNORECASE)
            visa_free_remote_phrase = re.compile(_PAN_REGION_REMOTE_PHRASE, re.IGNORECASE)
        else:
            visa_free_wide = None
            visa_free_remote_phrase = None

        return cls(
            name=name,
            home_local=home_local,
            home_country=home_country,
            visa_free_region=None,
            visa_free_wide=visa_free_wide,
            visa_free_remote_phrase=visa_free_remote_phrase,
            visa_required=_compile_tokens(visa_required),
            foreign=_compile_tokens(foreign_tokens),
            eligible_region=None,
            title_region_foreign=None,
        )


def _normalize_tokens(tokens: Iterable[str]) -> list[str]:
    """Lowercase, strip and de-duplicate a token vocabulary, keeping order."""
    seen: dict[str, None] = {}
    for token in tokens:
        cleaned = str(token).lower().strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


def _compile_tokens(tokens: Iterable[str]) -> re.Pattern[str] | None:
    """Compile a token list into a word-boundary alternation (or ``None``)."""
    escaped = [re.escape(t) for t in _normalize_tokens(tokens)]
    if not escaped:
        return None
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


def build_profile(name: str, **pattern_strings: str | None) -> GeoProfile:
    """Compile explicit pattern strings into a :class:`GeoProfile`.

    Each keyword must be a :class:`GeoProfile` pattern field name; the value is
    a regex source string (compiled once, with ``re.IGNORECASE``) or ``None``.
    """
    compiled: dict[str, re.Pattern[str] | None] = {}
    for field_name, source in pattern_strings.items():
        compiled[field_name] = re.compile(source, re.IGNORECASE) if source is not None else None
    return GeoProfile(name=name, **compiled)
