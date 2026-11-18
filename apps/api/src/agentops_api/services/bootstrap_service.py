"""Idempotent, concurrency-safe first-run local bootstrap.

Ensures an Organization, Project, Environment, and one "internal" ApiKey
exist for local development - reusing the exact same models and services
every other part of the platform already uses (api_key_service.create_api_key,
direct ORM creation for Organization/Project/Environment, the same pattern
provision_api_key.py's own CLI already uses for the same reason: there is no
AuthContext yet to call the AuthContext-based environment_service with).

Safe to call on every backend startup, and safe under concurrent callers
(e.g. multiple uvicorn workers starting together): each step checks for an
existing row by a well-known slug/name before inserting, and if a concurrent
caller wins the race, the unique constraint on that column causes this
call's insert to fail, which is caught and turned into a lookup of the
winner's row rather than an error. See main.py's startup hook and
scripts/bootstrap_local_dev.py for the two ways this gets invoked.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import ApiKey, Environment, Organization, Project
from agentops_api.services.api_key_service import create_api_key, revoke_api_key


logger = logging.getLogger(__name__)

_T = TypeVar("_T")

MAX_RACE_RETRIES = 3


def _get_or_create(
    db: DBSession,
    *,
    lookup: Callable[[], Select],
    build: Callable[[], object],
) -> _T:
    """Shared check-then-insert-with-retry for every row this module
    bootstraps. A concurrent caller winning the race surfaces either as an
    IntegrityError (the expected case - a unique constraint on the slug/
    name column this looks up by) or, rarely, as an OperationalError if
    Postgres detects a deadlock between the two concurrent inserts -
    either way, the fix is the same: roll back this attempt's failed insert
    and re-query, since the winning row is now visible.
    """
    existing = db.execute(lookup()).scalar_one_or_none()

    if existing is not None:
        return existing

    for attempt in range(MAX_RACE_RETRIES):
        row = build()
        db.add(row)

        try:
            db.flush()
            return row
        except (IntegrityError, OperationalError):
            db.rollback()
            existing = db.execute(lookup()).scalar_one_or_none()

            if existing is not None:
                return existing

            if attempt < MAX_RACE_RETRIES - 1:
                time.sleep(0.05 * (attempt + 1))

    raise RuntimeError("Could not create or find the expected row after several attempts")


LOCAL_ORGANIZATION_SLUG = "local-default"
LOCAL_PROJECT_SLUG = "local-default"
LOCAL_ENVIRONMENT_SLUG = "development"

# Reserved name identifying the one internal dashboard key - never a name a
# platform user could give their own integration key through the dashboard
# UI (that form only ever creates key_type="integration" rows), so this is
# safe to use as a lookup marker without a dedicated "is the default one"
# boolean column.
INTERNAL_KEY_NAME = "__internal_dashboard_key__"


@dataclass(frozen=True)
class BootstrapResult:
    organization_id: UUID
    project_id: UUID
    environment_id: UUID
    api_key_id: UUID
    # Only set when THIS call just created a new internal key - None when an
    # existing one was simply found, since the raw value is never
    # recoverable once created. See rotate_internal_key for lost-key recovery.
    raw_api_key: str | None


def _get_or_create_organization(db: DBSession) -> Organization:
    return _get_or_create(
        db,
        lookup=lambda: select(Organization).where(Organization.slug == LOCAL_ORGANIZATION_SLUG),
        build=lambda: Organization(name="Local Development", slug=LOCAL_ORGANIZATION_SLUG),
    )


def _get_or_create_project(db: DBSession, organization_id: UUID) -> Project:
    return _get_or_create(
        db,
        lookup=lambda: select(Project).where(
            Project.organization_id == organization_id,
            Project.slug == LOCAL_PROJECT_SLUG,
        ),
        build=lambda: Project(
            organization_id=organization_id, name="Local Development", slug=LOCAL_PROJECT_SLUG
        ),
    )

    return project


def _get_or_create_environment(db: DBSession, project_id: UUID) -> Environment:
    return _get_or_create(
        db,
        lookup=lambda: select(Environment).where(
            Environment.project_id == project_id,
            Environment.slug == LOCAL_ENVIRONMENT_SLUG,
        ),
        build=lambda: Environment(
            project_id=project_id,
            name="Development",
            slug=LOCAL_ENVIRONMENT_SLUG,
            description="Local development environment, created by the first-run bootstrap.",
        ),
    )


def _find_internal_key(db: DBSession, organization_id: UUID) -> ApiKey | None:
    return db.execute(
        select(ApiKey).where(
            ApiKey.organization_id == organization_id,
            ApiKey.name == INTERNAL_KEY_NAME,
            ApiKey.key_type == "internal",
            ApiKey.status == "active",
        )
    ).scalar_one_or_none()


def _get_or_create_internal_key(
    db: DBSession, organization_id: UUID, project_id: UUID, environment_id: UUID
) -> tuple[ApiKey, str | None]:
    existing = _find_internal_key(db, organization_id)

    if existing is not None:
        return existing, None

    try:
        record, raw_key = create_api_key(
            db,
            organization_id=organization_id,
            project_id=project_id,
            environment_id=environment_id,
            name=INTERNAL_KEY_NAME,
            key_type="internal",
        )
        return record, raw_key
    except (IntegrityError, OperationalError, RuntimeError):
        # A concurrent caller won the race: create_api_key's own
        # key_prefix-collision retry loop doesn't know about (and can't fix)
        # the one-internal-key-per-organization unique index below, so it
        # exhausts its attempts and raises - the fix here is the same as
        # every other _get_or_create step's: roll back and look up the
        # winner's row, which is now visible.
        db.rollback()
        winner = _find_internal_key(db, organization_id)

        if winner is None:
            raise

        return winner, None


def ensure_local_bootstrap(db: DBSession) -> BootstrapResult:
    """Call once per process (or on every startup - it's idempotent).

    Commits after each step rather than once at the end: create_api_key's
    own (extremely rare) prefix-collision retry calls db.rollback(), which
    would otherwise also discard this call's earlier, still-uncommitted
    organization/project/environment inserts.
    """
    organization = _get_or_create_organization(db)
    db.commit()

    project = _get_or_create_project(db, organization.id)
    db.commit()

    environment = _get_or_create_environment(db, project.id)
    db.commit()

    api_key_record, raw_key = _get_or_create_internal_key(
        db, organization.id, project.id, environment.id
    )
    db.commit()

    if raw_key is not None:
        logger.info(
            "Local bootstrap: created the internal dashboard API key (id=%s). "
            "The raw value is never logged.",
            api_key_record.id,
        )

    return BootstrapResult(
        organization_id=organization.id,
        project_id=project.id,
        environment_id=environment.id,
        api_key_id=api_key_record.id,
        raw_api_key=raw_key,
    )


def try_write_frontend_env_local(raw_key: str, backend_url: str) -> bool:
    """Best-effort, local-dev-only convenience: writes the internal key into
    apps/frontend/.env.local so a first-time user never has to do this by
    hand. Returns False (never raises) if the frontend directory can't be
    found or the file can't be written - callers must fall back to pointing
    the operator at scripts/bootstrap_local_dev.py instead. Merges into any
    existing file rather than overwriting it, and never logs the raw key.

    Only call this with a freshly-created key (ensure_local_bootstrap's
    raw_api_key is not None) - there is nothing to write when an existing
    key was simply found, since its raw value isn't available to re-write.
    """
    try:
        # apps/api/src/agentops_api/services/bootstrap_service.py -> repo root
        repo_root = Path(__file__).resolve().parents[5]
        frontend_dir = repo_root / "apps" / "frontend"

        if not frontend_dir.is_dir():
            return False

        env_path = frontend_dir / ".env.local"
        existing_lines: dict[str, str] = {}

        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, _, value = stripped.partition("=")
                existing_lines[key.strip()] = value

        existing_lines["BACKEND_API_URL"] = backend_url
        existing_lines["AGENTOPS_API_KEY"] = raw_key

        content = "\n".join(f"{key}={value}" for key, value in existing_lines.items()) + "\n"
        env_path.write_text(content, encoding="utf-8")

        return True
    except OSError:
        logger.warning(
            "Could not write apps/frontend/.env.local automatically. "
            "Run scripts/bootstrap_local_dev.py to provision it manually "
            "(the raw key is never logged)."
        )
        return False


def rotate_internal_key(
    db: DBSession, *, organization_id: UUID, project_id: UUID, environment_id: UUID
) -> tuple[ApiKey, str]:
    """Recovery path for a lost internal key (e.g. .env.local deleted or
    corrupted): revokes whatever internal key currently exists for this
    organization and mints a fresh one. Revocation followed by creation is
    the only correct way to "regenerate" a key - see api_key_service.py's
    module docstring: the raw value is never recoverable once created, so
    there is nothing to retrieve, only something to replace.
    """
    existing = _find_internal_key(db, organization_id)

    if existing is not None:
        revoke_api_key(db, existing)
        db.commit()

    record, raw_key = create_api_key(
        db,
        organization_id=organization_id,
        project_id=project_id,
        environment_id=environment_id,
        name=INTERNAL_KEY_NAME,
        key_type="internal",
    )
    db.commit()

    return record, raw_key
