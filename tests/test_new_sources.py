"""Tests for tools/scrape_new_sources.py - new German/EMEA market scrapers."""

from unittest.mock import MagicMock, patch

from scrape_new_sources import (
    ASHBY_COMPANIES,
    GREENHOUSE_COMPANIES,
    LEVER_COMPANIES,
    scrape_all_new_sources,
    scrape_ashby,
    scrape_greenhouse,
    scrape_himalayas,
    scrape_lever,
    scrape_startupjobs,
    scrape_thehub,
)

# ==================== Helper: mock httpx.Client context manager ====================


def _mock_httpx_client(mock_client_cls, response_data, is_json=True):
    """Set up a mock httpx.Client that returns the given data."""
    mock_response = MagicMock()
    if is_json:
        mock_response.json.return_value = response_data
    else:
        mock_response.text = response_data
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client
    return mock_client


# ==================== Company lists ====================


class TestCompanyLists:
    def test_greenhouse_companies_non_empty(self):
        assert len(GREENHOUSE_COMPANIES) > 0
        assert all(isinstance(c, str) for c in GREENHOUSE_COMPANIES)

    def test_lever_companies_non_empty(self):
        assert len(LEVER_COMPANIES) > 0
        assert all(isinstance(c, str) for c in LEVER_COMPANIES)

    def test_ashby_companies_non_empty(self):
        assert len(ASHBY_COMPANIES) > 0
        assert all(isinstance(c, str) for c in ASHBY_COMPANIES)

    def test_no_duplicate_slugs(self):
        """Slugs should be unique within each list."""
        assert len(GREENHOUSE_COMPANIES) == len(set(GREENHOUSE_COMPANIES))
        assert len(LEVER_COMPANIES) == len(set(LEVER_COMPANIES))
        assert len(ASHBY_COMPANIES) == len(set(ASHBY_COMPANIES))


# ==================== Himalayas scraper ====================


class TestScrapeHimalayas:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.time", create=True)
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_response(self, mock_client_cls, mock_time, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Senior Product Manager",
                        "companyName": "RemoteCo",
                        "location": "Remote, EU",
                        "applicationUrl": "https://himalayas.app/job/123",
                        "description": "Build product strategy.",
                        "pubDate": "2026-03-10",
                        "salary": "120-150k EUR",
                        "categories": ["product"],
                    }
                ]
            },
        )

        jobs = scrape_himalayas(keywords=["product manager"], limit=10)
        assert len(jobs) == 1
        assert jobs[0].title == "Senior Product Manager"
        assert jobs[0].company == "RemoteCo"
        assert jobs[0].source == "himalayas"
        assert jobs[0].remote is True

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_empty(self, mock_client_cls, mock_delay):
        _mock_httpx_client(mock_client_cls, {"jobs": []})
        jobs = scrape_himalayas(keywords=["nonexistent"])
        assert jobs == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_api_failure(self, mock_client_cls, mock_delay):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("timeout")
        mock_client_cls.return_value = mock_client
        # Should not raise, just return empty
        jobs = scrape_himalayas(keywords=["test"])
        assert jobs == []


# ==================== Greenhouse scraper ====================


class TestScrapeGreenhouse:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_jobs(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Technical Program Manager",
                        "location": {"name": "Berlin, Germany"},
                        "departments": [{"name": "Engineering"}],
                        "content": "<p>Build great things.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                        "updated_at": "2026-03-10T12:00:00Z",
                    },
                    {
                        "title": "Marketing Associate",
                        "location": {"name": "New York"},
                        "departments": [],
                        "content": "<p>Marketing stuff.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                        "updated_at": "2026-03-09",
                    },
                ]
            },
        )

        # No keyword filter - get all
        jobs = scrape_greenhouse(companies=["acme"])
        assert len(jobs) == 2
        assert jobs[0].title == "Technical Program Manager"
        assert jobs[0].source == "greenhouse"
        assert "Engineering" in jobs[0].tags
        assert "Build great things" in jobs[0].description

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_keyword_filter(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Technical Program Manager",
                        "location": {"name": "Remote"},
                        "departments": [],
                        "content": "",
                        "absolute_url": "https://example.com/1",
                    },
                    {
                        "title": "Sales Rep",
                        "location": {"name": "NY"},
                        "departments": [],
                        "content": "",
                        "absolute_url": "https://example.com/2",
                    },
                ]
            },
        )

        jobs = scrape_greenhouse(
            companies=["acme"],
            keyword_filter=["program manager", "engineer"],
        )
        assert len(jobs) == 1
        assert jobs[0].title == "Technical Program Manager"

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_remote_detection(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Dev",
                        "location": {"name": "Remote, EMEA"},
                        "departments": [],
                        "content": "",
                        "absolute_url": "",
                    },
                ]
            },
        )
        jobs = scrape_greenhouse(companies=["test"])
        assert jobs[0].remote is True

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_empty_board(self, mock_client_cls, mock_delay):
        _mock_httpx_client(mock_client_cls, {"jobs": []})
        jobs = scrape_greenhouse(companies=["empty-co"])
        assert jobs == []


