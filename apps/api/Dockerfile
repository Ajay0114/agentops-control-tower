# Build context is apps/api itself (see docker-compose.yml) - this image is
# the backend only, with no dependency on anything outside this directory.
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg[binary]'s wheel and a healthcheck-friendly curl.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

# Editable install isn't meaningful in an image with no later code changes,
# so install the package normally - pulls in fastapi/uvicorn/sqlalchemy/
# psycopg/alembic/argon2-cffi per pyproject.toml. No [dev] extras (pytest/
# ruff/httpx) in the runtime image.
RUN pip install --no-cache-dir .

COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

EXPOSE 8010

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8010/health/live || exit 1

# Applies pending migrations, then starts the API - safe to run on every
# container start, including repeated ones (alembic upgrade head is a
# no-op once the database is already current).
CMD alembic upgrade head && uvicorn agentops_api.main:app --host 0.0.0.0 --port 8010
