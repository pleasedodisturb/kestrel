"""Regression tests for two sources that could never return a job (G-1564).

Both were found by auditing Kestrel against its downstream fork after that fork
fixed the same defects:

  * ``scrape_germantechjobs`` parsed ``.//item`` (RSS) against a feed that
    serves ``<jobs><job>``. Measured against the live feed 2026-08-10: 4.2 MB,
    **1,011 <job> elements, 0 <item> elements**. It returned 0 forever while the
    board served a full listing.
  * ``scrape_thehub`` GET the HTML page thehub.io/jobs and called ``.json()``
    on it. It raised on every retry for every search term and has been removed.

The thesis these tests defend: **a source returning nothing must never look like
a source with nothing to return.** A silent zero is indistinguishable from an
empty board, so it survives indefinitely.

No network. Fixtures reproduce the real response *shapes*.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scrape_resilient  # noqa: E402
from scrape_resilient import scrape_germantechjobs  # noqa: E402

# The real feed's shape, reduced to three entries. Flat children, aliases on
# title/company/url, DD.MM.YYYY pubdate, no <channel> and no <item>.
GTJ_REAL_SHAPE = """<?xml version="1.0" encoding="UTF-8"?>
<jobs>
  <job>
    <title>Senior Backend Engineer</title>
    <company>Beispiel GmbH</company>
    <city>Berlin</city>
    <country>Germany</country>
    <url>https://germantechjobs.de/job/1</url>
    <salary>70000-90000</salary>
    <pubdate>09.08.2026</pubdate>
    <description>Build things.</description>
  </job>
  <job>
    <name>Solution Architect</name>
    <company-name>Muster AG</company-name>
    <location>Munich</location>
    <link>https://germantechjobs.de/job/2</link>
    <pubdate>10.08.2026</pubdate>
    <description>Architect things.</description>
  </job>
  <job>
    <title>Data Engineer</title>
    <company>Alt GmbH</company>
    <city>Hamburg</city>
    <country>Germany</country>
    <apply_url>https://germantechjobs.de/job/3</apply_url>
    <pubdate>01.01.2020</pubdate>
  </job>
