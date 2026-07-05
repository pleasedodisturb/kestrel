"""T3 auto-fill + 1-click-confirm lane.

The volume lane: **auto-FILL, human-CONFIRM**. For a role that clears every
guardrail (geo / blocklist / salary-floor / dedup / no-open-Q / auto-fillable ATS),
this lane opens the apply form and populates it up to -- but never past -- the submit
button, then presents a queue. A human skims and clicks submit.

HARD INVARIANT: this module NEVER submits. It reuses only the *fill* helpers from
``auto_apply`` (``fill_ashby_browser`` / ``fill_lever_browser`` / ... ) and never
calls ``confirm_and_submit_browser`` / ``submit_lever_api`` / ``submit_greenhouse_api``
(the three code paths that actually POST). ``tools/tests/test_t3_lane.py`` enforces
this by poisoning those three functions and asserting the prefill path never trips
them.
"""

from __future__ import annotations

import contextlib
import re

from blocklist import is_blocked
from job_scorer import geo_eligibility, is_api_submittable
from normalize import job_key
from open_question_probe import probe_open_questions

# Functions that ACTUALLY submit. The prefill path must never call these; listed
# here so the invariant test can poison every one of them.
FORBIDDEN_SUBMIT_FUNCS: tuple[str, ...] = (
    "confirm_and_submit_browser",
    "submit_lever_api",
    "submit_greenhouse_api",
)


def _salary_below_floor(job: dict, floor: int) -> bool:
    """True only if the role's salary is KNOWN and its top number is below floor.

    Unknown/absent salary never blocks (most JDs omit it) -- we don't lose a gem
    over a missing number; the blocklist already kills known lowballers.
    """
    text = f"{job.get('estimated_salary', '')} {job.get('salary', '')}".lower()
    # ">= 40" filters out monthly figures / bonuses ("10k/month", "15k signing") that
    # would otherwise look like a sub-floor annual salary. Real annual bands are 40k+;
    # anything below the floor that matters is well above 40k.
    nums = [int(n) for n in re.findall(r"(\d{2,3})\s*k", text) if int(n) >= 40]
    if not nums:
        for raw in re.findall(r"\d[\d,\.]{4,}", text):  # bare digit-only annual, e.g. 95000
            with contextlib.suppress(ValueError):
                nums.append(int(re.sub(r"[,\.]", "", raw)) // 1000)
    return bool(nums) and max(nums) < (floor // 1000)


def guardrail_check(
    job: dict,
    *,
    taken_keys: set | None = None,
    salary_floor: int = 0,
    probe: bool = True,
    client=None,
) -> dict:
    """Run every T3 guardrail. Returns {eligible, reason, checks}.

    Guardrails (ALL must pass before a role is queued for prefill):
      blocklist · geo (not foreign) · salary-floor · dedup-vs-DB · auto-fillable ATS
      · no open questions (essay/custom required free-text).

    ``salary_floor`` is caller-configurable and defaults to 0 (disabled) so no
    personal compensation figure is baked into the module; pass your own floor to
    reject known lowball roles.
    """
    taken_keys = taken_keys or set()
    checks: dict = {}

    blocked = is_blocked(job.get("company"))
    checks["blocklist"] = "blocked" if blocked else "ok"

    # Trust the pipeline's authoritative geo_class (set from per-job offices) when
    # present; only recompute from the unreliable list-location string as a fallback.
    # Recomputing would discard the offices override the gate exists for.
    geo = job.get("geo_class") or geo_eligibility(
        job.get("location"), job.get("offices"), bool(job.get("remote"))
    )
    checks["geo"] = geo

    lowball = _salary_below_floor(job, salary_floor)
    checks["salary"] = "below_floor" if lowball else "ok"

    is_dup = job_key(job.get("company"), job.get("title")) in taken_keys
    checks["dedup"] = "duplicate" if is_dup else "ok"

    submittable = is_api_submittable(job)
    checks["ats"] = "ok" if submittable else "not_auto_fillable"

    open_q = {"checked": False, "has_open_questions": False, "reason": "not probed"}
    if probe and submittable:
        open_q = probe_open_questions(job.get("url", ""), job.get("source", ""), client=client)
    checks["open_questions"] = (
        "essay"
        if open_q.get("has_open_questions")
        else ("none" if open_q.get("checked") else "unknown")
    )

    # Decide. First failing guardrail wins the skip reason.
    if blocked:
        return {"eligible": False, "reason": f"blocklist: {blocked}", "checks": checks}
    if geo == "foreign":
        return {
            "eligible": False,
            "reason": f"geo-ineligible: {job.get('location')}",
            "checks": checks,
        }
    if lowball:
        return {"eligible": False, "reason": "salary below floor", "checks": checks}
    if is_dup:
        return {"eligible": False, "reason": "already in DB", "checks": checks}
    if not submittable:
        return {"eligible": False, "reason": "not on an auto-fillable ATS", "checks": checks}
    if open_q.get("has_open_questions"):
        labels = "; ".join(open_q.get("essay_labels", []))
        return {
            "eligible": False,
            "reason": f"open questions ({labels}) -> T2 kit",
            "checks": checks,
        }

    return {"eligible": True, "reason": "ready to prefill", "checks": checks}


def build_queue(
    jobs: list[dict],
    *,
    taken_keys: set | None = None,
    salary_floor: int = 0,
    probe: bool = True,
    client=None,
) -> dict:
    """Partition jobs into a prefill queue + a skip list (with reasons)."""
    queue: list[dict] = []
    skipped: list[dict] = []
    for job in jobs:
        verdict = guardrail_check(
            job, taken_keys=taken_keys, salary_floor=salary_floor, probe=probe, client=client
        )
        entry = {**job, "_guardrail": verdict}
        (queue if verdict["eligible"] else skipped).append(entry)
    return {
        "queue": queue,
        "skipped": skipped,
        "summary": {"prefill_ready": len(queue), "skipped": len(skipped)},
    }


def prefill_application(
    page, personal: dict, app: dict, *, cv: str = "", cover: str = "", dry_run: bool = True
) -> dict:
    """Fill ONE apply form up to the submit button. NEVER submits.

    Reuses auto_apply's per-ATS fill helpers (which open the form + populate fields +
    upload files) and then STOPS. There is no submit call anywhere on this path.
    Returns {status, platform}. status="prefilled" means it's parked at the submit
    button for the human to review and click.

    ``cv`` / ``cover`` are repo-relative paths to the CV + cover PDF to upload. The
    auto_apply fillers index ``app["cv"]`` / ``app["cover_letter"]`` directly, so we
    inject them here (defaulting to "" so a missing file degrades to a skipped upload
    rather than a KeyError).
    """
    import auto_apply

    app = {
        **app,
        "cv": cv or app.get("cv", ""),
        "cover_letter": cover or app.get("cover_letter", ""),
    }
    platform = auto_apply.detect_platform(app.get("url", ""))
    filler = {
        "ashby": auto_apply.fill_ashby_browser,
        "lever": auto_apply.fill_lever_browser,
        "greenhouse": auto_apply.fill_greenhouse_browser,
    }.get(platform, auto_apply.fill_generic_browser)

    try:
        filler(page, personal, app)
    except Exception as exc:  # pragma: no cover - live-browser variance
        return {"status": "fill_error", "platform": platform, "error": str(exc)}

    # Intentionally NO submit. Leave the form parked at the submit button for review.
    return {"status": "prefilled", "platform": platform}
