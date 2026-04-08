"""Tests for tools/scrape_resilient.py — all scrapers, dedup, retry logic."""

import json
import time
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scrape_resilient import (
    ScrapedJob,
    _get_user_agent,
    _retry_with_backoff,
    deduplicate,
    save_results,
    scrape_aijobs,
    scrape_jobicy,
    scrape_remoteok,
    scrape_remotive,
    scrape_weworkremotely,
    scrape_germantechjobs,
)


# ==================== ScrapedJob dataclass ====================


class TestScrapedJob:
    def test_creation(self):
        job = ScrapedJob(
            title="AI PM",
            company="Acme",
            location="Remote",
            url="https://acme.com/jobs/1",
            source="remotive",
        )
        assert job.title == "AI PM"
        assert job.company == "Acme"
        assert job.remote is False  # default
        assert job.tags == []
        assert job.description == ""

    def test_dedup_key_case_insensitive(self):
        job1 = ScrapedJob(title="AI PM", company="Acme Corp", location="", url="", source="a")
        job2 = ScrapedJob(title="ai pm", company="ACME CORP", location="", url="", source="b")
        assert job1.dedup_key() == job2.dedup_key()

    def test_dedup_key_strips_whitespace(self):
        job1 = ScrapedJob(title=" AI PM ", company=" Acme ", location="", url="", source="a")
        job2 = ScrapedJob(title="AI PM", company="Acme", location="", url="", source="b")
        assert job1.dedup_key() == job2.dedup_key()

    def test_to_dict(self):
        job = ScrapedJob(title="X", company="Y", location="Z", url="u", source="s")
        d = asdict(job)
        assert d["title"] == "X"
        assert "tags" in d
        assert isinstance(d["tags"], list)


# ==================== Utility functions ====================


class TestGetUserAgent:
    def test_returns_string(self):
        ua = _get_user_agent()
        assert isinstance(ua, str)
        assert "Mozilla" in ua

    def test_returns_from_pool(self):
        agents = set(_get_user_agent() for _ in range(50))
        assert len(agents) >= 2  # should get at least 2 different ones


class TestRetryWithBackoff:
    @patch("scrape_resilient.time.sleep")  # skip actual sleeping
    def test_succeeds_first_try(self, mock_sleep):
        result = _retry_with_backoff(lambda: 42)
        assert result == 42
        mock_sleep.assert_not_called()

    @patch("scrape_resilient.time.sleep")
    def test_succeeds_after_retries(self, mock_sleep):
        call_count = {"n": 0}

        def flaky():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("fail")
            return "ok"

        result = _retry_with_backoff(flaky)
        assert result == "ok"
        assert call_count["n"] == 3

    @patch("scrape_resilient.time.sleep")
    def test_returns_none_after_all_retries_exhausted(self, mock_sleep):
        def always_fail():
            raise ConnectionError("always fails")

        result = _retry_with_backoff(always_fail)
        assert result is None


# ==================== Deduplication ====================


