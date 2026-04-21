"""Shared integer constraints for SQLite INT64 safety.

INT32 bounds are used for query/path parameters because ASGI test
transports (httpx/Schemathesis) serialize large integers through C
`int` when building URL strings, causing OverflowError at 2^63.
INT32_MAX (2^31-1 ≈ 2.1 billion) is more than sufficient for any
practical ID or pagination value in a self-hosted SQLite app.

Body (JSON) fields use the full INT64 range since JSON serialization
handles arbitrary-precision integers natively.
"""

# C-int-safe bounds for query/path parameters
INT32_MIN = -2_147_483_648
INT32_MAX = 2_147_483_647

# Full SQLite INTEGER range for JSON body fields
INT64_MIN = -9_223_372_036_854_775_808
INT64_MAX = 9_223_372_036_854_775_807
