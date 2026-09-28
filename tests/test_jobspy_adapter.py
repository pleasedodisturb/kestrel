"""Offline tests for JobSpyAdapter — per-site JobSpy sweep hardening (G-1802).

Offline: fake scrape_jobs injected via _import_jobspy, never imports jobspy or
touches the network.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time

import pytest
from pydantic import ValidationError

from career_os.config import Settings, settings
from career_os.discovery.adapters import JobSpyAdapter, ScrapeParams
from career_os.services.discovery import _scrape_all_adapters


class _FakeFrame:
    """Minimal stand-in for a pandas DataFrame: .empty and .iterrows()."""

    def __init__(self, rows: list[dict] | None = None):
        self._rows = rows or []

    @property
    def empty(self) -> bool:
        return not self._rows

    def iterrows(self):
        return iter(enumerate(self._rows))


class TestJobSpySiteRequests:
    """Default config talks to Indeed only, one scrape_jobs call per keyword."""

    @pytest.mark.asyncio
    async def test_default_config_requests_indeed_only(self, monkeypatch):
        """Two keywords produce exactly 2 scrape_jobs calls, each Indeed-only."""
        calls = []

        def fake_scrape_jobs(**kwargs):
            calls.append(kwargs)
            return _FakeFrame()

        adapter = JobSpyAdapter()
        monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake_scrape_jobs)

        params = ScrapeParams(keywords=["pm", "tpm"], locations=["Berlin"], limit_per_source=25)
        await adapter.scrape(params)

        assert len(calls) == 2
        assert calls[0] == {
            "site_name": ["indeed"],
            "search_term": "pm",
            "location": "Berlin",
            "results_wanted": 25,
            "hours_old": 168,
            "country_indeed": "Germany",
        }
        assert calls[1]["search_term"] == "tpm"

    def test_sites_is_indeed_only(self):
        """JobSpyAdapter.SITES contains only Indeed; no Glassdoor or Google."""
        assert JobSpyAdapter.SITES == ("indeed",)
        assert "glassdoor" not in JobSpyAdapter.SITES
        assert "google" not in JobSpyAdapter.SITES


class TestJobSpySiteIsolation:
    """One board raising must never drop another board's rows (AC2)."""

    @pytest.mark.asyncio
    async def test_one_site_failing_does_not_drop_other_sites_rows(self, monkeypatch, caplog):
        """One board raising keeps the other board's row."""
        adapter = JobSpyAdapter()
        monkeypatch.setattr(JobSpyAdapter, "SITES", ("indeed", "linkedin"))
        seen_site_names = []

        def fake_scrape_jobs(*, site_name, **kwargs):
            seen_site_names.append(site_name)
            if site_name == ["indeed"]:
                raise RuntimeError("indeed exploded")
            return _FakeFrame(
                [
                    {
                        "title": "LI Title",
                        "company": "Co",
                        "location": "Berlin",
                        "job_url": "http://li",
                    }
                ]
            )

        monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake_scrape_jobs)

        with caplog.at_level(logging.WARNING):
            rows = await adapter.scrape(ScrapeParams(keywords=["pm"], locations=["Berlin"]))

        assert len(rows) == 1
        assert rows[0].title == "LI Title"
        assert rows[0].url == "http://li"
        assert seen_site_names == [["indeed"], ["linkedin"]]
        assert any(
            "indeed" in rec.message and "indeed exploded" in rec.message
            for rec in caplog.records
            if rec.levelname == "WARNING"
        )

    @pytest.mark.asyncio
    async def test_all_sites_failing_raises_with_both_reasons(self, monkeypatch):
        """When every call fails, scrape raises RuntimeError naming every site+reason."""
        adapter = JobSpyAdapter()
        monkeypatch.setattr(JobSpyAdapter, "SITES", ("indeed", "linkedin"))

        def fake_scrape_jobs(*, site_name, **kwargs):
            raise RuntimeError(f"{site_name[0]} boom")

        monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake_scrape_jobs)

        with pytest.raises(RuntimeError) as exc_info:
            await adapter.scrape(ScrapeParams(keywords=["pm"], locations=["Berlin"]))

        message = str(exc_info.value)
        assert "indeed" in message and "indeed boom" in message
        assert "linkedin" in message and "linkedin boom" in message


