from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentops_api.models.core import User


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Deliberately a plain, lightly-constrained string rather than a
    # pydantic EmailStr: that type requires the optional email-validator
    # dependency, which isn't otherwise needed by this project. Full RFC
    # validation isn't security-relevant here - an invalid address simply
    # won't match any stored user and the login fails generically either way.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID | None
    email: str
    role: str
    status: str
    last_login_at: datetime | None
    # Display-only, like organization_id/project_id themselves (see
    # models/core.py's User docstring) - never consulted for authorization.
    # Read via the ORM relationship rather than `.model_validate(user)`'s
    # usual attribute-name matching, since neither name exists directly on
    # the User row - see `from_user` below, used at every call site instead.
    organization_name: str
    project_name: str | None

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            organization_id=user.organization_id,
            project_id=user.project_id,
            email=user.email,
            role=user.role,
            status=user.status,
            last_login_at=user.last_login_at,
            organization_name=user.organization.name,
            project_name=user.project.name if user.project else None,
        )


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
