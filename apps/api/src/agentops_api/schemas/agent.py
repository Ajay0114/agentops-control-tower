import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AgentStatus = Literal["registered", "active", "inactive", "archived"]


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=1, max_length=100)
    description: str | None = None
    framework: str | None = Field(default=None, max_length=50)


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    framework: str | None = Field(default=None, max_length=50)
    status: AgentStatus | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be set to null")

        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be set to null")

        return self


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    environment_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    framework: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class AgentVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=30)
    description: str | None = None
    configuration: dict[str, Any] | None = None


class AgentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    version: str
    description: str | None
    configuration: dict[str, Any] | None
    deployment_status: str
    deployed_at: datetime | None
    created_at: datetime
    updated_at: datetime
