
from uuid import UUID
from datetime import datetime
from fastapi import Query

from agentops_api.schemas.telemetry_query import (
    TelemetryEventListResponse,
    TelemetryEventResponse,
)
from agentops_api.services.telemetry_query_service import (
    get_telemetry_event,
    list_telemetry_events,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext, get_auth_context
from agentops_api.db import get_db
from agentops_api.schemas.telemetry import (
    TelemetryEvent,
    TelemetryIngestResponse,
)
from agentops_api.services.telemetry_service import (
    TelemetryIdempotencyConflictError,
    TelemetryNotFoundError,
    TelemetryValidationError,
    find_existing_telemetry_event,
    ingest_telemetry_event,
    validate_idempotent_telemetry_event,
)
from agentops_api.services.tenant_scope import get_scoped_execution



router = APIRouter(
    prefix="/api/v1/telemetry",
    tags=["telemetry"],
)


@router.post(
    "/events",
    response_model=TelemetryIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_telemetry_endpoint(
    data: TelemetryEvent,
    response: Response,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    try:
        record, created = ingest_telemetry_event(db, data, auth)

        db.commit()
        db.refresh(record)

        response.status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

        return TelemetryIngestResponse(
            id=record.id,
            event_id=record.event_id,
            organization_id=record.organization_id,
            event_type=record.event_type,
            occurred_at=record.occurred_at,
            received_at=record.received_at,
            created=created,
        )

    except TelemetryNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except TelemetryValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except TelemetryIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        # Recover from a concurrent duplicate event submission.
        try:
            existing = find_existing_telemetry_event(
                db,
                auth,
                data.event_id,
            )

            if existing is not None:
                validate_idempotent_telemetry_event(
                    existing,
                    data.model_dump(mode="json"),
                )

                response.status_code = status.HTTP_200_OK

                return TelemetryIngestResponse(
                    id=existing.id,
                    event_id=existing.event_id,
                    organization_id=existing.organization_id,
                    event_type=existing.event_type,
                    occurred_at=existing.occurred_at,
                    received_at=existing.received_at,
                    created=False,
                )

        except (TelemetryNotFoundError, TelemetryValidationError):
            pass

        except TelemetryIdempotencyConflictError as conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(conflict),
            ) from conflict

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telemetry event conflicts with an existing record or database constraint",
        ) from exc



@router.get(
    "/events",
    response_model=TelemetryEventListResponse,
)
def list_telemetry_events_endpoint(
    agent_id: UUID | None = None,
    execution_id: UUID | None = None,
    session_id: UUID | None = None,
    event_type: str | None = None,
    operation_status: str | None = None,
    trace_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must be earlier than or equal to end_time",
        )

    return list_telemetry_events(
        db,
        auth,
        agent_id=agent_id,
        execution_id=execution_id,
        session_id=session_id,
        event_type=event_type,
        operation_status=operation_status,
        trace_id=trace_id,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/events/{event_id}",
    response_model=TelemetryEventResponse,
)
def get_telemetry_event_endpoint(
    event_id: UUID,
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    record = get_telemetry_event(db, event_id, auth)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telemetry event not found",
        )

    return record


@router.get(
    "/executions/{execution_id}/events",
    response_model=TelemetryEventListResponse,
)
def get_execution_telemetry_endpoint(
    execution_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    execution = get_scoped_execution(db, execution_id, auth)

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    return list_telemetry_events(
        db,
        auth,
        execution_id=execution_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/traces/{trace_id}/events",
    response_model=TelemetryEventListResponse,
)
def get_trace_telemetry_endpoint(
    trace_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return list_telemetry_events(
        db,
        auth,
        trace_id=trace_id,
        page=page,
        page_size=page_size,
    )
