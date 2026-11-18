from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Deliberately a plain, lightly-constrained string rather than a
    # pydantic EmailStr: that type requires the optional email-validator
    # dependency, which isn't otherwise needed by this project. Full RFC
    # validation isn't security-relevant here - an invalid address simply
    # won't match any stored user and the login fails generically either way.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID | None
    email: str
    role: str
    status: str
    last_login_at: datetime | None


class LoginResponse(BaseModel):
    session_token: str
    expires_at: datetime
    user: UserResponse


class SessionValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_token: str = Field(min_length=1)
