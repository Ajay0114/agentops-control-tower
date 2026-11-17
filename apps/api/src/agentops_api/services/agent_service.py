from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import Agent, AgentVersion
from agentops_api.schemas.agent import AgentCreate, AgentUpdate, AgentVersionCreate
from agentops_api.services.tenant_scope import (
    get_scoped_environment,
    scope_agent_list,
    scope_agent_version_list,
)


class AgentValidationError(Exception):
    pass


def create_agent(db: DBSession, data: AgentCreate, auth: AuthContext) -> Agent:
    environment = get_scoped_environment(db, data.environment_id, auth)

    if environment is None:
        raise AgentValidationError("Environment not found")

    agent = Agent(
        environment_id=environment.id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        framework=data.framework,
    )

    db.add(agent)
    db.flush()

    return agent


def list_agents(
    db: DBSession,
    *,
    auth: AuthContext,
    environment_id: UUID | None = None,
    agent_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Agent]:
    statement = select(Agent).order_by(Agent.created_at.desc())
    statement = scope_agent_list(statement, auth)

    if environment_id is not None:
        statement = statement.where(Agent.environment_id == environment_id)

    if agent_status is not None:
        statement = statement.where(Agent.status == agent_status)

    statement = statement.limit(limit).offset(offset)

    return list(db.execute(statement).scalars().all())


def update_agent(db: DBSession, agent: Agent, data: AgentUpdate) -> Agent:
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(agent, field, value)

    db.flush()

    return agent


def create_agent_version(
    db: DBSession,
    agent: Agent,
    data: AgentVersionCreate,
) -> AgentVersion:
    version = AgentVersion(
        agent_id=agent.id,
        version=data.version,
        description=data.description,
        configuration=data.configuration,
    )

    db.add(version)
    db.flush()

    return version


def list_agent_versions(
    db: DBSession,
    agent_id: UUID,
    *,
    auth: AuthContext,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentVersion]:
    statement = (
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.created_at.desc())
    )
    statement = scope_agent_version_list(statement, auth)
    statement = statement.limit(limit).offset(offset)

    return list(db.execute(statement).scalars().all())
