from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext, get_auth_context
from agentops_api.db import get_db
from agentops_api.schemas.agent import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
)
from agentops_api.services.agent_service import (
    AgentValidationError,
    create_agent,
    create_agent_version,
    list_agent_versions,
    list_agents,
    update_agent,
)
from agentops_api.services.tenant_scope import get_scoped_agent, get_scoped_agent_version


router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent_endpoint(
    data: AgentCreate,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    try:
        agent = create_agent(db, data, auth)

        db.commit()
        db.refresh(agent)

        return agent

    except AgentValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An agent with this slug already exists for the environment",
        )


@router.get("", response_model=list[AgentResponse])
def list_agents_endpoint(
    environment_id: UUID | None = None,
    agent_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return list_agents(
        db,
        auth=auth,
        environment_id=environment_id,
        agent_status=agent_status,
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: UUID,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    agent = get_scoped_agent(db, agent_id, auth)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent_endpoint(
    agent_id: UUID,
    data: AgentUpdate,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    agent = get_scoped_agent(db, agent_id, auth)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = update_agent(db, agent, data)

    db.commit()
    db.refresh(agent)

    return agent


@router.post(
    "/{agent_id}/versions",
    response_model=AgentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_version_endpoint(
    agent_id: UUID,
    data: AgentVersionCreate,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    agent = get_scoped_agent(db, agent_id, auth)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        version = create_agent_version(db, agent, data)

        db.commit()
        db.refresh(version)

        return version

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This version already exists for the agent",
        )


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
def list_agent_versions_endpoint(
    agent_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    agent = get_scoped_agent(db, agent_id, auth)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return list_agent_versions(db, agent_id, auth=auth, limit=limit, offset=offset)


@router.get(
    "/{agent_id}/versions/{version_id}",
    response_model=AgentVersionResponse,
)
def get_agent_version_endpoint(
    agent_id: UUID,
    version_id: UUID,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    version = get_scoped_agent_version(db, agent_id, version_id, auth)

    if version is None:
        raise HTTPException(status_code=404, detail="Agent version not found")

    return version
