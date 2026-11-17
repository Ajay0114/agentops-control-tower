
from datetime import datetime
from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import TelemetryEventRecord


def list_telemetry_events(
    db: DBSession,
    *,
    agent_id: UUID | None = None,
    execution_id: UUID | None = None,
    session_id: UUID | None = None,
    event_type: str | None = None,
    operation_status: str | None = None,
    trace_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = []

    if agent_id is not None:
        filters.append(TelemetryEventRecord.agent_id == agent_id)

    if execution_id is not None:
        filters.append(TelemetryEventRecord.execution_id == execution_id)

    if session_id is not None:
        filters.append(TelemetryEventRecord.session_id == session_id)

    if event_type is not None:
        filters.append(TelemetryEventRecord.event_type == event_type)

    if operation_status is not None:
        filters.append(
            TelemetryEventRecord.operation_status == operation_status
        )

    if trace_id is not None:
        filters.append(
            TelemetryEventRecord.trace_id == trace_id.lower()
        )

    if start_time is not None:
        filters.append(TelemetryEventRecord.occurred_at >= start_time)

    if end_time is not None:
        filters.append(TelemetryEventRecord.occurred_at <= end_time)

    total = db.scalar(
        select(func.count())
        .select_from(TelemetryEventRecord)
        .where(*filters)
    )

    statement = (
        select(TelemetryEventRecord)
        .where(*filters)
        .order_by(
            TelemetryEventRecord.occurred_at.desc(),
            TelemetryEventRecord.received_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = db.scalars(statement).all()

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil((total or 0) / page_size),
    }


def get_telemetry_event(
    db: DBSession,
    event_id: UUID,
) -> TelemetryEventRecord | None:
    return db.execute(
        select(TelemetryEventRecord).where(
            TelemetryEventRecord.event_id == event_id
        )
    ).scalar_one_or_none()
