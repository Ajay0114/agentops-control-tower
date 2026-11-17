from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import Environment, Project
from agentops_api.schemas.environment import EnvironmentCreate, EnvironmentUpdate


class EnvironmentValidationError(Exception):
    pass


def create_environment(
    db: DBSession,
    data: EnvironmentCreate,
) -> Environment:
    project = db.get(Project, data.project_id)

    if project is None:
        raise EnvironmentValidationError("Project not found")

    environment = Environment(
        project_id=project.id,
        name=data.name,
        slug=data.slug,
        description=data.description,
    )

    db.add(environment)
    db.flush()

    return environment


def list_environments(
    db: DBSession,
    *,
    project_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Environment]:
    statement = select(Environment).order_by(Environment.created_at.desc())

    if project_id is not None:
        statement = statement.where(Environment.project_id == project_id)

    statement = statement.limit(limit).offset(offset)

    return list(db.execute(statement).scalars().all())


def update_environment(
    db: DBSession,
    environment: Environment,
    data: EnvironmentUpdate,
) -> Environment:
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(environment, field, value)

    db.flush()

    return environment
