---
phase: G-441-prompt-caching
reviewed: 2026-04-21T22:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/career_os/ai/anthropic_provider.py
  - tests/test_anthropic_provider.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# G-441: Code Review Report

**Reviewed:** 2026-04-21T22:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the prompt caching changes for the Anthropic provider. The rewrite moves `score()` from delegating to `complete()` to making its own API call, placing profile data in the system prefix alongside scoring instructions for prompt cache reuse. `batch_score()` gets the same treatment. A bug fix adds the missing `usage` field in the `complete()` retry-exhaustion fallback path (line 188).

**Positive observations:**
- The cache_control placement is correct -- a single system block with `{"type": "ephemeral"}` is the right Anthropic API pattern.
- Profile data correctly moved to system prefix for cache reuse across scoring calls.
- The bug fix on line 188 (adding `usage=usage` to the exhausted-retries fallback `AIResponse`) is correct -- this was genuinely missing and would have returned `usage=None` after retries.
- Token usage extraction correctly captures `cache_creation_input_tokens` and `cache_read_input_tokens`.
- Test coverage is thorough: 8 new tests verifying cache_control placement, profile-in-system, token tracking, and batch caching.
- The `anthropic-beta` header is correctly omitted from `score()` since it only applies to tool use in `complete()`.

## Warnings

### WR-01: score() drops structured-parse retry logic that complete() provides

**File:** `src/career_os/ai/anthropic_provider.py:190-298`
**Issue:** The old `score()` delegated to `complete()`, which has a retry loop (lines 83-188) that re-attempts the API call with a "Return ONLY valid JSON" nudge when `_try_parse_structured` fails. The new standalone `score()` makes a single API call with no retry on parse failure. If the LLM returns malformed JSON (which the retry logic in `complete()` was specifically designed to handle), `score()` now returns `structured=None` silently. This is a behavioral regression -- callers that relied on the retry-then-parse pattern for scoring will get `None` structured data more often.
**Fix:** Add the same retry loop to `score()`, or extract the retry logic into a shared helper. At minimum, add a `max_retries` parameter:
```python
async def score(
    self,
    job_description: str,
    profile_data: dict,
    *,
    tier: ComplexityTier | None = None,
    max_retries: int = 1,
    **kwargs: object,
) -> AIResponse:
    ...
    for attempt in range(1, max_retries + 2):
        if attempt > 1:
            user_content += "\n\nIMPORTANT: Return ONLY valid JSON..."
        # ... make API call ...
        structured = _try_parse_structured(content, AIFeature.score)
        if structured is not None:
            return AIResponse(...)
        if attempt <= max_retries:
            logger.warning("Structured parse failed for score, retrying...")
    return AIResponse(..., structured=None, ...)
```

### WR-02: batch_score() uses self._model instead of _resolve_model(tier)

**File:** `src/career_os/ai/anthropic_provider.py:354`
**Issue:** `score()` correctly calls `self._resolve_model(tier)` to select the model based on complexity tier (line 205). `batch_score()` hardcodes `self._model` (line 354), bypassing tier-based model routing. The base class `batch_score()` signature does not accept a `tier` parameter, so this is inherited from the original code, but it creates an inconsistency: real-time scoring can use Haiku/Opus based on tier, but batch scoring always uses the default model. This was a pre-existing issue, not introduced by this PR, but worth noting since the PR touched this code path.
**Fix:** Either add `tier` to `batch_score()` signature (requires base class change) or document the limitation. At minimum:
```python
# NOTE: batch_score always uses the default model (no tier routing).
# Real-time score() supports tier-based routing via _resolve_model().
params: dict = {
    "model": self._model,
    ...
}
```

## Info

### IN-01: Significant code duplication between score() and complete()

**File:** `src/career_os/ai/anthropic_provider.py:190-298`
**Issue:** The new `score()` duplicates roughly 40 lines of HTTP call logic, error handling, response parsing, and usage extraction that are identical to `complete()`. The error handling block (402/429, ConnectError, TimeoutException), content block parsing, and TokenUsage construction are copy-pasted. This increases maintenance burden -- any future change (e.g., new error codes, header changes) must be applied to both methods.
**Fix:** Extract the shared HTTP call + response parsing into a private helper method like `_call_api(payload, headers) -> dict` that both `complete()` and `score()` can use. This would reduce `score()` to ~20 lines of prompt construction + the helper call.

### IN-02: Batch score prompt is slightly abbreviated vs real-time score prompt

**File:** `src/career_os/ai/anthropic_provider.py:333-351` vs `219-237`
**Issue:** The user prompt in `batch_score()` (line 333-350) uses a slightly shorter version of the scoring instructions compared to `score()` (line 219-237). Specifically, `batch_score()` omits the detailed `desire_score` description ("how much the candidate would WANT this job -- considering company reputation, growth potential, culture signals, role excitement, compensation attractiveness, work-life balance") and just says "desire_score (0-10), desire_reasoning (string)." This was a pre-existing difference but is worth flagging since both prompts were touched in this PR.
**Fix:** Extract the scoring prompt into a shared constant or function to ensure consistency:
```python
def _scoring_user_prompt(job_description: str) -> str:
    """Build the user-message scoring prompt (shared by score + batch_score)."""
    return (
        "Score this job against the candidate profile. ..."
        f"Job Description:\n{job_description}"
    )
```

---

_Reviewed: 2026-04-21T22:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
