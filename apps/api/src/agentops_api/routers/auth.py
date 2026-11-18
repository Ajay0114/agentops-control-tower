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

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from agentops_api.db import get_db
from agentops_api.schemas.auth import LoginRequest, LoginResponse, LogoutRequest, UserResponse
from agentops_api.services.auth_service import (
    AuthServiceError,
    LoginRateLimitedError,
    authenticate,
    create_session,
    revoke_session,
    validate_session,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Invalid email or password"


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
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutRequest, db: DBSession = Depends(get_db)):
    revoke_session(db, data.session_token)
    db.commit()
    return None


@router.get("/me", response_model=UserResponse)
def me(
    x_session_token: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
):
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required")

    result = validate_session(db, x_session_token)
    db.commit()

    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")

    user, _session = result
    return UserResponse.model_validate(user)
