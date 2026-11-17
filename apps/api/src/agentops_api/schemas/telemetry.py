import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


TelemetryEventType = Literal[
    "agent.execution.started",
    "agent.execution.completed",
    "agent.execution.failed",
    "llm.request.started",
    "llm.request.completed",
    "llm.request.failed",
    "tool.call.started",
    "tool.call.completed",
    "tool.call.failed",
    "workflow.started",
    "workflow.completed",
    "workflow.failed",
    "agent.state.changed",
    "agent.context.updated",
]

OperationKind = Literal[
    "agent",
    "llm",
    "tool",
    "workflow",
    "state",
]

OperationStatus = Literal[
    "started",
    "completed",
    "failed",
    "cancelled",
]

CaptureMode = Literal[
    "metadata_only",
    "redacted",
    "restricted",
]


class TelemetrySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(min_length=1, max_length=100)
    service_name: str = Field(min_length=1, max_length=150)
    environment: str = Field(min_length=1, max_length=50)


class TelemetryAgent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version_id: UUID | None = None
    version: str | None = Field(default=None, max_length=50)


class TelemetryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    execution_id: UUID
    workflow_id: str | None = Field(default=None, max_length=150)

    trace_id: str = Field(
        pattern=r"^[0-9a-fA-F]{32}$",
    )
    span_id: str = Field(
        pattern=r"^[0-9a-fA-F]{16}$",
    )
    parent_span_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{16}$",
    )

    @model_validator(mode="after")
    def validate_trace_identifiers(self):
        if self.trace_id == "0" * 32:
            raise ValueError("trace_id cannot be all zeros")

        if self.span_id == "0" * 16:
            raise ValueError("span_id cannot be all zeros")

        if self.parent_span_id == "0" * 16:
            raise ValueError("parent_span_id cannot be all zeros")

        return self


class TelemetryOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    kind: OperationKind
    status: OperationStatus
    duration_ms: int | None = Field(default=None, ge=0)


class TelemetryModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=150)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)

    cost_usd: Decimal | None = Field(default=None, ge=0)


class TelemetryError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=150)
    code: str | None = Field(default=None, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    retryable: bool = False


class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture_mode: CaptureMode = "metadata_only"
    input_ref: str | None = Field(default=None, max_length=500)
    output_ref: str | None = Field(default=None, max_length=500)
    redacted: bool = True

    @model_validator(mode="after")
    def validate_payload_capture(self):
        if self.capture_mode == "metadata_only":
            if self.input_ref is not None or self.output_ref is not None:
                raise ValueError(
                    "metadata_only capture cannot contain payload references"
                )

        if self.capture_mode == "redacted" and not self.redacted:
            raise ValueError(
                "redacted capture must have redacted=true"
            )

        return self


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"

    event_id: UUID
    event_type: TelemetryEventType
    occurred_at: datetime

    source: TelemetrySource
    agent: TelemetryAgent
    context: TelemetryContext
    operation: TelemetryOperation

    model_usage: TelemetryModelUsage | None = None
    error: TelemetryError | None = None
    payload: TelemetryPayload | None = None

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "occurred_at must include timezone information"
            )

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_event_semantics(self):
        event_status = {
            "started": "started",
            "completed": "completed",
            "failed": "failed",
        }

        event_suffix = self.event_type.rsplit(".", maxsplit=1)[-1]

        expected_status = event_status.get(event_suffix)

        if (
            expected_status is not None
            and self.operation.status != expected_status
        ):
            raise ValueError(
                f"Event type '{self.event_type}' requires "
                f"operation status '{expected_status}'"
            )

        if self.operation.status == "failed" and self.error is None:
            raise ValueError(
                "error details are required for failed operations"
            )

        if self.operation.status != "failed" and self.error is not None:
            raise ValueError(
                "error details are only allowed for failed operations"
            )

        return self


class TelemetryIngestResponse(BaseModel):
    id: UUID
    event_id: UUID
    organization_id: UUID
    event_type: str
    occurred_at: datetime
    received_at: datetime
    created: bool

