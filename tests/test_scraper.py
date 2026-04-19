"""Unit tests for tools/scraper.py."""

from unittest.mock import patch

import pandas as pd
from scraper import (
    DEFAULT_HOURS_OLD,
    DEFAULT_KEYWORDS,
    DEFAULT_LOCATION,
    DEFAULT_RESULTS_PER_KEYWORD,
    DEFAULT_SITES,
    scrape_all,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_keywords_count(self):
        assert len(DEFAULT_KEYWORDS) == 7

    def test_default_keywords_are_strings(self):
        assert all(isinstance(kw, str) for kw in DEFAULT_KEYWORDS)

    def test_default_sites(self):
        assert DEFAULT_SITES == ["linkedin", "indeed", "glassdoor", "google"]

    def test_default_location(self):
        assert DEFAULT_LOCATION == "Berlin, Germany"

    def test_default_hours_old(self):
        assert DEFAULT_HOURS_OLD == 72

    def test_default_results_per_keyword(self):
        assert DEFAULT_RESULTS_PER_KEYWORD == 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jobs_df(rows):
    """Build a small DataFrame mimicking scrape_jobs output."""
    return pd.DataFrame(rows, columns=["title", "company", "location", "url"])


# ---------------------------------------------------------------------------
# scrape_all
# ---------------------------------------------------------------------------


class TestScrapeAll:
    @patch("scraper.scrape_jobs")
    def test_uses_default_parameters(self, mock_scrape):
        mock_scrape.return_value = _make_jobs_df(
            [
                ("PM", "Co", "Berlin", "http://a"),
            ]
        )

        scrape_all()

        assert mock_scrape.call_count == len(DEFAULT_KEYWORDS)
        first_call = mock_scrape.call_args_list[0]
        assert first_call.kwargs["site_name"] == DEFAULT_SITES
        assert first_call.kwargs["search_term"] == DEFAULT_KEYWORDS[0]
        assert first_call.kwargs["location"] == DEFAULT_LOCATION
        assert first_call.kwargs["results_wanted"] == DEFAULT_RESULTS_PER_KEYWORD
        assert first_call.kwargs["hours_old"] == DEFAULT_HOURS_OLD

    @patch("scraper.scrape_jobs")
    def test_custom_parameters_passed_through(self, mock_scrape):
        mock_scrape.return_value = _make_jobs_df(
            [
                ("PM", "Co", "Berlin", "http://a"),
            ]
        )

        scrape_all(
            keywords=["Custom Role"],
            location="Berlin, Germany",
            hours_old=24,
            results_per_keyword=10,
            sites=["linkedin"],
        )

        mock_scrape.assert_called_once_with(
            site_name=["linkedin"],
            search_term="Custom Role",
            location="Berlin, Germany",
            results_wanted=10,
            hours_old=24,
            country_indeed="Germany",
        )

    @patch("scraper.scrape_jobs")
    def test_adds_search_keyword_column(self, mock_scrape):
        mock_scrape.return_value = _make_jobs_df(
            [
                ("PM", "Co", "Berlin", "http://a"),
            ]
        )

        result = scrape_all(keywords=["My Keyword"])

        assert "search_keyword" in result.columns
        assert result["search_keyword"].iloc[0] == "My Keyword"

    @patch("scraper.scrape_jobs")
    def test_concatenates_results_from_multiple_keywords(self, mock_scrape):
        mock_scrape.side_effect = [
            _make_jobs_df([("PM", "Co A", "Berlin", "http://a")]),
            _make_jobs_df([("Eng", "Co B", "Munich", "http://b")]),
        ]

        result = scrape_all(keywords=["kw1", "kw2"])

        assert len(result) == 2
        assert set(result["search_keyword"]) == {"kw1", "kw2"}

    @patch("scraper.scrape_jobs")
    def test_deduplicates_by_title_company_location(self, mock_scrape):
        dup_row = ("PM", "Co", "Berlin", "http://a")
        mock_scrape.side_effect = [
            _make_jobs_df([dup_row]),
            _make_jobs_df([dup_row]),
        ]

        result = scrape_all(keywords=["kw1", "kw2"])

        assert len(result) == 1
        # Keeps the first occurrence
        assert result["search_keyword"].iloc[0] == "kw1"

    @patch("scraper.scrape_jobs")
    def test_dedup_keeps_different_locations(self, mock_scrape):
        mock_scrape.side_effect = [
            _make_jobs_df([("PM", "Co", "Berlin", "http://a")]),
            _make_jobs_df([("PM", "Co", "Munich", "http://b")]),
        ]

        result = scrape_all(keywords=["kw1", "kw2"])

        assert len(result) == 2

    @patch("scraper.scrape_jobs")
    def test_empty_results_returns_empty_dataframe(self, mock_scrape):
        mock_scrape.return_value = _make_jobs_df([])

        result = scrape_all(keywords=["kw1"])

        # scrape_jobs returned rows but empty; concat produces empty df
        assert isinstance(result, pd.DataFrame)

    @patch("scraper.scrape_jobs")
    def test_all_keywords_fail_returns_empty_dataframe(self, mock_scrape):
        mock_scrape.side_effect = RuntimeError("API error")

        result = scrape_all(keywords=["kw1", "kw2"])

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("scraper.scrape_jobs")
    def test_one_keyword_fails_others_succeed(self, mock_scrape):
        mock_scrape.side_effect = [
            RuntimeError("fail"),
            _make_jobs_df([("Eng", "Co B", "Munich", "http://b")]),
        ]

        result = scrape_all(keywords=["bad_kw", "good_kw"])

        assert len(result) == 1
        assert result["search_keyword"].iloc[0] == "good_kw"

    @patch("scraper.scrape_jobs")
    def test_error_is_printed_not_raised(self, mock_scrape, capsys):
        mock_scrape.side_effect = ValueError("boom")

        scrape_all(keywords=["kw1"])

        captured = capsys.readouterr()
        assert "Error scraping 'kw1'" in captured.out
        assert "boom" in captured.out

    @patch("scraper.scrape_jobs")
    def test_country_indeed_always_germany(self, mock_scrape):
        mock_scrape.return_value = _make_jobs_df(
            [
                ("PM", "Co", "Berlin", "http://a"),
            ]
        )

        scrape_all(keywords=["kw1"])

        assert mock_scrape.call_args.kwargs["country_indeed"] == "Germany"
