from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExecutionStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class ExecutionCreate(BaseModel):
    session_id: UUID
    agent_id: UUID
    agent_version_id: UUID | None = None
    external_execution_id: str | None = Field(
        default=None,
        max_length=150,
    )


class ExecutionTransition(BaseModel):
    status: Literal[
        "running",
        "completed",
        "failed",
        "cancelled",
    ]

    error_type: str | None = Field(
        default=None,
        max_length=150,
    )

    error_message: str | None = None

    @model_validator(mode="after")
    def validate_failure_details(self):
        if self.status == "failed" and not self.error_type:
            raise ValueError(
                "error_type is required when status is failed"
            )

        if self.status != "failed" and (
            self.error_type is not None
            or self.error_message is not None
        ):
            raise ValueError(
                "Error details are only allowed for failed executions"
            )

        return self


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    agent_id: UUID
    agent_version_id: UUID | None
    external_execution_id: str | None
    status: ExecutionStatus
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    error_type: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
