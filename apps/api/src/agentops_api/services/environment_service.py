from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import Environment
from agentops_api.schemas.environment import EnvironmentCreate, EnvironmentUpdate
from agentops_api.services.tenant_scope import get_scoped_project, scope_environment_list


class EnvironmentValidationError(Exception):
    pass


def create_environment(
    db: DBSession,
    data: EnvironmentCreate,
    auth: AuthContext,
) -> Environment:
    # Creating an environment is a project-level operation: a key restricted to
    # one specific environment has no standing to create a sibling, even inside
    # the same project, so it is rejected before any lookup.
    if auth.environment_id is not None:
        raise EnvironmentValidationError("Project not found")

    project = get_scoped_project(db, data.project_id, auth)

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
    auth: AuthContext,
    project_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Environment]:
    statement = select(Environment).order_by(Environment.created_at.desc())
    statement = scope_environment_list(statement, auth)

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
