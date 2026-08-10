"""Tests for tools/scrape_new_sources.py - new German/EMEA market scrapers."""

from unittest.mock import MagicMock, patch

from scrape_new_sources import (
    ASHBY_COMPANIES,
    GREENHOUSE_COMPANIES,
    LEVER_COMPANIES,
    scrape_all_new_sources,
    scrape_arbeitnow,
    scrape_ashby,
    scrape_greenhouse,
    scrape_himalayas,
    scrape_lever,
    scrape_remotely_de,
    scrape_startupjobs,
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


# TheHub tests removed with the scraper (G-1564).
#
# They passed for a scraper that could never work: each mocked httpx.Client
# and fed the parser a fabricated JSON dict, while the real endpoint served
# an HTML page. The tests exercised the parsing branch and never the
# request, so they asserted a shape the API had never returned. A mock that
# stands in for the thing that is broken proves only that the mock works.


# ==================== Combined orchestrator ====================


class TestScrapeAllNewSources:
    @patch("scrape_new_sources.scrape_remotely_de", return_value=[])
    @patch("scrape_new_sources.scrape_arbeitnow", return_value=[])
    @patch("scrape_new_sources.scrape_startupjobs", return_value=[])
    @patch("scrape_new_sources.scrape_ashby", return_value=[])
    @patch("scrape_new_sources.scrape_lever", return_value=[])
    @patch("scrape_new_sources.scrape_greenhouse", return_value=[])
    @patch("scrape_new_sources.scrape_himalayas", return_value=[])
    @patch("scrape_new_sources._random_delay")
    def test_calls_all_sources(
        self,
        mock_delay,
        mock_h,
        mock_gh,
        mock_lv,
        mock_as,
        mock_sj,
        mock_an,
        mock_rd,
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
        mock_an.return_value = [
            ScrapedJob(title="J3", company="C3", location="Berlin", url="u3", source="arbeitnow")
        ]
        mock_rd.return_value = [
            ScrapedJob(title="J4", company="C4", location="Köln", url="u4", source="remotely.de")
        ]

        result = scrape_all_new_sources()
        assert len(result) == 4
        mock_h.assert_called_once()
        mock_gh.assert_called_once()
        mock_lv.assert_called_once()
        mock_as.assert_called_once()
        mock_sj.assert_called_once()
        mock_an.assert_called_once()
        mock_rd.assert_called_once()

    @patch("scrape_new_sources.scrape_remotely_de", return_value=[])
    @patch("scrape_new_sources.scrape_arbeitnow", return_value=[])
    @patch("scrape_new_sources.scrape_startupjobs", return_value=[])
    @patch("scrape_new_sources.scrape_ashby", return_value=[])
    @patch("scrape_new_sources.scrape_lever", return_value=[])
    @patch("scrape_new_sources.scrape_greenhouse", return_value=[])
    @patch("scrape_new_sources.scrape_himalayas", return_value=[])
    @patch("scrape_new_sources._random_delay")
    def test_graceful_on_individual_failure(
        self,
        mock_delay,
        mock_h,
        mock_gh,
        mock_lv,
        mock_as,
        mock_sj,
        mock_an,
        mock_rd,
    ):
        """If one source throws, others still run."""
        result = scrape_all_new_sources()
        assert isinstance(result, list)  # no exception

    @patch("scrape_new_sources.scrape_startupjobs", return_value=[])
    @patch("scrape_new_sources.scrape_ashby", return_value=[])
    @patch("scrape_new_sources.scrape_lever", return_value=[])
    @patch("scrape_new_sources.scrape_greenhouse", return_value=[])
    @patch("scrape_new_sources.scrape_himalayas", return_value=[])
    @patch("scrape_new_sources.scrape_arbeitnow", side_effect=Exception("boom"))
    @patch("scrape_new_sources.scrape_remotely_de", side_effect=Exception("boom"))
    @patch("scrape_new_sources._random_delay")
    def test_eu_source_failures_isolated(
        self,
        mock_delay,
        mock_rd,
        mock_an,
        mock_h,
        mock_gh,
        mock_lv,
        mock_as,
        mock_sj,
    ):
        """arbeitnow / remotely.de exceptions must not break the orchestrator."""
        result = scrape_all_new_sources()
        assert isinstance(result, list)


# ==================== arbeitnow scraper ====================


class TestScrapeArbeitnow:
    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_response(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "data": [
                    {
                        "slug": "senior-pm-berlin-1",
                        "company_name": "Acme GmbH",
                        "title": "Senior Product Manager (m/w/d)",
                        "description": "<p>Build cool stuff.</p>",
                        "remote": True,
                        "url": "https://www.arbeitnow.com/jobs/acme/senior-pm-1",
                        "tags": ["product", "ai"],
                        "job_types": ["Full Time"],
                        "location": "Berlin, Deutschland",
                        "created_at": 1700000000,
                    }
                ]
            },
        )

        jobs = scrape_arbeitnow()
        assert len(jobs) == 1
        j = jobs[0]
        assert j.title == "Senior Product Manager (m/w/d)"
        assert j.company == "Acme GmbH"
        assert j.location == "Berlin, Deutschland"
        assert j.source == "arbeitnow"
        assert j.remote is True
        assert "product" in j.tags
        # HTML stripped from description
        assert "<p>" not in j.description
        assert "Build cool stuff" in j.description
        # created_at unix → ISO
        assert j.posted.startswith("20")

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_keyword_filter(self, mock_client_cls, mock_delay):
        _mock_httpx_client(
            mock_client_cls,
            {
                "data": [
                    {"title": "Product Manager", "company_name": "A", "url": "u1"},
                    {"title": "Accountant", "company_name": "B", "url": "u2"},
                ]
            },
        )
        jobs = scrape_arbeitnow(keyword_filter=["product"])
        assert len(jobs) == 1
        assert jobs[0].title == "Product Manager"

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_empty(self, mock_client_cls, mock_delay):
        _mock_httpx_client(mock_client_cls, {"data": []})
        assert scrape_arbeitnow() == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_malformed_response(self, mock_client_cls, mock_delay):
        """Unexpected shape — return [] rather than crash."""
        _mock_httpx_client(mock_client_cls, {"unexpected": "shape"})
        assert scrape_arbeitnow() == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_handles_api_failure(self, mock_client_cls, mock_delay):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("500")
        mock_client_cls.return_value = mock_client
        assert scrape_arbeitnow() == []


# ==================== remotely.de scraper ====================


class TestScrapeRemotelyDe:
    SITEMAP = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://www.remotely.de/job/orbem-ai-engineer</loc>"
        "<lastmod>2099-01-01T00:00:00.000Z</lastmod></url>"
        "<url><loc>https://www.remotely.de/job/old-listing</loc>"
        "<lastmod>2099-01-01T00:00:00.000Z</lastmod></url>"
        "</urlset>"
    )

    JOB_HTML = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "JobPosting",
          "title": "AI Engineer",
          "description": "<p>Build ML systems</p>",
          "datePosted": "2026-03-09T00:00:00+00:00",
          "hiringOrganization": {"@type": "Organization", "name": "Orbem"},
          "jobLocation": {
            "@type": "Place",
            "address": {
              "@type": "PostalAddress",
              "addressLocality": "Munich",
              "addressCountry": "DE"
            }
          },
          "occupationalCategory": "AI/ML",
          "url": "https://www.remotely.de/job/orbem-ai-engineer"
        }
        </script>
      </head>
      <body></body>
    </html>
    """

    def _make_client_mock(self, sitemap_text, detail_html):
        """Return a mock httpx.Client whose .get dispatches by URL substring."""

        def _get(url, *args, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "sitemap" in url:
                resp.text = sitemap_text
            else:
                resp.text = detail_html
            return resp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = _get
        return mock_client

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_parses_jobposting(self, mock_client_cls, mock_delay):
        mock_client_cls.return_value = self._make_client_mock(self.SITEMAP, self.JOB_HTML)
        jobs = scrape_remotely_de(limit=1, max_age_hours=None)
        assert len(jobs) == 1
        j = jobs[0]
        assert j.title == "AI Engineer"
        assert j.company == "Orbem"
        assert "Munich" in j.location
        assert "DE" in j.location
        assert j.source == "remotely.de"
        assert j.remote is True
        assert "AI/ML" in j.tags
        # HTML stripped
        assert "<p>" not in j.description
        assert "Build ML systems" in j.description

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_keyword_filter(self, mock_client_cls, mock_delay):
        mock_client_cls.return_value = self._make_client_mock(self.SITEMAP, self.JOB_HTML)
        # "ai engineer" matches → 1 (both sitemap entries return same JobPosting)
        jobs = scrape_remotely_de(keyword_filter=["ai engineer"], limit=2, max_age_hours=None)
        assert len(jobs) == 2
        # Non-matching keyword → 0
        mock_client_cls.return_value = self._make_client_mock(self.SITEMAP, self.JOB_HTML)
        jobs = scrape_remotely_de(keyword_filter=["accountant"], limit=2, max_age_hours=None)
        assert jobs == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_empty_sitemap(self, mock_client_cls, mock_delay):
        empty_sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        )
        mock_client_cls.return_value = self._make_client_mock(empty_sitemap, "")
        assert scrape_remotely_de(limit=10, max_age_hours=None) == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_malformed_detail_no_jsonld(self, mock_client_cls, mock_delay):
        """Detail page without a JobPosting block must be skipped, not crash."""
        mock_client_cls.return_value = self._make_client_mock(
            self.SITEMAP, "<html><body>no structured data</body></html>"
        )
        # Two sitemap entries, both lacking JSON-LD → 0 jobs, no exception
        jobs = scrape_remotely_de(limit=2, max_age_hours=None)
        assert jobs == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_sitemap_fetch_failure(self, mock_client_cls, mock_delay):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("503")
        mock_client_cls.return_value = mock_client
        assert scrape_remotely_de(limit=10) == []

    @patch("scrape_new_sources._random_delay")
    @patch("scrape_new_sources.httpx.Client")
    def test_malformed_sitemap_xml(self, mock_client_cls, mock_delay):
        """Bad XML must return [] rather than propagate ParseError."""
        mock_client_cls.return_value = self._make_client_mock("<not-xml", self.JOB_HTML)
        assert scrape_remotely_de(limit=5, max_age_hours=None) == []


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
