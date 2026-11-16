
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.db import get_db
from agentops_api.models.core import Execution
from agentops_api.schemas.execution import (
    ExecutionCreate,
    ExecutionResponse,
    ExecutionTransition,
)
from agentops_api.services.execution_service import (
    ExecutionIdempotencyConflictError,
    ExecutionNotFoundError,
    ExecutionValidationError,
    InvalidExecutionTransitionError,
    create_execution,
    find_existing_execution,
    transition_execution,
    validate_idempotent_request,
)


router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


@router.post(
    "",
    response_model=ExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_execution_endpoint(
    data: ExecutionCreate,
    response: Response,
    db: DBSession = Depends(get_db),
):
    try:
        execution, created = create_execution(db, data)

        db.commit()
        db.refresh(execution)

        response.status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

        return execution

    except ExecutionValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    except ExecutionIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))

    except IntegrityError:
        db.rollback()

        # Recover from a concurrent duplicate request.
        if data.external_execution_id is not None:
            existing = find_existing_execution(
                db,
                data.session_id,
                data.external_execution_id,
            )

            if existing is not None:
                try:
                    validate_idempotent_request(existing, data)
                except ExecutionIdempotencyConflictError as exc:
                    raise HTTPException(status_code=409, detail=str(exc))

                response.status_code = status.HTTP_200_OK
                return existing

        raise HTTPException(
            status_code=409,
            detail="Execution conflicts with an existing record",
        )


@router.get("", response_model=list[ExecutionResponse])
def list_executions(
    session_id: UUID | None = None,
    agent_id: UUID | None = None,
    execution_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
):
    statement = select(Execution).order_by(Execution.created_at.desc())

    if session_id is not None:
        statement = statement.where(Execution.session_id == session_id)

    if agent_id is not None:
        statement = statement.where(Execution.agent_id == agent_id)

    if execution_status is not None:
        statement = statement.where(Execution.status == execution_status)

    statement = statement.limit(limit).offset(offset)

    return db.execute(statement).scalars().all()


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(
    execution_id: UUID,
    db: DBSession = Depends(get_db),
):
    execution = db.get(Execution, execution_id)

    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    return execution


@router.patch(
    "/{execution_id}/status",
    response_model=ExecutionResponse,
)
def update_execution_status(
    execution_id: UUID,
    data: ExecutionTransition,
    db: DBSession = Depends(get_db),
):
    try:
        execution = transition_execution(db, execution_id, data)
        db.commit()
        db.refresh(execution)
        return execution

    except ExecutionNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    except InvalidExecutionTransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Execution update conflicts with database constraints",
        )
