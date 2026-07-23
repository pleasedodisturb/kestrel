"""Detect free-text "open questions" on an ATS apply form.

The tiered operating model routes a role to the T3 auto-fill lane only when it is
"no-open-Q" -- i.e. the apply form asks nothing beyond standard fields the pipeline
can populate (name/email/phone/CV/cover/LinkedIn/standard selects). A required free
essay ("Why do you want to work here?") or a custom required textarea means a human
must write something, so it stays in the T2 rapid-fire kit.

This probe is AUTHORITATIVE for Greenhouse (the questions API exposes label +
required + field types). For other ATSes it returns checked=False (unknown); the
T3 browser-fill detects an unfilled required textarea live as the real backstop.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from batch_probe import parse_greenhouse_url


def _is_greenhouse_host(url: str) -> bool:
    """True iff the URL's host is greenhouse.io or a subdomain of it.

    A substring test ("greenhouse.io" in url) also matches attacker-controlled
    hosts like greenhouse.io.evil.com or evil.com/greenhouse.io (CodeQL
    py/incomplete-url-substring-sanitization) — route on the parsed hostname.
    """
    host = (urlparse(url).hostname or "").lower()
    return host == "greenhouse.io" or host.endswith(".greenhouse.io")


# Standard fields the pipeline can auto-populate (substring match on the lowercased
# question label). A required textarea whose label hits one of these is NOT an essay.
_STANDARD_LABELS: tuple[str, ...] = (
    "first name",
    "last name",
    "full name",
    "name",
    "email",
    "phone",
    "resume",
    "cv",
    "cover letter",
    "linkedin",
    "github",
    "portfolio",
    "website",
    "location",
    "city",
    "country",
    "address",
    "pronoun",
    "how did you hear",
    "where did you hear",
    "referr",
    "salary",
    "compensation",
    "notice period",
    "start date",
    "availability",
    "work authoriz",
    "authorized to work",
    "visa",
    "sponsor",
    "relocat",
    # EEO / demographic selects (optional, not essays)
    "gender",
    "race",
    "ethnicit",
    "veteran",
    "disab",
    "hispanic",
    "lgbt",
)

_FILLABLE_FIELD_TYPES: frozenset[str] = frozenset(
    {"input_text", "input_file", "multi_value_single_select", "multi_value_multi_select", "boolean"}
)

# The ONLY free-text (textarea) questions that are standard, not essays. Everything
# else with a required textarea is a human-writes-it essay. Matching textareas
# specifically (rather than any label substring) avoids false negatives where an
# essay prompt merely contains a standard word -- "Name a project you're proud of"
# (has "name"), "your favorite website?" (has "website").
_TEXTAREA_STANDARD_LABELS: tuple[str, ...] = (
    "resume",
    "cv",
    "cover letter",
    "how did you hear",
    "where did you hear",
    "referr",
    "anything else",
    "additional info",
)


def _is_essay_question(q: dict) -> bool:
    """A required free-text question that is NOT a standard field => an essay."""
    if not q.get("required"):
        return False
    label = (q.get("label") or "").lower()
    field_types = {f.get("type") for f in q.get("fields", [])}
    if "textarea" in field_types:
        # A required free textarea is an essay unless it's one of the known-standard
        # textareas (resume/cover/how-did-you-hear/...).
        return not any(s in label for s in _TEXTAREA_STANDARD_LABELS)
    # No textarea: an essay only if there's no structured field type we can fill
    # (a standard input_text / select / file / boolean is fine).
    return not (field_types & _FILLABLE_FIELD_TYPES)


def probe_greenhouse(slug: str, job_id: str, client: httpx.Client | None = None) -> dict:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}?questions=true"
    owns = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=True)
    try:
        r = client.get(url)
        r.raise_for_status()
        questions = r.json().get("questions", [])
    except (httpx.HTTPError, ValueError) as exc:  # pragma: no cover - network
        return {
            "checked": False,
            "has_open_questions": False,
            "essay_labels": [],
            "reason": f"greenhouse questions fetch failed: {exc}",
        }
    finally:
        if owns:
            client.close()
    essays = [q.get("label", "?") for q in questions if _is_essay_question(q)]
    return {
        "checked": True,
        "has_open_questions": bool(essays),
        "essay_labels": essays,
        "reason": (
            f"{len(essays)} required free-text question(s)" if essays else "no open questions"
        ),
    }


def probe_open_questions(url: str, source: str, client: httpx.Client | None = None) -> dict:
    """Best-effort open-question probe for an apply URL.

    Returns {checked, has_open_questions, essay_labels, reason}. checked=False means
    we could not authoritatively determine it (caller decides; the T3 browser-fill
    detects live required textareas as the backstop).
    """
    src = (source or "").lower().strip()
    if src == "greenhouse" or _is_greenhouse_host(url or ""):
        parsed = parse_greenhouse_url(url or "")
        if parsed:
            return probe_greenhouse(parsed[0], parsed[1], client=client)
    return {
        "checked": False,
        "has_open_questions": False,
        "essay_labels": [],
        "reason": f"open-question probe not implemented for source={src!r}",
    }
