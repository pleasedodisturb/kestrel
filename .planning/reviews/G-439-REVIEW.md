---
phase: G-439-prefilter-discovery
reviewed: 2026-04-21T16:15:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/career_os/discovery/prefilter.py
  - src/career_os/config.py
  - src/career_os/services/discovery.py
  - tests/test_prefilter.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# G-439: Code Review Report — Pre-filter Discovery Integration

**Reviewed:** 2026-04-21T16:15:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

The pre-filter feature is well-designed: clean separation of concerns (pure-function filter logic in `prefilter.py`, wiring in `discovery.py`, config in `config.py`), good use of `re.escape()` to prevent regex injection, and solid test coverage across all three strategies. The `PrefilterMetrics` dataclass gives good observability.

Three warnings found: an invalid config value causes an unhandled `ValueError` crash at runtime, the `_build_prefilter_config` function does not validate the type of user-supplied keyword lists from JSON (could cause `TypeError`), and the `_merge_raw_jobs` call is duplicated for jobs that pass the prefilter. Two info items on test gaps and a minor dead-path concern.

No security vulnerabilities found. The `re.escape()` usage on all user-supplied keywords is correct and prevents ReDoS.

## Warnings

### WR-01: Invalid `PREFILTER_STRATEGY` env var crashes with unhandled ValueError

**File:** `src/career_os/services/discovery.py:126`
**Issue:** `PrefilterStrategy(settings.prefilter_strategy)` raises `ValueError` if the env var is set to an invalid value (e.g., `PREFILTER_STRATEGY=aggressive`). This crashes the entire discovery sweep with an unhandled exception. Unlike the AI provider key validation in `config.py` which uses a Pydantic `model_validator`, this value is a plain `str` field with no validation.
**Fix:** Validate in `config.py` using a Pydantic validator, or catch the error in `_build_prefilter_config` with a fallback:
```python
# Option A: validate in config.py (preferred — fail fast at startup)
from pydantic import field_validator

@field_validator("prefilter_strategy")
@classmethod
def validate_prefilter_strategy(cls, v: str) -> str:
    valid = {"strict", "moderate", "off"}
    if v not in valid:
        raise ValueError(
            f"PREFILTER_STRATEGY must be one of {valid}, got '{v}'"
        )
    return v

# Option B: defensive fallback in _build_prefilter_config
try:
    strategy = PrefilterStrategy(settings.prefilter_strategy)
except ValueError:
    logger.warning(
        "Invalid PREFILTER_STRATEGY '%s', defaulting to 'strict'",
        settings.prefilter_strategy,
    )
    strategy = PrefilterStrategy.STRICT
```

### WR-02: No type validation on search profile filter overrides

**File:** `src/career_os/services/discovery.py:148-153`
**Issue:** The `prefilter_title_keywords`, `prefilter_skill_keywords`, and `prefilter_blacklist_industries` values are read from user-supplied JSON (`search_profile.filters`) and passed directly to `PrefilterConfig` without type checking. If a user stores a string instead of a list (e.g., `"prefilter_title_keywords": "python"`) or a nested object, `_compile_patterns` will iterate over individual characters of the string, creating single-character regex patterns that match almost everything. This silently produces wrong results rather than raising an error.
**Fix:** Add type guards before assignment:
```python
if sp_filters.get("prefilter_title_keywords"):
    val = sp_filters["prefilter_title_keywords"]
    if isinstance(val, list):
        title_keywords = val
    else:
        logger.warning("prefilter_title_keywords must be a list, got %s — ignoring", type(val).__name__)
```

### WR-03: Duplicated `_merge_raw_jobs` call for prefiltered jobs

**File:** `src/career_os/services/discovery.py:456,484`
**Issue:** When the prefilter is active, `_merge_raw_jobs(group)` is called at line 456 to build merged dicts for filtering, then called again at line 484 for every job that passes the filter (during DB upsert). This is redundant work. More importantly, it creates a subtle correctness risk: if `_merge_raw_jobs` had side effects or non-determinism (it currently does not, but future changes could introduce this), the two calls could produce different results.
**Fix:** Cache the merged dicts from the prefilter pass and reuse them during upsert. For example, build a `{key: merged_dict}` mapping during the prefilter phase and look up from it during the upsert loop instead of re-merging.

## Info

### IN-01: No test for invalid `prefilter_strategy` config value

**File:** `tests/test_prefilter.py`
**Issue:** The test suite covers valid strategy values ("strict", "moderate", "off") but does not test what happens when an invalid value is configured (e.g., `PREFILTER_STRATEGY=invalid`). This is the scenario described in WR-01.
**Fix:** Add a test:
```python
def test_invalid_strategy_raises_or_defaults(self):
    from career_os.services.discovery import _build_prefilter_config
    with patch("career_os.config.settings") as mock_settings:
        mock_settings.prefilter_strategy = "invalid"
        with pytest.raises(ValueError):
            _build_prefilter_config()
```

### IN-02: `_build_prefilter_config` mock patches `career_os.config.settings` at import-time module level

**File:** `tests/test_prefilter.py:372-413`
**Issue:** The `_build_prefilter_config` tests patch `career_os.config.settings` but the function under test imports `settings` inside the function body (`from career_os.config import settings`). This works because the patch targets the module attribute, but it is fragile -- if someone refactors the import to a top-level `from career_os.config import settings`, the patch would silently stop working. The tests currently pass, so this is informational only.
**Fix:** Consider patching `career_os.services.discovery.settings` (the name as seen by the function) to make the test resilient to import refactoring. However, since the function uses a deferred import, the current approach is correct for now.

---

_Reviewed: 2026-04-21T16:15:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
