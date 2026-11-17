from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import Environment, Session
from agentops_api.schemas.session import SessionCreate


class SessionValidationError(Exception):
    pass


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
) -> tuple[Session, bool]:
    environment = db.get(Environment, data.environment_id)

    if environment is None:
        raise SessionValidationError("Environment not found")

    # The caller supplies both environment_id and project_id directly: never trust
    # that they agree without checking, since environment_id alone already
    # determines the owning project.
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
    project_id: UUID | None = None,
    environment_id: UUID | None = None,
    session_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Session]:
    statement = select(Session).order_by(Session.created_at.desc())

    if project_id is not None:
        statement = statement.where(Session.project_id == project_id)

    if environment_id is not None:
        statement = statement.where(Session.environment_id == environment_id)

    if session_status is not None:
        statement = statement.where(Session.status == session_status)

    statement = statement.limit(limit).offset(offset)

    return list(db.execute(statement).scalars().all())
