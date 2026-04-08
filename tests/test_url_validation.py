"""Tests for URL validation utilities.

Verifies that detect_platform and related helpers use proper hostname
parsing instead of substring matching, preventing bypass via query
parameters, fragments, or subdomain tricks.
"""

from career_os.utils.url_validation import (
    detect_platform,
    is_greenhouse_eu,
    url_has_domain,
)


class TestDetectPlatform:
    """Verify platform detection from job URLs."""

    def test_ashby_valid(self):
        assert detect_platform("https://jobs.ashbyhq.com/n8n/abc-123") == "ashby"

    def test_greenhouse_valid(self):
        assert detect_platform("https://boards.greenhouse.io/anthropic/jobs/123") == "greenhouse"

    def test_greenhouse_eu_valid(self):
        assert detect_platform("https://boards.eu.greenhouse.io/company/jobs/456") == "greenhouse"

    def test_lever_valid(self):
        assert detect_platform("https://jobs.lever.co/mistral/67858cb5") == "lever"

    def test_lever_eu_valid(self):
        assert detect_platform("https://jobs.eu.lever.co/company/abc") == "lever"

    def test_workable_valid(self):
        assert detect_platform("https://apply.workable.com/company/j/abc123/") == "workable"

    def test_linkedin_valid(self):
        assert detect_platform("https://www.linkedin.com/jobs/view/123") == "linkedin"

    def test_remotely_valid(self):
        assert detect_platform("https://www.remotely.de/jobs/some-job") == "remotely"

    def test_unknown_platform(self):
        assert detect_platform("https://careers.example.com/job/123") == "unknown"

    # -- Bypass attempts that substring matching would miss --

    def test_greenhouse_in_query_rejected(self):
        """URL with greenhouse.io in query param must NOT match."""
        assert detect_platform("https://evil.com/?redirect=greenhouse.io") == "unknown"

    def test_greenhouse_in_fragment_rejected(self):
        assert detect_platform("https://evil.com/#greenhouse.io") == "unknown"

    def test_greenhouse_subdomain_spoof_rejected(self):
        """greenhouse.io.evil.com is NOT greenhouse.io."""
        assert detect_platform("https://greenhouse.io.evil.com/jobs") == "unknown"

    def test_ashby_in_path_rejected(self):
        assert detect_platform("https://evil.com/jobs.ashbyhq.com/fake") == "unknown"

    def test_lever_in_query_rejected(self):
        assert detect_platform("https://phishing.com?url=jobs.lever.co") == "unknown"

    def test_empty_url(self):
        assert detect_platform("") == "unknown"

    def test_malformed_url(self):
        assert detect_platform("not-a-url") == "unknown"

    def test_no_scheme(self):
        """URL without scheme - urlparse puts it all in path."""
        assert detect_platform("jobs.ashbyhq.com/company/123") == "unknown"


class TestIsGreenhouseEu:
    """Verify EU Greenhouse detection."""

    def test_eu_greenhouse(self):
        assert is_greenhouse_eu("https://boards.eu.greenhouse.io/company/jobs/123") is True

    def test_global_greenhouse(self):
        assert is_greenhouse_eu("https://boards.greenhouse.io/company/jobs/123") is False

    def test_eu_in_query_rejected(self):
        assert is_greenhouse_eu("https://evil.com?r=eu.greenhouse.io") is False

    def test_empty(self):
        assert is_greenhouse_eu("") is False


class TestUrlHasDomain:
    """Verify url_has_domain helper."""

    def test_exact_match(self):
        assert url_has_domain("https://greenhouse.io/path", "greenhouse.io") is True

    def test_subdomain_match(self):
        assert url_has_domain("https://boards.greenhouse.io/path", "greenhouse.io") is True

    def test_query_param_no_match(self):
        assert url_has_domain("https://evil.com?x=greenhouse.io", "greenhouse.io") is False

    def test_subdomain_spoof_no_match(self):
        assert url_has_domain("https://greenhouse.io.evil.com", "greenhouse.io") is False

    def test_case_insensitive(self):
        assert url_has_domain("https://BOARDS.GREENHOUSE.IO/path", "greenhouse.io") is True
