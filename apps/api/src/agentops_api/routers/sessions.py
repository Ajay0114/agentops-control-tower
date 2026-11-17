from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.db import get_db
from agentops_api.models.core import Session
from agentops_api.schemas.session import SessionCreate, SessionResponse
from agentops_api.services.session_service import (
    SessionValidationError,
    create_session,
    find_existing_session,
    list_sessions,
)


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session_endpoint(
    data: SessionCreate,
    response: Response,
    db: DBSession = Depends(get_db),
):
    try:
        session, created = create_session(db, data)

        db.commit()
        db.refresh(session)

        response.status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

        return session

    except SessionValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    except IntegrityError:
        db.rollback()

        # Recover from a concurrent duplicate request.
        existing = find_existing_session(
            db,
            data.environment_id,
            data.external_session_id,
        )

        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

        raise HTTPException(
            status_code=409,
            detail="Session conflicts with an existing record",
        )


@router.get("", response_model=list[SessionResponse])
def list_sessions_endpoint(
    project_id: UUID | None = None,
    environment_id: UUID | None = None,
    session_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
):
    return list_sessions(
        db,
        project_id=project_id,
        environment_id=environment_id,
        session_status=session_status,
        limit=limit,
        offset=offset,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, db: DBSession = Depends(get_db)):
    session = db.get(Session, session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session
