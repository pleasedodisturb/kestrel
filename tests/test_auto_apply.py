"""Unit tests for tools/auto_apply.py.

Tests cover: detect_platform, parse_lever_url, parse_greenhouse_url,
update_csv_status, _try_fill, _fill_input, _upload_file, screenshot,
extract_greenhouse_api_key, submit_lever_api, submit_greenhouse_api,
confirm_and_submit_browser, process_application, BROWSER_HANDLERS.
"""

import csv
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from auto_apply import (
    BROWSER_HANDLERS,
    _fill_input,
    _try_fill,
    _upload_file,
    confirm_and_submit_browser,
    detect_platform,
    extract_greenhouse_api_key,
    parse_greenhouse_url,
    parse_lever_url,
    process_application,
    screenshot,
    submit_greenhouse_api,
    submit_lever_api,
    update_csv_status,
)

# ===================================================================
# detect_platform
# ===================================================================


class TestDetectPlatform:
    """Tests for detect_platform(url)."""

    def test_ashby(self):
        assert detect_platform("https://jobs.ashbyhq.com/company/abc") == "ashby"

    def test_ashby_with_path(self):
        assert detect_platform("https://jobs.ashbyhq.com/someorg/jobs/123") == "ashby"

    def test_lever_global(self):
        assert detect_platform("https://jobs.lever.co/mistral/67858cb5") == "lever"

    def test_lever_eu(self):
        assert detect_platform("https://jobs.eu.lever.co/tradelink/42af") == "lever"

    def test_greenhouse(self):
        assert (
            detect_platform("https://job-boards.greenhouse.io/grafanalabs/jobs/123") == "greenhouse"
        )

    def test_greenhouse_eu(self):
        assert (
            detect_platform("https://job-boards.eu.greenhouse.io/jetbrains/jobs/456")
            == "greenhouse"
        )

    def test_remotely(self):
        assert detect_platform("https://remotely.de/jobs/some-role") == "remotely"

    def test_company_attio(self):
        assert detect_platform("https://attio.com/careers/some-role") == "company"

    def test_linkedin(self):
        assert detect_platform("https://www.linkedin.com/jobs/view/123456") == "linkedin"

    def test_linkedin_without_www(self):
        assert detect_platform("https://linkedin.com/jobs/view/789") == "linkedin"

    def test_unknown_random_domain(self):
        assert detect_platform("https://example.com/jobs/apply") == "unknown"

    def test_unknown_empty_string(self):
        assert detect_platform("") == "unknown"

    def test_greenhouse_embedded_in_longer_url(self):
        url = "https://boards.greenhouse.io/embed/job_board?for=grafanalabs"
        assert detect_platform(url) == "greenhouse"

    def test_lever_in_query_param_rejected(self):
        # Proper URL parsing rejects lever.co in query params (not in hostname)
        assert detect_platform("https://redirect.example.com/?next=jobs.lever.co/x") == "unknown"

    def test_case_insensitive_match(self):
        # URL hostnames are case-insensitive per RFC 3986
        assert detect_platform("https://JOBS.LEVER.CO/test/123") == "lever"


# ===================================================================
# parse_lever_url
# ===================================================================


