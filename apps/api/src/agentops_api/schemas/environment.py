import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EnvironmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=50)
    description: str | None = None


class EnvironmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None

    @model_validator(mode="after")
    def reject_null_name(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be set to null")

        return self


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime
