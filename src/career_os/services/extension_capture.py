"""Extension capture orchestration (G-1391 / Part B — "the eye" backend).

Turns a job captured by the browser extension into a *scored* ``DiscoveredJob``
by REUSING the existing services, never reimplementing scoring or its prompt:

- dedupe/normalization from ``services.discovery`` (``_normalize`` + the
  ``(profile_id, title, company, location)`` unique key),
- scoring from ``services.scoring.score_job`` (the single source of the prompt),
- a single ``AI_PROVIDER`` completion to extract structured fields when the
  client could only scrape raw text.

Cost/DoS is bounded per SECURITY T-01B-01: the JD/raw-text is size-capped
(``settings.extension_max_jd_chars``) BEFORE any LLM or scoring call, and the
raw-text extraction makes at most ONE provider call.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from career_os.ai.base import AIFeature
from career_os.ai.factory import get_ai_provider
from career_os.config import settings
from career_os.models.discovery import DiscoveredJob
from career_os.models.scoring import ScoredJob
from career_os.schemas.extension import CaptureRequest
from career_os.services.discovery import _normalize
from career_os.services.scoring import score_job

logger = logging.getLogger(__name__)

# Dimensional sub-scores are on a 0-10 scale; "mid" is the neutral midpoint used
# to decide whether seniority is a match for the plain-language gap.
_SENIORITY_OK_THRESHOLD = 5.0
# Cap the number of missing keywords surfaced in the plain-language gap so the
# string stays glanceable in the extension panel.
_MAX_MISSING_KEYWORDS = 5


class CaptureTooLargeError(ValueError):
    """Raised when the captured JD/raw-text exceeds settings.extension_max_jd_chars.

    A ``ValueError`` subclass so the route maps it to HTTP 413 (SECURITY
    T-01B-01) while callers can still catch it precisely.
    """


class CaptureIncompleteError(ValueError):
    """Raised when a payload has neither structured (title+company) nor raw text."""


# ---------------------------------------------------------------------------
# LLM extraction fallback (raw-text-only payloads)
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
Extract the job posting fields from the text below and return ONLY a JSON object
with these keys: "company", "title", "description", "location", "salary".
Use an empty string for any field you cannot determine. Do not add commentary.

Job posting text:
---
{raw_text}
---
"""


def _parse_extraction_json(content: str) -> dict:
    """Parse the provider's extraction reply into a dict, tolerating loose formatting.

    Strips common Markdown code fences and, failing a clean parse, extracts the
    first ``{...}`` object. Never raises — returns ``{}`` when nothing parses so
    the caller can fall back to raw text.
    """
    text = (content or "").strip()
    if text.startswith("```"):
        # Drop a leading ```json / ``` fence and any trailing fence.
        text = text.split("```", 2)
        text = text[1] if len(text) > 1 else ""
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass
    # Last resort: grab the first brace-delimited object.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


async def _extract_fields_via_llm(raw_text: str) -> dict:
    """Extract {company,title,description,location,salary} from raw text.

    Makes EXACTLY ONE ``provider.complete`` call. On an unparseable reply it
    falls back to using the raw text as the description so scoring can proceed.
    """
    provider = get_ai_provider()
    response = await provider.complete(
        _EXTRACTION_PROMPT.format(raw_text=raw_text),
        feature=AIFeature.complete,
    )
    fields = _parse_extraction_json(response.content)
    return {
        "company": str(fields.get("company") or "").strip(),
        "title": str(fields.get("title") or "").strip(),
        "description": str(fields.get("description") or "").strip() or raw_text,
        "location": str(fields.get("location") or "").strip(),
        "salary": str(fields.get("salary") or "").strip(),
    }


# ---------------------------------------------------------------------------
# Dedupe: find-or-create the DiscoveredJob
# ---------------------------------------------------------------------------


def _find_or_create_discovered_job(db: Session, profile_id: int, fields: dict) -> DiscoveredJob:
    """Return the existing DiscoveredJob for this (profile, title/company/location) or create one.

    Reuses discovery's ``_normalize`` for the dedup key so a captured job dedupes
    against the exact same unique tuple discovery uses. On a hit, a blank stored
    description is enriched with the freshly-captured one.
    """
    title = (fields.get("title") or "").strip() or "Unknown"
    company = (fields.get("company") or "").strip() or "Unknown"
    location = (fields.get("location") or "").strip()
    title_norm = _normalize(title)
    company_norm = _normalize(company)
    location_norm = _normalize(location)

    existing = (
        db.query(DiscoveredJob)
        .filter(
            DiscoveredJob.profile_id == profile_id,
            DiscoveredJob.title_normalized == title_norm,
            DiscoveredJob.company_normalized == company_norm,
            DiscoveredJob.location_normalized == location_norm,
        )
        .first()
    )
    if existing is not None:
        if not (existing.description or "").strip() and (fields.get("description") or "").strip():
            existing.description = fields["description"]
        db.flush()
        return existing

    source = (fields.get("source") or "").strip() or "extension"
    url = (fields.get("url") or "").strip()
    dj = DiscoveredJob(
        profile_id=profile_id,
        title=title,
        company=company,
        location=location,
        url=url or None,
        description=(fields.get("description") or "").strip() or None,
        salary_range=(fields.get("salary") or "").strip() or None,
        remote=bool(fields.get("remote", False)),
        posted_at=None,
        title_normalized=title_norm,
        company_normalized=company_norm,
        location_normalized=location_norm,
        sources=json.dumps([source]),
        source_urls=json.dumps([url] if url else []),
    )
    db.add(dj)
    db.flush()
    return dj


