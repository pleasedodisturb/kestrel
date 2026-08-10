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
from unittest.mock import MagicMock

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
    """Serve fixture XML by mocking the HTTP CLIENT, not `_retry_with_backoff`.

    This distinction is the entire point of this file, so it is worth stating.
    Patching ``_retry_with_backoff`` would stub out the layer *above* the
    request, meaning ``_fetch`` never runs — the URL, the verb, the headers and
    the ``.text`` vs ``.json()`` choice would all go untested. That is precisely
    how TheHub kept three green tests while GETting an HTML page and calling
    ``.json()`` on it: its tests mocked away the broken thing and then asserted
    that the mock worked.

    Patching ``httpx.Client`` keeps the real ``_fetch`` in the loop, so a
    mutation to the URL or the response accessor fails these tests.
    """

    def _serve(xml: str):
        response = MagicMock()
        response.text = xml
        response.raise_for_status = MagicMock()
        # .json() must EXPLODE. If production ever calls it on this XML feed —
        # the TheHub mistake — the test has to fail rather than hand back a mock.
        response.json = MagicMock(
            side_effect=ValueError("Expecting value: line 1 column 1 (char 0)")
        )
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.get = MagicMock(return_value=response)
        # Any non-GET verb is a bug in a feed reader; make it obvious.
        client.post = MagicMock(side_effect=AssertionError("feed must be fetched with GET"))
        monkeypatch.setattr(scrape_resilient.httpx, "Client", MagicMock(return_value=client))
        monkeypatch.setattr(scrape_resilient, "_random_delay", lambda *a, **k: None)
        monkeypatch.setattr(scrape_resilient.time, "sleep", lambda *a, **k: None)
        return client

    return _serve


