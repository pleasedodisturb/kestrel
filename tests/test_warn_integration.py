"""Tests for WARN Act layoff integration (Epic 9 / G-277).

Covers:
- Company name normalization
- Filing lookup and severity thresholds
- Red flag detection via detect_red_flags()
- Graceful degradation when warn-scraper is absent
- Flag description content
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from career_os.database import Base
from career_os.models.warn import WARNFiling
from career_os.services.red_flags import _detect_recent_layoffs, detect_red_flags
from career_os.services.warn_data import (
    _parse_date,
    _parse_int,
    company_names_match,
    get_filings_for_company,
    load_warn_data,
    normalize_company_name,
    upsert_filing,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with warn_filings table."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    """Transactional test session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _make_filing(
    db: Session,
    company_name: str,
    state: str = "CA",
    notice_date: date | None = None,
    employees_affected: int | None = 100,
    effective_date: date | None = None,
) -> WARNFiling:
    """Helper: insert a WARNFiling and flush."""
    nd = notice_date or date.today()
    filing = upsert_filing(
        db,
        company_name=company_name,
        state=state,
        notice_date=nd,
        effective_date=effective_date,
        employees_affected=employees_affected,
    )
    db.flush()
    return filing


# ---------------------------------------------------------------------------
# Company name normalization
# ---------------------------------------------------------------------------


class TestNormalizeCompanyName:
    def test_strips_llc(self):
        assert normalize_company_name("Acme LLC") == "acme"

    def test_strips_inc(self):
        assert normalize_company_name("Acme Inc") == "acme"

    def test_strips_incorporated(self):
        assert normalize_company_name("Acme Incorporated") == "acme"

    def test_strips_corp(self):
        assert normalize_company_name("Acme Corp") == "acme"

    def test_strips_corporation(self):
        assert normalize_company_name("Acme Corporation") == "acme"

    def test_strips_ltd(self):
        assert normalize_company_name("Acme Ltd") == "acme"

    def test_strips_limited(self):
        assert normalize_company_name("Acme Limited") == "acme"

    def test_google_llc(self):
        assert normalize_company_name("Google LLC") == "google"

    def test_meta_platforms_inc(self):
        assert normalize_company_name("Meta Platforms, Inc.") == "meta platforms"

    def test_microsoft_corporation(self):
        assert normalize_company_name("Microsoft Corporation") == "microsoft"

    def test_already_normalized(self):
        assert normalize_company_name("acme") == "acme"

    def test_empty_string(self):
        assert normalize_company_name("") == ""

    def test_removes_punctuation(self):
        assert normalize_company_name("Acme, Inc.") == "acme"

    def test_case_insensitive(self):
        assert normalize_company_name("ACME LLC") == "acme"

    def test_extra_whitespace(self):
        assert normalize_company_name("  Acme  LLC  ") == "acme"

    def test_stacked_suffixes(self):
        # "Corp., Inc." — two suffixes
        assert normalize_company_name("Acme Corp., Inc.") == "acme"

    def test_multi_word_company(self):
        # Suffixes are stripped iteratively until no more match.
        # "Sunrise Foods Company Inc" → strip "inc" → strip "company" → "sunrise foods"
        assert normalize_company_name("Sunrise Foods Company Inc") == "sunrise foods"


class TestCompanyNamesMatch:
    def test_match_with_llc_vs_bare(self):
        assert company_names_match("Google LLC", "Google") is True

    def test_match_inc_vs_bare(self):
        assert company_names_match("Stripe, Inc.", "Stripe") is True

    def test_no_match_different_companies(self):
        assert company_names_match("Apple Inc", "Microsoft") is False

    def test_no_match_empty_job(self):
        assert company_names_match("Acme LLC", "") is False

    def test_no_match_empty_filing(self):
        assert company_names_match("", "Acme") is False

    def test_case_insensitive_match(self):
        assert company_names_match("ACME CORP", "acme") is True

    def test_exact_match_both_bare(self):
        assert company_names_match("stripe", "stripe") is True


# ---------------------------------------------------------------------------
# Database upsert / dedup
# ---------------------------------------------------------------------------