# ==================== Lever scraper ====================


class TestScrapeLever:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_postings(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            [
                {
                    "text": "Developer Relations Engineer",
                    "categories": {
                        "location": "Remote, EU",
                        "team": "DevRel",
                        "commitment": "Full-time",
                    },
                    "lists": [
                        {"text": "Responsibilities", "content": "<li>Build community</li>"},
                    ],
                    "hostedUrl": "https://jobs.lever.co/acme/123",
                    "createdAt": 1710000000,
                },
            ],
        )

        jobs = scrape_lever(companies=["acme"])
        assert len(jobs) == 1
        assert jobs[0].title == "Developer Relations Engineer"
        assert jobs[0].source == "lever"
        assert "DevRel" in jobs[0].tags
        assert jobs[0].remote is True

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_keyword_filter(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            [
                {"text": "DevRel", "categories": {"location": ""}, "lists": [], "hostedUrl": ""},
                {
                    "text": "Accountant",
                    "categories": {"location": ""},
                    "lists": [],
                    "hostedUrl": "",
                },
            ],
        )

        jobs = scrape_lever(companies=["co"], keyword_filter=["devrel"])
        assert len(jobs) == 1

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_non_list_response(self, mock_client_cls, mock_delay):
        """Lever sometimes returns {} for invalid slugs."""
        _mock_httpx_client(mock_client_cls, {"error": "not found"})
        jobs = scrape_lever(companies=["nonexistent"])
        assert jobs == []


# ==================== Ashby scraper ====================


class TestScrapeAshby:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_jobs(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Staff Engineer",
                        "location": "Remote",
                        "department": "Engineering",
                        "compensation": {
                            "min": 140000,
                            "max": 180000,
                            "currency": "EUR",
                        },
                        "descriptionPlain": "Build infra.",
                        "jobUrl": "https://jobs.ashbyhq.com/acme/1",
                        "publishedAt": "2026-03-10",
                    },
                ]
            },
        )

        jobs = scrape_ashby(companies=["acme"])
        assert len(jobs) == 1
        assert jobs[0].title == "Staff Engineer"
        assert jobs[0].source == "ashby"
        assert jobs[0].salary == "140000-180000 EUR"
        assert "Engineering" in jobs[0].tags

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_jobpostings_key(self, mock_client_cls, mock_delay):
        """Ashby may return jobPostings instead of jobs."""
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobPostings": [
                    {
                        "title": "PM",
                        "location": {"name": "Berlin"},
                        "department": {"name": "Product"},
                        "descriptionPlain": "Manage products.",
                        "publishedUrl": "https://jobs.ashbyhq.com/co/2",
                    },
                ]
            },
        )

        jobs = scrape_ashby(companies=["co"])
        assert len(jobs) == 1
        assert jobs[0].location == "Berlin"
        assert jobs[0].tags == ["Product"]

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_keyword_filter(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {"title": "Engineer", "location": "", "jobUrl": ""},
                    {"title": "Sales", "location": "", "jobUrl": ""},
                ]
            },
        )
        jobs = scrape_ashby(companies=["co"], keyword_filter=["engineer"])
        assert len(jobs) == 1

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_string_compensation(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Dev",
                        "location": "",
                        "compensationTierSummary": "120-150k EUR",
                        "jobUrl": "",
                    },
                ]
            },
        )
        jobs = scrape_ashby(companies=["co"])
        assert jobs[0].salary == "120-150k EUR"


# ==================== startup.jobs scraper ====================


class TestScrapeStartupJobs:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_algolia_hits(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "hits": [
                    {
                        "title": "AI Product Lead",
                        "company_name": "Cool Startup",
                        "location": "Remote",
                        "url": "https://startup.jobs/ai-lead",
                        "description": "Lead AI product.",
                        "published_at": "2026-03-10",
                        "remote": True,
                        "tags": ["ai", "product"],
                    },
                ]
            },
        )

        jobs = scrape_startupjobs(keywords=["AI"])
        assert len(jobs) == 1
        assert jobs[0].title == "AI Product Lead"
        assert jobs[0].source == "startupjobs"
        assert jobs[0].remote is True

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_builds_url_from_slug(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "hits": [
                    {
                        "title": "Dev",
                        "company_name": "Co",
                        "slug": "dev-at-co-123",
                        "location": "",
                    },
                ]
            },
        )
        jobs = scrape_startupjobs(keywords=["dev"])
        assert "startup.jobs/dev-at-co-123" in jobs[0].url

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_empty_hits(self, mock_client_cls, mock_delay):
        _mock_httpx_client(mock_client_cls, {"hits": []})
        jobs = scrape_startupjobs(keywords=["nothing"])
        assert jobs == []


