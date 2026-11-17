from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import Session
from agentops_api.schemas.session import SessionCreate
from agentops_api.services.tenant_scope import get_scoped_environment, scope_session_list


class SessionValidationError(Exception):
    """The request body is self-contradictory (422) - e.g. environment_id and
    project_id, each individually valid, do not actually belong together."""


class SessionNotFoundError(Exception):
    """A referenced resource does not exist, or is outside the authenticated
    key's scope (404) - indistinguishable from each other on purpose."""


def find_existing_session(
    db: DBSession,
    environment_id: UUID,
    external_session_id: str,
) -> Session | None:
    return db.execute(
        select(Session).where(
            Session.environment_id == environment_id,
            Session.external_session_id == external_session_id,
        )
    ).scalar_one_or_none()


def create_session(
    db: DBSession,
    data: SessionCreate,
    auth: AuthContext,
) -> tuple[Session, bool]:
    environment = get_scoped_environment(db, data.environment_id, auth)

    if environment is None:
        raise SessionNotFoundError("Environment not found")

    # The caller supplies both environment_id and project_id directly: never trust
    # that they agree without checking, since environment_id alone already
    # determines the owning project. environment.project_id is already known to
    # be within the authenticated scope (get_scoped_environment guarantees it),
    # so requiring equality here also transitively confirms data.project_id is.
    if environment.project_id != data.project_id:
        raise SessionValidationError(
            "Environment does not belong to the specified project"
        )

    existing = find_existing_session(
        db,
        data.environment_id,
        data.external_session_id,
    )

    if existing is not None:
        return existing, False

    session = Session(
        project_id=data.project_id,
        environment_id=data.environment_id,
        external_session_id=data.external_session_id,
        status="active",
    )

    db.add(session)
    db.flush()

    return session, True


def list_sessions(
    db: DBSession,
    *,
    auth: AuthContext,
    project_id: UUID | None = None,
    environment_id: UUID | None = None,
    session_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Session]:
    statement = select(Session).order_by(Session.created_at.desc())
    statement = scope_session_list(statement, auth)

    if project_id is not None:
        statement = statement.where(Session.project_id == project_id)

    if environment_id is not None:
        statement = statement.where(Session.environment_id == environment_id)

    if session_status is not None:
        statement = statement.where(Session.status == session_status)

    statement = statement.limit(limit).offset(offset)

    return list(db.execute(statement).scalars().all())
