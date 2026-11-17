from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import Agent, AgentVersion, Environment
from agentops_api.schemas.agent import AgentCreate, AgentUpdate, AgentVersionCreate


class AgentValidationError(Exception):
    pass


def create_agent(db: DBSession, data: AgentCreate) -> Agent:
    environment = db.get(Environment, data.environment_id)

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
    environment_id: UUID | None = None,
    agent_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Agent]:
    statement = select(Agent).order_by(Agent.created_at.desc())

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
    limit: int = 50,
    offset: int = 0,
) -> list[AgentVersion]:
    statement = (
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.execute(statement).scalars().all())


def get_agent_version(
    db: DBSession,
    agent_id: UUID,
    version_id: UUID,
) -> AgentVersion | None:
    return db.execute(
        select(AgentVersion).where(
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent_id,
        )
    ).scalar_one_or_none()
