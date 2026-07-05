"""Tests for tools/blocklist.py -- single-source word-boundary company blocklist.

Covers the two failure modes a substring matcher has:
  * false-negative: a bare token must block its company without needing substring
    containment;
  * false-positive: a short token (e.g. "orbix") must NOT match inside an
    unrelated word ("Orbixual Systems").

The floor tests enforce the non-shrink PATTERN: every FLOOR_BLOCKED entry must
stay loaded and blocked. In this repo the personal config/blocklist.yaml is
gitignored, so CI only exercises the embedded floor; the guard bites for real
once a tracked config exists (e.g. in a private fork) -- that config must then
stay a superset of the floor or this suite goes red. All fixtures use the
FICTIONAL floor entries shipped with the repo.
"""

import sys
from pathlib import Path

import pytest

# Add tools/ to path so we can import the module directly (tools-test convention).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import blocklist  # noqa: E402
from blocklist import (  # noqa: E402
    BLOCKED_COMPANIES,
    FLOOR_BLOCKED,
    FLOOR_SOFT_FLAG,
    SOFT_FLAG_COMPANIES,
    is_blocked,
    prompt_snippet,
    soft_flag_reason,
)

# --- CI floor: the live YAML can never shrink below the canonical set ----------


@pytest.mark.parametrize("entry", FLOOR_BLOCKED)
def test_floor_entry_is_loaded(entry):
    assert entry in BLOCKED_COMPANIES, (
        f"Floor company {entry!r} missing from the loaded blocklist -- the list "
        f"must never drop a values-based entry (non-shrink CI guard)."
    )


@pytest.mark.parametrize("entry", FLOOR_BLOCKED)
def test_floor_entry_is_blocked(entry):
    # Use a realistic company string that contains the entry as a whole word.
    assert is_blocked(f"{entry.title()} Inc") is not None


def test_soft_flag_floor_loaded():
    for company in FLOOR_SOFT_FLAG:
        assert company in SOFT_FLAG_COMPANIES


# --- Word-boundary: true positives --------------------------------------------


@pytest.mark.parametrize(
    "company",
    [
        "Orbix",
        "Orbix Technologies",
        "EvilCorp",
        "Acme Spyware GmbH",
        "ShadowTrack Systems",
        "Panopticorp Ltd",
        "Villain Industries Inc",
        "Lowball Labs",
    ],
)
def test_blocks_real_blocked_company(company):
    assert is_blocked(company) is not None, f"{company} should be blocked"


# --- Word-boundary: NO false positives (the substring bug) ---------------------


@pytest.mark.parametrize(
    "company",
    [
        "Orbixual Systems",  # contains "orbix" but is not Orbix (word boundary)
        "Acmethyst",  # contains "acme" but no whole-word "acme spyware"
        "Brightlake Analytics",
        "Metabase",
        "Texas Instruments",
        "Corbixture Ltd",  # contains "orbix" mid-word
    ],
)
def test_does_not_block_unrelated_company(company):
    assert is_blocked(company) is None, f"{company} should NOT be blocked"


# --- Soft-flag: surfaced, not blocked -----------------------------------------


@pytest.mark.parametrize("company", ["FlagCo", "FlagCo AI", "CooldownCo", "CooldownCo SE"])
def test_soft_flagged_not_blocked(company):
    assert is_blocked(company) is None
    assert soft_flag_reason(company) is not None


def test_non_flagged_company_clean():
    assert is_blocked("Supabase") is None
    assert soft_flag_reason("Supabase") is None


def test_empty_and_none_safe():
    for val in (None, "", "   "):
        assert is_blocked(val) is None
        assert soft_flag_reason(val) is None


# --- Fallback: a broken/missing YAML still yields the floor --------------------


def test_load_falls_back_to_floor_on_missing_yaml(monkeypatch, tmp_path):
    monkeypatch.setattr(blocklist, "_CONFIG_PATH", tmp_path / "does-not-exist.yaml")
    blocked, soft = blocklist._load()
    assert set(FLOOR_BLOCKED).issubset(set(blocked))
    assert set(FLOOR_SOFT_FLAG).issubset(set(soft))


def test_load_falls_back_to_floor_on_empty_blocked(monkeypatch, tmp_path):
    bad = tmp_path / "blocklist.yaml"
    bad.write_text("blocked: {}\nsoft_flag: {}\n", encoding="utf-8")
    monkeypatch.setattr(blocklist, "_CONFIG_PATH", bad)
    blocked, _ = blocklist._load()
    assert set(FLOOR_BLOCKED).issubset(set(blocked))


# --- Prompt snippet for agent injection ---------------------------------------


def test_prompt_snippet_mentions_blocked_and_soft():
    snippet = prompt_snippet().lower()
    assert "orbix" in snippet
    assert "flagco" in snippet


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
