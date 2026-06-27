"""Tests for the Eyas-ported daily_pipeline improvements.

Covers the generic, PII-free pipeline changes upstreamed from Eyas (G-1217):
- source-priority ordering before the scoring cap (G-1114)
- budget-based scoring cap (G-1119)
- normalized dedup via job_key (G-1122)

tools/tests/ is not in the CI testpaths (pre-existing); run locally with:
pytest tools/tests/test_daily_pipeline_port.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# daily_pipeline.py inserts tools/ + src/ on sys.path at import time, but add
# tools/ here too so the import itself resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import daily_pipeline as dp  # noqa: E402
from daily_pipeline import (  # noqa: E402
    SCORING_CAP_CEILING,
    SCORING_CAP_FLOOR,
    _source_priority,
    effective_scoring_cap,
)


class TestSourceScoringPriority:
    def test_ats_sources_rank_ahead_of_job_boards(self):
        """Curated-company ATS boards must sort before generic boards."""
        assert _source_priority({"source": "greenhouse"}) < _source_priority({"source": "remoteok"})
        assert _source_priority({"source": "ashby"}) < _source_priority({"source": "himalayas"})
        assert _source_priority({"source": "lever"}) < _source_priority({"source": "arbeitnow"})
        assert _source_priority({"source": "workable"}) < _source_priority({"source": "remoteok"})

    def test_unknown_and_missing_source_get_default(self):
        default = _source_priority({"source": "some-random-board"})
        assert _source_priority({}) == default
        assert _source_priority({"source": None}) == default
        # default must be strictly worse than any ATS source
        assert default > _source_priority({"source": "ashby"})

    def test_case_insensitive(self):
        assert _source_priority({"source": "GreenHouse"}) == _source_priority(
            {"source": "greenhouse"}
        )

    def test_cap_keeps_ats_drops_job_boards(self):
        """The actual fix: when capped, ATS jobs survive, generic boards get skipped."""
        jobs = [{"source": "remoteok"} for _ in range(3)] + [
            {"source": "greenhouse"} for _ in range(3)
        ]
        jobs.sort(key=_source_priority)
        kept = jobs[:3]
        assert all(j["source"] == "greenhouse" for j in kept), "ATS jobs must survive the cap"


class TestEffectiveScoringCap:
    def test_default_covers_full_scrape(self, monkeypatch):
        """Default $5/day budget must score a realistic full scrape (~2600+)."""
        monkeypatch.delenv("PIPELINE_MAX_SCORE", raising=False)
        monkeypatch.delenv("PIPELINE_DAILY_BUDGET_USD", raising=False)
        cap = effective_scoring_cap()
        assert cap >= 2600, f"default cap {cap} too low — would drop a full scrape"
        assert cap <= SCORING_CAP_CEILING

    def test_explicit_override_wins(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_MAX_SCORE", "1234")
        assert effective_scoring_cap() == 1234

    def test_budget_scales_cap(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_MAX_SCORE", raising=False)
        monkeypatch.setenv("PIPELINE_DAILY_BUDGET_USD", "1.5")
        low = effective_scoring_cap()
        monkeypatch.setenv("PIPELINE_DAILY_BUDGET_USD", "9.0")
        high = effective_scoring_cap()
        assert high > low

    def test_floor_and_ceiling_enforced(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_MAX_SCORE", raising=False)
        monkeypatch.setenv("PIPELINE_DAILY_BUDGET_USD", "0.0001")
        assert effective_scoring_cap() == SCORING_CAP_FLOOR
        monkeypatch.setenv("PIPELINE_DAILY_BUDGET_USD", "9999")
        assert effective_scoring_cap() == SCORING_CAP_CEILING

    def test_garbage_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_MAX_SCORE", raising=False)
        monkeypatch.setenv("PIPELINE_DAILY_BUDGET_USD", "abc")
        cap = effective_scoring_cap()
        assert SCORING_CAP_FLOOR <= cap <= SCORING_CAP_CEILING


class TestNormalizedDedup:
    def test_drifted_tracked_job_is_deduped(self, tmp_path, monkeypatch):
        """A scraped job that differs only by trivial drift from a tracked entry
        must be deduped (the G-1122 normalization), not re-surfaced."""

        # Force the CSV-fallback path: make the DB branch raise.
        def _boom():
            raise RuntimeError("no db in test")

        monkeypatch.setattr("career_os.database.SessionLocal", _boom, raising=False)

        csv_path = tmp_path / "applications.csv"
        csv_path.write_text("company,role\nHugging Face GmbH,Senior PM (m/f/d)\n")

        config = dp.PipelineConfig()
        config.csv_path = csv_path

        jobs = [
            {"company": "Huggingface", "title": "Senior PM"},  # drift of tracked -> drop
            {"company": "Globex", "title": "Staff Engineer"},  # genuinely new -> keep
        ]
        new_jobs = dp.step_dedup_against_tracking(config, jobs)

        companies = {j["company"] for j in new_jobs}
        assert companies == {"Globex"}, "drifted duplicate should be removed, new job kept"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
