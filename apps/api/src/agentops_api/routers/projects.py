from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext, get_auth_context
from agentops_api.db import get_db
from agentops_api.schemas.project import ProjectCreate, ProjectResponse
from agentops_api.services.organization_service import (
    OrganizationValidationError,
    create_project,
)


router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    data: ProjectCreate,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    try:
        project = create_project(db, name=data.name, auth=auth)

        db.commit()
        db.refresh(project)

        return project

    except OrganizationValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
