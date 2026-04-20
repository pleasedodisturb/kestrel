"""Shared integer constraints for SQLite INT64 safety."""

# SQLite INTEGER is signed 64-bit: -2^63 to 2^63-1
INT64_MIN = -9_223_372_036_854_775_808
INT64_MAX = 9_223_372_036_854_775_807
