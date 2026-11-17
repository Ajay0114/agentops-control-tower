from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext, get_auth_context
from agentops_api.db import get_db
from agentops_api.schemas.environment import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
)
from agentops_api.services.environment_service import (
    EnvironmentValidationError,
    create_environment,
    list_environments,
    update_environment,
)
from agentops_api.services.tenant_scope import get_scoped_environment


router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


@router.post(
    "",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_environment_endpoint(
    data: EnvironmentCreate,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    try:
        environment = create_environment(db, data, auth)

        db.commit()
        db.refresh(environment)

        return environment

    except EnvironmentValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An environment with this slug already exists for the project",
        )


@router.get("", response_model=list[EnvironmentResponse])
def list_environments_endpoint(
    project_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return list_environments(
        db, auth=auth, project_id=project_id, limit=limit, offset=offset
    )


@router.get("/{environment_id}", response_model=EnvironmentResponse)
def get_environment(
    environment_id: UUID,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    environment = get_scoped_environment(db, environment_id, auth)

    if environment is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    return environment


@router.patch("/{environment_id}", response_model=EnvironmentResponse)
def update_environment_endpoint(
    environment_id: UUID,
    data: EnvironmentUpdate,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    environment = get_scoped_environment(db, environment_id, auth)

    if environment is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    environment = update_environment(db, environment, data)

    db.commit()
    db.refresh(environment)

    return environment