class TestParseLeverUrl:
    """Tests for parse_lever_url(url)."""

    def test_global_standard(self):
        url = "https://jobs.lever.co/mistral/67858cb5-1234-5678-abcd-def012345678"
        base, site, posting = parse_lever_url(url)
        assert base == "https://api.lever.co"
        assert site == "mistral"
        assert posting == "67858cb5-1234-5678-abcd-def012345678"

    def test_eu_standard(self):
        url = "https://jobs.eu.lever.co/tradelink/42af0000-1111-2222-3333-444455556666"
        base, site, posting = parse_lever_url(url)
        assert base == "https://api.eu.lever.co"
        assert site == "tradelink"
        assert posting == "42af0000-1111-2222-3333-444455556666"

    def test_trailing_slash(self):
        url = "https://jobs.lever.co/company/posting-id/"
        _base, site, posting = parse_lever_url(url)
        assert site == "company"
        assert posting == "posting-id"

    def test_extra_path_segments_ignored(self):
        url = "https://jobs.lever.co/org/posting/extra/segment"
        _base, site, posting = parse_lever_url(url)
        assert site == "org"
        assert posting == "posting"

    def test_invalid_too_few_segments(self):
        with pytest.raises(ValueError, match="Cannot parse Lever URL"):
            parse_lever_url("https://jobs.lever.co/onlyone")

    def test_invalid_no_path(self):
        with pytest.raises(ValueError, match="Cannot parse Lever URL"):
            parse_lever_url("https://jobs.lever.co/")

    def test_invalid_empty_path(self):
        with pytest.raises(ValueError, match="Cannot parse Lever URL"):
            parse_lever_url("https://jobs.lever.co")

    def test_apply_suffix_counts_as_second_segment(self):
        # URL like /company/apply has two segments
        url = "https://jobs.lever.co/company/apply"
        _base, site, posting = parse_lever_url(url)
        assert site == "company"
        assert posting == "apply"


# ===================================================================
# parse_greenhouse_url
# ===================================================================


class TestParseGreenhouseUrl:
    """Tests for parse_greenhouse_url(url)."""

    def test_standard_global(self):
        url = "https://job-boards.greenhouse.io/grafanalabs/jobs/5796211004"
        board, job_id = parse_greenhouse_url(url)
        assert board == "grafanalabs"
        assert job_id == "5796211004"

    def test_standard_eu(self):
        url = "https://job-boards.eu.greenhouse.io/jetbrains/jobs/4782168101"
        board, job_id = parse_greenhouse_url(url)
        assert board == "jetbrains"
        assert job_id == "4782168101"

    def test_trailing_slash(self):
        url = "https://job-boards.greenhouse.io/org/jobs/12345/"
        board, job_id = parse_greenhouse_url(url)
        assert board == "org"
        assert job_id == "12345"

    def test_extra_path_after_job_id(self):
        url = "https://job-boards.greenhouse.io/org/jobs/99999/extra"
        board, job_id = parse_greenhouse_url(url)
        assert board == "org"
        assert job_id == "99999"

    def test_invalid_missing_jobs_segment(self):
        with pytest.raises(ValueError, match="Cannot parse Greenhouse URL"):
            parse_greenhouse_url("https://job-boards.greenhouse.io/org/12345")

    def test_invalid_too_short(self):
        with pytest.raises(ValueError, match="Cannot parse Greenhouse URL"):
            parse_greenhouse_url("https://job-boards.greenhouse.io/org")

    def test_invalid_empty_path(self):
        with pytest.raises(ValueError, match="Cannot parse Greenhouse URL"):
            parse_greenhouse_url("https://job-boards.greenhouse.io/")

    def test_invalid_wrong_keyword(self):
        with pytest.raises(ValueError, match="Cannot parse Greenhouse URL"):
            parse_greenhouse_url("https://job-boards.greenhouse.io/org/positions/123")

    def test_query_params_ignored(self):
        url = "https://job-boards.greenhouse.io/org/jobs/555?gh_jid=555"
        board, job_id = parse_greenhouse_url(url)
        assert board == "org"
        assert job_id == "555"


# ===================================================================
# update_csv_status
# ===================================================================


