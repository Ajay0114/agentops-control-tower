from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    # Never organization_id - the caller's own session determines that; see
    # routers/auth.py's create_integration_api_key.
    project_id: UUID | None = None
    environment_id: UUID | None = None


class IntegrationApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    project_id: UUID | None
    environment_id: UUID | None
    status: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class IntegrationApiKeyCreateResponse(BaseModel):
    api_key: IntegrationApiKeyResponse
    # Present only on this one response, at creation time - never
    # retrievable again afterward. See api_key_service.py's module docstring.
    raw_key: str