class TestJobSpyTimeout:
    """A hung executor call must never stall the sweep (AC3)."""

    @pytest.mark.asyncio
    async def test_hung_scraper_times_out_and_sweep_returns_fast(self, monkeypatch):
        """A blocked executor call is abandoned after jobspy_timeout_seconds."""
        monkeypatch.setattr(settings, "jobspy_timeout_seconds", 0.05)
        event = threading.Event()

        def fake_scrape_jobs(**kwargs):
            event.wait(5)
            return _FakeFrame()

        adapter = JobSpyAdapter()
        monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake_scrape_jobs)

        try:
            start = time.monotonic()
            jobs, warnings, sources_queried = await _scrape_all_adapters(
                [adapter], ScrapeParams(keywords=["pm"])
            )
            elapsed = time.monotonic() - start

            assert elapsed < 2.0
            assert jobs == []
            assert sources_queried == []
            assert len(warnings) == 1
            assert warnings[0]["source"] == "jobspy"
            assert "timed out" in warnings[0]["error"] and "indeed" in warnings[0]["error"]
        finally:
            event.set()

    @pytest.mark.asyncio
    async def test_hung_calls_are_bounded_and_quarantine_new_calls(self, monkeypatch):
        """Abandoned threads are counted; at the pool size new calls fail fast
        instead of queueing, and the count drops once the threads return."""
        monkeypatch.setattr(settings, "jobspy_timeout_seconds", 0.05)
        monkeypatch.setattr(JobSpyAdapter, "MAX_WORKERS", 2)
        monkeypatch.setattr(JobSpyAdapter, "_executor", None)
        monkeypatch.setattr(JobSpyAdapter, "_hung", 0)
        release = threading.Event()

        def fake_scrape_jobs(**kwargs):
            release.wait(5)
            return _FakeFrame()

        adapter = JobSpyAdapter()
        monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake_scrape_jobs)
        try:
            for _ in range(2):
                _, warnings, _ = await _scrape_all_adapters(
                    [adapter], ScrapeParams(keywords=["pm"])
                )
                assert "timed out" in warnings[0]["error"]
            assert JobSpyAdapter.hung_calls() == 2
            start = time.monotonic()
            _, warnings, _ = await _scrape_all_adapters([adapter], ScrapeParams(keywords=["pm"]))
            assert time.monotonic() - start < 0.05, "refused up front, not after a timeout"
            assert "quarantined" in warnings[0]["error"]
            assert JobSpyAdapter.hung_calls() == 2
        finally:
            release.set()
        for _ in range(50):
            if JobSpyAdapter.hung_calls() == 0:
                break
            await asyncio.sleep(0.02)
        assert JobSpyAdapter.hung_calls() == 0
        _, warnings, _ = await _scrape_all_adapters([adapter], ScrapeParams(keywords=["pm"]))
        assert warnings == []

    @pytest.mark.asyncio
    async def test_partial_timeout_keeps_other_sites_row(self, monkeypatch, caplog):
        """One board timing out does not drop another board's row."""
        monkeypatch.setattr(settings, "jobspy_timeout_seconds", 0.05)
        monkeypatch.setattr(JobSpyAdapter, "SITES", ("indeed", "linkedin"))
        event = threading.Event()

        def fake_scrape_jobs(*, site_name, **kwargs):
            if site_name == ["indeed"]:
                event.wait(5)
                return _FakeFrame()
            return _FakeFrame(
                [{"title": "LI", "company": "Co", "location": "Berlin", "job_url": "http://li"}]
            )

        adapter = JobSpyAdapter()
        monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake_scrape_jobs)

        try:
            with caplog.at_level(logging.WARNING):
                start = time.monotonic()
                rows = await adapter.scrape(ScrapeParams(keywords=["pm"], locations=["Berlin"]))
                elapsed = time.monotonic() - start

            assert elapsed < 2.0
            assert len(rows) == 1
            assert rows[0].title == "LI"
            assert any(
                "timed out" in rec.message and "indeed" in rec.message
                for rec in caplog.records
                if rec.levelname == "WARNING"
            )
        finally:
            event.set()


class TestJobSpyMissingDependency:
    """python-jobspy not being installed must produce a warning, not a crash."""

    @pytest.mark.asyncio
    async def test_missing_jobspy_records_a_warning_not_a_crash(self, monkeypatch):
        """With python-jobspy not importable, the sweep records a warning."""
        monkeypatch.setitem(sys.modules, "jobspy", None)

        adapter = JobSpyAdapter()
        jobs, warnings, sources_queried = await _scrape_all_adapters(
            [adapter], ScrapeParams(keywords=["pm"])
        )

        assert jobs == []
        assert sources_queried == []
        assert len(warnings) == 1
        assert warnings[0]["source"] == "jobspy"
        assert "python-jobspy is not installed" in warnings[0]["error"]


class TestJobSpyTimeoutSetting:
    """Settings.jobspy_timeout_seconds: default, env override, and validation."""

    def test_default_is_60(self):
        """Settings field defaults to 60 seconds and is a float."""
        field = Settings.model_fields["jobspy_timeout_seconds"]
        assert field.default == 60
        assert field.annotation is float

    def test_env_var_override(self, monkeypatch):
        """JOBSPY_TIMEOUT_SECONDS from the environment overrides the default."""
        monkeypatch.setenv("JOBSPY_TIMEOUT_SECONDS", "7")
        s = Settings(_env_file=None, ai_provider="mock", auth_enabled=False)
        assert s.jobspy_timeout_seconds == 7.0
        assert isinstance(s.jobspy_timeout_seconds, float)

    def test_zero_is_rejected(self, monkeypatch):
        """A value of 0 fails Settings validation (gt=0)."""
        monkeypatch.setenv("JOBSPY_TIMEOUT_SECONDS", "0")
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None, ai_provider="mock", auth_enabled=False)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("jobspy_timeout_seconds",) for e in errors)
        assert any("greater than" in e["msg"] for e in errors)

    @pytest.mark.parametrize("value", ["inf", "+inf", "-inf", "nan", "Infinity", "NaN"])
    def test_non_finite_is_rejected(self, monkeypatch, value):
        """inf would make the 'hard' timeout unbounded; nan is never a duration."""
        monkeypatch.setenv("JOBSPY_TIMEOUT_SECONDS", value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
