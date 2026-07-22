"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from career_os import __version__
from career_os.api.ai import router as ai_router
from career_os.api.analytics import router as analytics_router
from career_os.api.applications import router as applications_router
from career_os.api.batch import router as batch_router
from career_os.api.calendar import router as calendar_router
from career_os.api.coaching import router as coaching_router
from career_os.api.contacts import router as contacts_router
from career_os.api.discovery import router as discovery_router
from career_os.api.extension import router as extension_router
from career_os.api.follow_ups import router as follow_ups_router
from career_os.api.gaps import router as gaps_router
from career_os.api.goals import router as goals_router
from career_os.api.integrations import router as integrations_router
from career_os.api.intelligence import router as intelligence_router
from career_os.api.interview_prep import router as interview_prep_router
from career_os.api.jobs import router as jobs_router
from career_os.api.learning import router as learning_router
from career_os.api.market import router as market_router
from career_os.api.oauth import limiter as oauth_limiter
from career_os.api.oauth import router as oauth_router
from career_os.api.onboarding import router as onboarding_router
from career_os.api.presets import router as presets_router
from career_os.api.privacy import router as privacy_router
from career_os.api.profiles import router as profiles_router
from career_os.api.pushover import router as pushover_router
from career_os.api.research import router as research_router
from career_os.api.scoring import router as scoring_router
from career_os.api.skills import router as skills_router
from career_os.api.star_stories import app_router as star_stories_app_router
from career_os.api.star_stories import router as star_stories_router
from career_os.api.ticktick import router as ticktick_router
from career_os.api.voice import router as voice_router
from career_os.config import settings
from career_os.database import SessionLocal
from career_os.discovery.scheduler import start_scheduler, stop_scheduler
from career_os.migration.seed import seed_default_profile, seed_ghost_detection_records
from career_os.models.models import Application
from career_os.services.occupation_taxonomy import populate_occupations
from career_os.services.ticktick_scheduler import (
    start_ticktick_scheduler,
    stop_ticktick_scheduler,
)

logger = logging.getLogger(__name__)


PACKAGE_DIR = Path(__file__).resolve().parent


def _alembic_ini_candidates(pkg_dir: Path, cwd: Path) -> list[Path]:
    """Ordered alembic.ini locations, most specific first.

    In Docker the CWD is /app which already contains alembic.ini; locally the CWD
    may differ. An *installed wheel* has no repo root at all, so the packaged
    config is the last resort — migrations live in career_os/_alembic (G-1350).

    Split out so the fallback order is directly testable without a real install.
    """
    return [
        cwd / "alembic.ini",
        pkg_dir.parents[1] / "alembic.ini",  # src/../alembic.ini (repo checkout)
        pkg_dir / "_alembic.ini",  # installed wheel
    ]


def _resolve_alembic_ini(pkg_dir: Path | None = None, cwd: Path | None = None) -> Path:
    """Return the first alembic config that exists, else raise.

    Previously a miss warned and returned, which let an installed deployment run
    on an unmigrated DB and fail later as opaque 500s. A packaged config always
    ships now, so a miss means a broken install (G-1350).
    """
    pkg_dir = pkg_dir or PACKAGE_DIR
    cwd = cwd or Path.cwd()
    for candidate in _alembic_ini_candidates(pkg_dir, cwd):
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "No alembic config found (looked for alembic.ini in CWD, the repo root, "
        f"and the packaged {pkg_dir / '_alembic.ini'}). The install is incomplete "
        "— refusing to start on a possibly unmigrated database."
    )


def _auto_migrate() -> None:
    """Run Alembic migrations programmatically (upgrade head).

    Fail fast on errors so mis-configurations are caught immediately
    rather than resulting in 500s at runtime.
    """
    try:
        from alembic import command
        from alembic.config import Config

        ini_path = _resolve_alembic_ini()
        cfg = Config(str(ini_path))
        # The ini hard-codes sqlalchemy.url, so without this the app would
        # confidently migrate data/career_os.db while running against whatever
        # DATABASE_URL points at — "migration complete" on an unmigrated DB,
        # the exact failure this path exists to prevent (G-1350).
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")
        logger.info("Auto-migration complete (alembic upgrade head) using %s", ini_path)
    except Exception:
        logger.exception("Auto-migration failed")
        raise


