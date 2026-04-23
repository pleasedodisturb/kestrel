"""Tests that all documentation links in README are valid files."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestDocumentationLinks:
    """Verify all doc links in README point to real files."""

    def _extract_md_links(self, filepath: Path) -> list[tuple[str, str]]:
        """Extract all markdown links from a file. Returns (text, url) tuples."""
        content = filepath.read_text()
        return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

    def test_readme_exists(self) -> None:
        assert (ROOT / "README.md").exists()

    def test_all_readme_doc_links_resolve(self) -> None:
        """Every .md link in README must point to a real file."""
        links = self._extract_md_links(ROOT / "README.md")
        md_links = [
            (text, url) for text, url in links if url.endswith(".md") and not url.startswith("http")
        ]
        assert len(md_links) > 0, "No .md links found in README"

        for text, url in md_links:
            target = ROOT / url
            assert target.exists(), f"Broken link in README: [{text}]({url}) -> {target}"

    def test_all_doc_files_have_front_matter(self) -> None:
        """Every doc .md file should have Jekyll front matter for GitHub Pages."""
        doc_files = list((ROOT / "docs").glob("*.md"))
        assert len(doc_files) > 0, "No docs found"

        # Internal/dev docs excluded from Pages - only user-facing docs need front matter
        # index.md is auto-generated (sitemap) and doesn't need front matter
        skip_prefixes = ("validation-contract", "M6-M9", "JOB_SEARCH", "market-research", "images")
        skip_names = {"index.md"}
        for f in doc_files:
            if f.name.startswith(skip_prefixes) or f.name in skip_names:
                continue
            content = f.read_text()
            assert content.startswith("---"), (
                f"{f.name} missing Jekyll front matter (should start with ---)"
            )

    def test_required_docs_exist(self) -> None:
        """All docs referenced in README must exist."""
        required = [
            "docs/guides/QUICKSTART.md",
            "docs/guides/FAQ.md",
            "docs/guides/HELP.md",
            "docs/reference/AI-PROVIDERS.md",
            "docs/guides/COMPARISON.md",
            "docs/reference/REFERENCE.md",
            "DEPLOY.md",
            "CONTRIBUTING.md",
            "LICENSE",
        ]
        for doc in required:
            assert (ROOT / doc).exists(), f"Required doc missing: {doc}"

    def test_doc_illustrations_referenced_correctly(self) -> None:
        """Docs that reference illustrations should point to existing files."""
        for f in (ROOT / "docs").glob("*.md"):
            content = f.read_text()
            img_links = re.findall(r'<img src="([^"]+)"', content)
            for img in img_links:
                if img.startswith("http"):  # Skip external URLs
                    continue
                img_path = ROOT / img[3:] if img.startswith("../") else ROOT / "docs" / img
                assert img_path.exists(), f"Broken image in {f.name}: {img} -> {img_path}"

    def test_readme_illustration_exists(self) -> None:
        """README hero illustration must exist."""
        readme = (ROOT / "README.md").read_text()
        img_links = re.findall(r'<img src="([^"]+)"', readme)
        for img in img_links:
            if img.startswith("http"):
                continue
            if "illustrations" in img:
                assert (ROOT / img).exists(), f"Broken illustration in README: {img}"

    def test_no_pricing_strategy_in_repo(self) -> None:
        """Pricing strategy should not be in the public repo."""
        assert not (ROOT / "docs" / "pricing-strategy.md").exists(), (
            "pricing-strategy.md should not be in public repo"
        )

    def test_gitignore_blocks_pricing(self) -> None:
        """Gitignore should prevent pricing strategy from being re-added."""
        gitignore = (ROOT / ".gitignore").read_text()
        assert "pricing-strategy" in gitignore, "pricing-strategy.md not in .gitignore"
