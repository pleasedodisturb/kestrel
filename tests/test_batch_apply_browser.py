"""Tests for tools/batch_apply_browser.py — browser-based job application automation.

Tests cover:
- Platform detection
- Cover letter text extraction
- Form filling logic (Lever, Greenhouse, Ashby)
- Custom question handlers
- Source field filling
- Submit/CAPTCHA detection
- Helper functions (_fill_field_by_label, _click_radio_by_label, _select_dropdown_option)
- process_application
- _run_test_url
- fill_custom_questions (company-specific)

All browser interactions are mocked — no real Playwright or network calls.
"""

# Import the module under test
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# G-1477: import batch_apply_browser as a bare module off tools/, matching
# tests/conftest.py and every other tool test in this repo. The package-
# qualified `tools.` form does not resolve in the Python 3.11 CI environment:
# tools/ has no __init__.py, so it is only a namespace *portion*, and a
# regular `tools` package anywhere on sys.path silently shadows it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

# batch_apply_browser loads config/personal.yaml at import time.
# Skip the entire module when the config file is absent (CI, fresh clones).
_personal_config = Path(__file__).resolve().parent.parent / "config" / "personal.yaml"
if not _personal_config.exists():
    pytest.skip(
        "config/personal.yaml not found — skipping batch_apply_browser tests",
        allow_module_level=True,
    )

from batch_apply_browser import (
    PERSONAL,
    detect_platform,
    get_cover_letter_text,
)

# ---------------------------------------------------------------------------
# detect_platform
# ---------------------------------------------------------------------------


class TestDetectPlatform:
    def test_ashby(self):
        assert detect_platform("https://jobs.ashbyhq.com/company/abc123") == "ashby"

    def test_lever(self):
        assert detect_platform("https://jobs.lever.co/nimbusworks/abc123") == "lever"

    def test_lever_eu(self):
        assert detect_platform("https://jobs.eu.lever.co/tradelink/abc123") == "lever"

    def test_greenhouse(self):
        assert detect_platform("https://job-boards.greenhouse.io/company/jobs/123") == "greenhouse"

    def test_greenhouse_eu(self):
        assert (
            detect_platform("https://job-boards.eu.greenhouse.io/company/jobs/123") == "greenhouse"
        )

    def test_linkedin(self):
        assert detect_platform("https://www.linkedin.com/jobs/view/12345") == "linkedin"

    def test_workable(self):
        assert detect_platform("https://apply.workable.com/company/j/abc123") == "workable"

    def test_unknown(self):
        assert detect_platform("https://careers.example.com/apply") == "other"

    def test_empty_string(self):
        assert detect_platform("") == "other"


# ---------------------------------------------------------------------------
# get_cover_letter_text
# ---------------------------------------------------------------------------


class TestGetCoverLetterText:
    def test_extracts_body_after_frontmatter(self, tmp_path):
        cl = tmp_path / "cover-letter.md"
        cl.write_text(
            "Jane Doe\n"
            "email@example.com\n"
            "\n"
            "March 27, 2026\n"
            "\n"
            "**Re: Some Role**\n"
            "\n"
            "---\n"
            "\n"
            "This is the body.\n"
            "\n"
            "Second paragraph.\n"
            "\n"
            "Test User\n"
        )
        result = get_cover_letter_text(cl)
        assert "This is the body." in result
        assert "Second paragraph." in result
        assert "Test User" in result

    def test_strips_bold_markdown(self, tmp_path):
        cl = tmp_path / "cover-letter.md"
        cl.write_text(
            "Name\nemail\n\nDate\n\n**Re: Role**\n\n---\n\n"
            "I have **strong skills** in **everything**.\n"
        )
        result = get_cover_letter_text(cl)
        assert "**" not in result
        assert "strong skills" in result
        assert "everything" in result

    def test_returns_empty_for_missing_file(self):
        result = get_cover_letter_text(Path("/nonexistent/path/cover.md"))
        assert result == ""

    def test_handles_no_frontmatter_delimiter(self, tmp_path):
        cl = tmp_path / "cover-letter.md"
        cl.write_text("Just some text without any frontmatter delimiters.")
        result = get_cover_letter_text(cl)
        assert "Just some text" in result

    def test_handles_empty_file(self, tmp_path):
        cl = tmp_path / "cover-letter.md"
        cl.write_text("")
        result = get_cover_letter_text(cl)
        assert result == ""


# ---------------------------------------------------------------------------
# PERSONAL constants
# ---------------------------------------------------------------------------


class TestPersonalConstants:
    """Verify PERSONAL dict has all required fields."""

    def test_has_required_fields(self):
        required = [
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "linkedin",
            "github",
            "location",
        ]
        for field in required:
            assert field in PERSONAL, f"Missing field: {field}"

    def test_email_format(self):
        assert "@" in PERSONAL["email"]

    def test_phone_format(self):
        assert PERSONAL["phone"].startswith("+")

    def test_linkedin_is_url(self):
        assert PERSONAL["linkedin"].startswith("https://")

    def test_github_is_url(self):
        assert PERSONAL["github"].startswith("https://")


# ---------------------------------------------------------------------------
# Mock helpers for async Playwright tests
# ---------------------------------------------------------------------------