def _startup_populate_occupations() -> None:
    """Populate the ESCO occupations taxonomy at startup (G-1351 Phase C).

    Non-fatal: a first-ever `match_occupation()` call already holding a SQLite
    write lock would otherwise latch its own lazy populate to `unknown` until
    the next process restart (Phase B review carried note); running it once
    here, eagerly, at startup makes the lazy in-`match_occupation` populate a
    fallback rather than the primary path. Any failure (e.g. a locked/
    read-only DB) is logged and swallowed — the app must still start.
    Extracted to a standalone function so it is directly unit-testable
    (drive it in isolation rather than the full lifespan generator).
    """
    db = SessionLocal()
    try:
        populate_occupations(db)
    except Exception as e:
        logger.warning("Could not populate occupation taxonomy at startup: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: auto-migrate then seed default profile on startup."""
    # 1. Run Alembic migrations (fail fast on error)
    _auto_migrate()

    # 2. Seed default profile and ghost detection records
    db = SessionLocal()
    try:
        profile = seed_default_profile(db)
        seed_ghost_detection_records(db, profile.id)
    except Exception as e:
        logger.warning("Could not seed default data: %s", e)

    # 3. Normalize existing statuses to lowercase (handles legacy/migrated data)
    try:
        all_apps = db.query(Application).all()
        fixed = 0
        for app_obj in all_apps:
            lower = app_obj.status.strip().lower()
            if app_obj.status != lower:
                app_obj.status = lower
                fixed += 1
        if fixed:
            db.commit()
            logger.info("Normalized %d application statuses to lowercase", fixed)
    except Exception as e:
        logger.warning("Could not normalize statuses: %s", e)
    finally:
        db.close()

    # 3.5. Populate the ESCO occupations taxonomy (non-fatal — see
    # _startup_populate_occupations docstring, G-1351 Phase C).
    _startup_populate_occupations()

    # 4. Start background discovery scheduler
    start_scheduler()

    # 5. Start background TickTick sync scheduler (every 15 min)
    start_ticktick_scheduler()

    yield

    # Shutdown: stop schedulers
    stop_ticktick_scheduler()
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Job Search & Career Strategy Platform",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting for OAuth endpoints
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.state.limiter = oauth_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Onboarding structured error handler — returns {error, resolution} JSON (D-10)
from career_os.errors.onboarding import OnboardingError  # noqa: E402


@app.exception_handler(OnboardingError)
async def onboarding_error_handler(request: Request, exc: OnboardingError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.user_message, "resolution": exc.resolution},
    )


# PII safety boundary error handler — returns 422 with clear user message
from career_os.ai.privacy import PrivacyError  # noqa: E402


@app.exception_handler(PrivacyError)
async def privacy_error_handler(request: Request, exc: PrivacyError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": str(exc),
            "resolution": (
                "Switch to a privacy-safe provider: Ollama (local), Anthropic, "
                "or OpenRouter with ZDR enabled. Set the AI_PROVIDER environment variable."
            ),
        },
    )


# API key auth middleware (disabled by default for local use)
from career_os.middleware import APIKeyAuthMiddleware  # noqa: E402

app.add_middleware(
    APIKeyAuthMiddleware,
    auth_enabled=settings.auth_enabled,
    auth_api_key=settings.auth_api_key,
)

# CORS middleware — added last so it wraps all other middleware
# (Starlette executes middleware in reverse-addition order).
_cors_origins: list[str] = (
    ["*"]
    if settings.frontend_url == "*"
    else [
        settings.frontend_url,
        "http://localhost:8101",
        "http://127.0.0.1:8101",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Additive: concrete chrome-extension:// origins for the browser extension
    # (Phase 0 / G-1390). This never uses "*", so it does not widen the existing
    # credentialed-wildcard risk on _cors_origins; the extension sends its token in
    # a header (not cookies) so the credentialed frontend allowance is untouched.
    allow_origin_regex=settings.extension_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ai_router)
app.include_router(analytics_router)
app.include_router(batch_router)
app.include_router(calendar_router)
app.include_router(applications_router)
app.include_router(coaching_router)
app.include_router(contacts_router)
app.include_router(discovery_router)
app.include_router(extension_router)
app.include_router(follow_ups_router)
app.include_router(gaps_router)
app.include_router(goals_router)
app.include_router(integrations_router)
app.include_router(intelligence_router)
app.include_router(interview_prep_router)
app.include_router(jobs_router)
app.include_router(learning_router)
app.include_router(market_router)
app.include_router(oauth_router)
app.include_router(onboarding_router)
app.include_router(presets_router)
app.include_router(privacy_router)
app.include_router(profiles_router)
app.include_router(pushover_router)
app.include_router(research_router)
app.include_router(scoring_router)
app.include_router(skills_router)
app.include_router(star_stories_router)
app.include_router(star_stories_app_router)
app.include_router(ticktick_router)
app.include_router(voice_router)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check with database connectivity verification."""
    from sqlalchemy import text

    from career_os.database import SessionLocal

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return JSONResponse(content={"status": "ok", "database": "connected"})
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": str(e)},
        )


# ---------------------------------------------------------------------------
# Serve built frontend static files in production mode
# ---------------------------------------------------------------------------
# When the React frontend has been built (frontend/dist exists), mount it so
# that a single FastAPI process serves both the API and the SPA.  In local
# development with Vite's dev server this directory won't exist, so this block
# is a no-op.

# Check multiple locations for the built frontend:
# 1. Development: project_root/frontend/dist (when running from repo)
# 2. pip install: package_dir/_frontend_dist (bundled in wheel)
_FRONTEND_DIR_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "frontend" / "dist",  # dev / Docker
    Path(__file__).resolve().parent / "_frontend_dist",  # pip install
]
_FRONTEND_DIR = next((d for d in _FRONTEND_DIR_CANDIDATES if d.is_dir()), None)

if _FRONTEND_DIR is not None and _FRONTEND_DIR.is_dir():
    # Serve static assets (JS, CSS, images) under /assets
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIR / "assets"),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str) -> FileResponse:
        """Catch-all: serve the SPA index.html for client-side routing."""
        file_path = _FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIR / "index.html")
