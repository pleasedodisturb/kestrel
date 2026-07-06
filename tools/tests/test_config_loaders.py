"""Direct unit tests for the G-1303 gitignored-config loaders.

Covers the five loaders that merge a committed, obviously-fictional "floor" with
an optional gitignored per-user config:

- ``tools/batch_apply_browser.py``: ``_read_personal_yaml``, ``_load_answers``,
  ``_load_role_overlays``, ``_load_custom_questions`` (config/personal.yaml).
- ``tools/scrape_new_sources.py``: ``_load_company_lists`` (config/companies.yaml).
- ``tools/tier0_ats_poller.py``: ``_load_tier0_companies`` (config/companies.yaml).

Each loader is exercised for the four behaviours that matter for a config that
ships a floor: YAML absent (floor used, silent), present-and-overrides
(config wins over floor), malformed (fallback to floor + a logged warning), and
the dedup / config-wins merge semantics.

Follows the tools-test convention of adding ``tools/`` to ``sys.path`` so the
modules import directly (see ``test_normalize.py``). ``tools.batch_apply_browser``
loads ``config/personal.yaml`` eagerly at import, so — like
``tests/test_batch_apply_overlay.py`` — we seed it from the committed example.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOLS_DIR = _REPO_ROOT / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

# batch_apply_browser eagerly loads config/personal.yaml at import time; seed it
# from the committed example so this module always imports (CI does the same).
_personal_config = _REPO_ROOT / "config" / "personal.yaml"
_personal_example = _REPO_ROOT / "config" / "personal.yaml.example"
if not _personal_config.exists() and _personal_example.exists():
    shutil.copy(_personal_example, _personal_config)

if not _personal_config.exists():
    pytest.skip(
        "config/personal.yaml{.example} not found — skipping loader tests",
        allow_module_level=True,
    )

import batch_apply_browser as bab  # noqa: E402
import scrape_new_sources as sns  # noqa: E402
import tier0_ats_poller as t0  # noqa: E402


def _write_yaml(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# batch_apply_browser._read_personal_yaml — the raw reader
# ---------------------------------------------------------------------------


class TestReadPersonalYaml:
    """`_read_personal_yaml` reads config/personal.yaml (relative to PROJECT_ROOT)."""

    def test_absent_returns_empty_dict(self, tmp_path, monkeypatch):
        # PROJECT_ROOT points at a dir with no config/personal.yaml.
        monkeypatch.setattr(bab, "PROJECT_ROOT", tmp_path)
        assert bab._read_personal_yaml() == {}

    def test_present_returns_parsed_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bab, "PROJECT_ROOT", tmp_path)
        _write_yaml(tmp_path / "config" / "personal.yaml", "answers:\n  why_company: hello\n")
        cfg = bab._read_personal_yaml()
        assert cfg == {"answers": {"why_company": "hello"}}

    def test_empty_file_returns_empty_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bab, "PROJECT_ROOT", tmp_path)
        _write_yaml(tmp_path / "config" / "personal.yaml", "")
        assert bab._read_personal_yaml() == {}

    def test_malformed_raises_yaml_error(self, tmp_path, monkeypatch):
        # The raw reader does not swallow — callers are responsible for fallback.
        monkeypatch.setattr(bab, "PROJECT_ROOT", tmp_path)
        _write_yaml(tmp_path / "config" / "personal.yaml", "answers: [unterminated\n")
        with pytest.raises(yaml.YAMLError):
            bab._read_personal_yaml()


# ---------------------------------------------------------------------------
# batch_apply_browser._load_answers
# ---------------------------------------------------------------------------


class TestLoadAnswers:
    def test_absent_uses_floor(self, monkeypatch):
        monkeypatch.setattr(bab, "_read_personal_yaml", lambda: {})
        answers = bab._load_answers()
        # Every fictional floor answer is present.
        for key, val in bab._FLOOR_ANSWERS.items():
            assert answers[key] == val
        # `@location` is exposed for rule references.
        assert "location" in answers

    def test_config_overrides_floor(self, monkeypatch):
        monkeypatch.setattr(
            bab,
            "_read_personal_yaml",
            lambda: {"answers": {"why_company": "custom answer", "new_key": "extra"}},
        )
        answers = bab._load_answers()
        assert answers["why_company"] == "custom answer"  # config wins
        assert answers["new_key"] == "extra"  # new keys added
        # Untouched floor keys survive.
        assert answers["ai_policy"] == bab._FLOOR_ANSWERS["ai_policy"]

    def test_malformed_falls_back_with_warning(self, monkeypatch, caplog):
        def _boom():
            raise yaml.YAMLError("bad yaml")

        monkeypatch.setattr(bab, "_read_personal_yaml", _boom)
        with caplog.at_level(logging.WARNING, logger="batch_apply_browser"):
            answers = bab._load_answers()
        assert answers["why_company"] == bab._FLOOR_ANSWERS["why_company"]
        assert any("answers" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# batch_apply_browser._load_role_overlays
# ---------------------------------------------------------------------------


class TestLoadRoleOverlays:
    def test_absent_uses_floor(self, monkeypatch):
        monkeypatch.setattr(bab, "_read_personal_yaml", lambda: {})
        overlays = bab._load_role_overlays()
        assert set(overlays) == set(bab._FLOOR_ROLE_OVERLAYS)
        # Values are normalized to tuples.
        for fields in overlays.values():
            assert all(isinstance(f, tuple) and len(f) == 3 for f in fields)

    def test_config_overrides_floor_per_slug(self, monkeypatch):
        monkeypatch.setattr(
            bab,
            "_read_personal_yaml",
            lambda: {
                "role_overlays": {
                    "meridianlabs-senior-engineer": [["Custom question", "Yes", False]],
                    "acme-new-role": [["Brand new", "No", False]],
                }
            },
        )
        overlays = bab._load_role_overlays()
        # Existing floor slug is replaced by config.
        assert overlays["meridianlabs-senior-engineer"] == [("Custom question", "Yes", False)]
        # New slug is added (lower-cased key).
        assert overlays["acme-new-role"] == [("Brand new", "No", False)]
        # Untouched floor slug survives.
        assert "meridianlabs-engineering-manager" in overlays

    def test_config_slug_key_is_lowercased(self, monkeypatch):
        monkeypatch.setattr(
            bab,
            "_read_personal_yaml",
            lambda: {"role_overlays": {"ACME-Mixed-Case": [["Q", "Yes", False]]}},
        )
        overlays = bab._load_role_overlays()
        assert "acme-mixed-case" in overlays

    def test_malformed_falls_back_with_warning(self, monkeypatch, caplog):
        def _boom():
            raise yaml.YAMLError("bad yaml")

        monkeypatch.setattr(bab, "_read_personal_yaml", _boom)
        with caplog.at_level(logging.WARNING, logger="batch_apply_browser"):
            overlays = bab._load_role_overlays()
        assert set(overlays) == set(bab._FLOOR_ROLE_OVERLAYS)
        assert any("role_overlays" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# batch_apply_browser._load_custom_questions
# ---------------------------------------------------------------------------


def _match_keys(rules):
    return {
        (r.get("match", {}).get("platform", ""), r.get("match", {}).get("slug_or_url", "").lower())
        for r in rules
    }


class TestLoadCustomQuestions:
    def test_absent_uses_floor(self, monkeypatch):
        monkeypatch.setattr(bab, "_read_personal_yaml", lambda: {})
        rules = bab._load_custom_questions()
        assert len(rules) == len(bab._FLOOR_CUSTOM_QUESTIONS)
        assert _match_keys(rules) == _match_keys(bab._FLOOR_CUSTOM_QUESTIONS)

    def test_config_replaces_matching_floor_rule(self, monkeypatch):
        # Same (platform, slug_or_url) as a floor rule -> dedup replaces it.
        override = {
            "match": {"platform": "greenhouse", "slug_or_url": "meridianlabs"},
            "text_fields": [{"label": "Only my question", "value": "Yes"}],
        }
        monkeypatch.setattr(bab, "_read_personal_yaml", lambda: {"custom_questions": [override]})
        rules = bab._load_custom_questions()
        # No duplicate for that match key.
        gh_meridian = [
            r
            for r in rules
            if r["match"]["platform"] == "greenhouse"
            and r["match"]["slug_or_url"].lower() == "meridianlabs"
        ]
        assert len(gh_meridian) == 1
        assert gh_meridian[0]["text_fields"] == [{"label": "Only my question", "value": "Yes"}]
        # Total count unchanged (replaced, not appended).
        assert len(rules) == len(bab._FLOOR_CUSTOM_QUESTIONS)

    def test_config_appends_new_rule(self, monkeypatch):
        new_rule = {
            "match": {"platform": "greenhouse", "slug_or_url": "brand-new-co"},
            "text_fields": [{"label": "New", "value": "Yes"}],
        }
        monkeypatch.setattr(bab, "_read_personal_yaml", lambda: {"custom_questions": [new_rule]})
        rules = bab._load_custom_questions()
        assert len(rules) == len(bab._FLOOR_CUSTOM_QUESTIONS) + 1
        assert ("greenhouse", "brand-new-co") in _match_keys(rules)

    def test_dedup_is_case_insensitive_on_slug(self, monkeypatch):
        override = {
            "match": {"platform": "greenhouse", "slug_or_url": "MeridianLabs"},
            "text_fields": [{"label": "Case", "value": "Yes"}],
        }
        monkeypatch.setattr(bab, "_read_personal_yaml", lambda: {"custom_questions": [override]})
        rules = bab._load_custom_questions()
        assert len(rules) == len(bab._FLOOR_CUSTOM_QUESTIONS)  # replaced, not added

    def test_malformed_falls_back_with_warning(self, monkeypatch, caplog):
        def _boom():
            raise yaml.YAMLError("bad yaml")

        monkeypatch.setattr(bab, "_read_personal_yaml", _boom)
        with caplog.at_level(logging.WARNING, logger="batch_apply_browser"):
            rules = bab._load_custom_questions()
        assert _match_keys(rules) == _match_keys(bab._FLOOR_CUSTOM_QUESTIONS)
        assert any("custom_questions" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# scrape_new_sources._load_company_lists
# ---------------------------------------------------------------------------


class TestLoadCompanyLists:
    def test_absent_uses_floor_silently(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(sns, "_COMPANIES_CONFIG", tmp_path / "companies.yaml")
        with caplog.at_level(logging.WARNING, logger="scrape_new_sources"):
            lists = sns._load_company_lists()
        assert lists["greenhouse"] == sns._FLOOR_GREENHOUSE_COMPANIES
        assert lists["lever"] == sns._FLOOR_LEVER_COMPANIES
        assert lists["ashby"] == sns._FLOOR_ASHBY_COMPANIES
        # Absent config is the normal case — no warning.
        assert not caplog.records

    def test_present_overrides_floor(self, tmp_path, monkeypatch):
        cfg = _write_yaml(
            tmp_path / "companies.yaml",
            "greenhouse:\n  - acme\n  - beta\nlever:\n  - gamma\n",
        )
        monkeypatch.setattr(sns, "_COMPANIES_CONFIG", cfg)
        lists = sns._load_company_lists()
        assert lists["greenhouse"] == ["acme", "beta"]  # config wins
        assert lists["lever"] == ["gamma"]
        # ashby absent from config -> keeps floor.
        assert lists["ashby"] == sns._FLOOR_ASHBY_COMPANIES

    def test_empty_list_keeps_floor(self, tmp_path, monkeypatch):
        cfg = _write_yaml(tmp_path / "companies.yaml", "greenhouse: []\n")
        monkeypatch.setattr(sns, "_COMPANIES_CONFIG", cfg)
        lists = sns._load_company_lists()
        assert lists["greenhouse"] == sns._FLOOR_GREENHOUSE_COMPANIES

    def test_entries_are_stripped(self, tmp_path, monkeypatch):
        cfg = _write_yaml(tmp_path / "companies.yaml", "lever:\n  - '  spaced  '\n  - ''\n")
        monkeypatch.setattr(sns, "_COMPANIES_CONFIG", cfg)
        lists = sns._load_company_lists()
        assert lists["lever"] == ["spaced"]  # trimmed, empties dropped

    def test_malformed_falls_back_with_warning(self, tmp_path, monkeypatch, caplog):
        cfg = _write_yaml(tmp_path / "companies.yaml", "greenhouse: [unterminated\n")
        monkeypatch.setattr(sns, "_COMPANIES_CONFIG", cfg)
        with caplog.at_level(logging.WARNING, logger="scrape_new_sources"):
            lists = sns._load_company_lists()
        assert lists["greenhouse"] == sns._FLOOR_GREENHOUSE_COMPANIES
        assert any("companies.yaml" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# tier0_ats_poller._load_tier0_companies
# ---------------------------------------------------------------------------


class TestLoadTier0Companies:
    def test_absent_uses_floor_silently(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(t0, "COMPANIES_CONFIG", tmp_path / "companies.yaml")
        with caplog.at_level(logging.WARNING, logger="tier0_ats_poller"):
            companies = t0._load_tier0_companies()
        assert companies == t0._FLOOR_TIER_0_COMPANIES
        assert not caplog.records

    def test_present_replaces_floor(self, tmp_path, monkeypatch):
        cfg = _write_yaml(
            tmp_path / "companies.yaml",
            "tier0:\n  Acme: [greenhouse, acme-slug]\n  Beta: [lever, beta-slug]\n",
        )
        monkeypatch.setattr(t0, "COMPANIES_CONFIG", cfg)
        companies = t0._load_tier0_companies()
        assert companies == {
            "Acme": ("greenhouse", "acme-slug"),
            "Beta": ("lever", "beta-slug"),
        }
        # Config fully replaces the floor when a valid tier0 map is present.
        assert "example-greenhouse-co" not in companies

    def test_malformed_spec_entries_ignored(self, tmp_path, monkeypatch):
        # Entries that are not a 2-item list are skipped; a valid one still parses.
        cfg = _write_yaml(
            tmp_path / "companies.yaml",
            "tier0:\n  Good: [ashby, good-slug]\n  Bad: [only-one]\n",
        )
        monkeypatch.setattr(t0, "COMPANIES_CONFIG", cfg)
        companies = t0._load_tier0_companies()
        assert companies == {"Good": ("ashby", "good-slug")}

    def test_empty_tier0_keeps_floor(self, tmp_path, monkeypatch):
        cfg = _write_yaml(tmp_path / "companies.yaml", "tier0: {}\n")
        monkeypatch.setattr(t0, "COMPANIES_CONFIG", cfg)
        companies = t0._load_tier0_companies()
        assert companies == t0._FLOOR_TIER_0_COMPANIES

    def test_malformed_falls_back_with_warning(self, tmp_path, monkeypatch, caplog):
        cfg = _write_yaml(tmp_path / "companies.yaml", "tier0: [unterminated\n")
        monkeypatch.setattr(t0, "COMPANIES_CONFIG", cfg)
        with caplog.at_level(logging.WARNING, logger="tier0_ats_poller"):
            companies = t0._load_tier0_companies()
        assert companies == t0._FLOOR_TIER_0_COMPANIES
        assert any("companies.yaml" in r.message for r in caplog.records)