def _make_empty_locator():
    """Create a mock locator that reports count=0 (field not found)."""
    loc = AsyncMock()
    loc.count = AsyncMock(return_value=0)
    loc.first = AsyncMock()
    loc.first.count = AsyncMock(return_value=0)
    loc.first.fill = AsyncMock()
    loc.first.click = AsyncMock()
    loc.first.set_input_files = AsyncMock()
    loc.first.get_attribute = AsyncMock(return_value=None)
    loc.first.evaluate = AsyncMock(return_value="input")
    loc.first.select_option = AsyncMock()
    loc.nth = MagicMock(return_value=loc.first)
    loc.locator = MagicMock(return_value=_make_empty_locator_inner())
    # Direct fill/click on loc itself (some source code calls loc.fill() directly)
    loc.fill = AsyncMock()
    loc.click = AsyncMock()
    loc.set_input_files = AsyncMock()
    loc.select_option = AsyncMock()
    loc.get_attribute = AsyncMock(return_value=None)
    loc.evaluate = AsyncMock(return_value="input")
    return loc


def _make_empty_locator_inner():
    """Inner empty locator to avoid infinite recursion in locator.locator()."""
    loc = AsyncMock()
    loc.count = AsyncMock(return_value=0)
    loc.first = AsyncMock()
    loc.first.count = AsyncMock(return_value=0)
    loc.first.fill = AsyncMock()
    loc.first.click = AsyncMock()
    loc.first.set_input_files = AsyncMock()
    loc.first.get_attribute = AsyncMock(return_value=None)
    loc.first.evaluate = AsyncMock(return_value="input")
    loc.first.select_option = AsyncMock()
    loc.nth = MagicMock(return_value=loc.first)
    return loc


def _make_found_locator(value=None, tag="input"):
    """Create a mock locator that reports count=1 (field found)."""
    loc = AsyncMock()
    loc.count = AsyncMock(return_value=1)
    loc.first = AsyncMock()
    loc.first.count = AsyncMock(return_value=1)
    loc.first.fill = AsyncMock()
    loc.first.click = AsyncMock()
    loc.first.set_input_files = AsyncMock()
    loc.first.get_attribute = AsyncMock(return_value=value)
    loc.first.evaluate = AsyncMock(return_value=tag)
    loc.first.select_option = AsyncMock()
    loc.first.locator = MagicMock(return_value=_make_empty_locator())
    loc.nth = MagicMock(return_value=loc.first)
    loc.locator = MagicMock(return_value=_make_empty_locator())
    # Direct fill/click on loc itself
    loc.fill = AsyncMock()
    loc.click = AsyncMock()
    loc.set_input_files = AsyncMock()
    loc.select_option = AsyncMock()
    loc.get_attribute = AsyncMock(return_value=value)
    loc.evaluate = AsyncMock(return_value=tag)
    return loc


def make_page_with_fields(field_map=None, url="https://jobs.lever.co/company/abc123/apply"):
    """Create a mock Playwright page with a smart locator factory.

    Args:
        field_map: dict mapping substring patterns to found locators.
            Keys are substrings to match in CSS selectors.
            Values can be True (auto-create found locator) or a pre-built locator.
        url: the page URL.
    """
    if field_map is None:
        field_map = {}

    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.screenshot = AsyncMock()
    page.url = url
    page.title = AsyncMock(return_value="Job Application")
    page.evaluate = AsyncMock(return_value=None)
    page.inner_text = AsyncMock(return_value="")

    # Build resolved field_map (replace True with actual locators)
    resolved = {}
    for key, val in field_map.items():
        if val is True:
            resolved[key] = _make_found_locator()
        else:
            resolved[key] = val

    def locator_factory(sel):
        for key, loc in resolved.items():
            if key in sel:
                return loc
        return _make_empty_locator()

    page.locator = MagicMock(side_effect=locator_factory)
    page.get_by_text = MagicMock(return_value=_make_empty_locator())

    return page


# ---------------------------------------------------------------------------
# fill_source_field
# ---------------------------------------------------------------------------


class TestFillSourceField:
    @pytest.mark.asyncio
    async def test_fills_text_input_by_name(self):
        from batch_apply_browser import fill_source_field

        found_loc = _make_found_locator(value="text", tag="input")
        page = make_page_with_fields({'name*="source"': found_loc})

        await fill_source_field(page)
        found_loc.first.fill.assert_called_with("Job board")

    @pytest.mark.asyncio
    async def test_fills_select_by_name(self):
        from batch_apply_browser import fill_source_field

        select_loc = _make_found_locator(tag="select")
        page = make_page_with_fields({'name*="source"': select_loc})

        await fill_source_field(page)
        select_loc.first.select_option.assert_called()

    @pytest.mark.asyncio
    async def test_no_source_field_doesnt_crash(self):
        from batch_apply_browser import fill_source_field

        page = make_page_with_fields({})
        await fill_source_field(page)  # Should not raise

    @pytest.mark.asyncio
    async def test_fills_via_label_for_attr(self):
        from batch_apply_browser import fill_source_field

        label_loc = _make_found_locator()
        label_loc.first.get_attribute = AsyncMock(return_value="source-input")

        target_loc = _make_found_locator(tag="input")

        page = make_page_with_fields(
            {
                'label:has-text("How did you hear': label_loc,
                "#source-input": target_loc,
            }
        )

        await fill_source_field(page)
        target_loc.first.fill.assert_called_with("Job board")


