"""Tests for the tiered operating-model functions in tools/job_scorer.py.

Covers is_dream_tier / apply_floors / classify_tier / assign_tiers using FICTIONAL
example dream-tier entries. Adds tools/ to sys.path (tools-test convention).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_scorer import apply_floors as _apply_floors
from job_scorer import (
    assign_tiers,
    classify_tier,
    is_api_submittable,
    is_dream_tier,
)


class TestDreamTierFloor:
    def _job(self, company, score, location="Remote, EU", geo_class="eligible_remote"):
        return {
            "title": "Product Manager",
            "company": company,
            "fit_score": score,
            "location": location,
            "geo_class": geo_class,
            "fit_reasoning": "x",
        }

    def test_is_dream_tier(self):
        assert is_dream_tier("Zephyrx")
        assert is_dream_tier("Aspirational Labs")
        assert not is_dream_tier("Acme Corp")

    def test_dream_tier_word_boundary_no_false_positive(self):
        # word-boundary match (not substring): a longer word must NOT match.
        assert is_dream_tier("Zephyrxian Systems") is False
        assert is_dream_tier("Zephyrx") is True

    def test_floors_underscored_dream_company(self):
        jobs = _apply_floors([self._job("Zephyrx", 4)])
        assert jobs[0]["fit_score"] == 8
        assert jobs[0]["floor_applied"] is True
        assert jobs[0]["review_flag"] is True

    def test_does_not_lower_high_dream_score(self):
        jobs = _apply_floors([self._job("Aspirational Labs", 9)])
        assert jobs[0]["fit_score"] == 9
        assert not jobs[0].get("floor_applied")

    def test_does_not_resurrect_blocked(self):
        # A blocked/pre-filtered dream-tier row (score 0) must stay 0.
        jobs = _apply_floors([self._job("Zephyrx", 0)])
        assert jobs[0]["fit_score"] == 0

    def test_geo_foreign_dream_not_floored_into_digest(self):
        jobs = _apply_floors([self._job("Zephyrx", 3, location="Paris", geo_class="foreign")])
        assert jobs[0]["fit_score"] == 3
        assert jobs[0]["review_flag"] is True

    def test_non_dream_untouched(self):
        jobs = _apply_floors([self._job("Acme Corp", 4)])
        assert jobs[0]["fit_score"] == 4

    def test_floor_does_not_resurrect_hard_capped(self):
        # A wrong-function hard-capped dream role must NOT be floored (that would
        # resurrect a sales/HR role at a dream company); it stays capped but visible.
        jobs = _apply_floors(
            [
                {
                    "title": "Account Executive",
                    "company": "Zephyrx",
                    "fit_score": 2,
                    "location": "Remote, EU",
                    "geo_class": "eligible_remote",
                    "fit_reasoning": "x",
                    "cap_applied": True,
                    "cap_reason": "wrong_function",
                }
            ]
        )
        assert jobs[0]["fit_score"] == 2  # stays capped
        assert not jobs[0].get("floor_applied")
        assert jobs[0]["review_flag"] is True  # but visible for review


class TestTierClassifier:
    def _j(
        self,
        score,
        company="Acme",
        source="greenhouse",
        url="https://boards.greenhouse.io/acme/jobs/1",
        geo_class="eligible_remote",
        **extra,
    ):
        d = {
            "fit_score": score,
            "company": company,
            "source": source,
            "url": url,
            "geo_class": geo_class,
        }
        d.update(extra)
        return d

    def test_t1_dream_company_even_low_score(self):
        assert classify_tier(self._j(4, company="Zephyrx")) == "T1"

    def test_t1_high_score(self):
        assert classify_tier(self._j(9, company="Random Co")) == "T1"

    def test_t1_warm_intro(self):
        assert classify_tier(self._j(5, warm_intro=True)) == "T1"

    def test_t2_strong_fit(self):
        assert classify_tier(self._j(6)) == "T2"
        assert classify_tier(self._j(7)) == "T2"

    def test_t3_acceptable_autofillable(self):
        assert classify_tier(self._j(5, source="ashby")) == "T3"

    def test_t3_requires_ats_source(self):
        # score 5 on a non-ATS board is not auto-fillable -> no tier
        assert classify_tier(self._j(5, source="ai-jobs", url="https://ai-jobs.net/x")) is None

    def test_t3_requires_geo_eligible(self):
        assert classify_tier(self._j(5, geo_class="foreign")) is None

    def test_below_bar_no_tier(self):
        assert classify_tier(self._j(4)) is None

    def test_blocked_not_resurrected(self):
        assert classify_tier(self._j(0, company="Zephyrx")) is None

    def test_is_api_submittable(self):
        assert (
            is_api_submittable(
                self._j(5, source="workable", url="https://apply.workable.com/acme/")
            )
            is True
        )
        assert is_api_submittable(self._j(5, source="indeed", url="https://indeed.com/x")) is False
        assert is_api_submittable(self._j(5, source="greenhouse", url="")) is False

    def test_spoofed_non_ats_host_rejected(self):
        # Security: source says greenhouse but the URL is a foreign host -> NOT
        # auto-fillable (would otherwise lure PII auto-fill onto an attacker page).
        assert (
            is_api_submittable(
                self._j(5, source="greenhouse", url="https://attacker.example/apply")
            )
            is False
        )
        assert (
            classify_tier(self._j(5, source="greenhouse", url="https://attacker.example/apply"))
            is None
        )
        # non-https ATS host also rejected
        assert (
            is_api_submittable(
                self._j(5, source="greenhouse", url="http://boards.greenhouse.io/x/jobs/1")
            )
            is False
        )

    def test_assign_tiers_sets_fields(self):
        jobs = [self._j(9), self._j(5, source="ashby"), self._j(2)]
        assign_tiers(jobs)
        assert jobs[0]["tier"] == "T1" and jobs[0]["auto_fillable"] is False
        assert jobs[1]["tier"] == "T3" and jobs[1]["auto_fillable"] is True
        assert jobs[2]["tier"] is None and jobs[2]["auto_fillable"] is False