class TestDeduplicate:
    def test_removes_exact_duplicates(self):
        jobs = [
            ScrapedJob(title="AI PM", company="Acme", location="", url="", source="a"),
            ScrapedJob(title="AI PM", company="Acme", location="Remote", url="x", source="b"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1
        assert result[0].source == "a"  # keeps first

    def test_case_insensitive_dedup(self):
        jobs = [
            ScrapedJob(title="AI PM", company="Acme", location="", url="", source="a"),
            ScrapedJob(title="ai pm", company="ACME", location="", url="", source="b"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1

    def test_keeps_different_jobs(self):
        jobs = [
            ScrapedJob(title="AI PM", company="Acme", location="", url="", source="a"),
            ScrapedJob(title="TPM", company="Acme", location="", url="", source="b"),
            ScrapedJob(title="AI PM", company="Other", location="", url="", source="c"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 3

    def test_empty_list(self):
        assert deduplicate([]) == []


# ==================== Save results ====================


class TestSaveResults:
    def test_saves_json(self, tmp_path):
        jobs = [
            ScrapedJob(title="Test", company="Co", location="X", url="u", source="s"),
        ]
        path = save_results(jobs, tmp_path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1
        assert data[0]["title"] == "Test"

    def test_creates_directory(self, tmp_path):
        output_dir = tmp_path / "new" / "nested"
        jobs = [ScrapedJob(title="T", company="C", location="L", url="u", source="s")]
        path = save_results(jobs, output_dir)
        assert path.exists()


# ==================== Remotive scraper ====================


class TestScrapeRemotive:
    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_parses_response(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {
                    "title": "AI Product Manager",
                    "company_name": "Remotive Co",
                    "candidate_required_location": "EU",
                    "url": "https://remotive.com/job/123",
                    "description": "Build things",
                    "publication_date": "2026-03-10",
                    "salary": "120-150k",
                    "tags": ["ai", "product"],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_remotive(search="AI", limit=10)
        assert len(jobs) == 1
        assert jobs[0].title == "AI Product Manager"
        assert jobs[0].company == "Remotive Co"
        assert jobs[0].source == "remotive"
        assert jobs[0].remote is True

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_handles_empty_response(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = {"jobs": []}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_remotive()
        assert jobs == []


# ==================== RemoteOK scraper ====================


class TestScrapeRemoteOK:
    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_parses_response_skips_legal_notice(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"legal": "notice"},  # no "id" — should be skipped
            {
                "id": "123",
                "position": "ML Engineer",
                "company": "RemoteCo",
                "location": "Worldwide",
                "url": "https://remoteok.com/job/123",
                "description": "Build ML stuff",
                "date": "2026-03-10",
                "tags": ["ml", "python"],
            },
        ]
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_remoteok(limit=10)
        assert len(jobs) == 1
        assert jobs[0].title == "ML Engineer"
        assert jobs[0].source == "remoteok"

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_handles_string_tags(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "1", "position": "Dev", "company": "X", "tags": "python"},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_remoteok()
        assert jobs[0].tags == ["python"]


# ==================== Jobicy scraper ====================


class TestScrapeJobicy:
    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_parses_response(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {
                    "jobTitle": "Data Scientist",
                    "companyName": "EU Corp",
                    "jobGeo": "Europe",
                    "url": "https://jobicy.com/job/456",
                    "jobDescription": "Data work",
                    "pubDate": "2026-03-10",
                    "annualSalaryMin": "80000",
                    "jobIndustry": ["data-science"],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_jobicy(count=10, geo="europe")
        assert len(jobs) == 1
        assert jobs[0].title == "Data Scientist"
        assert jobs[0].source == "jobicy"
        assert jobs[0].remote is True


# ==================== We Work Remotely scraper ====================


class TestScrapeWeWorkRemotely:
    SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>We Work Remotely</title>
        <item>
          <title>Acme Inc: Senior Developer</title>
          <link>https://weworkremotely.com/job/123</link>
          <description>Build great software remotely.</description>
          <pubDate>Mon, 10 Mar 2026 00:00:00 +0000</pubDate>
        </item>
        <item>
          <title>Just a Role Title</title>
          <link>https://weworkremotely.com/job/456</link>
          <description>No company prefix here.</description>
          <pubDate>Sun, 09 Mar 2026 00:00:00 +0000</pubDate>
        </item>
      </channel>
    </rss>"""

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_parses_rss(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.text = self.SAMPLE_RSS
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_weworkremotely()
        assert len(jobs) == 2
        # First item has "Company: Role" format
        assert jobs[0].company == "Acme Inc"
        assert jobs[0].title == "Senior Developer"
        assert jobs[0].source == "weworkremotely"
        # Second item has no colon — whole string is the title
        assert jobs[1].company == ""
        assert jobs[1].title == "Just a Role Title"

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_respects_limit(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.text = self.SAMPLE_RSS
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_weworkremotely(limit=1)
        assert len(jobs) == 1


# ==================== GermanTechJobs scraper ====================


class TestScrapeGermanTechJobs:
    SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Python Developer (m/f/d)</title>
          <link>https://germantechjobs.de/job/789</link>
          <description>Python backend work in Berlin.</description>
          <pubDate>Mon, 10 Mar 2026 10:00:00 +0100</pubDate>
        </item>
      </channel>
    </rss>"""

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_parses_xml_feed(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.text = self.SAMPLE_XML
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_germantechjobs()
        assert len(jobs) == 1
        assert jobs[0].title == "Python Developer (m/f/d)"
        assert jobs[0].location == "Germany"
        assert jobs[0].source == "germantechjobs"


# ==================== AI-Jobs.net scraper ====================


class TestScrapeAiJobs:
    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_parses_list_response(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "title": "NLP Research Scientist",
                "company": "AI Lab",
                "location": "Remote, US",
                "url": "https://aijobs.net/job/1",
                "description": "NLP research",
                "date": "2026-03-10",
                "salary_min": 120000,
                "salary_max": 160000,
                "salary_currency": "USD",
                "tags": ["nlp", "research"],
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_aijobs(limit=10)
        assert len(jobs) == 1
        assert jobs[0].title == "NLP Research Scientist"
        assert jobs[0].source == "aijobs"
        assert jobs[0].salary == "120000-160000 USD"
        assert jobs[0].remote is True  # "remote" in location

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_handles_dict_response(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {"title": "ML Eng", "company": "Co", "location": "Berlin"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_aijobs()
        assert len(jobs) == 1
        assert jobs[0].salary == ""  # no salary fields

    @patch("scrape_resilient._random_delay")
    @patch("scrape_resilient.time.sleep")
    @patch("scrape_resilient.httpx.Client")
    def test_non_remote_location(self, mock_client_cls, mock_sleep, mock_delay):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"title": "Dev", "company": "X", "location": "Berlin, Germany"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        jobs = scrape_aijobs()
        assert jobs[0].remote is False


# ==================== Browser fallback ====================


class TestBrowserFallback:
    def test_returns_empty_without_playwright(self):
        from scrape_resilient import scrape_with_browser

        # Playwright is not installed in test env, so should return []
        result = scrape_with_browser(["https://example.com"])
        assert result == []