# ---------------------------------------------------------------------------
# fill_lever
# ---------------------------------------------------------------------------


class TestFillLever:
    @pytest.mark.asyncio
    async def test_navigates_to_apply_url(self):
        from batch_apply_browser import fill_lever

        page = make_page_with_fields({})
        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_lever(page, app, dry_run=False)

        page.goto.assert_called_once()
        call_url = page.goto.call_args[0][0]
        assert call_url.endswith("/apply")

    @pytest.mark.asyncio
    async def test_uploads_cv_first(self):
        from batch_apply_browser import fill_lever

        file_loc = _make_found_locator()
        page = make_page_with_fields({'type="file"': file_loc})

        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_lever(page, app, dry_run=False)

        file_loc.first.set_input_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_fills_name_email_phone(self):
        from batch_apply_browser import fill_lever

        name_loc = _make_found_locator()
        email_loc = _make_found_locator()
        phone_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'name="name"': name_loc,
                'name="email"': email_loc,
                'name="phone"': phone_loc,
            }
        )

        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_lever(page, app, dry_run=False)

        # name_input.fill("") then name_input.fill(PERSONAL["full_name"])
        # The source calls loc.fill() directly (not loc.first.fill())
        assert name_loc.fill.call_count >= 1
        assert email_loc.fill.call_count >= 1
        assert phone_loc.fill.call_count >= 1

    @pytest.mark.asyncio
    async def test_fills_linkedin_github(self):
        from batch_apply_browser import fill_lever

        linkedin_loc = _make_found_locator()
        github_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'name="urls[LinkedIn]"': linkedin_loc,
                'name="urls[GitHub]"': github_loc,
            }
        )

        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_lever(page, app, dry_run=False)

        linkedin_loc.first.fill.assert_called_with(PERSONAL["linkedin"])
        github_loc.first.fill.assert_called_with(PERSONAL["github"])

    @pytest.mark.asyncio
    async def test_returns_true(self):
        from batch_apply_browser import fill_lever

        page = make_page_with_fields({})
        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                result = await fill_lever(page, app, dry_run=False)

        assert result is True


# ---------------------------------------------------------------------------
# fill_greenhouse
# ---------------------------------------------------------------------------


