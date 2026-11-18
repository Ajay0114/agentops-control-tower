"""Local dashboard account endpoints (M7).

These are deliberately independent of ``AuthContext``/``get_auth_context``:
a session token identifies a *person*, not a tenant-scoped API key, and
logging in is necessarily reachable before any such identity is known. They
are called server-to-server by the Next.js dashboard layer only - the
browser never talks to this API directly (see docs/architecture/
m7-dashboard-and-auth.md for the full trust-boundary write-up) - so the
session token here travels as an explicit request field/header, never as a
cookie this API would need to parse or trust.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import get_auth_context
from agentops_api.db import get_db
from agentops_api.models.core import Project, User
from agentops_api.schemas.api_key import (
    IntegrationApiKeyCreate,
    IntegrationApiKeyCreateResponse,
    IntegrationApiKeyResponse,
)
from agentops_api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    SignupRequest,
    UserResponse,
)
from agentops_api.services.api_key_service import (
    ApiKeyValidationError,
    create_api_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
)
from agentops_api.services.auth_service import (
    AuthServiceError,
    LoginRateLimitedError,
    UserAlreadyExistsError,
    authenticate,
    create_session,
    revoke_session,
    signup,
    validate_session,
)
from agentops_api.services.organization_service import OrganizationValidationError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Invalid email or password"


def get_session_user(
    x_session_token: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
) -> User:
    """Shared dependency for every endpoint below that acts on behalf of a
    logged-in dashboard user (as opposed to AuthContext's tenant-scoped API
    key). Used by /me and by the API key management endpoints - never by any
    data endpoint, which continue to authenticate via AuthContext only."""
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required")

    result = validate_session(db, x_session_token)
    db.commit()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid"
        )

    user, _session = result
    return user


@dataclass(frozen=True)
class KeyManagementScope:
    organization_id: UUID
    project_id: UUID | None


def get_key_management_scope(
    background_tasks: BackgroundTasks,
    x_session_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
) -> KeyManagementScope:
    """Resolves the (organization, project) scope for API-key management,
    accepting either a logged-in dashboard session OR this deployment's own
    tenant-scoped API key as proof of identity.

    The second path is what keeps key management working when the
    frontend's local-auth bypass is active (see docs/architecture/
    m7-dashboard-and-auth.md section 6): there is no login to check in that
    mode, so the dashboard instead presents the same AGENTOPS_API_KEY it
    already uses for every other request. Session identity is tried first
    and, when present, always wins - matching the normal (non-bypass) path.
    """
    if x_session_token:
        result = validate_session(db, x_session_token)
        db.commit()

        if result is not None:
            user, _session = result
            return KeyManagementScope(organization_id=user.organization_id, project_id=user.project_id)

    if authorization:
        auth = get_auth_context(background_tasks, authorization=authorization, db=db)
        return KeyManagementScope(organization_id=auth.organization_id, project_id=auth.project_id)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: DBSession = Depends(get_db)):
    try:
        user = authenticate(db, data.email, data.password)
    except LoginRateLimitedError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )
    except AuthServiceError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    session, raw_token = create_session(db, user)
    db.commit()
    db.refresh(user)

    return LoginResponse(
        session_token=raw_token,
        expires_at=session.expires_at,
        user=UserResponse.from_user(user),
    )


@router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def signup_endpoint(data: SignupRequest, db: DBSession = Depends(get_db)):
    """Self-service customer onboarding (M8): creates a brand-new
    organization and its first (admin) user, then immediately logs them in
    - the same session-issuing step `/login` performs - so a first-time
    customer lands straight in the onboarding flow with no separate login
    step of their own. See auth_service.signup's docstring for why a
    duplicate email never leaves a half-created organization behind."""
    try:
        _organization, user = signup(
            db, organization_name=data.organization_name, email=data.email, password=data.password
        )
    except UserAlreadyExistsError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    except OrganizationValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    session, raw_token = create_session(db, user)
    db.commit()
    db.refresh(user)

    return LoginResponse(
        session_token=raw_token,
        expires_at=session.expires_at,
        user=UserResponse.from_user(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutRequest, db: DBSession = Depends(get_db)):
    revoke_session(db, data.session_token)
    db.commit()
    return None


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_session_user)):
    return UserResponse.from_user(user)


# --- Integration API key management (M7 follow-up) -----------------------
#
# These act on behalf of the logged-in dashboard user (get_session_user),
# never AuthContext - and their *scope* is always the caller's own
# organization/project from their session, never anything the browser
# supplies. They only ever see/create/revoke key_type="integration" rows:
# the internal dashboard key (see bootstrap_service.py) is structurally
# invisible here, by filtering on key_type rather than trusting a naming
# convention or the UI to simply not ask for it.


def _validate_requested_scope(
    db: DBSession, scope: KeyManagementScope, project_id: UUID | None
) -> UUID | None:
    """Resolves the project_id this new key should actually be created
    with, given what the caller asked for. Never trusts project_id alone -
    it must belong to the caller's own organization, and if the caller's
    own identity is itself narrowed to one project, that project always
    wins over whatever was requested."""
    if scope.project_id is not None:
        return scope.project_id

    if project_id is None:
        return None

    project = db.get(Project, project_id)

    if project is None or project.organization_id != scope.organization_id:
        raise ApiKeyValidationError("Project not found")

    return project_id


@router.get("/api-keys", response_model=list[IntegrationApiKeyResponse])
def list_integration_api_keys(
    scope: KeyManagementScope = Depends(get_key_management_scope),
    db: DBSession = Depends(get_db),
):
    return list_api_keys(db, scope.organization_id, key_type="integration")


@router.post(
    "/api-keys",
    response_model=IntegrationApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_integration_api_key(
    data: IntegrationApiKeyCreate,
    scope: KeyManagementScope = Depends(get_key_management_scope),
    db: DBSession = Depends(get_db),
):
    try:
        project_id = _validate_requested_scope(db, scope, data.project_id)

        record, raw_key = create_api_key(
            db,
            organization_id=scope.organization_id,
            name=data.name,
            project_id=project_id,
            environment_id=data.environment_id,
            key_type="integration",
        )
    except ApiKeyValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    db.commit()
    db.refresh(record)

    return IntegrationApiKeyCreateResponse(
        api_key=IntegrationApiKeyResponse.model_validate(record),
        raw_key=raw_key,
    )


@router.post("/api-keys/{api_key_id}/revoke", response_model=IntegrationApiKeyResponse)
def revoke_integration_api_key(
    api_key_id: UUID,
    scope: KeyManagementScope = Depends(get_key_management_scope),
    db: DBSession = Depends(get_db),
):
    record = get_api_key(db, api_key_id)

    # Scoped the same way every other resource lookup in this codebase is:
    # a key outside the caller's organization, or an internal key, is
    # indistinguishable from one that doesn't exist (404, never 403) - see
    # tenant_scope.py's module docstring for why that matters.
    if (
        record is None
        or record.organization_id != scope.organization_id
        or record.key_type != "integration"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    record = revoke_api_key(db, record)
    db.commit()

    return IntegrationApiKeyResponse.model_validate(record)