# ==================== TheHub scraper ====================


class TestScrapeTheHub:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_list_response(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "jobs": [
                    {
                        "title": "Founding Engineer",
                        "company_name": "Berlin Startup",
                        "location": "Berlin, Germany",
                        "url": "https://thehub.io/jobs/1",
                        "description": "Build from scratch.",
                        "published_at": "2026-03-10",
                        "remote": False,
                        "tags": ["engineering"],
                    },
                ]
            },
        )

        jobs = scrape_thehub(keywords=["engineer"])
        assert len(jobs) == 1
        assert jobs[0].title == "Founding Engineer"
        assert jobs[0].source == "thehub"

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_data_key(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "data": [
                    {
                        "title": "PM",
                        "company": {"name": "Startup"},
                        "location": "Berlin",
                        "url": "u",
                    },
                ]
            },
        )
        jobs = scrape_thehub(keywords=["pm"])
        assert len(jobs) == 1
        assert jobs[0].company == "Startup"

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_api_failure(self, mock_client_cls, mock_delay):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("404")
        mock_client_cls.return_value = mock_client
        jobs = scrape_thehub(keywords=["test"])
        assert jobs == []


# ==================== Combined orchestrator ====================


class TestScrapeAllNewSources:
    @patch("scrape_new_sources.scrape_thehub", return_value=[])
    @patch("scrape_new_sources.scrape_startupjobs", return_value=[])
    @patch("scrape_new_sources.scrape_ashby", return_value=[])
    @patch("scrape_new_sources.scrape_lever", return_value=[])
    @patch("scrape_new_sources.scrape_greenhouse", return_value=[])
    @patch("scrape_new_sources.scrape_himalayas", return_value=[])
    @patch("scrape_new_sources._random_delay")
    def test_calls_all_sources(
        self, mock_delay, mock_h, mock_gh, mock_lv, mock_as, mock_sj, mock_th
    ):
        from scrape_resilient import ScrapedJob

        mock_h.return_value = [
            ScrapedJob(title="Job1", company="Co1", location="Remote", url="u1", source="himalayas")
        ]
        mock_gh.return_value = [
            ScrapedJob(
                title="Job2", company="Co2", location="Berlin", url="u2", source="greenhouse"
            )
        ]

        result = scrape_all_new_sources()
        assert len(result) == 2
        mock_h.assert_called_once()
        mock_gh.assert_called_once()
        mock_lv.assert_called_once()
        mock_as.assert_called_once()
        mock_sj.assert_called_once()
        mock_th.assert_called_once()

    @patch("scrape_new_sources.scrape_thehub", side_effect=Exception("boom"))
    @patch("scrape_new_sources.scrape_startupjobs", return_value=[])
    @patch("scrape_new_sources.scrape_ashby", return_value=[])
    @patch("scrape_new_sources.scrape_lever", return_value=[])
    @patch("scrape_new_sources.scrape_greenhouse", return_value=[])
    @patch("scrape_new_sources.scrape_himalayas", return_value=[])
    @patch("scrape_new_sources._random_delay")
    def test_graceful_on_individual_failure(
        self, mock_delay, mock_h, mock_gh, mock_lv, mock_as, mock_sj, mock_th
    ):
        """If one source throws, others still run."""
        result = scrape_all_new_sources()
        assert isinstance(result, list)  # no exception


# ==================== Keyword preset expansions ====================


class TestExpandedPresets:
    def test_new_presets_exist(self):
        from germany_jobs import PRESETS

        assert "devrel" in PRESETS
        assert "leadership" in PRESETS

    def test_devrel_has_keywords(self):
        from germany_jobs import PRESETS

        devrel = PRESETS["devrel"]
        assert any("Developer Relations" in k for k in devrel)
        assert any("Developer Advocate" in k for k in devrel)
        assert any("DevRel" in k for k in devrel)

    def test_leadership_has_keywords(self):
        from germany_jobs import PRESETS

        leadership = PRESETS["leadership"]
        assert any("Head of Engineering" in k for k in leadership)
        assert any("VP Engineering" in k for k in leadership)

    def test_expanded_tpm_has_technical_product_manager(self):
        from germany_jobs import PRESETS

        assert "Technical Product Manager" in PRESETS["tpm"]

    def test_expanded_ai_has_mlops(self):
        from germany_jobs import PRESETS

        assert "MLOps" in PRESETS["ai"]

    def test_expanded_builder_has_founding_engineer(self):
        from germany_jobs import PRESETS

        assert "Founding Engineer" in PRESETS["builder"]
        assert "Staff Engineer" in PRESETS["builder"]