def _latest_fresh_score(db: Session, profile_id: int, discovered_job_id: int) -> ScoredJob | None:
    """Return the newest non-stale ScoredJob for this discovered job, or None.

    A capture that re-hits an already-scored job reuses this instead of paying
    for another LLM scoring call and writing a duplicate ScoredJob row (MED-03).
    Stale scores (weights/profile changed → ``is_stale``) are ignored so a
    re-capture correctly re-scores when the existing score is no longer valid.
    """
    return (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.discovered_job_id == discovered_job_id,
            ScoredJob.is_stale.is_(False),
        )
        .order_by(ScoredJob.created_at.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def capture_and_score(
    db: Session, payload: CaptureRequest, *, profile_id: int
) -> tuple[DiscoveredJob, ScoredJob]:
    """Normalize + dedupe + (optionally LLM-extract) + score a captured job.

    Returns ``(DiscoveredJob, ScoredJob)``. Raises ``CaptureTooLargeError`` (→413)
    for oversize input BEFORE any LLM/scoring call, ``CaptureIncompleteError``
    (→400) when nothing usable is present, and propagates scoring exceptions
    (``ProfileIncompleteError``, ``CreditsExhaustedError``/``ProviderQuotaError``,
    ``ScoringError``) for the route to map.
    """
    cap = settings.extension_max_jd_chars
    if cap and cap > 0:
        for candidate in ((payload.description or ""), (payload.raw_text or "")):
            if len(candidate) > cap:
                raise CaptureTooLargeError(f"Captured text exceeds the {cap}-character limit")

    title = (payload.title or "").strip()
    company = (payload.company or "").strip()
    description = (payload.description or "").strip()
    location = payload.location
    salary = payload.salary
    source = payload.source

    # Raw-text-only path: the client couldn't scrape structured fields. Exactly
    # one LLM call fills them in before dedupe + scoring.
    if not (title and company):
        raw_text = (payload.raw_text or "").strip() or description
        if not raw_text:
            raise CaptureIncompleteError("Capture needs either title+company or raw_text to score")
        extracted = await _extract_fields_via_llm(raw_text)
        title = title or extracted["title"]
        company = company or extracted["company"]
        description = description or extracted["description"]
        location = location or extracted["location"] or None
        salary = salary or extracted["salary"] or None

    fields = {
        "title": title,
        "company": company,
        "location": location or "",
        "description": description,
        "salary": salary or "",
        "url": payload.url,
        "source": source,
    }
    dj = _find_or_create_discovered_job(db, profile_id, fields)

    # Re-capture short-circuit (MED-03): if this job was already scored and the
    # score is still fresh, return it instead of making another paid LLM scoring
    # call and inserting a duplicate ScoredJob row. A brand-new capture has no
    # prior score, so this only triggers on a genuine dedupe hit.
    existing_score = _latest_fresh_score(db, profile_id, dj.id)
    if existing_score is not None:
        db.commit()  # persist any description enrichment from the dedupe hit
        db.refresh(dj)
        return dj, existing_score

    scored = await score_job(
        db,
        profile_id,
        job_description=description or dj.description or "",
        job_url=payload.url,
        job_title=dj.title,
        job_company=dj.company,
        discovered_job_id=dj.id,
    )
    db.refresh(dj)
    return dj, scored


# ---------------------------------------------------------------------------
# Plain-language gap
# ---------------------------------------------------------------------------


def _coerce_json_list(value: object) -> list:
    """Return a list from a JSON string / list / None. Never raises."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def build_plain_language_gap(scored: ScoredJob) -> str:
    """Build a glanceable gap string, e.g. "missing: Kubernetes, Go; seniority ✓".

    Derived from ``ats_keywords`` (unmatched → listed missing, capped) and
    ``dim_seniority_alignment`` (≥ mid → "seniority ✓"). Defensive against
    JSON-string / None / malformed fields — never raises.
    """
    missing: list[str] = []
    for kw in _coerce_json_list(getattr(scored, "ats_keywords", None)):
        if isinstance(kw, dict) and not kw.get("matched", False):
            keyword = str(kw.get("keyword") or "").strip()
            if keyword:
                missing.append(keyword)
        if len(missing) >= _MAX_MISSING_KEYWORDS:
            break

    parts: list[str] = []
    if missing:
        parts.append("missing: " + ", ".join(missing))
    else:
        parts.append("no major keyword gaps")

    seniority = getattr(scored, "dim_seniority_alignment", None)
    if isinstance(seniority, int | float):
        if seniority >= _SENIORITY_OK_THRESHOLD:
            parts.append("seniority ✓")
        else:
            parts.append("seniority gap")

    return "; ".join(parts)