class TestGermanTechJobsParser:
    def test_parses_the_real_jobs_job_shape(self, feed):
        """The whole bug: `.//item` against `<jobs><job>` returned 0 forever."""
        feed(GTJ_REAL_SHAPE)
        jobs = scrape_germantechjobs()
        assert len(jobs) == 3, "the <jobs><job> shape must yield jobs, not silence"

    def test_fetches_the_feed_url_with_GET_and_reads_text_not_json(self, feed):
        """Exercise the REQUEST, not just the parse.

        Replaces an earlier version of this test that asserted about
        ElementTree and never touched production code — a fixture self-check
        masquerading as a regression test. This one fails if the URL, the verb,
        or the response accessor changes, which is the TheHub failure class.
        """
        client = feed(GTJ_REAL_SHAPE)
        scrape_germantechjobs()
        client.get.assert_called_once()
        (url,), _ = client.get.call_args
        assert url == scrape_resilient.GERMANTECHJOBS_RSS
        client.post.assert_not_called()

    def test_nested_job_elements_are_not_silently_skipped(self, feed):
        """A grouped feed must not lose its entries.

        `findall("job") or findall(".//job")` looks defensive but short-circuits:
        the direct-child form returns a NON-EMPTY partial list, so the fallback
        never runs and nested entries vanish with no warning. A silent wrong
        subset is worse than the zero this module exists to prevent.
        """
        grouped = """<?xml version="1.0"?>
        <jobs>
          <job><title>Top Level</title><pubdate>01.08.2026</pubdate></job>
          <category>
            <job><title>Nested One</title><pubdate>02.08.2026</pubdate></job>
            <job><title>Nested Two</title><pubdate>03.08.2026</pubdate></job>
          </category>
        </jobs>"""
        feed(grouped)
        titles = {j.title for j in scrape_germantechjobs()}
        assert titles == {"Top Level", "Nested One", "Nested Two"}, (
            f"nested <job> entries were dropped: got {titles}"
        )

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

    def test_an_unparseable_date_cannot_hijack_the_top_slot(self, feed):
        """A raw string sort ranks garbage above every real date.

        `_gtj_posted` passes anything it cannot parse through verbatim, and under
        a reverse-lexical sort every string starting above '2' outranks every ISO
        date. One row reading "Mon, 01 Jan 2010 ..." would take rank 0 and, with a
        limit applied after, evict a genuinely fresh posting.
        """
        xml = """<?xml version="1.0"?>
        <jobs>
          <job><title>Garbage Date</title><pubdate>Mon, 01 Jan 2010 00:00:00 GMT</pubdate></job>
          <job><title>Fresh</title><pubdate>09.08.2026</pubdate></job>
          <job><title>Fresher</title><pubdate>10.08.2026</pubdate></job>
        </jobs>"""
        feed(xml)
        jobs = scrape_germantechjobs()
        assert jobs[0].title == "Fresher", f"garbage date hijacked rank 0: {jobs[0].title}"
        assert [j.title for j in jobs[:2]] == ["Fresher", "Fresh"]

    def test_a_dated_job_is_not_evicted_by_an_undated_one(self, feed):
        """The mirror failure, and the worse one.

        Under a naive sort an undated job lands dead last and is then
        DETERMINISTICALLY excluded by `limit` — permanently invisible, which is
        the silent-loss failure this module exists to prevent. Undated rows must
        stay reachable while never outranking a real date.
        """
        xml = """<?xml version="1.0"?>
        <jobs>
          <job><title>No Date</title></job>
          <job><title>Old</title><pubdate>01.01.2020</pubdate></job>
        </jobs>"""
        feed(xml)
        jobs = scrape_germantechjobs()
        titles = [j.title for j in jobs]
        assert titles == ["Old", "No Date"], titles
        assert "No Date" in titles, "an undated job must not become unreachable"

    def test_explicit_location_beats_a_bare_country(self, feed):
        """Composing city+country first discards the most specific signal.

        A posting carrying <country>Germany</country> AND
        <location>Frankfurt am Main, Germany</location> must not collapse to
        "Germany" — this project's geo classifier reads the bare country as a
        relocation and the qualified string as a no-move local role.
        """
        xml = """<?xml version="1.0"?>
        <jobs>
          <job>
            <title>Local Role</title>
            <country>Germany</country>
            <location>Frankfurt am Main, Germany</location>
            <pubdate>10.08.2026</pubdate>
          </job>
        </jobs>"""
        feed(xml)
        assert scrape_germantechjobs()[0].location == "Frankfurt am Main, Germany"

    def test_camelcase_pubdate_alias_is_read(self, feed):
        """pubdate was the one field with no alias; XML is case-sensitive."""
        xml = """<?xml version="1.0"?>
        <jobs><job><title>X</title><pubDate>10.08.2026</pubDate></job></jobs>"""
        feed(xml)
        assert scrape_germantechjobs()[0].posted == "2026-08-10"

    def test_still_accepts_the_legacy_rss_shape(self, feed):
        feed(GTJ_RSS_SHAPE)
        jobs = scrape_germantechjobs()
        assert len(jobs) == 1
        assert jobs[0].title == "Platform Engineer"

    def test_rss_fallback_sorts_and_limits_like_the_primary_branch(self, feed):
        """One field, one format, one ordering — regardless of which branch fired.

        The fallback used to apply `limit` with no sort and no date
        normalisation, so `posted` was ISO in one branch and RFC-822 in the
        other, and `limit` trimmed the HEAD instead of the stale tail. Any
        downstream date comparison then depended on an invisible condition.
        """
        rss = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item><title>Oldest</title><pubDate>01.01.2020</pubDate></item>
          <item><title>Newest</title><pubDate>10.08.2026</pubDate></item>
        </channel></rss>"""
        feed(rss)
        jobs = scrape_germantechjobs(limit=1)
        assert [j.title for j in jobs] == ["Newest"], "fallback trimmed the head, not the tail"
        assert jobs[0].posted == "2026-08-10", (
            "fallback must normalise dates like the primary branch"
        )

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
