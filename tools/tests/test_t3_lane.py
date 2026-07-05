"""Tests for tools/t3_lane.py — guardrails + the NEVER-SUBMIT invariant.

Adds tools/ to sys.path so the module imports directly (tools-test convention).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import t3_lane


def _job(**k):
    d = {
        "company": "Acme",
        "title": "Product Manager AI",
        "location": "Berlin",
        "url": "https://job-boards.greenhouse.io/acme/jobs/1",
        "source": "greenhouse",
        "geo_class": "home",
        "fit_score": 5,
        "estimated_salary": "130-150k EUR",
    }
    d.update(k)
    return d


# --- guardrails ---


def test_clean_role_eligible(monkeypatch):
    monkeypatch.setattr(
        t3_lane,
        "probe_open_questions",
        lambda *a, **k: {"checked": True, "has_open_questions": False, "essay_labels": []},
    )
    v = t3_lane.guardrail_check(_job())
    assert v["eligible"] is True


def test_blocked_company_rejected():
    v = t3_lane.guardrail_check(_job(company="Evilcorp"), probe=False)
    assert v["eligible"] is False and "blocklist" in v["reason"]


def test_geo_foreign_rejected():
    v = t3_lane.guardrail_check(
        _job(location="San Francisco, CA", geo_class="foreign"), probe=False
    )
    assert v["eligible"] is False and "geo" in v["reason"]


def test_non_ats_rejected():
    # Non-ATS source AND a non-ATS host URL -> not auto-fillable.
    v = t3_lane.guardrail_check(
        _job(source="indeed", url="https://indeed.com/viewjob?jk=1"), probe=False
    )
    assert v["eligible"] is False and "auto-fillable" in v["reason"]


def test_dedup_rejected():
    from normalize import job_key

    taken = {job_key("Acme", "Product Manager AI")}
    v = t3_lane.guardrail_check(_job(), taken_keys=taken, probe=False)
    assert v["eligible"] is False and "DB" in v["reason"]


def test_essay_rejected(monkeypatch):
    monkeypatch.setattr(
        t3_lane,
        "probe_open_questions",
        lambda *a, **k: {"checked": True, "has_open_questions": True, "essay_labels": ["Why us?"]},
    )
    v = t3_lane.guardrail_check(_job())
    assert v["eligible"] is False and "open questions" in v["reason"]


@pytest.mark.parametrize(
    "text,floor,expect",
    [
        ("90k EUR", 100000, True),
        ("150k EUR", 100000, False),
        ("", 100000, False),  # unknown never blocks
        ("95000 EUR", 100000, True),  # bare digit-only annual parsed as 95k
    ],
)
def test_salary_floor(text, floor, expect):
    assert t3_lane._salary_below_floor({"estimated_salary": text}, floor) is expect


def test_salary_floor_disabled_by_default():
    # Default salary_floor=0 must never block any role (no personal figure baked in).
    assert t3_lane._salary_below_floor({"estimated_salary": "50k EUR"}, 0) is False


def test_build_queue_partitions(monkeypatch):
    monkeypatch.setattr(
        t3_lane,
        "probe_open_questions",
        lambda *a, **k: {"checked": True, "has_open_questions": False, "essay_labels": []},
    )
    jobs = [_job(), _job(company="Evilcorp")]
    q = t3_lane.build_queue(jobs)
    assert q["summary"]["prefill_ready"] == 1
    assert q["summary"]["skipped"] == 1


# --- THE INVARIANT: prefill never submits ---


def test_prefill_never_submits(monkeypatch):
    import auto_apply

    called: list[str] = []
    for name in t3_lane.FORBIDDEN_SUBMIT_FUNCS:
        monkeypatch.setattr(auto_apply, name, lambda *a, _n=name, **k: called.append(_n))
    # Also make the fillers no-ops so we isolate the submit question.
    for f in (
        "fill_ashby_browser",
        "fill_lever_browser",
        "fill_greenhouse_browser",
        "fill_generic_browser",
    ):
        monkeypatch.setattr(auto_apply, f, lambda *a, **k: None)

    page = MagicMock()
    res = t3_lane.prefill_application(
        page, {"first_name": "A", "last_name": "B", "email": "x@y.z"}, _job()
    )

    assert res["status"] == "prefilled"
    assert called == [], f"T3 prefill called a submit function: {called}"


def test_prefill_uses_correct_filler(monkeypatch):
    import auto_apply

    used = {}
    monkeypatch.setattr(
        auto_apply,
        "fill_greenhouse_browser",
        lambda *a, **k: used.setdefault("filler", "greenhouse"),
    )
    for name in t3_lane.FORBIDDEN_SUBMIT_FUNCS:
        monkeypatch.setattr(auto_apply, name, lambda *a, **k: pytest.fail("submitted!"))
    t3_lane.prefill_application(
        MagicMock(), {}, _job(url="https://job-boards.greenhouse.io/x/jobs/9")
    )
    assert used.get("filler") == "greenhouse"


def test_salary_monthly_or_bonus_not_blocked():
    # "10k/month" / "15k signing bonus" must not look like a sub-floor annual.
    assert t3_lane._salary_below_floor({"estimated_salary": "10k / month"}, 100000) is False
    assert t3_lane._salary_below_floor({"salary": "15k signing bonus"}, 100000) is False
    assert t3_lane._salary_below_floor({"estimated_salary": "90k EUR"}, 100000) is True


def test_guardrail_trusts_authoritative_geo_class(monkeypatch):
    monkeypatch.setattr(
        t3_lane,
        "probe_open_questions",
        lambda *a, **k: {"checked": True, "has_open_questions": False, "essay_labels": []},
    )
    # list-location string is a foreign city, but the pipeline-set geo_class is 'home'
    # (offices override). The guardrail must trust geo_class, not re-derive foreign.
    v = t3_lane.guardrail_check(_job(location="Paris, France", geo_class="home"))
    assert v["eligible"] is True
    assert v["checks"]["geo"] == "home"


def test_prefill_injects_cv_cover_keys(monkeypatch):
    import auto_apply

    captured = {}
    monkeypatch.setattr(
        auto_apply, "fill_greenhouse_browser", lambda page, personal, app: captured.update(app)
    )
    for n in t3_lane.FORBIDDEN_SUBMIT_FUNCS:
        monkeypatch.setattr(auto_apply, n, lambda *a, **k: pytest.fail("submitted!"))
    # job dict has NO cv/cover_letter -> prefill must inject them (avoid KeyError).
    t3_lane.prefill_application(MagicMock(), {}, _job(), cv="cv/x.pdf", cover="cv/c.pdf")
    assert captured.get("cv") == "cv/x.pdf"
    assert captured.get("cover_letter") == "cv/c.pdf"


# --- exercise the REAL fillers, assert none click submit ---


class _RecLocator:
    def __init__(self, sel, page):
        self._sel, self._page = sel, page

    def count(self):
        return 1

    def nth(self, i):
        return self

    @property
    def first(self):
        return self

    def click(self, *a, **k):
        import re as _re

        if _re.search(r"submit", self._sel, _re.I):
            self._page.submits.append(self._sel)

    def __getattr__(self, name):
        return lambda *a, **k: False if name in ("is_visible", "is_enabled") else None


class _RecPage:
    def __init__(self):
        self.submits = []

    def locator(self, sel):
        return _RecLocator(sel, self)

    def __getattr__(self, name):
        return lambda *a, **k: None


def test_real_fillers_never_click_submit(monkeypatch):
    import auto_apply

    monkeypatch.setattr(auto_apply.time, "sleep", lambda *a, **k: None)
    for n in t3_lane.FORBIDDEN_SUBMIT_FUNCS:
        monkeypatch.setattr(auto_apply, n, lambda *a, **k: pytest.fail("submit fn called"))
    personal = {
        "first_name": "A",
        "last_name": "B",
        "email": "a@b.c",
        "phone": "1",
        "linkedin": "",
        "github": "",
        "location": "Berlin",
    }
    for url in [
        "https://job-boards.greenhouse.io/x/jobs/1",
        "https://jobs.lever.co/x/1",
        "https://jobs.ashbyhq.com/x",
        "https://example.com/generic",
    ]:
        page = _RecPage()
        t3_lane.prefill_application(page, personal, _job(url=url), cv="cv/x.pdf", cover="cv/c.pdf")
        assert page.submits == [], f"real filler clicked submit for {url}: {page.submits}"