class TestUpsertFiling:
    def test_inserts_new_filing(self, db):
        filing = _make_filing(db, "TestCo LLC", notice_date=date(2026, 1, 1))
        assert filing.id is not None
        assert filing.company_name_normalized == "testco"

    def test_dedup_returns_existing(self, db):
        nd = date(2026, 2, 1)
        f1 = upsert_filing(db, company_name="Acme LLC", state="CA", notice_date=nd)
        db.flush()
        f2 = upsert_filing(db, company_name="Acme LLC", state="CA", notice_date=nd)
        db.flush()
        assert f1.id == f2.id

    def test_enriches_existing_with_employee_count(self, db):
        nd = date(2026, 3, 1)
        f1 = upsert_filing(
            db, company_name="Acme LLC", state="NY", notice_date=nd, employees_affected=None
        )
        db.flush()
        f2 = upsert_filing(
            db, company_name="Acme LLC", state="NY", notice_date=nd, employees_affected=250
        )
        db.flush()
        assert f1.id == f2.id
        assert f1.employees_affected == 250

    def test_different_state_creates_new_row(self, db):
        nd = date(2026, 4, 1)
        f1 = upsert_filing(db, company_name="Acme LLC", state="CA", notice_date=nd)
        db.flush()
        f2 = upsert_filing(db, company_name="Acme LLC", state="TX", notice_date=nd)
        db.flush()
        assert f1.id != f2.id


# ---------------------------------------------------------------------------
# Filing lookups
# ---------------------------------------------------------------------------


class TestGetFilingsForCompany:
    def test_returns_matching_filings(self, db):
        _make_filing(db, "Stripe, Inc.", state="CA", notice_date=date(2026, 1, 15))
        results = get_filings_for_company(db, "Stripe")
        assert len(results) >= 1
        assert results[0].company_name == "Stripe, Inc."

    def test_no_match_returns_empty(self, db):
        results = get_filings_for_company(db, "NonExistentCo")
        assert results == []

    def test_empty_name_returns_empty(self, db):
        results = get_filings_for_company(db, "")
        assert results == []

    def test_since_filter_excludes_old(self, db):
        _make_filing(db, "OldCo LLC", notice_date=date(2024, 1, 1))
        _make_filing(db, "OldCo LLC", notice_date=date(2026, 1, 1))
        results = get_filings_for_company(db, "OldCo", since=date(2025, 6, 1))
        assert len(results) == 1
        assert results[0].notice_date == date(2026, 1, 1)

    def test_orders_by_notice_date_desc(self, db):
        _make_filing(db, "BigCorp Inc", notice_date=date(2025, 6, 1))
        _make_filing(db, "BigCorp Inc", notice_date=date(2026, 1, 1), state="NY")
        results = get_filings_for_company(db, "BigCorp")
        assert results[0].notice_date > results[-1].notice_date


# ---------------------------------------------------------------------------
# _detect_recent_layoffs severity thresholds
# ---------------------------------------------------------------------------


class TestDetectRecentLayoffs:
    def test_warn_within_60_days_severity_warning(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=30)
        _make_filing(db, "RifCo Inc", notice_date=notice, employees_affected=200)

        flag = _detect_recent_layoffs("RifCo Inc", db=db, today=today)
        assert flag is not None
        assert flag["severity"] == "warning"
        assert flag["flag_type"] == "recent_layoffs"

    def test_warn_61_to_180_days_severity_caution(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=90)
        _make_filing(db, "CautionCo LLC", notice_date=notice, employees_affected=50)

        flag = _detect_recent_layoffs("CautionCo LLC", db=db, today=today)
        assert flag is not None
        assert flag["severity"] == "caution"

    def test_warn_older_than_180_days_no_flag(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=200)
        _make_filing(db, "OldLayoffCo", notice_date=notice)

        flag = _detect_recent_layoffs("OldLayoffCo", db=db, today=today)
        assert flag is None

    def test_no_warn_data_no_flag(self, db):
        flag = _detect_recent_layoffs("CleanCompany LLC", db=db, today=date(2026, 4, 14))
        assert flag is None

    def test_no_db_returns_none(self):
        flag = _detect_recent_layoffs("AnyCompany", db=None)
        assert flag is None

    def test_no_company_name_returns_none(self, db):
        flag = _detect_recent_layoffs(None, db=db)
        assert flag is None

    def test_empty_company_name_returns_none(self, db):
        flag = _detect_recent_layoffs("", db=db)
        assert flag is None


# ---------------------------------------------------------------------------
# Flag description content
# ---------------------------------------------------------------------------


class TestWarnFlagDescription:
    def test_description_includes_date(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=20)
        _make_filing(db, "DescriptCo", notice_date=notice, employees_affected=300)

        flag = _detect_recent_layoffs("DescriptCo", db=db, today=today)
        assert flag is not None
        assert notice.isoformat() in flag["description"]

    def test_description_includes_employee_count(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=15)
        _make_filing(db, "HeadcountCo", notice_date=notice, employees_affected=500)

        flag = _detect_recent_layoffs("HeadcountCo", db=db, today=today)
        assert flag is not None
        assert "500" in flag["description"]

    def test_description_includes_state(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=10)
        _make_filing(db, "StateCo Inc", state="WA", notice_date=notice)

        flag = _detect_recent_layoffs("StateCo Inc", db=db, today=today)
        assert flag is not None
        assert "WA" in flag["description"]

    def test_description_without_employee_count(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=10)
        _make_filing(db, "NullEmployeesCo", notice_date=notice, employees_affected=None)

        flag = _detect_recent_layoffs("NullEmployeesCo", db=db, today=today)
        assert flag is not None
        # Should not crash and should not include 'None'
        assert "None" not in flag["description"]


