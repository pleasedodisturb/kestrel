"""Tests for research utility functions in tools/research_jobs.py and tools/research_optiver_pdf.py."""

from unittest.mock import MagicMock, patch

# research_optiver_pdf has module-level httpx.get call; patch before import
with patch("httpx.get", return_value=MagicMock(content=b"", text="")):
    from research_jobs import fetch_text
    from research_optiver_pdf import extract_strings


# ---------------------------------------------------------------------------
# fetch_text tests
# ---------------------------------------------------------------------------


class TestFetchText:
    """Tests for fetch_text(url, max_chars)."""

    def _mock_response(self, html: str) -> MagicMock:
        resp = MagicMock()
        resp.text = html
        return resp

    @patch("research_jobs.httpx.get")
    def test_strips_script_tags(self, mock_get):
        mock_get.return_value = self._mock_response(
            "<html><script>var x=1;</script><p>Hello</p></html>"
        )
        result = fetch_text("https://example.com")
        assert "var x=1" not in result
        assert "Hello" in result

    @patch("research_jobs.httpx.get")
    def test_strips_script_tags_with_attributes(self, mock_get):
        mock_get.return_value = self._mock_response(
            '<script type="text/javascript">alert("hi")</script><p>Content</p>'
        )
        result = fetch_text("https://example.com")
        assert "alert" not in result
        assert "Content" in result

    @patch("research_jobs.httpx.get")
    def test_strips_style_tags(self, mock_get):
        mock_get.return_value = self._mock_response("<style>body{color:red}</style><p>Visible</p>")
        result = fetch_text("https://example.com")
        assert "color:red" not in result
        assert "Visible" in result

    @patch("research_jobs.httpx.get")
    def test_strips_style_tags_with_attributes(self, mock_get):
        mock_get.return_value = self._mock_response(
            '<style type="text/css">.cls{margin:0}</style><div>Text</div>'
        )
        result = fetch_text("https://example.com")
        assert "margin" not in result
        assert "Text" in result

    @patch("research_jobs.httpx.get")
    def test_strips_html_tags(self, mock_get):
        mock_get.return_value = self._mock_response("<div><p>Hello</p><a href='#'>World</a></div>")
        result = fetch_text("https://example.com")
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result

    @patch("research_jobs.httpx.get")
    def test_collapses_whitespace(self, mock_get):
        mock_get.return_value = self._mock_response("<p>Hello</p>   \n\n\t  <p>World</p>")
        result = fetch_text("https://example.com")
        # Multiple whitespace should collapse to single spaces
        assert "  " not in result
        assert "Hello" in result
        assert "World" in result

    @patch("research_jobs.httpx.get")
    def test_strips_leading_trailing_whitespace(self, mock_get):
        mock_get.return_value = self._mock_response("  <p>Content</p>  ")
        result = fetch_text("https://example.com")
        assert result == "Content"

    @patch("research_jobs.httpx.get")
    def test_truncates_to_max_chars(self, mock_get):
        long_text = "A" * 5000
        mock_get.return_value = self._mock_response(f"<p>{long_text}</p>")
        result = fetch_text("https://example.com")
        assert len(result) == 2500  # default max_chars

    @patch("research_jobs.httpx.get")
    def test_custom_max_chars(self, mock_get):
        long_text = "B" * 500
        mock_get.return_value = self._mock_response(f"<p>{long_text}</p>")
        result = fetch_text("https://example.com", max_chars=100)
        assert len(result) == 100

    @patch("research_jobs.httpx.get")
    def test_short_content_not_truncated(self, mock_get):
        mock_get.return_value = self._mock_response("<p>Short</p>")
        result = fetch_text("https://example.com", max_chars=100)
        assert result == "Short"

    @patch("research_jobs.httpx.get")
    def test_error_handling(self, mock_get):
        mock_get.side_effect = Exception("Connection timed out")
        result = fetch_text("https://example.com")
        assert result.startswith("ERROR: ")
        assert "Connection timed out" in result

    @patch("research_jobs.httpx.get")
    def test_error_handling_httpx_timeout(self, mock_get):
        import httpx

        mock_get.side_effect = httpx.TimeoutException("read timed out")
        result = fetch_text("https://example.com")
        assert result.startswith("ERROR: ")

    @patch("research_jobs.httpx.get")
    def test_multiline_script_tag(self, mock_get):
        html = """<html>
        <script>
            function foo() {
                return 42;
            }
        </script>
        <body>Real content</body>
        </html>"""
        mock_get.return_value = self._mock_response(html)
        result = fetch_text("https://example.com")
        assert "function" not in result
        assert "Real content" in result

    @patch("research_jobs.httpx.get")
    def test_request_params(self, mock_get):
        """Verify httpx.get is called with correct parameters."""
        mock_get.return_value = self._mock_response("<p>OK</p>")
        fetch_text("https://example.com")
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["timeout"] == 20
        assert call_kwargs.kwargs["follow_redirects"] is True
        assert "User-Agent" in call_kwargs.kwargs["headers"]

    @patch("research_jobs.httpx.get")
    def test_empty_html(self, mock_get):
        mock_get.return_value = self._mock_response("")
        result = fetch_text("https://example.com")
        assert result == ""


