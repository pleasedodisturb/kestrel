import json
import re
from html.parser import HTMLParser

import httpx


class _HTMLStripper(HTMLParser):
    """Strip HTML tags safely using the stdlib parser instead of regex."""

    _SKIP_TAGS = frozenset({"script", "style"})

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self._fed: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, d):
        if self._skip_depth == 0:
            self._fed.append(d)

    def get_data(self) -> str:
        return "".join(self._fed)


def strip_html_tags(html_text: str) -> str:
    """Remove HTML tags from *html_text* and return plain text.

    Uses stdlib ``HTMLParser`` so it handles malformed markup safely -
    unlike a regex approach which can be bypassed with crafted input.
    """
    s = _HTMLStripper()
    s.feed(html_text)
    return s.get_data()


def fetch_text(url, max_chars=2500):
    try:
        r = httpx.get(
            url,
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120"
            },
        )
        text = strip_html_tags(r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"ERROR: {e}"


results = {}
results["remotely"] = fetch_text("https://www.remotely.de")
results["optiver_faq"] = fetch_text("https://www.optiver.com/working-at-optiver/faq/")
results["optiver_jobs_page"] = fetch_text(
    "https://www.optiver.com/working-at-optiver/career-opportunities/current-opportunities/"
)
results["mongodb_product"] = fetch_text("https://www.mongodb.com/careers/departments/product")
print(json.dumps(results, ensure_ascii=False, indent=2))
