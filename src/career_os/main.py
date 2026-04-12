"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from career_os.api.ai import router as ai_router
from career_os.api.analytics import router as analytics_router
from career_os.api.applications import router as applications_router
from career_os.api.calendar import router as calendar_router
from career_os.api.coaching import router as coaching_router
from career_os.api.contacts import router as contacts_router
from career_os.api.discovery import router as discovery_router
from career_os.api.follow_ups import router as follow_ups_router
from career_os.api.gaps import router as gaps_router
from career_os.api.goals import router as goals_router
from career_os.api.integrations import router as integrations_router
from career_os.api.intelligence import router as intelligence_router
from career_os.api.interview_prep import router as interview_prep_router
from career_os.api.jobs import router as jobs_router
from career_os.api.learning import router as learning_router
from career_os.api.market import router as market_router
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
from career_os.services.ticktick_scheduler import (
    start_ticktick_scheduler,
    stop_ticktick_scheduler,
)

logger = logging.getLogger(__name__)


def _auto_migrate() -> None:
    """Run Alembic migrations programmatically (upgrade head).

    Fail fast on errors so mis-configurations are caught immediately
    rather than resulting in 500s at runtime.
    """
    try:
        from alembic import command
        from alembic.config import Config

        # Resolve alembic.ini relative to the project root.
        # In Docker the CWD is /app which already contains alembic.ini.
        # Locally, the CWD may differ, so try a few common locations.
        candidates = [
            Path.cwd() / "alembic.ini",
            Path(__file__).resolve().parents[2] / "alembic.ini",  # src/../alembic.ini
        ]
        ini_path: Path | None = None
        for candidate in candidates:
            if candidate.is_file():
                ini_path = candidate
                break

        if ini_path is None:
            logger.warning("alembic.ini not found — skipping auto-migration")
            return

        cfg = Config(str(ini_path))
        command.upgrade(cfg, "head")
        logger.info("Auto-migration complete (alembic upgrade head)")
    except Exception:
        logger.exception("Auto-migration failed")
        raise


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
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for frontend
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth middleware (disabled by default for local use)
from career_os.middleware import APIKeyAuthMiddleware  # noqa: E402

app.add_middleware(
    APIKeyAuthMiddleware,
    auth_enabled=settings.auth_enabled,
    auth_api_key=settings.auth_api_key,
)

# Include routers
app.include_router(ai_router)
app.include_router(analytics_router)
app.include_router(calendar_router)
app.include_router(applications_router)
app.include_router(coaching_router)
app.include_router(contacts_router)
app.include_router(discovery_router)
app.include_router(follow_ups_router)
app.include_router(gaps_router)
app.include_router(goals_router)
app.include_router(integrations_router)
app.include_router(intelligence_router)
app.include_router(interview_prep_router)
app.include_router(jobs_router)
app.include_router(learning_router)
app.include_router(market_router)
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
async def health_check() -> dict:
    """Health check with database connectivity verification."""
    from sqlalchemy import text

    from career_os.database import SessionLocal

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        from fastapi.responses import JSONResponse

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
