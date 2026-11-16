
import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agentops_api.config import get_settings
from agentops_api.db import engine
from agentops_api.routers.executions import router as executions_router


settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.app_name,
    description="Enterprise AI Agent Operations Platform",
    version="0.1.0",
)

app.include_router(executions_router)

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
