
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TelemetryEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    event_id: UUID
    schema_version: str
    event_type: str
    occurred_at: datetime
    received_at: datetime

    agent_id: UUID
    agent_version_id: UUID | None
    session_id: UUID
    execution_id: UUID

    source_platform: str
    service_name: str
    environment: str

    operation_name: str
    operation_kind: str
    operation_status: str
    duration_ms: int | None

    trace_id: str
    span_id: str
    parent_span_id: str | None

    model_usage: dict[str, Any] | None
    error: dict[str, Any] | None
    payload: dict[str, Any] | None
    attributes: dict[str, Any]

    event_data: dict[str, Any]


class TelemetryEventListResponse(BaseModel):
    items: list[TelemetryEventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
