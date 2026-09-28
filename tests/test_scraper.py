"""Unit tests for tools/scraper.py."""

import sys
from unittest.mock import patch

import pandas as pd
import pytest
from scraper import (
    DEFAULT_HOURS_OLD,
    DEFAULT_KEYWORDS,
    DEFAULT_LOCATION,
    DEFAULT_RESULTS_PER_KEYWORD,
    DEFAULT_SITES,
    main,
    scrape_all,
    validate_sites,
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
        assert DEFAULT_SITES == ["linkedin", "indeed"]
        assert "google" not in DEFAULT_SITES

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


# ---------------------------------------------------------------------------
# Site validation (G-1802): google is rejected up front
# ---------------------------------------------------------------------------


class TestSiteValidation:
    def test_validate_sites_accepts_defaults(self):
        """linkedin + indeed pass validation without raising."""
        validate_sites(["linkedin", "indeed"])

    def test_validate_sites_accepts_explicit_glassdoor(self):
        """Glassdoor is off by default but still accepted when requested explicitly."""
        validate_sites(["glassdoor"])

    @patch("scraper.scrape_jobs")
    def test_scrape_all_rejects_google(self, mock_scrape):
        """scrape_all raises ValueError naming google and the upstream issue; never calls scrape_jobs."""
        with pytest.raises(ValueError) as exc_info:
            scrape_all(keywords=["kw"], sites=["indeed", "google"])

        assert "google" in str(exc_info.value)
        assert "#302" in str(exc_info.value)
        mock_scrape.assert_not_called()

    @patch("scraper.scrape_jobs")
    def test_scrape_all_rejects_google_case_insensitive(self, mock_scrape):
        """A capitalized "Google" is rejected the same way as lowercase."""
        with pytest.raises(ValueError) as exc_info:
            scrape_all(keywords=["kw"], sites=["Google"])

        assert "google" in str(exc_info.value).lower()
        mock_scrape.assert_not_called()

    @patch("scraper.scrape_jobs")
    def test_main_rejects_google_with_exit_code_2(self, mock_scrape, monkeypatch, capsys):
        """The CLI exits 2 with a stderr message naming google and #302."""
        monkeypatch.setattr(sys, "argv", ["scraper.py", "--sites", "indeed", "google"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "google" in captured.err
        assert "#302" in captured.err
        mock_scrape.assert_not_called()
