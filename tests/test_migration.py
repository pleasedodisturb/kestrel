"""Tests for data migration: CSV import, package linking, profile seeding.

Tests cover:
- Schema validation (tables exist, columns correct, FKs present)
- Default profile seeding
- CSV import with all 46 rows
- Status mapping (interested→Interested, applied→Applied, discovery→Discovered, outreach→Interested)
- Edge cases: empty URLs, mixed salary formats, German entries, missing scores
- Application package linking
- Profile API endpoint
- Multi-user profile isolation
"""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, create_test_engine
from career_os.migration.csv_import import (
    _map_status,
    _normalize_salary,
    _normalize_url,
    _parse_date,
    _parse_fit_score,
    import_csv,
)
from career_os.migration.link_packages import link_packages
from career_os.migration.seed import seed_default_profile
from career_os.models.models import (
    ActivityLog,
    Application,
    ApplicationPackage,
    Profile,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    eng = create_test_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine) -> Session:
    """Create a test database session."""
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def seeded_db(db: Session) -> Session:
    """Database session with a default profile seeded."""
    seed_default_profile(db)
    return db


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV with edge cases for testing."""
    csv_path = tmp_path / "applications.csv"
    rows = [
        {
            "date_applied": "2026-02-23",
            "company": "TestCorp",
            "role": "Engineer",
            "url": "https://example.com/job1",
            "source": "linkedin",
            "status": "interested",
            "salary_range": "€80k-€100k",
            "contact": "",
            "next_step": "Apply",
            "notes": "Good fit",
            "fit_score": "8.5",
        },
        {
            "date_applied": "2026-03-01",
            "company": "GermanCo GmbH",
            "role": "KI-Manager/in",
            "url": "",
            "source": "arbeitsagentur",
            "status": "discovery",
            "salary_range": "",
            "contact": "",
            "next_step": "",
            "notes": "German entry",
            "fit_score": "7",
        },
        {
            "date_applied": "2026-03-03",
            "company": "UKStartup",
            "role": "Product Engineer",
            "url": "https://example.com/job2",
            "source": "ashby",
            "status": "applied",
            "salary_range": "£90k-£130k + options",
            "contact": "",
            "next_step": "",
            "notes": "",
            "fit_score": "9.5",
        },
        {
            "date_applied": "2026-03-03",
            "company": "OutreachCo",
            "role": "PM Role",
            "url": "https://outreach.co/careers",
            "source": "company",
            "status": "outreach",
            "salary_range": "",
            "contact": "",
            "next_step": "",
            "notes": "Proactive outreach",
            "fit_score": "8",
        },
        {
            "date_applied": "2026-02-23",
            "company": "USCompany",
            "role": "TPM IV",
            "url": "https://example.com/job3",
            "source": "linkedin",
            "status": "interested",
            "salary_range": "$95-115/hr",
            "contact": "",
            "next_step": "",
            "notes": "Hourly rate",
            "fit_score": "",
        },
    ]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


# ── Schema Tests ────────────────────────────────────────────────────────────


class TestSchema:
    """Verify database schema is correct."""

    def test_all_tables_exist(self, engine) -> None:
        """All 5 expected tables exist in the database."""
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "profiles",
            "applications",
            "activity_log",
            "follow_ups",
            "application_packages",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_profiles_columns(self, engine) -> None:
        """Profiles table has correct columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("profiles")}
        expected = {"id", "name", "email", "location", "job_family", "created_at", "updated_at"}
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_applications_columns(self, engine) -> None:
        """Applications table has correct columns including profile_id FK."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("applications")}
        expected = {
            "id",
            "profile_id",
            "company",
            "role",
            "url",
            "source",
            "status",
            "salary_range",
            "contact",
            "next_step",
            "notes",
            "fit_score",
            "date_applied",
            "created_at",
            "updated_at",
            "archived_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_all_tables_have_profile_id_fk(self, engine) -> None:
        """All tables (except profiles) have profile_id foreign key."""
        inspector = inspect(engine)
        for table_name in ["applications", "activity_log", "follow_ups", "application_packages"]:
            columns = {c["name"] for c in inspector.get_columns(table_name)}
            assert "profile_id" in columns, f"{table_name} missing profile_id column"
            fks = inspector.get_foreign_keys(table_name)
            fk_columns = {fk["constrained_columns"][0] for fk in fks}
            assert "profile_id" in fk_columns, f"{table_name} missing profile_id FK constraint"

    def test_activity_log_columns(self, engine) -> None:
        """Activity log table has correct columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("activity_log")}
        expected = {
            "id",
            "profile_id",
            "application_id",
            "action",
            "details",
            "source",
            "created_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_follow_ups_columns(self, engine) -> None:
        """Follow-ups table has correct columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("follow_ups")}
        expected = {
            "id",
            "profile_id",
            "application_id",
            "due_date",
            "follow_up_type",
            "notes",
            "completed_at",
            "created_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_application_packages_columns(self, engine) -> None:
        """Application packages table has correct columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("application_packages")}
        expected = {
            "id",
            "profile_id",
            "application_id",
            "package_dir",
            "cover_letter_path",
            "cv_path",
            "created_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"


# ── Profile Seeding Tests ────────────────────────────────────────────────────


class TestProfileSeeding:
    """Tests for default profile seeding."""

    def test_seed_creates_profile(self, db: Session) -> None:
        """Seeding creates a default profile when none exists."""
        profile = seed_default_profile(db)
        assert profile.id is not None
        assert profile.name == "Kestrel User"
        assert profile.location == "Frankfurt, Germany"
        assert profile.job_family is not None

    def test_seed_idempotent(self, db: Session) -> None:
        """Seeding is idempotent — returns existing profile on second call."""
        p1 = seed_default_profile(db)
        p2 = seed_default_profile(db)
        assert p1.id == p2.id

    def test_profile_has_timestamps(self, db: Session) -> None:
        """Profile has created_at and updated_at timestamps."""
        profile = seed_default_profile(db)
        assert profile.created_at is not None
        assert profile.updated_at is not None


# ── Status Mapping Tests ────────────────────────────────────────────────────


class TestStatusMapping:
    """Tests for CSV status → Kanban status mapping."""

    def test_interested_maps_to_interested(self) -> None:
        assert _map_status("interested") == "interested"

    def test_applied_maps_to_applied(self) -> None:
        assert _map_status("applied") == "applied"

    def test_discovery_maps_to_discovered(self) -> None:
        assert _map_status("discovery") == "discovered"

    def test_outreach_maps_to_interested(self) -> None:
        assert _map_status("outreach") == "interested"

    def test_researching_maps_to_discovered(self) -> None:
        assert _map_status("researching") == "discovered"

    def test_unknown_status_defaults_to_discovered(self) -> None:
        assert _map_status("unknown_status") == "discovered"

    def test_status_case_insensitive(self) -> None:
        assert _map_status("INTERESTED") == "interested"
        assert _map_status("Applied") == "applied"
        assert _map_status("Discovery") == "discovered"

    def test_status_with_whitespace(self) -> None:
        assert _map_status("  interested  ") == "interested"


# ── Parser Helper Tests ────────────────────────────────────────────────────


class TestParserHelpers:
    """Tests for CSV field parsing helpers."""

    def test_parse_date_valid(self) -> None:
        dt = _parse_date("2026-02-23")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 23
        assert dt.tzinfo is not None  # timezone-aware

    def test_parse_date_empty(self) -> None:
        assert _parse_date("") is None
        assert _parse_date("  ") is None

    def test_parse_date_invalid(self) -> None:
        assert _parse_date("not-a-date") is None

    def test_parse_fit_score_float(self) -> None:
        assert _parse_fit_score("8.5") == 8.5
        assert _parse_fit_score("9.5") == 9.5

    def test_parse_fit_score_int(self) -> None:
        assert _parse_fit_score("8") == 8.0

    def test_parse_fit_score_empty(self) -> None:
        assert _parse_fit_score("") is None
        assert _parse_fit_score("  ") is None

    def test_parse_fit_score_invalid(self) -> None:
        assert _parse_fit_score("N/A") is None

    def test_normalize_url_valid(self) -> None:
        assert _normalize_url("https://example.com") == "https://example.com"

    def test_normalize_url_empty(self) -> None:
        assert _normalize_url("") is None
        assert _normalize_url("  ") is None

    def test_normalize_salary_eur(self) -> None:
        assert _normalize_salary("€80k-€100k") == "€80k-€100k"

    def test_normalize_salary_gbp(self) -> None:
        assert _normalize_salary("£90k-£130k + options") == "£90k-£130k + options"

    def test_normalize_salary_usd_hourly(self) -> None:
        assert _normalize_salary("$95-115/hr") == "$95-115/hr"

    def test_normalize_salary_estimated(self) -> None:
        assert _normalize_salary("100-130k (estimated)") == "100-130k (estimated)"

    def test_normalize_salary_empty(self) -> None:
        assert _normalize_salary("") is None
        assert _normalize_salary("  ") is None


# ── CSV Import Tests ────────────────────────────────────────────────────────


class TestCsvImport:
    """Tests for CSV import with edge cases."""

    def test_import_sample_csv(self, seeded_db: Session, sample_csv: Path) -> None:
        """Import sample CSV and verify correct row count."""
        stats = import_csv(seeded_db, sample_csv, profile_id=1)
        assert stats["imported"] == 5
        assert stats["skipped"] == 0

    def test_import_status_mapping(self, seeded_db: Session, sample_csv: Path) -> None:
        """Verify status mapping is applied correctly during import (all lowercase)."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        apps = seeded_db.query(Application).all()
        statuses = {a.company: a.status for a in apps}

        assert statuses["TestCorp"] == "interested"
        assert statuses["GermanCo GmbH"] == "discovered"
        assert statuses["UKStartup"] == "applied"
        assert statuses["OutreachCo"] == "interested"  # outreach→interested

    def test_import_empty_urls(self, seeded_db: Session, sample_csv: Path) -> None:
        """Rows with empty URLs are imported with url=None."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        german_app = (
            seeded_db.query(Application).filter(Application.company == "GermanCo GmbH").first()
        )
        assert german_app is not None
        assert german_app.url is None

    def test_import_mixed_salary_formats(self, seeded_db: Session, sample_csv: Path) -> None:
        """Mixed salary formats (EUR, GBP, USD/hourly) preserved correctly."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        apps = {a.company: a for a in seeded_db.query(Application).all()}

        assert apps["TestCorp"].salary_range == "€80k-€100k"
        assert apps["UKStartup"].salary_range == "£90k-£130k + options"
        assert apps["USCompany"].salary_range == "$95-115/hr"
        assert apps["GermanCo GmbH"].salary_range is None  # empty

    def test_import_german_entries(self, seeded_db: Session, sample_csv: Path) -> None:
        """German-language entries (KI-Manager/in) imported correctly."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        german_app = (
            seeded_db.query(Application).filter(Application.role == "KI-Manager/in").first()
        )
        assert german_app is not None
        assert german_app.company == "GermanCo GmbH"
        assert german_app.source == "arbeitsagentur"

    def test_import_missing_fit_scores(self, seeded_db: Session, sample_csv: Path) -> None:
        """Rows with missing fit scores import with fit_score=None."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        us_app = seeded_db.query(Application).filter(Application.company == "USCompany").first()
        assert us_app is not None
        assert us_app.fit_score is None

    def test_import_creates_activity_logs(self, seeded_db: Session, sample_csv: Path) -> None:
        """Each imported row creates an activity log entry."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        log_count = seeded_db.query(ActivityLog).count()
        assert log_count == 5  # One per imported row

    def test_import_activity_log_source(self, seeded_db: Session, sample_csv: Path) -> None:
        """Activity log entries from import have source='csv_migration'."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        logs = seeded_db.query(ActivityLog).all()
        for log in logs:
            assert log.source == "csv_migration"
            assert log.action == "imported"

    def test_import_date_parsing(self, seeded_db: Session, sample_csv: Path) -> None:
        """Dates parsed correctly as timezone-aware datetimes."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        app = seeded_db.query(Application).filter(Application.company == "TestCorp").first()
        assert app is not None
        assert app.date_applied is not None
        assert app.date_applied.year == 2026
        assert app.date_applied.month == 2
        assert app.date_applied.day == 23

    def test_import_file_not_found(self, seeded_db: Session) -> None:
        """Importing from a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            import_csv(seeded_db, "/nonexistent/path.csv", profile_id=1)

    def test_import_profile_id_set(self, seeded_db: Session, sample_csv: Path) -> None:
        """All imported applications have the correct profile_id."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        apps = seeded_db.query(Application).all()
        for app in apps:
            assert app.profile_id == 1

    def test_import_warnings_for_empty_urls(self, seeded_db: Session, sample_csv: Path) -> None:
        """Import reports warnings for empty URLs."""
        stats = import_csv(seeded_db, sample_csv, profile_id=1)
        warnings = stats["warnings"]
        empty_url_warnings = [w for w in warnings if "Empty URL" in str(w)]
        assert len(empty_url_warnings) == 1  # Only GermanCo has empty URL in sample


