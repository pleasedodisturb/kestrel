"""Unit tests for tools/scraper.py."""

from unittest.mock import patch

import pandas as pd
from scraper import (
    DEFAULT_HOURS_OLD,
    DEFAULT_KEYWORDS,
    DEFAULT_LOCATION,
    DEFAULT_RESULTS_PER_KEYWORD,
    DEFAULT_SITES,
    JOB_FAMILY_KEYWORDS,
    _match_job_family,
    get_keywords_for_profile,
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


# ---------------------------------------------------------------------------
# JOB_FAMILY_KEYWORDS
# ---------------------------------------------------------------------------


class TestJobFamilyKeywords:
    def test_all_values_are_lists_of_strings(self):
        for family, keywords in JOB_FAMILY_KEYWORDS.items():
            assert isinstance(keywords, list), f"{family} keywords is not a list"
            assert len(keywords) > 0, f"{family} has empty keywords"
            for kw in keywords:
                assert isinstance(kw, str), f"{family} has non-string keyword: {kw}"

    def test_no_empty_keywords(self):
        for family, keywords in JOB_FAMILY_KEYWORDS.items():
            for kw in keywords:
                assert kw.strip(), f"{family} has blank keyword"

    def test_core_scoring_families_have_keyword_presets(self):
        """Core tech/product job families from scoring should have keyword presets.

        JOB_FAMILY_WEIGHTS has 280+ families across all industries. Keyword
        presets cover the most common tech/product families. Uncovered families
        fall back to using the role title itself as a search keyword via
        get_keywords_for_profile().
        """
        core_families = [
            "TPM", "SWE", "Product Engineer", "DevRel", "AI Program Lead",
            "Backend Engineer", "Frontend Engineer", "Full-Stack Developer",
            "DevOps Engineer", "ML Engineer", "Data Engineer", "Data Scientist",
            "Engineering Manager", "Product Manager", "UX Designer",
        ]
        for family in core_families:
            assert family in JOB_FAMILY_KEYWORDS, (
                f"Core family '{family}' missing from JOB_FAMILY_KEYWORDS"
            )

    def test_tpm_keywords_present(self):
        assert "TPM" in JOB_FAMILY_KEYWORDS
        kws = JOB_FAMILY_KEYWORDS["TPM"]
        assert any("Technical Program Manager" in kw for kw in kws)

    def test_devrel_keywords_present(self):
        assert "DevRel" in JOB_FAMILY_KEYWORDS
        kws = JOB_FAMILY_KEYWORDS["DevRel"]
        assert any("Developer Advocate" in kw for kw in kws)

    def test_swe_keywords_present(self):
        assert "SWE" in JOB_FAMILY_KEYWORDS
        kws = JOB_FAMILY_KEYWORDS["SWE"]
        assert any("Software Engineer" in kw for kw in kws)


# ---------------------------------------------------------------------------
# _match_job_family
# ---------------------------------------------------------------------------


class TestMatchJobFamily:
    def test_exact_match(self):
        assert _match_job_family("TPM") == "TPM"

    def test_case_insensitive_match(self):
        assert _match_job_family("tpm") == "TPM"
        assert _match_job_family("devrel") == "DevRel"

    def test_substring_match(self):
        assert _match_job_family("Senior TPM") == "TPM"

    def test_no_match_returns_none(self):
        assert _match_job_family("Underwater Basket Weaver") is None

    def test_exact_key_preferred_over_substring(self):
        result = _match_job_family("Product Engineer")
        assert result == "Product Engineer"

    def test_whitespace_stripped(self):
        assert _match_job_family("  TPM  ") == "TPM"


# ---------------------------------------------------------------------------
# get_keywords_for_profile
# ---------------------------------------------------------------------------


class TestGetKeywordsForProfile:
    def test_no_args_returns_defaults(self):
        result = get_keywords_for_profile()
        assert result == DEFAULT_KEYWORDS

    def test_job_family_returns_preset(self):
        result = get_keywords_for_profile(job_family="TPM")
        assert result == JOB_FAMILY_KEYWORDS["TPM"]

    def test_job_family_case_insensitive(self):
        result = get_keywords_for_profile(job_family="devrel")
        assert result == JOB_FAMILY_KEYWORDS["DevRel"]

    def test_unknown_job_family_returns_defaults(self):
        result = get_keywords_for_profile(job_family="Nonexistent Role")
        assert result == DEFAULT_KEYWORDS

    def test_target_roles_single_match(self):
        result = get_keywords_for_profile(target_roles=["TPM"])
        assert result == JOB_FAMILY_KEYWORDS["TPM"]

    def test_target_roles_multiple_match(self):
        result = get_keywords_for_profile(target_roles=["TPM", "DevRel"])
        # Should contain keywords from both families
        for kw in JOB_FAMILY_KEYWORDS["TPM"]:
            assert kw in result
        for kw in JOB_FAMILY_KEYWORDS["DevRel"]:
            assert kw in result

    def test_target_roles_deduplication(self):
        result = get_keywords_for_profile(target_roles=["TPM", "TPM"])
        # Should not have duplicates
        assert len(result) == len(set(kw.lower() for kw in result))

    def test_target_roles_unrecognized_used_as_keyword(self):
        result = get_keywords_for_profile(target_roles=["Chief Llama Wrangler"])
        assert "Chief Llama Wrangler" in result

    def test_target_roles_mixed_recognized_and_unrecognized(self):
        result = get_keywords_for_profile(
            target_roles=["TPM", "Chief Llama Wrangler"]
        )
        # TPM keywords should be present
        assert any("Technical Program Manager" in kw for kw in result)
        # Unrecognized role used as-is
        assert "Chief Llama Wrangler" in result

    def test_target_roles_takes_precedence_over_job_family(self):
        result = get_keywords_for_profile(
            target_roles=["DevRel"],
            job_family="TPM",
        )
        # Should use target_roles, not job_family
        assert result == JOB_FAMILY_KEYWORDS["DevRel"]

    def test_empty_target_roles_falls_through_to_job_family(self):
        result = get_keywords_for_profile(target_roles=[], job_family="TPM")
        assert result == JOB_FAMILY_KEYWORDS["TPM"]

    def test_returns_new_list_not_reference(self):
        result = get_keywords_for_profile(job_family="TPM")
        result.append("extra")
        # Original should be unmodified
        assert "extra" not in JOB_FAMILY_KEYWORDS["TPM"]