# ---------------------------------------------------------------------------
# extract_strings tests
# ---------------------------------------------------------------------------


class TestExtractStrings:
    """Tests for extract_strings(data, min_len).

    NOTE: The implementation only flushes accumulated chars when hitting
    a non-printable byte. Strings at EOF without a trailing non-printable
    are NOT captured. All test data must end with a non-printable byte
    (e.g. \\x00) for the final string to be captured.
    """

    def test_simple_ascii_string(self):
        # Must end with non-printable to flush
        data = b"Hello World\x00"
        result = extract_strings(data)
        assert result == ["Hello World"]

    def test_min_len_default_filters_short(self):
        data = b"Hi\x00"
        result = extract_strings(data)
        assert result == []

    def test_min_len_default_keeps_long(self):
        data = b"Test\x00"
        result = extract_strings(data)
        assert result == ["Test"]

    def test_custom_min_len(self):
        data = b"AB\x00CDEF\x00GHIJKLMN\x00"
        result = extract_strings(data, min_len=6)
        assert "AB" not in result
        assert "CDEF" not in result
        assert "GHIJKLMN" in result

    def test_mixed_binary_and_ascii(self):
        data = b"\x00\x01\x02Hello\x80\x90\xffWorld!\x00\x00"
        result = extract_strings(data)
        assert "Hello" in result
        assert "World!" in result

    def test_binary_separators(self):
        data = b"Alpha\x00\x00\x00Beta\x01Gamma\x00"
        result = extract_strings(data)
        assert "Alpha" in result
        assert "Beta" in result
        assert "Gamma" in result

    def test_empty_data(self):
        result = extract_strings(b"")
        assert result == []

    def test_all_binary(self):
        data = bytes(range(0, 32)) + bytes([127, 128, 255])
        result = extract_strings(data)
        assert result == []

    def test_printable_range_boundaries(self):
        # Space (32) is printable, tilde (126) is printable
        data = b" ~~~~\x00"
        result = extract_strings(data)
        assert result == [" ~~~~"]

    def test_non_printable_boundary(self):
        # DEL (127) is NOT printable in this implementation
        data = b"ABCD\x7fEFGH\x00"
        result = extract_strings(data)
        assert "ABCD" in result
        assert "EFGH" in result

    def test_min_len_one(self):
        data = b"\x00A\x00BC\x00DEF\x00"
        result = extract_strings(data, min_len=1)
        assert "A" in result
        assert "BC" in result
        assert "DEF" in result

    def test_strings_at_end_without_terminator(self):
        # The implementation only flushes on non-printable byte.
        # Strings at EOF without trailing non-printable are NOT captured.
        data = b"\x00TestString"
        result = extract_strings(data)
        assert "TestString" not in result

    def test_exact_min_len_boundary(self):
        data = b"\x00ABC\x00ABCD\x00"
        result = extract_strings(data, min_len=4)
        assert "ABC" not in result
        assert "ABCD" in result

    def test_pdf_like_binary_data(self):
        # \x50 is 'P' (printable), so it joins with "Privacy Policy"
        # Use \x01 before Privacy to cleanly separate
        data = b"\x00\x01%PDF-1.4\x00\x00\xff\xfe/Type /Catalog\x00\x01Privacy Policy\x00"
        result = extract_strings(data, min_len=4)
        assert "%PDF-1.4" in result
        assert "/Type /Catalog" in result
        assert "Privacy Policy" in result
