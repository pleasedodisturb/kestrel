"""Tests for tools/source_registry.py (G-1802).

This is the first test file for tools/source_registry.py. It covers only
browser_disabled_reason / BROWSER_DISABLED_HOSTS — the rest of the module
(FLOOR_SOURCES, JOBSPY_BOARDS, classify/check/status_table) is a
pre-existing gap flagged, not fixed, by this ticket.
"""

from source_registry import BROWSER_DISABLED_HOSTS, UNPARSEABLE_URL_REASON, browser_disabled_reason


class TestBrowserDisabledReason:
    """browser_disabled_reason matches Indeed hosts, label-based and fail-closed."""

    def test_matches_www_indeed_com(self):
        """https://www.indeed.com/... is refused with the recorded reason."""
        reason = browser_disabled_reason("https://www.indeed.com/jobs?q=pm")
        assert reason == BROWSER_DISABLED_HOSTS["indeed"]
        assert reason is not None

    def test_matches_de_indeed_subdomain(self):
        """A ccTLD subdomain like de.indeed.com still matches."""
        reason = browser_disabled_reason("https://de.indeed.com/viewjob?jk=1")
        assert reason == BROWSER_DISABLED_HOSTS["indeed"]

    def test_matches_indeed_de_cctld(self):
        """indeed.de (a different TLD, same label) still matches."""
        reason = browser_disabled_reason("https://indeed.de/")
        assert reason == BROWSER_DISABLED_HOSTS["indeed"]

    def test_matches_indeed_co_uk(self):
        """indeed.co.uk still matches on the indeed label."""
        reason = browser_disabled_reason("https://www.indeed.co.uk/x")
        assert reason == BROWSER_DISABLED_HOSTS["indeed"]

    def test_matches_uppercase_host(self):
        """Matching is case-insensitive."""
        reason = browser_disabled_reason("https://WWW.INDEED.COM/x")
        assert reason == BROWSER_DISABLED_HOSTS["indeed"]

    def test_matches_scheme_less_input(self):
        """A scheme-less URL is re-parsed so it is still caught (fail closed)."""
        reason = browser_disabled_reason("indeed.com/jobs")
        assert reason == BROWSER_DISABLED_HOSTS["indeed"]

    def test_returns_none_for_example_com(self):
        """A non-Indeed host is allowed through."""
        assert browser_disabled_reason("https://example.com/careers") is None

    def test_linkedin_hosts_are_refused(self):
        for url in (
            "https://www.linkedin.com/jobs/view/123",
            "https://de.linkedin.com/jobs/search/?keywords=x",
            "LINKEDIN.COM/jobs",
        ):
            reason = browser_disabled_reason(url)
            assert reason is not None and "LinkedIn" in reason, url

    def test_returns_none_for_notindeed_com(self):
        """A host that merely contains "indeed" as a substring is NOT matched."""
        assert browser_disabled_reason("https://notindeed.com/") is None

    def test_only_host_counts_not_query_string(self):
        """A query string mentioning indeed does not trigger a false match."""
        assert browser_disabled_reason("https://example.com/?q=indeed") is None

    def test_refuses_garbage_input(self):
        """Non-URL input is handled without raising and is refused (fail closed)."""
        assert browser_disabled_reason("not a url") == UNPARSEABLE_URL_REASON
        assert browser_disabled_reason("") == UNPARSEABLE_URL_REASON
        assert browser_disabled_reason("http://[bad") == UNPARSEABLE_URL_REASON


class TestBrowserDisabledHostsContent:
    """BROWSER_DISABLED_HOSTS["indeed"] records why and points at the alternative."""

    def test_indeed_reason_mentions_cloudflare_and_ticket(self):
        """The reason cites the Cloudflare 403 and the G-1802 ticket."""
        reason = BROWSER_DISABLED_HOSTS["indeed"]
        assert "Cloudflare 403" in reason
        assert "G-1802" in reason

    def test_indeed_reason_mentions_jobspy_alternative(self):
        """The reason says Indeed is still reachable via python-jobspy."""
        reason = BROWSER_DISABLED_HOSTS["indeed"]
        assert "jobspy" in reason.lower()
        assert "indeed" in reason.lower()