class TestUpdateCsvStatus:
    """Tests for update_csv_status(company, role, new_status)."""

    CSV_HEADER = "date_applied,company,role,url,source,status,salary_range\n"

    def _make_csv(self, tmp_path, rows_text):
        """Helper: create tracking/applications.csv under tmp_path."""
        tracking = tmp_path / "tracking"
        tracking.mkdir(exist_ok=True)
        csv_file = tracking / "applications.csv"
        csv_file.write_text(self.CSV_HEADER + rows_text)
        return csv_file

    def _read_rows(self, csv_file):
        """Helper: read CSV back as list of dicts."""
        with open(csv_file, newline="") as f:
            return list(csv.DictReader(f))

    def test_updates_matching_row(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Senior Engineer,https://acme.com,linkedin,interested,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "Senior Engineer", "applied")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "applied"
        assert rows[0]["date_applied"] == str(date.today())

    def test_role_match_is_case_insensitive_substring(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Senior Software Engineer,https://acme.com,linkedin,interested,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "software engineer", "applied")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "applied"

    def test_company_match_is_exact_stripped(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01, Acme ,Senior Engineer,https://acme.com,linkedin,interested,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "Senior Engineer", "applied")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "applied"

    def test_company_mismatch_no_update(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Senior Engineer,https://acme.com,linkedin,interested,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("WrongCo", "Senior Engineer", "applied")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "interested"

    def test_role_mismatch_no_update(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Senior Engineer,https://acme.com,linkedin,interested,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "Product Manager", "applied")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "interested"

    def test_updates_only_matching_row_among_many(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Engineer,https://acme.com,linkedin,interested,100k\n"
            "2026-03-02,Beta,Designer,https://beta.com,indeed,pending,90k\n"
            "2026-03-03,Gamma,Engineer,https://gamma.com,remote,open,110k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Beta", "Designer", "applied")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "interested"
        assert rows[1]["status"] == "applied"
        assert rows[2]["status"] == "open"

    def test_no_op_if_csv_missing(self, tmp_path):
        # Should not raise; just return silently
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "Engineer", "applied")

    def test_custom_status_value(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Engineer,https://acme.com,linkedin,pending,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "Engineer", "rejected")
        rows = self._read_rows(csv_file)
        assert rows[0]["status"] == "rejected"

    def test_multiple_matches_all_updated(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Senior Engineer,https://acme.com/1,linkedin,pending,100k\n"
            "2026-03-02,Acme,Junior Engineer,https://acme.com/2,linkedin,pending,80k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("Acme", "Engineer", "applied")
        rows = self._read_rows(csv_file)
        # Both rows contain "engineer" (case-insensitive) and company matches
        assert rows[0]["status"] == "applied"
        assert rows[1]["status"] == "applied"

    def test_company_match_is_case_sensitive(self, tmp_path):
        csv_file = self._make_csv(
            tmp_path,
            "2026-03-01,Acme,Engineer,https://acme.com,linkedin,pending,100k\n",
        )
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            update_csv_status("acme", "Engineer", "applied")
        rows = self._read_rows(csv_file)
        # strip() comparison is exact, so "Acme" != "acme"
        assert rows[0]["status"] == "pending"


# ===================================================================
# _fill_input
# ===================================================================


class TestFillInput:
    """Tests for _fill_input(context, selector, value).

    We only test the early-return on empty value. The Playwright
    locator paths require a real browser, so they are not tested here.
    """

    def test_returns_false_for_empty_string(self):
        context = MagicMock()
        assert _fill_input(context, "input#name", "") is False
        # Should never touch the locator
        context.locator.assert_not_called()

    def test_returns_false_for_none(self):
        context = MagicMock()
        assert _fill_input(context, "input#name", None) is False
        context.locator.assert_not_called()

    def test_returns_false_when_locator_not_found(self):
        context = MagicMock()
        loc = MagicMock()
        loc.count.return_value = 0
        context.locator.return_value = loc
        assert _fill_input(context, "input#name", "Alice") is False

    def test_returns_true_when_locator_found_and_filled(self):
        context = MagicMock()
        loc = MagicMock()
        loc.count.return_value = 1
        context.locator.return_value = loc
        assert _fill_input(context, "input#name", "Alice") is True
        loc.first.click.assert_called_once()
        loc.first.fill.assert_called_once_with("Alice")

    def test_returns_false_when_fill_raises(self):
        context = MagicMock()
        loc = MagicMock()
        loc.count.return_value = 1
        loc.first.click.side_effect = Exception("element detached")
        context.locator.return_value = loc
        assert _fill_input(context, "input#name", "Alice") is False


# ===================================================================
# _try_fill
# ===================================================================


class TestTryFill:
    """Tests for _try_fill(context, selectors, value)."""

    def test_returns_false_for_empty_value(self):
        context = MagicMock()
        assert _try_fill(context, ["input#a", "input#b"], "") is False
        context.locator.assert_not_called()

    def test_returns_false_for_none_value(self):
        context = MagicMock()
        assert _try_fill(context, ["input#a"], None) is False

    def test_tries_selectors_in_order_stops_on_first_match(self):
        context = MagicMock()
        loc_miss = MagicMock()
        loc_miss.count.return_value = 0
        loc_hit = MagicMock()
        loc_hit.count.return_value = 1

        def locator_side_effect(sel):
            if sel == "input#a":
                return loc_miss
            return loc_hit

        context.locator.side_effect = locator_side_effect

        result = _try_fill(context, ["input#a", "input#b", "input#c"], "value")
        assert result is True
        # Should have tried a (miss), then b (hit), and never reached c
        assert context.locator.call_count == 2

    def test_returns_false_when_no_selector_matches(self):
        context = MagicMock()
        loc = MagicMock()
        loc.count.return_value = 0
        context.locator.return_value = loc

        result = _try_fill(context, ["input#a", "input#b"], "value")
        assert result is False
        assert context.locator.call_count == 2

    def test_empty_selector_list(self):
        context = MagicMock()
        assert _try_fill(context, [], "value") is False


# ===================================================================
# _upload_file
# ===================================================================


class TestUploadFile:
    """Tests for _upload_file(context, index, file_path, label)."""

    def test_uploads_when_input_exists(self):
        context = MagicMock()
        file_inputs = MagicMock()
        file_inputs.count.return_value = 2
        context.locator.return_value = file_inputs

        with patch("auto_apply.time"):
            result = _upload_file(context, 0, "/tmp/cv.pdf", "CV")
        assert result is True
        file_inputs.nth.assert_called_once_with(0)
        file_inputs.nth(0).set_input_files.assert_called_with("/tmp/cv.pdf")

    def test_returns_false_when_index_out_of_range(self):
        context = MagicMock()
        file_inputs = MagicMock()
        file_inputs.count.return_value = 1
        context.locator.return_value = file_inputs

        result = _upload_file(context, 2, "/tmp/cv.pdf", "CV")
        assert result is False

    def test_returns_false_when_no_file_inputs(self):
        context = MagicMock()
        file_inputs = MagicMock()
        file_inputs.count.return_value = 0
        context.locator.return_value = file_inputs

        result = _upload_file(context, 0, "/tmp/cv.pdf", "CV")
        assert result is False

    def test_returns_false_on_exception(self):
        context = MagicMock()
        file_inputs = MagicMock()
        file_inputs.count.return_value = 1
        file_inputs.nth.return_value.set_input_files.side_effect = Exception("fail")
        context.locator.return_value = file_inputs

        result = _upload_file(context, 0, "/tmp/cv.pdf", "CV")
        assert result is False


# ===================================================================
# screenshot
# ===================================================================


class TestScreenshot:
    """Tests for screenshot(page, name)."""

    def test_creates_directory_and_saves(self, tmp_path):
        page = MagicMock()
        screenshots_dir = tmp_path / "screenshots"

        with (
            patch("auto_apply.SCREENSHOTS_DIR", screenshots_dir),
            patch("auto_apply.time") as mock_time,
        ):
            mock_time.time.return_value = 1234567890
            result = screenshot(page, "test_shot")

        assert screenshots_dir.exists()
        expected_path = screenshots_dir / "test_shot_1234567890.png"
        assert result == expected_path
        page.screenshot.assert_called_once_with(path=str(expected_path), full_page=True)

    def test_uses_existing_directory(self, tmp_path):
        page = MagicMock()
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()

        with (
            patch("auto_apply.SCREENSHOTS_DIR", screenshots_dir),
            patch("auto_apply.time") as mock_time,
        ):
            mock_time.time.return_value = 9999999999
            result = screenshot(page, "existing_dir")

        assert result == screenshots_dir / "existing_dir_9999999999.png"


# ===================================================================
# extract_greenhouse_api_key
# ===================================================================


class TestExtractGreenhouseApiKey:
    """Tests for extract_greenhouse_api_key(board_token)."""

    def test_returns_no_key_needed_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("auto_apply.httpx.get", return_value=mock_resp):
            result = extract_greenhouse_api_key("grafanalabs")
        assert result == "__no_key_needed__"

    def test_falls_back_to_eu_endpoint(self):
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 404
        mock_resp_eu = MagicMock()
        mock_resp_eu.status_code = 200

        with patch("auto_apply.httpx.get", side_effect=[mock_resp_fail, mock_resp_eu]):
            result = extract_greenhouse_api_key("jetbrains")
        assert result == "__no_key_needed_eu__"

    def test_returns_none_when_both_fail(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("auto_apply.httpx.get", return_value=mock_resp):
            result = extract_greenhouse_api_key("nonexistent")
        assert result is None

    def test_returns_none_on_network_error(self):
        with patch("auto_apply.httpx.get", side_effect=Exception("timeout")):
            result = extract_greenhouse_api_key("board")
        assert result is None

    def test_global_200_short_circuits_eu(self):
        """When global returns 200, EU should never be tried."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("auto_apply.httpx.get", return_value=mock_resp) as mock_get:
            result = extract_greenhouse_api_key("test")
        assert result == "__no_key_needed__"
        # Only one call made (global endpoint)
        mock_get.assert_called_once()


# ===================================================================
# submit_lever_api
# ===================================================================


class TestSubmitLeverApi:
    """Tests for submit_lever_api(personal, app, dry_run)."""

    @pytest.fixture
    def personal(self):
        return {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "+49123456789",
            "linkedin": "https://linkedin.com/in/johndoe",
            "github": "https://github.com/johndoe",
        }

    @pytest.fixture
    def lever_app(self, tmp_path):
        """Create an app dict with real temp files."""
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF-1.4 fake cv")
        cl_md = tmp_path / "cover.md"
        cl_md.write_text("---\ntitle: Cover\n---\n\nDear Hiring Manager,\n\n**Bold text** here.")
        return {
            "company": "Mistral",
            "role": "Engineer",
            "url": "https://jobs.lever.co/mistral/abc-123",
            "cv": str(cv.relative_to(tmp_path)),
            "cover_letter": str((tmp_path / "cover.pdf").relative_to(tmp_path)),
        }

    def test_dry_run_returns_ok(self, personal, lever_app, tmp_path):
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            result = submit_lever_api(personal, lever_app, dry_run=True)
        assert result["ok"] is True
        assert result["method"] == "lever_api"
        assert result["detail"] == "dry run"

    def test_successful_submission(self, personal, lever_app, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "applicationId": "app-42"}

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp),
        ):
            result = submit_lever_api(personal, lever_app, dry_run=False)
        assert result["ok"] is True
        assert "app-42" in result["detail"]

    def test_api_error_response(self, personal, lever_app, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"ok": False, "error": "invalid posting"}
        mock_resp.text = "invalid posting"

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp),
        ):
            result = submit_lever_api(personal, lever_app, dry_run=False)
        assert result["ok"] is False
        assert result["method"] == "lever_api"

    def test_network_exception(self, personal, lever_app, tmp_path):
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", side_effect=Exception("connection refused")),
        ):
            result = submit_lever_api(personal, lever_app, dry_run=False)
        assert result["ok"] is False
        assert "connection refused" in result["detail"]

    def test_cover_letter_without_frontmatter(self, personal, tmp_path):
        """Cover letter without --- delimiter uses full text."""
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF-1.4 fake")
        cl_md = tmp_path / "cover.md"
        cl_md.write_text("Dear Hiring Manager,\n\nI am applying.")
        app = {
            "company": "Co",
            "role": "Dev",
            "url": "https://jobs.lever.co/co/xyz-123",
            "cv": str(cv.relative_to(tmp_path)),
            "cover_letter": str((tmp_path / "cover.pdf").relative_to(tmp_path)),
        }
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            result = submit_lever_api(personal, app, dry_run=True)
        assert result["ok"] is True


# ===================================================================
# submit_greenhouse_api
# ===================================================================


class TestSubmitGreenhouseApi:
    """Tests for submit_greenhouse_api(personal, app, dry_run)."""

    @pytest.fixture
    def personal(self):
        return {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "phone": "+49987654321",
            "location": "Berlin, Germany",
        }

    @pytest.fixture
    def gh_app(self, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF-1.4 fake cv")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF-1.4 fake cl")
        return {
            "company": "Grafana",
            "role": "SRE",
            "url": "https://job-boards.greenhouse.io/grafanalabs/jobs/123456",
            "cv": str(cv.relative_to(tmp_path)),
            "cover_letter": str(cl.relative_to(tmp_path)),
        }

    def test_dry_run_returns_ok(self, personal, gh_app, tmp_path):
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            result = submit_greenhouse_api(personal, gh_app, dry_run=True)
        assert result["ok"] is True
        assert result["method"] == "greenhouse_api"
        assert result["detail"] == "dry run"

    def test_successful_submission_200(self, personal, gh_app, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp),
        ):
            result = submit_greenhouse_api(personal, gh_app, dry_run=False)
        assert result["ok"] is True
        assert "200" in result["detail"]

    def test_successful_submission_201(self, personal, gh_app, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 201

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp),
        ):
            result = submit_greenhouse_api(personal, gh_app, dry_run=False)
        assert result["ok"] is True

    def test_api_error_response(self, personal, gh_app, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = "Validation failed"

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp),
        ):
            result = submit_greenhouse_api(personal, gh_app, dry_run=False)
        assert result["ok"] is False
        assert "Validation failed" in result["detail"]

    def test_network_exception(self, personal, gh_app, tmp_path):
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", side_effect=Exception("timeout")),
        ):
            result = submit_greenhouse_api(personal, gh_app, dry_run=False)
        assert result["ok"] is False
        assert "timeout" in result["detail"]

    def test_eu_endpoint_used_for_eu_url(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF-1.4")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF-1.4")
        app = {
            "company": "JetBrains",
            "role": "Dev",
            "url": "https://job-boards.eu.greenhouse.io/jetbrains/jobs/789",
            "cv": str(cv.relative_to(tmp_path)),
            "cover_letter": str(cl.relative_to(tmp_path)),
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp) as mock_post,
        ):
            submit_greenhouse_api(personal, app, dry_run=False)
        # Verify EU endpoint was used
        call_url = mock_post.call_args[0][0]
        from urllib.parse import urlparse

        assert "eu.greenhouse.io" in urlparse(call_url).hostname  # noqa: S101

    def test_missing_files_still_posts(self, personal, tmp_path):
        """When CV/CL files don't exist, no files attached but POST still sent."""
        app = {
            "company": "NoCo",
            "role": "Dev",
            "url": "https://job-boards.greenhouse.io/noco/jobs/999",
            "cv": "nonexistent_cv.pdf",
            "cover_letter": "nonexistent_cl.pdf",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.httpx.post", return_value=mock_resp) as mock_post,
        ):
            result = submit_greenhouse_api(personal, app, dry_run=False)
        assert result["ok"] is True
        # files dict should be empty (no files attached)
        _, kwargs = mock_post.call_args
        assert kwargs["files"] == {}


# ===================================================================
# confirm_and_submit_browser
# ===================================================================


class TestConfirmAndSubmitBrowser:
    """Tests for confirm_and_submit_browser(page, company, role, dry_run)."""

    def test_dry_run_takes_screenshot_returns_true(self):
        page = MagicMock()
        with patch("auto_apply.screenshot") as mock_ss:
            result = confirm_and_submit_browser(page, "Acme Corp", "Engineer", dry_run=True)
        assert result is True
        mock_ss.assert_called_once()
        # Slug should strip spaces and dots
        assert "acme" in mock_ss.call_args[0][1].lower()

    def test_submit_on_enter(self):
        page = MagicMock()
        submit_btn = MagicMock()
        submit_btn.count.return_value = 1
        page.locator.return_value = submit_btn

        with (
            patch("auto_apply.screenshot"),
            patch("builtins.input", return_value=""),
            patch("auto_apply.time"),
        ):
            result = confirm_and_submit_browser(page, "Acme", "Dev", dry_run=False)
        assert result is True
        submit_btn.first.click.assert_called_once()

    def test_skip_returns_false(self):
        page = MagicMock()

        with patch("auto_apply.screenshot"), patch("builtins.input", return_value="s"):
            result = confirm_and_submit_browser(page, "Acme", "Dev", dry_run=False)
        assert result is False

    def test_quit_exits(self):
        page = MagicMock()

        with (
            patch("auto_apply.screenshot"),
            patch("builtins.input", return_value="q"),
            pytest.raises(SystemExit),
        ):
            confirm_and_submit_browser(page, "Acme", "Dev", dry_run=False)

    def test_no_submit_button_asks_manual(self):
        page = MagicMock()
        submit_btn = MagicMock()
        submit_btn.count.return_value = 0
        page.locator.return_value = submit_btn

        with patch("auto_apply.screenshot"), patch("builtins.input", side_effect=["", ""]):
            result = confirm_and_submit_browser(page, "Acme", "Dev", dry_run=False)
        assert result is True

    def test_slug_strips_dots_and_spaces(self):
        page = MagicMock()
        with patch("auto_apply.screenshot") as mock_ss:
            confirm_and_submit_browser(page, "Acme Corp.", "Dev", dry_run=True)
        name_arg = mock_ss.call_args[0][1]
        assert "." not in name_arg
        assert " " not in name_arg


# ===================================================================
# process_application
# ===================================================================


class TestProcessApplication:
    """Tests for process_application(page, personal, app, dry_run, browser_only)."""

    @pytest.fixture
    def personal(self):
        return {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "+49000000000",
        }

    def test_returns_false_when_cv_missing(self, personal, tmp_path):
        app = {
            "company": "Co",
            "role": "Dev",
            "url": "https://example.com/jobs/1",
            "cv": "missing.pdf",
            "cover_letter": "also_missing.pdf",
        }
        page = MagicMock()
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            result = process_application(page, personal, app, dry_run=True, browser_only=False)
        assert result is False

    def test_returns_false_when_cover_letter_missing(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        app = {
            "company": "Co",
            "role": "Dev",
            "url": "https://example.com/jobs/1",
            "cv": "cv.pdf",
            "cover_letter": "missing_cl.pdf",
        }
        page = MagicMock()
        with patch("auto_apply.PROJECT_ROOT", tmp_path):
            result = process_application(page, personal, app, dry_run=True, browser_only=False)
        assert result is False

    def test_lever_api_success_skips_browser(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "Mistral",
            "role": "Engineer",
            "url": "https://jobs.lever.co/mistral/abc-123",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.submit_lever_api", return_value={"ok": True, "method": "lever_api"}),
            patch("auto_apply.update_csv_status"),
        ):
            result = process_application(page, personal, app, dry_run=False, browser_only=False)
        assert result is True

    def test_lever_api_failure_falls_back_to_browser(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "Mistral",
            "role": "Engineer",
            "url": "https://jobs.lever.co/mistral/abc-123",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        mock_fill = MagicMock(return_value=True)
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.submit_lever_api", return_value={"ok": False, "detail": "fail"}),
            patch.dict("auto_apply.BROWSER_HANDLERS", {"lever": mock_fill}),
            patch("auto_apply.confirm_and_submit_browser", return_value=True),
            patch("auto_apply.update_csv_status"),
        ):
            result = process_application(page, personal, app, dry_run=False, browser_only=False)
        assert result is True
        mock_fill.assert_called_once()

    def test_browser_only_skips_api(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "Mistral",
            "role": "Engineer",
            "url": "https://jobs.lever.co/mistral/abc-123",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        mock_fill = MagicMock(return_value=True)
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.submit_lever_api") as mock_api,
            patch.dict("auto_apply.BROWSER_HANDLERS", {"lever": mock_fill}),
            patch("auto_apply.confirm_and_submit_browser", return_value=True),
            patch("auto_apply.update_csv_status"),
        ):
            result = process_application(page, personal, app, dry_run=False, browser_only=True)
        assert result is True
        mock_api.assert_not_called()

    def test_greenhouse_api_success(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "Grafana",
            "role": "SRE",
            "url": "https://job-boards.greenhouse.io/grafanalabs/jobs/123",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch(
                "auto_apply.submit_greenhouse_api",
                return_value={"ok": True, "method": "greenhouse_api"},
            ),
            patch("auto_apply.update_csv_status"),
        ):
            result = process_application(page, personal, app, dry_run=False, browser_only=False)
        assert result is True

    def test_browser_handler_exception_returns_false(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "Unknown Co",
            "role": "Dev",
            "url": "https://unknown-company.com/careers/dev",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.fill_generic_browser", side_effect=Exception("form broken")),
            patch("auto_apply.screenshot"),
        ):
            result = process_application(page, personal, app, dry_run=False, browser_only=False)
        assert result is False

    def test_dry_run_does_not_update_csv(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "Mistral",
            "role": "Engineer",
            "url": "https://jobs.lever.co/mistral/abc-123",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        with (
            patch("auto_apply.PROJECT_ROOT", tmp_path),
            patch("auto_apply.submit_lever_api", return_value={"ok": True, "method": "lever_api"}),
            patch("auto_apply.update_csv_status") as mock_csv,
        ):
            process_application(page, personal, app, dry_run=True, browser_only=False)
        mock_csv.assert_not_called()

    def test_linkedin_opens_url_dry_run(self, personal, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cl = tmp_path / "cover.pdf"
        cl.write_bytes(b"%PDF")
        app = {
            "company": "LinkedIn Co",
            "role": "PM",
            "url": "https://www.linkedin.com/jobs/view/123456",
            "cv": "cv.pdf",
            "cover_letter": "cover.pdf",
        }
        page = MagicMock()
        with patch("auto_apply.PROJECT_ROOT", tmp_path), patch("auto_apply.time"):
            result = process_application(page, personal, app, dry_run=True, browser_only=False)
        assert result is True
        page.goto.assert_called_once()


# ===================================================================
# BROWSER_HANDLERS mapping
# ===================================================================


class TestBrowserHandlers:
    """Tests for the BROWSER_HANDLERS dict."""

    def test_all_expected_platforms_present(self):
        expected = {"ashby", "lever", "greenhouse", "company", "remotely", "unknown"}
        assert set(BROWSER_HANDLERS.keys()) == expected

    def test_handlers_are_callable(self):
        for platform, handler in BROWSER_HANDLERS.items():
            assert callable(handler), f"Handler for {platform} is not callable"

    def test_company_and_remotely_use_generic(self):
        from auto_apply import fill_generic_browser

        assert BROWSER_HANDLERS["company"] is fill_generic_browser
        assert BROWSER_HANDLERS["remotely"] is fill_generic_browser
        assert BROWSER_HANDLERS["unknown"] is fill_generic_browser
