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
# pan-region remote postings. The first group is truly region-agnostic
# (global/worldwide/anywhere); the second is European multi-country shorthand
# (emea/dach/...), carried over from the gate this replaces. A non-European
# home config that should NOT treat bare "EMEA" as reachable needs a custom
# ``build_profile`` — the flat config route cannot express that distinction.
# The multi-country names are absent from ``PUBLIC_GEOGRAPHY_TOKENS`` on
# purpose — nothing here can collide with the foreign vocabulary.
_PAN_REGION_WIDE = (
    r"\b(?:global(?:ly)?|worldwide|anywhere|international|"
    r"emea|european|europe|dach|benelux|nordics|eu[\s\-]?wide)\b"
)
_PAN_REGION_REMOTE_PHRASE = (
    r"(?:work[ \-]from[ \-]anywhere|remote[ ,\-]*(?:global(?:ly)?|worldwide|anywhere)|"
    r"(?:global(?:ly)?|worldwide|anywhere)[ ,\-]*remote)"
)

# Short/ambiguous foreign signals that are only safe to read off a LOCATION,
# OFFICE or TITLE string. They are deliberately NEVER consulted on description
# prose, where bare "us" means "join us" rather than the United States. Each
# entry pairs the bare token (matched against the caller's reserved vocabulary
# so a home region named "UK" is never made foreign) with its pattern source.
_FOREIGN_LOCATION_ONLY: tuple[tuple[str, str], ...] = (
    ("us", r"\bus\b"),
    ("uk", r"\buk\b"),
    ("na", r"\bna\b"),  # North America
    ("u.s.", r"\bu\.s\.(?:a\b)?"),
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
    # Short foreign signals safe ONLY on location/office/title strings, never on
    # description prose (see ``_FOREIGN_LOCATION_ONLY``).
    foreign_location_only: re.Pattern[str] | None = None
    # Tokens that rescue a multi-region posting ("EMEA/AMER"-shaped strings).
    eligible_region: re.Pattern[str] | None = None
    # Market-naming tokens in a title ("(AMER)", ", Korea") that bind first.
    title_region_foreign: re.Pattern[str] | None = None
    # When True a home hit wins outright, even alongside a foreign token. Set by
    # ``from_home_tokens`` (the user-config route), where the home vocabulary is
    # an explicit "this is MY region" statement and the foreign vocabulary is a
    # generic public list that cannot know which cities sit in the home country.
    # The presets keep False: they carry curated, non-overlapping vocabularies
    # and rely on the foreign token to veto (e.g. a home city named alongside a
    # foreign market in one string).
    home_wins: bool = False
    # When False an unspecified/bare "Remote" posting with no other geo signal
    # is ``unknown`` instead of ``eligible_remote`` — the user asked for an
    # explicit home-region anchor.
    allow_unspecified_remote: bool = True

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

        The returned profile sets ``home_wins=True``: a home token wins
        classification outright, even when the same string also carries a
        foreign token. Token subtraction alone cannot honour that contract —
        it has no city-to-country knowledge, so a home-country city that
        appears in the public list ("Berlin, Germany" for a ``germany`` home)
        would otherwise classify foreign inside the user's own country.

        ``allow_pan_region_remote`` drives BOTH the pan-region vocabulary and
        ``allow_unspecified_remote``; setting it False is what makes an
        unanchored "Remote" posting ``unknown`` rather than eligible.
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

        # Short foreign signals ("Remote - US") the plain token list cannot
        # express, minus anything the caller claimed as home.
        location_only = [src for tok, src in _FOREIGN_LOCATION_ONLY if tok not in reserved]
        foreign_location_only = (
            re.compile("|".join(location_only), re.IGNORECASE) if location_only else None
        )

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
            foreign_location_only=foreign_location_only,
            # The multi-region rescue (contract rule 1) needs an eligible
            # vocabulary to fire; without it "Remote EMEA/US" would classify
            # foreign off the US token alone. The pan-region vocabulary is the
            # config route's only notion of "eligible region", so reuse it.
            eligible_region=visa_free_wide,
            title_region_foreign=None,
            home_wins=True,
            allow_unspecified_remote=allow_pan_region_remote,
        )


def _normalize_tokens(tokens: Iterable[str]) -> list[str]:
    """Lowercase, strip and de-duplicate a token vocabulary, keeping order."""
    seen: dict[str, None] = {}
    for token in tokens:
        cleaned = str(token).lower().strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


def _token_pattern(token: str) -> str:
    """Escape one token and fence it with the word boundaries it can honour.

    A ``\\b`` is only meaningful next to a word character: appending one after a
    token ending in punctuation ("u.s.") demands a word character follow, so
    the token could never match at end-of-string or before a comma. The
    boundary is therefore applied per-side, per-token.
    """
    prefix = r"\b" if token[:1].isalnum() else ""
    suffix = r"\b" if token[-1:].isalnum() else ""
    return prefix + re.escape(token) + suffix


def _compile_tokens(tokens: Iterable[str]) -> re.Pattern[str] | None:
    """Compile a token list into a boundary-fenced alternation (or ``None``).

    Tokens with no alphanumeric character are dropped: unfenced, a token like
    ``"-"`` would match every hyphen in every string and classify the whole
    corpus off one stray config entry.
    """
    usable = [t for t in _normalize_tokens(tokens) if any(c.isalnum() for c in t)]
    if not usable:
        return None
    return re.compile("|".join(_token_pattern(t) for t in usable), re.IGNORECASE)


def build_profile(name: str, **pattern_strings: str | None) -> GeoProfile:
    """Compile explicit pattern strings into a :class:`GeoProfile`.

    Each keyword must be a :class:`GeoProfile` pattern field name; the value is
    a regex source string (compiled once, with ``re.IGNORECASE``) or ``None``.
    The non-pattern flags (``home_wins``, ``allow_unspecified_remote``) are not
    settable here — presets keep their defaults.

    CAVEAT: pattern strings are compiled verbatim, NOT escaped — that is the
    point of this route, but it means a catastrophic pattern (nested
    quantifiers such as ``(\\S+)+``) would hang the classifier on scraped text.
    Keep patterns to literal alternations with at most one non-nested
    quantifier, as the shipped presets do. Build profiles from untrusted input
    with :meth:`GeoProfile.from_home_tokens`, which ``re.escape``-s every token.
    """
    compiled: dict[str, re.Pattern[str] | None] = {}
    for field_name, source in pattern_strings.items():
        compiled[field_name] = re.compile(source, re.IGNORECASE) if source is not None else None
    return GeoProfile(name=name, **compiled)