# ── Real CSV Import Tests ────────────────────────────────────────────────────


class TestRealCsvImport:
    """Tests importing the actual tracking/applications.csv."""

    @pytest.fixture
    def real_csv_path(self) -> Path:
        """Path to the real applications.csv."""
        csv_path = Path(__file__).resolve().parents[1] / "tracking" / "applications.csv"
        if not csv_path.exists():
            pytest.skip("tracking/applications.csv not found")
        return csv_path

    def test_import_all_real_rows(self, seeded_db: Session, real_csv_path: Path) -> None:
        """All rows from real CSV imported without errors."""
        stats = import_csv(seeded_db, real_csv_path, profile_id=1)
        assert stats["imported"] == 46
        assert stats["skipped"] == 0

    def test_real_csv_count_in_db(self, seeded_db: Session, real_csv_path: Path) -> None:
        """Database count matches CSV row count after import."""
        import_csv(seeded_db, real_csv_path, profile_id=1)
        count = seeded_db.query(Application).count()
        assert count == 46

    def test_real_csv_status_distribution(self, seeded_db: Session, real_csv_path: Path) -> None:
        """Status distribution matches expected mapping (all lowercase)."""
        import_csv(seeded_db, real_csv_path, profile_id=1)

        from sqlalchemy import func

        status_counts = dict(
            seeded_db.query(Application.status, func.count(Application.id))
            .group_by(Application.status)
            .all()
        )
        # interested(27) + outreach(4) → interested: 31
        # discovery(13) → discovered: 13
        # applied(2) → applied: 2
        assert status_counts.get("interested", 0) == 31
        assert status_counts.get("discovered", 0) == 13
        assert status_counts.get("applied", 0) == 2

    def test_spot_check_mistral_dach(self, seeded_db: Session, real_csv_path: Path) -> None:
        """Spot-check: Mistral AI Deployment Strategist has score 8.5, status applied."""
        import_csv(seeded_db, real_csv_path, profile_id=1)

        app = (
            seeded_db.query(Application)
            .filter(
                Application.company == "Mistral AI",
                Application.role.contains("Deployment Strategist"),
            )
            .first()
        )
        assert app is not None
        assert app.fit_score == 8.5
        assert app.status == "applied"

    def test_spot_check_plain(self, seeded_db: Session, real_csv_path: Path) -> None:
        """Spot-check: Plain Senior Product Engineer has score 9.5, status applied."""
        import_csv(seeded_db, real_csv_path, profile_id=1)

        # Plain has two entries (interested + applied); get the applied one
        app = (
            seeded_db.query(Application)
            .filter(
                Application.company == "Plain",
                Application.status == "applied",
            )
            .first()
        )
        assert app is not None
        assert app.fit_score == 9.5
        assert app.status == "applied"

    def test_spot_check_shopware_tpm(self, seeded_db: Session, real_csv_path: Path) -> None:
        """Spot-check: shopware AG TPM has score 8.5, status interested."""
        import_csv(seeded_db, real_csv_path, profile_id=1)

        app = (
            seeded_db.query(Application)
            .filter(
                Application.company == "shopware AG",
                Application.role.contains("Technical Program Manager"),
            )
            .first()
        )
        assert app is not None
        assert app.fit_score == 8.5
        assert app.status == "interested"

    def test_real_csv_empty_urls_handled(self, seeded_db: Session, real_csv_path: Path) -> None:
        """Empty URL rows imported correctly."""
        import_csv(seeded_db, real_csv_path, profile_id=1)

        # FlexIT Consulting has empty URL
        app = (
            seeded_db.query(Application).filter(Application.company == "FlexIT Consulting").first()
        )
        assert app is not None
        assert app.url is None  # Empty URL stored as None

    def test_real_csv_german_entries(self, seeded_db: Session, real_csv_path: Path) -> None:
        """German entries imported correctly."""
        import_csv(seeded_db, real_csv_path, profile_id=1)

        # Check NTT DATA KI-Engineer
        app = (
            seeded_db.query(Application)
            .filter(
                Application.company == "NTT DATA",
                Application.role == "KI-Engineer",
            )
            .first()
        )
        assert app is not None
        assert app.source == "arbeitsagentur"

    def test_real_csv_no_silent_drops(self, seeded_db: Session, real_csv_path: Path) -> None:
        """No rows silently dropped — imported + skipped = total CSV rows."""
        stats = import_csv(seeded_db, real_csv_path, profile_id=1)
        total = int(stats["imported"]) + int(stats["skipped"])
        assert total == 46  # All rows accounted for