class TestFillGreenhouse:
    @pytest.mark.asyncio
    async def test_clicks_apply_button(self):
        from batch_apply_browser import fill_greenhouse

        apply_loc = _make_found_locator()
        page = make_page_with_fields(
            {
                "Apply": apply_loc,
            }
        )

        app = {
            "url": "https://job-boards.greenhouse.io/company/jobs/123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_greenhouse(page, app, dry_run=False)

        apply_loc.first.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_fills_first_last_name_email_phone(self):
        from batch_apply_browser import fill_greenhouse

        first_loc = _make_found_locator()
        last_loc = _make_found_locator()
        email_loc = _make_found_locator()
        phone_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'id*="first_name"': first_loc,
                'id*="last_name"': last_loc,
                'id*="email"': email_loc,
                'id*="phone"': phone_loc,
            }
        )

        app = {
            "url": "https://job-boards.greenhouse.io/company/jobs/123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_greenhouse(page, app, dry_run=False)

        first_loc.first.fill.assert_called_with(PERSONAL["first_name"])
        last_loc.first.fill.assert_called_with(PERSONAL["last_name"])
        email_loc.first.fill.assert_called_with(PERSONAL["email"])
        phone_loc.first.fill.assert_called_with(PERSONAL["phone"])

    @pytest.mark.asyncio
    async def test_uploads_resume(self):
        from batch_apply_browser import fill_greenhouse

        # For greenhouse, resume_input = page.locator('input[type="file"]').first
        # then await resume_input.count() > 0 — but .first is an attribute of the
        # locator returned by page.locator(). The source calls .first then .count()
        # on the .first element AND also .set_input_files on it.
        file_loc = _make_found_locator()
        # .first needs count (source: resume_input = loc.first, await resume_input.count())
        file_loc.first.count = AsyncMock(return_value=1)

        page = make_page_with_fields(
            {
                'type="file"': file_loc,
            }
        )

        app = {
            "url": "https://job-boards.greenhouse.io/company/jobs/123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_greenhouse(page, app, dry_run=False)

        # resume_input is file_loc.first, then set_input_files called on it
        file_loc.first.set_input_files.assert_called()

    @pytest.mark.asyncio
    async def test_returns_true(self):
        from batch_apply_browser import fill_greenhouse

        page = make_page_with_fields({})
        app = {
            "url": "https://job-boards.greenhouse.io/company/jobs/123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                result = await fill_greenhouse(page, app, dry_run=False)

        assert result is True


# ---------------------------------------------------------------------------
# fill_ashby
# ---------------------------------------------------------------------------


class TestFillAshby:
    @pytest.mark.asyncio
    async def test_fills_system_fields(self):
        from batch_apply_browser import fill_ashby

        name_loc = _make_found_locator()
        email_loc = _make_found_locator()
        phone_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'name="name"': name_loc,
                'name="email"': email_loc,
                'name="phone"': phone_loc,
            },
            url="https://jobs.ashbyhq.com/company/abc123",
        )

        app = {
            "url": "https://jobs.ashbyhq.com/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_ashby(page, app, dry_run=False)

        name_loc.first.fill.assert_called_with(PERSONAL["full_name"])
        email_loc.first.fill.assert_called_with(PERSONAL["email"])
        phone_loc.first.fill.assert_called_with(PERSONAL["phone"])

    @pytest.mark.asyncio
    async def test_clicks_apply_button(self):
        from batch_apply_browser import fill_ashby

        apply_loc = _make_found_locator()
        page = make_page_with_fields(
            {
                "Apply": apply_loc,
            },
            url="https://jobs.ashbyhq.com/company/abc123",
        )

        app = {
            "url": "https://jobs.ashbyhq.com/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_ashby(page, app, dry_run=False)

        apply_loc.first.click.assert_called()

    @pytest.mark.asyncio
    async def test_fills_linkedin(self):
        from batch_apply_browser import fill_ashby

        linkedin_loc = _make_found_locator()
        page = make_page_with_fields(
            {
                "linkedin": linkedin_loc,
            },
            url="https://jobs.ashbyhq.com/company/abc123",
        )

        app = {
            "url": "https://jobs.ashbyhq.com/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                await fill_ashby(page, app, dry_run=False)

        linkedin_loc.first.fill.assert_called_with(PERSONAL["linkedin"])

    @pytest.mark.asyncio
    async def test_returns_true(self):
        from batch_apply_browser import fill_ashby

        page = make_page_with_fields({}, url="https://jobs.ashbyhq.com/company/abc123")
        app = {
            "url": "https://jobs.ashbyhq.com/company/abc123",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                result = await fill_ashby(page, app, dry_run=False)

        assert result is True


# ---------------------------------------------------------------------------
# _fill_field_by_label
# ---------------------------------------------------------------------------


class TestFillFieldByLabel:
    @pytest.mark.asyncio
    async def test_fills_via_for_attribute(self):
        from batch_apply_browser import _fill_field_by_label

        label_loc = _make_found_locator()
        label_loc.first.get_attribute = AsyncMock(return_value="my-input")

        target_loc = _make_found_locator(tag="input")

        page = make_page_with_fields(
            {
                'label:has-text("My Label")': label_loc,
                "#my-input": target_loc,
            }
        )

        result = await _fill_field_by_label(page, "My Label", "my value")
        assert result is True
        target_loc.first.fill.assert_called_with("my value")

    @pytest.mark.asyncio
    async def test_fills_select_via_for_attribute(self):
        from batch_apply_browser import _fill_field_by_label

        label_loc = _make_found_locator()
        label_loc.first.get_attribute = AsyncMock(return_value="my-select")

        target_loc = _make_found_locator(tag="select")

        page = make_page_with_fields(
            {
                'label:has-text("Country")': label_loc,
                "#my-select": target_loc,
            }
        )

        result = await _fill_field_by_label(page, "Country", "Germany")
        assert result is True
        target_loc.first.select_option.assert_called_with(label="Germany")

    @pytest.mark.asyncio
    async def test_fills_via_sibling_fallback(self):
        from batch_apply_browser import _fill_field_by_label

        label_loc = _make_found_locator()
        label_loc.first.get_attribute = AsyncMock(return_value=None)  # No 'for' attr

        sibling_loc = _make_found_locator(tag="textarea")
        label_loc.first.locator = MagicMock(return_value=sibling_loc)

        page = make_page_with_fields(
            {
                'label:has-text("Description")': label_loc,
            }
        )

        result = await _fill_field_by_label(page, "Description", "some text")
        assert result is True
        sibling_loc.first.fill.assert_called_with("some text")

    @pytest.mark.asyncio
    async def test_fills_via_aria_label_fallback(self):
        from batch_apply_browser import _fill_field_by_label

        aria_loc = _make_found_locator(tag="input")
        page = make_page_with_fields(
            {
                'aria-label*="Email"': aria_loc,
            }
        )

        result = await _fill_field_by_label(page, "Email", "test@example.com")
        assert result is True
        aria_loc.first.fill.assert_called_with("test@example.com")

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        from batch_apply_browser import _fill_field_by_label

        page = make_page_with_fields({})

        result = await _fill_field_by_label(page, "Nonexistent", "value")
        assert result is False

    @pytest.mark.asyncio
    async def test_exact_match_mode(self):
        from batch_apply_browser import _fill_field_by_label

        label_loc = _make_found_locator()
        label_loc.first.get_attribute = AsyncMock(return_value="exact-field")

        target_loc = _make_found_locator(tag="input")

        page = make_page_with_fields(
            {
                'label:text-is("Exact Label")': label_loc,
                "#exact-field": target_loc,
            }
        )

        result = await _fill_field_by_label(page, "Exact Label", "val", exact=True)
        assert result is True
        target_loc.first.fill.assert_called_with("val")


# ---------------------------------------------------------------------------
# _click_radio_by_label
# ---------------------------------------------------------------------------


class TestClickRadioByLabel:
    @pytest.mark.asyncio
    async def test_clicks_standard_radio(self):
        from batch_apply_browser import _click_radio_by_label

        radio_loc = _make_found_locator()
        page = make_page_with_fields(
            {
                'label:has-text("Yes")': radio_loc,
            }
        )

        result = await _click_radio_by_label(page, "Yes")
        assert result is True
        radio_loc.first.click.assert_called()

    @pytest.mark.asyncio
    async def test_clicks_via_get_by_text_fallback(self):
        from batch_apply_browser import _click_radio_by_label

        text_loc = _make_found_locator()
        page = make_page_with_fields({})
        page.get_by_text = MagicMock(return_value=text_loc)

        result = await _click_radio_by_label(page, "Agree to terms")
        assert result is True
        text_loc.first.click.assert_called()

    @pytest.mark.asyncio
    async def test_clicks_via_js_fallback(self):
        from batch_apply_browser import _click_radio_by_label

        page = make_page_with_fields({})
        page.get_by_text = MagicMock(return_value=_make_empty_locator())
        page.evaluate = AsyncMock(return_value=True)

        result = await _click_radio_by_label(page, "Some Option")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_radio(self):
        from batch_apply_browser import _click_radio_by_label

        page = make_page_with_fields({})
        page.get_by_text = MagicMock(return_value=_make_empty_locator())
        page.evaluate = AsyncMock(return_value=False)

        result = await _click_radio_by_label(page, "Nonexistent Option")
        assert result is False


# ---------------------------------------------------------------------------
# _select_dropdown_option
# ---------------------------------------------------------------------------


class TestSelectDropdownOption:
    @pytest.mark.asyncio
    async def test_selects_native_dropdown(self):
        from batch_apply_browser import _select_dropdown_option

        label_loc = _make_found_locator()
        parent_loc = AsyncMock()
        select_loc = _make_found_locator(tag="select")

        parent_loc.locator = MagicMock(return_value=select_loc)
        label_loc.first.locator = MagicMock(return_value=parent_loc)

        page = make_page_with_fields(
            {
                'label:has-text("Country")': label_loc,
            }
        )

        result = await _select_dropdown_option(page, "Country", "Germany")
        assert result is True
        select_loc.first.select_option.assert_called_with(label="Germany")

    @pytest.mark.asyncio
    async def test_clicks_custom_dropdown_option(self):
        from batch_apply_browser import _select_dropdown_option

        label_loc = _make_found_locator()
        parent_loc = AsyncMock()

        # Custom dropdown (button, not select)
        button_loc = _make_found_locator(tag="button")
        parent_loc.locator = MagicMock(return_value=button_loc)
        label_loc.first.locator = MagicMock(return_value=parent_loc)

        option_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'label:has-text("Type")': label_loc,
                'role="option"': option_loc,
            }
        )

        result = await _select_dropdown_option(page, "Type", "Full-time")
        assert result is True
        button_loc.first.click.assert_called()
        option_loc.first.click.assert_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_label(self):
        from batch_apply_browser import _select_dropdown_option

        page = make_page_with_fields({})

        result = await _select_dropdown_option(page, "Nonexistent", "Option")
        assert result is False

    @pytest.mark.asyncio
    async def test_falls_back_to_div_has_text(self):
        from batch_apply_browser import _select_dropdown_option

        # First label:has-text returns empty, then div:has-text returns found
        div_loc = _make_found_locator()
        parent_loc = AsyncMock()
        select_loc = _make_found_locator(tag="select")
        parent_loc.locator = MagicMock(return_value=select_loc)
        div_loc.first.locator = MagicMock(return_value=parent_loc)

        page = make_page_with_fields(
            {
                'div:has-text("Region")': div_loc,
            }
        )

        result = await _select_dropdown_option(page, "Region", "Europe")
        assert result is True
        select_loc.first.select_option.assert_called_with(label="Europe")

    @pytest.mark.asyncio
    async def test_dispatches_portaled_combobox_when_no_label_match(self):
        """When neither label nor div matches but a global combobox trigger
        with matching aria-label exists, we still drive the portaled menu.

        This covers the portaled-menu Greenhouse pattern where the visible label
        isn't a <label> element and isn't a wrapping div either."""
        from batch_apply_browser import _select_dropdown_option

        trigger_loc = _make_found_locator(tag="button")
        option_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'button[aria-haspopup="listbox"]': trigger_loc,
                'role="option"': option_loc,
            }
        )

        result = await _select_dropdown_option(page, "Do you require visa sponsorship?", "No")
        assert result is True
        # Trigger was clicked to open the portaled listbox
        trigger_loc.first.click.assert_called()
        # Option was clicked AND a mousedown was dispatched (react-select pattern)
        option_loc.first.click.assert_called()
        option_loc.first.dispatch_event.assert_called_with("mousedown")

    @pytest.mark.asyncio
    async def test_portaled_fallback_when_inline_option_missing(self):
        """When the label is found and a button trigger exists near it but
        the inline-option lookup returns nothing, we fall through to the
        portaled-menu path so an option in document.body is still picked."""
        from batch_apply_browser import _select_dropdown_option

        label_loc = _make_found_locator()
        parent_loc = AsyncMock()
        # The inline trigger is a button (so the native-select branch is skipped).
        button_loc = _make_found_locator(tag="button")
        parent_loc.locator = MagicMock(return_value=button_loc)
        label_loc.first.locator = MagicMock(return_value=parent_loc)

        # Inline option lookup returns nothing — simulates a portaled menu
        # that's NOT inside the label's parent.
        empty_option_loc = _make_empty_locator()
        # But a page-scoped portaled option exists.
        portaled_option_loc = _make_found_locator()

        # Distinguish between inline and portaled selectors using has-text
        # on different keys: inline option selector contains the option text,
        # the portaled selector also does. We want the FIRST option lookup
        # (the inline one) to return empty and the SECOND (portaled) to find.
        # Easiest: have field_map return the empty locator for
        # 'role="option"' AND a different match for the portaled path?
        # Actually the inline lookup uses the same role="option" selector.
        # We side-step this by making the inline call return empty via a
        # counter-based factory.
        call_count = {"n": 0}

        def factory(sel):
            if 'role="option"' in sel:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return empty_option_loc
                return portaled_option_loc
            if 'label:has-text("Visa")' in sel:
                return label_loc
            return _make_empty_locator()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.locator = MagicMock(side_effect=factory)
        page.get_by_text = MagicMock(return_value=_make_empty_locator())

        result = await _select_dropdown_option(page, "Visa", "No")
        assert result is True
        button_loc.first.click.assert_called()
        portaled_option_loc.first.click.assert_called()


# ---------------------------------------------------------------------------
# _click_portaled_option and _select_portaled_combobox
# ---------------------------------------------------------------------------


class TestPortaledComboboxDispatch:
    """Cover the new portaled-React-combobox dispatch path (G-626)."""

    @pytest.mark.asyncio
    async def test_click_portaled_option_dispatches_mousedown_and_click(self):
        from batch_apply_browser import _click_portaled_option

        option_loc = _make_found_locator()
        page = make_page_with_fields({'role="option"': option_loc})

        result = await _click_portaled_option(page, "Yes")
        assert result is True
        option_loc.first.dispatch_event.assert_called_with("mousedown")
        option_loc.first.click.assert_called()

    @pytest.mark.asyncio
    async def test_click_portaled_option_survives_dispatch_failure(self):
        """If dispatch_event raises (older Playwright / weird mock), we still
        click. This is the safety net referenced in the docstring."""
        from batch_apply_browser import _click_portaled_option

        option_loc = _make_found_locator()
        option_loc.first.dispatch_event = AsyncMock(side_effect=RuntimeError("no dispatch"))
        page = make_page_with_fields({'role="option"': option_loc})

        result = await _click_portaled_option(page, "Yes")
        assert result is True
        option_loc.first.click.assert_called()

    @pytest.mark.asyncio
    async def test_click_portaled_option_returns_false_when_not_found(self):
        from batch_apply_browser import _click_portaled_option

        page = make_page_with_fields({})

        result = await _click_portaled_option(page, "Anything")
        assert result is False

    @pytest.mark.asyncio
    async def test_select_portaled_combobox_uses_aria_haspopup_trigger(self):
        """The portaled-menu pattern: <button aria-haspopup="listbox"> opens a
        portaled <div role="listbox"> in document.body."""
        from batch_apply_browser import _select_portaled_combobox

        trigger_loc = _make_found_locator(tag="button")
        option_loc = _make_found_locator()
        page = make_page_with_fields(
            {
                'button[aria-haspopup="listbox"]': trigger_loc,
                'role="option"': option_loc,
            }
        )

        result = await _select_portaled_combobox(page, "Are you open to relocation?", "Yes")
        assert result is True
        trigger_loc.first.click.assert_called()
        option_loc.first.click.assert_called()
        option_loc.first.dispatch_event.assert_called_with("mousedown")

    @pytest.mark.asyncio
    async def test_select_portaled_combobox_returns_false_with_no_trigger(self):
        from batch_apply_browser import _select_portaled_combobox

        page = make_page_with_fields({})
        # All selectors return empty — no combobox trigger anywhere.
        result = await _select_portaled_combobox(page, "Anything", "Value")
        assert result is False

    @pytest.mark.asyncio
    async def test_select_portaled_combobox_skips_failing_selectors(self):
        """Some Playwright selectors (e.g. :has() with certain inner exprs)
        may raise. We should swallow those and keep trying other patterns."""
        from batch_apply_browser import _select_portaled_combobox

        # First selectors raise; final selector finds the trigger.
        trigger_loc = _make_found_locator(tag="button")
        option_loc = _make_found_locator()

        def factory(sel):
            if "aria-label" in sel:
                # Simulate Playwright rejecting this selector
                raise ValueError("bad selector")
            if "aria-haspopup" in sel:
                return trigger_loc
            if 'role="option"' in sel:
                return option_loc
            return _make_empty_locator()

        page = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.locator = MagicMock(side_effect=factory)
        page.get_by_text = MagicMock(return_value=_make_empty_locator())

        result = await _select_portaled_combobox(page, "Label", "Value")
        assert result is True
        trigger_loc.first.click.assert_called()


# ---------------------------------------------------------------------------
# _fill_field_by_label falls through to portaled combobox
# ---------------------------------------------------------------------------


class TestFillFieldByLabelComboboxFallback:
    @pytest.mark.asyncio
    async def test_falls_through_to_combobox_when_no_sibling_input(self):
        """If the label is found but no input/textarea/select sibling exists,
        and the field is actually a portaled React combobox, the new fallback
        should drive it."""
        from batch_apply_browser import _fill_field_by_label

        label_loc = _make_found_locator()
        label_loc.first.get_attribute = AsyncMock(return_value=None)
        # Sibling lookup returns empty for every tag.
        label_loc.first.locator = MagicMock(return_value=_make_empty_locator())

        trigger_loc = _make_found_locator(tag="button")
        option_loc = _make_found_locator()

        page = make_page_with_fields(
            {
                'label:has-text("Visa sponsorship")': label_loc,
                'button[aria-haspopup="listbox"]': trigger_loc,
                'role="option"': option_loc,
            }
        )

        result = await _fill_field_by_label(page, "Visa sponsorship", "No")
        assert result is True
        trigger_loc.first.click.assert_called()
        option_loc.first.click.assert_called()


# ---------------------------------------------------------------------------
# Config-driven answer bank
# ---------------------------------------------------------------------------


class TestAnswerBank:
    """The answer bank + @-ref resolver that replaced the hardcoded essays."""

    def test_answer_bank_populated(self):
        from batch_apply_browser import ANSWERS

        assert "why_company" in ANSWERS
        assert len(ANSWERS["why_company"]) > 20

    def test_location_ref_seeded_from_personal(self):
        from batch_apply_browser import ANSWERS, PERSONAL

        assert ANSWERS["location"] == PERSONAL["location"]

    def test_resolve_answer_dereferences_ref(self):
        from batch_apply_browser import ANSWERS, _resolve_answer

        assert _resolve_answer("@why_company") == ANSWERS["why_company"]

    def test_resolve_answer_passes_through_literal(self):
        from batch_apply_browser import _resolve_answer

        assert _resolve_answer("Yes") == "Yes"

    def test_resolve_answer_unknown_ref_returns_empty(self):
        from batch_apply_browser import _resolve_answer

        assert _resolve_answer("@nonexistent_key") == ""

    def test_custom_questions_floor_present(self):
        # The fictional floor rules are always loaded so the fill mechanism is
        # testable regardless of the (gitignored) config contents.
        from batch_apply_browser import CUSTOM_QUESTIONS

        matches = {
            (r["match"].get("platform"), r["match"].get("slug_or_url")) for r in CUSTOM_QUESTIONS
        }
        assert ("greenhouse", "meridianlabs") in matches
        assert ("lever", "nimbusworks") in matches
        assert ("ashby", "novadynamics") in matches


# ---------------------------------------------------------------------------
# fill_custom_questions
# ---------------------------------------------------------------------------


class TestFillCustomQuestions:
    @pytest.mark.asyncio
    async def test_lever_rule_fills_location(self):
        from batch_apply_browser import fill_custom_questions

        page = make_page_with_fields({})
        app = {"url": "https://jobs.lever.co/nimbusworks/abc123", "slug": "nimbusworks"}

        with patch(
            "batch_apply_browser._fill_field_by_label",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fill:
            with patch(
                "batch_apply_browser._click_radio_by_label",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with patch("batch_apply_browser._select_dropdown_option", new_callable=AsyncMock):
                    await fill_custom_questions(page, app)
            # Should have tried to fill "Current location"
            labels = [c[0][1] for c in mock_fill.call_args_list if len(c[0]) >= 2]
            location_calls = [label for label in labels if "location" in label.lower()]
            assert len(location_calls) > 0

    @pytest.mark.asyncio
    async def test_greenhouse_rule_fills_fields(self):
        from batch_apply_browser import fill_custom_questions

        page = make_page_with_fields({})
        app = {
            "url": "https://job-boards.greenhouse.io/meridianlabs/jobs/123",
            "slug": "meridianlabs-senior-engineer",
        }

        with patch(
            "batch_apply_browser._fill_field_by_label",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fill:
            with patch("batch_apply_browser._select_dropdown_option", new_callable=AsyncMock):
                await fill_custom_questions(page, app)
                assert mock_fill.call_count > 0
                # Check the "Why {company}" / "Country" baseline labels were filled
                labels = [c[0][1] for c in mock_fill.call_args_list if len(c[0]) >= 2]
                assert any("Meridian" in label or "Country" in label for label in labels)

    @pytest.mark.asyncio
    async def test_greenhouse_rule_appends_role_overlay(self):
        # The slug matches a role overlay, so the qualifying-question extras
        # (which mention a local-language question) must also be filled.
        from batch_apply_browser import fill_custom_questions

        page = make_page_with_fields({})
        app = {
            "url": "https://job-boards.greenhouse.io/meridianlabs/jobs/123",
            "slug": "meridianlabs-senior-engineer",
        }

        with patch(
            "batch_apply_browser._fill_field_by_label",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fill:
            with patch("batch_apply_browser._select_dropdown_option", new_callable=AsyncMock):
                await fill_custom_questions(page, app)
        labels = " ".join(c[0][1] for c in mock_fill.call_args_list if len(c[0]) >= 2).lower()
        assert "language" in labels

    @pytest.mark.asyncio
    async def test_ashby_rule_fills_fields(self):
        from batch_apply_browser import fill_custom_questions

        page = make_page_with_fields({})
        app = {
            "url": "https://jobs.ashbyhq.com/novadynamics/abc123",
            "slug": "novadynamics",
        }

        with patch(
            "batch_apply_browser._fill_field_by_label",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fill:
            with patch(
                "batch_apply_browser._click_radio_by_label",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with patch("batch_apply_browser._select_dropdown_option", new_callable=AsyncMock):
                    await fill_custom_questions(page, app)
                    labels = [c[0][1] for c in mock_fill.call_args_list if len(c[0]) >= 2]
                    assert any(
                        "salary" in label.lower() or "notice" in label.lower() for label in labels
                    )

    @pytest.mark.asyncio
    async def test_unknown_company_does_nothing(self):
        from batch_apply_browser import fill_custom_questions

        page = make_page_with_fields({})
        app = {"url": "https://example.com/jobs/123", "slug": "unknown"}

        # Should not raise
        await fill_custom_questions(page, app)


# ---------------------------------------------------------------------------
# process_application
# ---------------------------------------------------------------------------


class TestProcessApplication:
    @pytest.mark.asyncio
    async def test_skips_unsupported_platform(self):
        from batch_apply_browser import process_application

        browser = AsyncMock()
        app = {
            "url": "https://www.linkedin.com/jobs/view/12345",
            "slug": "some-company",
            "role": "Engineer",
        }

        result = await process_application(browser, app, 1, 1, dry_run=True)
        assert result["status"] == "skipped"
        assert "linkedin" in result["reason"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_dry_run_status(self):
        from batch_apply_browser import process_application

        browser = AsyncMock()
        page = make_page_with_fields({}, url="https://jobs.lever.co/company/abc123")

        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        browser.new_context = AsyncMock(return_value=context)

        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "slug": "test-co",
            "role": "Engineer",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
            with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                with patch("batch_apply_browser.SCREENSHOTS_DIR") as mock_dir:
                    mock_dir.__truediv__ = MagicMock(return_value=Path("/tmp/test.png"))
                    result = await process_application(browser, app, 1, 1, dry_run=True)

        assert result["status"] == "dry-run"
        assert result["slug"] == "test-co"

    @pytest.mark.asyncio
    async def test_error_returns_error_status(self):
        from batch_apply_browser import process_application

        browser = AsyncMock()
        page = AsyncMock()
        page.goto = AsyncMock(side_effect=Exception("Connection refused"))
        page.screenshot = AsyncMock()

        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        browser.new_context = AsyncMock(return_value=context)

        app = {
            "url": "https://jobs.lever.co/company/abc123",
            "slug": "fail-co",
            "role": "Engineer",
            "cover_letter": "cv/applications/test/cover-letter.pdf",
        }

        with patch("batch_apply_browser.SCREENSHOTS_DIR") as mock_dir:
            mock_dir.mkdir = MagicMock()
            mock_dir.__truediv__ = MagicMock(return_value=Path("/tmp/err.png"))
            result = await process_application(browser, app, 1, 1, dry_run=False)

        assert result["status"] == "error"
        assert "Connection refused" in result["error"]


# ---------------------------------------------------------------------------
# _run_test_url
# ---------------------------------------------------------------------------


class TestRunTestUrl:
    @pytest.mark.asyncio
    async def test_unsupported_platform_returns_early(self):
        from batch_apply_browser import _run_test_url

        # linkedin is not in FILLERS, should print and return without launching browser
        with patch("builtins.print") as mock_print:
            await _run_test_url("https://www.linkedin.com/jobs/view/12345")
            printed = " ".join(str(c) for c in mock_print.call_args_list)
            assert (
                "No filler" in printed
                or "no filler" in printed.lower()
                or "linkedin" in printed.lower()
            )

    @pytest.mark.asyncio
    async def test_lever_url_runs_filler(self):
        mock_page = make_page_with_fields({}, url="https://jobs.lever.co/testco/abc123")
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)

        # async_playwright() returns an async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_async_pw = MagicMock(return_value=mock_cm)

        # Mock playwright at sys.modules level since it's imported locally inside _run_test_url
        mock_pw_module = MagicMock()
        mock_pw_module.async_api.async_playwright = mock_async_pw
        with patch.dict(
            "sys.modules",
            {"playwright": mock_pw_module, "playwright.async_api": mock_pw_module.async_api},
        ):
            from batch_apply_browser import _run_test_url

            with patch("batch_apply_browser.fill_source_field", new_callable=AsyncMock):
                with patch("batch_apply_browser.fill_custom_questions", new_callable=AsyncMock):
                    with patch("batch_apply_browser.SCREENSHOTS_DIR") as mock_dir:
                        mock_dir.mkdir = MagicMock()
                        mock_dir.__truediv__ = MagicMock(return_value=Path("/tmp/test.png"))
                        await _run_test_url("https://jobs.lever.co/testco/abc123")

        mock_page.goto.assert_called()


# ---------------------------------------------------------------------------
# FILLERS dict
# ---------------------------------------------------------------------------


class TestFillersDict:
    def test_fillers_has_all_platforms(self):
        from batch_apply_browser import FILLERS

        assert "lever" in FILLERS
        assert "greenhouse" in FILLERS
        assert "ashby" in FILLERS

    def test_fillers_values_are_callable(self):
        from batch_apply_browser import FILLERS

        for platform, func in FILLERS.items():
            assert callable(func), f"FILLERS['{platform}'] is not callable"