</jobs>
"""

# The legacy RSS shape, still accepted in case the board switches back.
GTJ_RSS_SHAPE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Platform Engineer</title>
    <link>https://germantechjobs.de/job/9</link>
    <description>Legacy shape.</description>
    <pubDate>Mon, 10 Aug 2026 09:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""

# Neither shape — the case that must WARN rather than pass as an empty board.
GTJ_UNKNOWN_SHAPE = """<?xml version="1.0" encoding="UTF-8"?>
<listings><posting><title>Something</title></posting></listings>
"""


@pytest.fixture
def feed(monkeypatch):
    """Serve fixture XML in place of the network."""

    def _serve(xml: str):
        monkeypatch.setattr(scrape_resilient, "_retry_with_backoff", lambda fn: xml)

    return _serve


class TestGermanTechJobsParser:
    def test_parses_the_real_jobs_job_shape(self, feed):
        """The whole bug: `.//item` against `<jobs><job>` returned 0 forever."""
        feed(GTJ_REAL_SHAPE)
        jobs = scrape_germantechjobs()
        assert len(jobs) == 3, "the <jobs><job> shape must yield jobs, not silence"

    def test_old_rss_selector_would_have_found_nothing(self):
        """Pin the defect itself, so the fix cannot be quietly reverted.

        This is the assertion that proves the test is worth having: against the
        real feed shape the previous selector yields zero, which is exactly why
        the source sat dead without anyone noticing.
        """
        import xml.etree.ElementTree as ET

        root = ET.fromstring(GTJ_REAL_SHAPE)
        assert root.findall(".//item") == [], "fixture must reproduce the real shape"
        assert len(root.findall("job")) == 3

    def test_reads_aliased_child_elements(self, feed):
        """The feed uses name/company-name/link/apply_url as aliases."""
        feed(GTJ_REAL_SHAPE)
        by_title = {j.title: j for j in scrape_germantechjobs()}
        assert "Solution Architect" in by_title
        alias = by_title["Solution Architect"]
        assert alias.company == "Muster AG"
        assert alias.url == "https://germantechjobs.de/job/2"
        assert by_title["Data Engineer"].url.endswith("/job/3")  # apply_url alias

    def test_builds_location_from_city_and_country(self, feed):
        feed(GTJ_REAL_SHAPE)
        by_title = {j.title: j for j in scrape_germantechjobs()}
        assert by_title["Senior Backend Engineer"].location == "Berlin, Germany"
        # Falls back to <location> when city/country are absent.
        assert by_title["Solution Architect"].location == "Munich"

    def test_normalizes_ddmmyyyy_pubdate_to_iso(self, feed):
        feed(GTJ_REAL_SHAPE)
        by_title = {j.title: j for j in scrape_germantechjobs()}
        assert by_title["Senior Backend Engineer"].posted == "2026-08-09"

    def test_returns_freshest_first_so_limit_trims_the_stale_tail(self, feed):
        """A promoted 2020 listing must not displace a role from this week."""
        feed(GTJ_REAL_SHAPE)
        jobs = scrape_germantechjobs(limit=2)
        assert len(jobs) == 2
        assert [j.posted for j in jobs] == ["2026-08-10", "2026-08-09"]
        assert all(j.posted != "2020-01-01" for j in jobs)

    def test_still_accepts_the_legacy_rss_shape(self, feed):
        feed(GTJ_RSS_SHAPE)
        jobs = scrape_germantechjobs()
        assert len(jobs) == 1
        assert jobs[0].title == "Platform Engineer"

    def test_unknown_shape_warns_instead_of_passing_as_empty(self, feed, caplog):
        """The point of the whole exercise.

        An unrecognised schema must announce itself as a PARSER failure. If it
        returns an empty list quietly, it is indistinguishable from a board with
        no jobs — and that is how this source stayed broken.
        """
        feed(GTJ_UNKNOWN_SHAPE)
        with caplog.at_level("WARNING"):
            jobs = scrape_germantechjobs()
        assert jobs == []
        assert any("PARSER failure" in r.getMessage() for r in caplog.records), (
            "an unparseable feed must warn, not return a silent zero"
        )

    def test_malformed_xml_does_not_raise(self, feed):
        feed("<jobs><job><title>unclosed")
        assert scrape_germantechjobs() == []


class TestTheHubRemoved:
    def test_thehub_scraper_is_gone(self):
        """It GET an HTML page and called .json(); it could never succeed.

        Removed rather than left in place, because dead code that always returns
        zero is the silent-zero failure in its purest form.
        """
        import scrape_new_sources

        assert not hasattr(scrape_new_sources, "scrape_thehub")

    def test_no_module_still_imports_it(self):
        """A dangling import would break the whole scrape at runtime."""
        import scrape_new_sources  # noqa: F401
        import scrape_resilient  # noqa: F401
        # Importing both is the assertion: a leftover `from ... import
        # scrape_thehub` raises ImportError here rather than mid-scan.


class TestTitleMatchingSingularAndPlural:
    def test_solution_architect_singular_is_matched(self):
        """One character used to drop a whole class of roles.

        "solutions" does not substring-match "Solution Architect", so a
        plural-only list silently skips every employer using the singular.
        """
        from kit_builder import _ARCHETYPE_RULES

        keywords = [kw for _, kws in _ARCHETYPE_RULES for kw in kws]
        title = "Solution Architect"
        assert any(kw in title.lower() for kw in keywords), (
            "the singular form must match; plural-only lists lose these roles"
        )

    def test_plural_still_matched(self):
        from kit_builder import _ARCHETYPE_RULES

        keywords = [kw for _, kws in _ARCHETYPE_RULES for kw in kws]
        assert any(kw in "Solutions Architect".lower() for kw in keywords)

    def test_search_queries_cover_both_forms(self):
        from scrape_new_sources import _SR_QUERIES

        assert "solution architect" in _SR_QUERIES
        assert "solutions architect" in _SR_QUERIES