# ---------------------------------------------------------------------------
# detect_red_flags() integration
# ---------------------------------------------------------------------------


class TestDetectRedFlagsWarnIntegration:
    def test_warn_flag_appears_in_detect_red_flags(self, db):
        today = date(2026, 4, 14)
        notice = today - timedelta(days=30)
        _make_filing(db, "RiskyBiz Inc", notice_date=notice, employees_affected=150)

        with patch("career_os.services.red_flags._detect_recent_layoffs") as mock_detect:
            mock_detect.return_value = {
                "flag_type": "recent_layoffs",
                "severity": "warning",
                "description": "WARN filing 30 days ago.",
            }
            flags = detect_red_flags(
                "Great job opportunity.",
                company_name="RiskyBiz Inc",
                db=db,
            )

        warn_flags = [f for f in flags if f["flag_type"] == "recent_layoffs"]
        assert len(warn_flags) == 1

    def test_no_warn_flag_when_no_company(self, db):
        flags = detect_red_flags("Great job opportunity.", db=db)
        warn_flags = [f for f in flags if f["flag_type"] == "recent_layoffs"]
        assert len(warn_flags) == 0

    def test_no_warn_flag_when_no_db(self):
        flags = detect_red_flags("Great job opportunity.", company_name="SomeCo")
        warn_flags = [f for f in flags if f["flag_type"] == "recent_layoffs"]
        assert len(warn_flags) == 0

    def test_existing_rules_unaffected(self, db):
        """Adding WARN parameters must not break existing red flag rules."""
        old_flags = detect_red_flags("Great job opportunity.")
        new_flags = detect_red_flags(
            "Great job opportunity.",
            company_name="CleanCo",
            db=db,
        )
        # Both should produce same base flags (no WARN filing in DB for CleanCo)
        assert old_flags == new_flags


# ---------------------------------------------------------------------------
# Graceful skip when warn-scraper not installed
# ---------------------------------------------------------------------------


class TestGracefulSkipNoWarnScraper:
    def test_load_warn_data_skips_gracefully_when_not_installed(self, db):
        """load_warn_data returns {} without raising when warn-scraper absent."""
        with patch("career_os.services.warn_data._is_warnscraper_available", return_value=False):
            result = load_warn_data(db, states=["CA", "NY"])
        assert result == {}

    def test_detect_recent_layoffs_skips_on_import_error(self, db):
        """_detect_recent_layoffs returns None when warn_data module import fails.

        Simulates warn-scraper not being installed by making the lazy import of
        career_os.services.warn_data raise ImportError. The function must catch
        this and return None rather than propagating the error.
        """
        import importlib
        import sys

        # Remove warn_data from sys.modules so the lazy import re-executes,
        # then substitute a broken module reference.
        saved = sys.modules.pop("career_os.services.warn_data", None)
        sys.modules["career_os.services.warn_data"] = None  # type: ignore[assignment]
        try:
            flag = _detect_recent_layoffs("SomeCo", db=db)
            assert flag is None
        finally:
            if saved is not None:
                sys.modules["career_os.services.warn_data"] = saved
            else:
                sys.modules.pop("career_os.services.warn_data", None)
                importlib.import_module("career_os.services.warn_data")


# ---------------------------------------------------------------------------
# Internal helper tests
# ---------------------------------------------------------------------------


class TestParseDateHelper:
    def test_parses_iso_string(self):
        assert _parse_date("2026-01-15") == date(2026, 1, 15)

    def test_parses_us_format(self):
        assert _parse_date("01/15/2026") == date(2026, 1, 15)

    def test_parses_date_object(self):
        d = date(2026, 3, 10)
        assert _parse_date(d) == d

    def test_returns_none_for_none(self):
        assert _parse_date(None) is None

    def test_returns_none_for_empty_string(self):
        assert _parse_date("") is None

    def test_returns_none_for_unparseable(self):
        assert _parse_date("not-a-date") is None


class TestParseIntHelper:
    def test_parses_int(self):
        assert _parse_int(42) == 42

    def test_parses_float(self):
        assert _parse_int(42.0) == 42

    def test_parses_string_with_commas(self):
        assert _parse_int("1,500") == 1500

    def test_returns_none_for_none(self):
        assert _parse_int(None) is None

    def test_returns_none_for_empty_string(self):
        assert _parse_int("") is None

    def test_returns_none_for_non_numeric(self):
        assert _parse_int("n/a") is None
