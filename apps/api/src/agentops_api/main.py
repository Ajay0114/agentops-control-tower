
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agentops_api.config import get_settings
from agentops_api.db import SessionLocal, engine
from agentops_api.routers.agents import router as agents_router
from agentops_api.routers.auth import router as auth_router
from agentops_api.routers.dashboard import router as dashboard_router
from agentops_api.routers.environments import router as environments_router
from agentops_api.routers.executions import router as executions_router
from agentops_api.routers.projects import router as projects_router
from agentops_api.routers.sessions import router as sessions_router
from agentops_api.routers.telemetry import router as telemetry_router
from agentops_api.services.bootstrap_service import (
    ensure_local_bootstrap,
    try_write_frontend_env_local,
)
from fastapi.middleware.cors import CORSMiddleware


settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Local-only, zero-manual-steps first-run bootstrap: ensures an
    # organization/project/environment/internal API key exist, and - best
    # effort - provisions that key into the dashboard's own .env.local. Gated
    # on app_env == "local" so this never runs (and never could run) against
    # a real deployment; nothing here is reachable by a browser request. See
    # docs/architecture/m7-dashboard-and-auth.md and
    # services/bootstrap_service.py.
    #
    # Also skipped under pytest: TestClient(app)'s `with` block runs this
    # same lifespan, but via the module-level SessionLocal - NOT through
    # conftest.py's dependency_overrides, which only redirect FastAPI's own
    # Depends(get_db) resolution for route handlers, not a direct import
    # used here. Without this guard, every test using the `client` fixture
    # would bootstrap real rows into the actual local Postgres database
    # instead of the isolated agentops_test one.
    if settings.app_env == "local" and "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            with SessionLocal() as db:
                result = ensure_local_bootstrap(db)

            if result.raw_api_key is not None:
                # uvicorn's bind port is a CLI-level concern, not part of
                # Settings - localhost:8010 matches every documented local
                # setup command (README, docs/architecture/*.md).
                written = try_write_frontend_env_local(
                    result.raw_api_key, "http://localhost:8010"
                )
                if written:
                    logger.info(
                        "Local bootstrap: provisioned apps/frontend/.env.local automatically."
                    )
                else:
                    logger.warning(
                        "Local bootstrap created a new internal API key but could not "
                        "write apps/frontend/.env.local automatically. Run "
                        "`python apps/api/scripts/bootstrap_local_dev.py` to provision it."
                    )
        except Exception:
            logger.exception(
                "Local bootstrap failed - the dashboard may need "
                "`python apps/api/scripts/bootstrap_local_dev.py` run manually."
            )

    yield


app = FastAPI(
    title=settings.app_name,
    description="Enterprise AI Agent Operations Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(environments_router)
app.include_router(projects_router)
app.include_router(agents_router)
app.include_router(sessions_router)
app.include_router(executions_router)
app.include_router(telemetry_router)
app.include_router(auth_router)
app.include_router(dashboard_router)

@app.get("/", tags=["platform"])
def root():

    return {
        "application": settings.app_name,
        "environment": settings.app_env,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health/live", tags=["health"])
def liveness():

    return {
        "status": "alive",
    }


@app.get("/health/ready", tags=["health"])
def readiness():

    try:

        with engine.connect() as connection:

            connection.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "dependencies": {
                "database": "connected",
            },
        }

    except SQLAlchemyError:

        logger.exception("Database readiness check failed")

        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "dependencies": {
                    "database": "unavailable",
                },
            },
        )