# ── Package Linking Tests ────────────────────────────────────────────────────


class TestPackageLinking:
    """Tests for linking application packages."""

    @pytest.fixture
    def mock_packages_dir(self, tmp_path: Path) -> Path:
        """Create a mock packages directory with test data."""
        pkg_dir = tmp_path / "applications"
        pkg_dir.mkdir()

        # Create a mock package directory
        pkg = pkg_dir / "plain-sr-product-engineer-ai"
        pkg.mkdir()
        (pkg / "cover-letter.md").write_text("Test cover letter")
        (pkg / "user-plain-cv.pdf").write_bytes(b"fake pdf")

        return pkg_dir

    def test_link_package_to_application(
        self, seeded_db: Session, mock_packages_dir: Path, sample_csv: Path
    ) -> None:
        """Package linked to matching application by company."""
        # First import some data — we need a "Plain" application with matching name
        # Create one manually for this test
        from career_os.models.models import Application

        app = Application(
            profile_id=1,
            company="Plain",
            role="Senior Product Engineer (AI)",
            url="https://example.com",
            status="applied",
        )
        seeded_db.add(app)
        seeded_db.commit()

        stats = link_packages(seeded_db, mock_packages_dir, profile_id=1)
        assert stats["linked"] == 1

        # Verify the package record
        pkg = seeded_db.query(ApplicationPackage).first()
        assert pkg is not None
        assert pkg.application_id == app.id
        assert pkg.profile_id == 1
        assert "plain-sr-product-engineer-ai" in pkg.package_dir

    def test_link_finds_cover_letter(self, seeded_db: Session, mock_packages_dir: Path) -> None:
        """Package linking finds cover letter files."""
        app = Application(
            profile_id=1,
            company="Plain",
            role="Senior Product Engineer (AI)",
            url="https://example.com",
            status="applied",
        )
        seeded_db.add(app)
        seeded_db.commit()

        link_packages(seeded_db, mock_packages_dir, profile_id=1)

        pkg = seeded_db.query(ApplicationPackage).first()
        assert pkg is not None
        assert pkg.cover_letter_path is not None
        assert "cover-letter.md" in pkg.cover_letter_path

    def test_link_finds_cv(self, seeded_db: Session, mock_packages_dir: Path) -> None:
        """Package linking finds CV PDF files."""
        app = Application(
            profile_id=1,
            company="Plain",
            role="Senior Product Engineer (AI)",
            url="https://example.com",
            status="applied",
        )
        seeded_db.add(app)
        seeded_db.commit()

        link_packages(seeded_db, mock_packages_dir, profile_id=1)

        pkg = seeded_db.query(ApplicationPackage).first()
        assert pkg is not None
        assert pkg.cv_path is not None
        assert "cv.pdf" in pkg.cv_path

    def test_link_nonexistent_dir(self, seeded_db: Session) -> None:
        """Linking from nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            link_packages(seeded_db, "/nonexistent/path", profile_id=1)


# ── Profile API Tests ────────────────────────────────────────────────────────


class TestProfileAPI:
    """Tests for the profiles API endpoint.

    Uses a temp file-based SQLite since in-memory SQLite doesn't work across
    sessions/threads with the FastAPI test client.
    """

    @pytest.fixture
    def api_client(self, tmp_path: Path) -> TestClient:
        """Create a test client with temp file-based database."""
        from contextlib import asynccontextmanager

        from fastapi import APIRouter, Depends, FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware

        from career_os.models.models import Profile as ProfileModel
        from career_os.schemas.profiles import ProfileListResponse, ProfileResponse

        db_path = tmp_path / "test.db"
        test_engine = create_test_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(test_engine)
        TestSession = sessionmaker(bind=test_engine)

        # Seed default profile
        db = TestSession()
        seed_default_profile(db)
        db.close()

        def get_test_db():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        @asynccontextmanager
        async def noop_lifespan(app: FastAPI):
            yield

        test_app = FastAPI(lifespan=noop_lifespan)
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        test_router = APIRouter(prefix="/api/profiles", tags=["profiles"])

        @test_router.get("", response_model=ProfileListResponse)
        async def list_profiles(
            db: Session = Depends(get_test_db),
        ) -> ProfileListResponse:
            profiles = db.query(ProfileModel).all()
            return ProfileListResponse(
                profiles=[ProfileResponse.model_validate(p) for p in profiles],
                count=len(profiles),
            )

        @test_router.get("/{profile_id}", response_model=ProfileResponse)
        async def get_profile(
            profile_id: int, db: Session = Depends(get_test_db)
        ) -> ProfileResponse:
            profile = db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
            if profile is None:
                raise HTTPException(status_code=404, detail="Profile not found")
            return ProfileResponse.model_validate(profile)

        test_app.include_router(test_router)

        client = TestClient(test_app)
        yield client

    def test_list_profiles_returns_default(self, api_client: TestClient) -> None:
        """GET /api/profiles returns the seeded default profile."""
        response = api_client.get("/api/profiles")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert data["profiles"][0]["name"] == "Kestrel User"
        assert data["profiles"][0]["location"] == "Frankfurt, Germany"

    def test_list_profiles_structure(self, api_client: TestClient) -> None:
        """GET /api/profiles returns correct response structure."""
        response = api_client.get("/api/profiles")
        data = response.json()
        assert "profiles" in data
        assert "count" in data
        profile = data["profiles"][0]
        assert "id" in profile
        assert "name" in profile
        assert "email" in profile
        assert "location" in profile
        assert "job_family" in profile
        assert "created_at" in profile
        assert "updated_at" in profile

    def test_get_profile_by_id(self, api_client: TestClient) -> None:
        """GET /api/profiles/{id} returns specific profile."""
        response = api_client.get("/api/profiles/1")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Kestrel User"

    def test_get_profile_not_found(self, api_client: TestClient) -> None:
        """GET /api/profiles/{id} returns 404 for non-existent profile."""
        response = api_client.get("/api/profiles/999")
        assert response.status_code == 404


# ── Multi-User Isolation Tests ────────────────────────────────────────────────


class TestMultiUserIsolation:
    """Tests for profile_id isolation across tables."""

    def test_applications_bound_to_profile(self, seeded_db: Session, sample_csv: Path) -> None:
        """Applications are bound to the importing profile."""
        import_csv(seeded_db, sample_csv, profile_id=1)

        # Create a second profile
        p2 = Profile(name="Other User", email="other@example.com")
        seeded_db.add(p2)
        seeded_db.commit()

        # Profile 1 has apps, profile 2 does not
        p1_apps = seeded_db.query(Application).filter(Application.profile_id == 1).count()
        p2_apps = seeded_db.query(Application).filter(Application.profile_id == p2.id).count()
        assert p1_apps == 5
        assert p2_apps == 0
