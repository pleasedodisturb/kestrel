---
phase: G-446-openai-direct-provider
reviewed: 2026-04-21T18:30:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/career_os/ai/openai_provider.py
  - src/career_os/ai/factory.py
  - src/career_os/ai/__init__.py
  - tests/conftest.py
  - tests/test_openai_provider.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# G-446: Code Review Report — OpenAI Direct Provider

**Reviewed:** 2026-04-21T18:30:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

The OpenAI direct provider is a clean adaptation of the existing Together provider pattern. Factory registration, `__init__.py` exports, and `conftest.py` safety guards (env blanking + network blocking for `api.openai.com`) are all correctly wired. API key handling is sound -- no hardcoded secrets, key validated on init, Bearer auth used properly. Two warnings found: an `UnboundLocalError` crash on a degenerate `max_retries` value and missing test coverage for the retry/fallback path. Two info items for completeness.

## Warnings

### WR-01: UnboundLocalError when max_retries is negative

**File:** `src/career_os/ai/openai_provider.py:135-141`
**Issue:** If `max_retries` is set to a value below `-1` (e.g., `-2`), `range(1, max_retries + 2)` produces an empty range. The loop body never executes, so `content` and `model_used` are never assigned. The fallback `return` at line 135 then raises `UnboundLocalError`. While unlikely in normal usage, this is a crash path reachable through the public API. The same bug exists in `together_provider.py` -- this is inherited, not introduced.

**Fix:** Guard at the top of `complete()` or initialize defaults before the loop:
```python
content = ""
model_used = self._model

for attempt in range(1, max_retries + 2):
    ...
```

### WR-02: Retry logic and structured parse failure path not tested

**File:** `tests/test_openai_provider.py`
**Issue:** The retry loop (lines 69-133 of the provider) is a non-trivial code path: when `_try_parse_structured` returns `None` for a structured feature, the provider retries with a "return ONLY valid JSON" suffix. Neither the retry attempt nor the exhausted-retries fallback (returning `structured=None`) is covered by any test. This is the most complex logic in the provider and the most likely place for regressions.

**Fix:** Add two tests:
```python
@pytest.mark.asyncio
async def test_retries_on_structured_parse_failure(self) -> None:
    """Provider retries when structured parse fails for a structured feature."""
    provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
    call_count = 0

    async def mock_post(url, headers=None, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        # Return invalid JSON for score feature
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "not valid json"}}],
                "model": "gpt-4o-mini",
            },
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await provider.complete("test", feature=AIFeature.score, max_retries=1)

    assert call_count == 2  # initial + 1 retry
    assert result.structured is None
    assert result.content == "not valid json"

@pytest.mark.asyncio
async def test_retry_appends_json_instruction(self) -> None:
    """Retry attempts append JSON instruction to prompt."""
    provider = OpenAIProvider(api_key=_TEST_CREDENTIAL)
    payloads = []

    async def mock_post(url, headers=None, json=None, **kwargs):
        payloads.append(json)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "bad"}}],
                "model": "gpt-4o-mini",
            },
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        await provider.complete("test", feature=AIFeature.score, max_retries=1)

    # First attempt: original prompt
    assert "IMPORTANT" not in payloads[0]["messages"][-1]["content"]
    # Second attempt: includes JSON instruction
    assert "IMPORTANT: Return ONLY valid JSON" in payloads[1]["messages"][-1]["content"]
```

## Info

### IN-01: score() signature does not include tier parameter from base class

**File:** `src/career_os/ai/openai_provider.py:143-153`
**Issue:** The base class `AIProvider.score()` declares `*, tier: ComplexityTier | None = None` as a keyword argument. The OpenAI provider's `score()` method does not accept `tier`, meaning `provider.score(jd, profile, tier=ComplexityTier.SIMPLE)` would raise `TypeError`. This is inherited from the Together provider pattern -- not a regression but worth tracking for when tier-based routing is implemented.

**Fix:** Add `tier` to the signature (can be ignored in body for now):
```python
async def score(
    self,
    job_description: str,
    profile_data: dict,
    *,
    tier: ComplexityTier | None = None,
    **kwargs: object,
) -> AIResponse:
```

### IN-02: No direct test for _extract_error_detail helper

**File:** `src/career_os/ai/openai_provider.py:156-163`
**Issue:** The `_extract_error_detail` function handles multiple cases (valid JSON with dict error, non-dict error, unparseable response) but is only exercised indirectly through the 402/429 tests. The fallback paths (non-dict error, JSON parse failure) are not covered.

**Fix:** Add a small unit test class for `_extract_error_detail` covering the three branches: dict error, string error, and unparseable body.

---

_Reviewed: 2026-04-21T18:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
