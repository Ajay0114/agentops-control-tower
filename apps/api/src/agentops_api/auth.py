"""Reusable FastAPI authentication dependency.

Every future protected endpoint depends on ``get_auth_context`` to obtain a
trusted :class:`AuthContext`. Nothing downstream may trust an
``organization_id``/``project_id``/``environment_id`` taken from a request body
or query string - the values on ``AuthContext`` are the only tenant identity
a protected endpoint or service may rely on.

This module does not scope any resource query itself - wiring ``AuthContext``
into the registry/execution/telemetry routers and services is Milestone 5-D.

One exception: an API key may be restricted to an ``environment_id`` without
an explicit ``project_id`` (M5-B allows creating such a key). Since
``environment_id`` always implies a single owning project, ``AuthContext``
derives that project here, once, so every downstream project-scope check can
simply read ``AuthContext.project_id`` without re-deriving it. The derivation
fails closed: if the environment cannot be loaded, authentication fails
entirely rather than ever falling back to treating the key as project- or
organization-unrestricted.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from agentops_api.db import SessionLocal, get_db
from agentops_api.models.core import ApiKey, Environment
from agentops_api.services.api_key_service import touch_last_used, verify_api_key


logger = logging.getLogger(__name__)

# Deliberately generic and identical for every failure mode - a missing header,
# a malformed header, an unknown key, a revoked key and an expired key must
# all be indistinguishable from the outside.
AUTHENTICATION_ERROR_DETAIL = "Invalid or missing API key"


@dataclass(frozen=True)
class AuthContext:
    """The trusted identity of the caller, derived solely from a verified API key."""

    api_key_id: UUID
    organization_id: UUID
    project_id: UUID | None
    environment_id: UUID | None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=AUTHENTICATION_ERROR_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized()

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()

    return token


def _run_touch_last_used(api_key_id: UUID) -> None:
    """Runs in a FastAPI BackgroundTask, after the response has been sent.

    Opens its own session rather than reusing the request-scoped one, which
    ``get_db`` will have already closed by the time this runs.
    """
    db = SessionLocal()

    try:
        touch_last_used(db, api_key_id)
    except Exception:
        # Never let a best-effort bookkeeping write surface as a request
        # failure, or raise after the response is already gone. Logged without
        # the key itself - only its id is in scope here.
        logger.exception("Failed to update last_used_at for api_key_id=%s", api_key_id)
    finally:
        db.close()


def _effective_project_id(db: DBSession, record: ApiKey) -> UUID | None:
    """The project this key is confined to, deriving it from environment_id
    when the key itself only stores an environment restriction.

    Fails closed: if the key has environment_id set but no project_id, and the
    environment cannot be loaded, raises 401 rather than returning None (which
    would be misread downstream as "no project restriction").
    """
    if record.environment_id is None or record.project_id is not None:
        return record.project_id

    environment = db.get(Environment, record.environment_id)

    if environment is None:
        raise _unauthorized()

    return environment.project_id


def get_auth_context(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
) -> AuthContext:
    """FastAPI dependency: authenticate the request and return a trusted context.

    Raises HTTP 401 for any failure - missing header, malformed header, unknown
    key, wrong secret, revoked key, expired key, or an unresolvable scope
    restriction - with the same generic detail message in every case.
    """
    raw_key = _extract_bearer_token(authorization)

    record = verify_api_key(db, raw_key)

    if record is None:
        raise _unauthorized()

    project_id = _effective_project_id(db, record)

    background_tasks.add_task(_run_touch_last_used, record.id)

    return AuthContext(
        api_key_id=record.id,
        organization_id=record.organization_id,
        project_id=project_id,
        environment_id=record.environment_id,
    )
