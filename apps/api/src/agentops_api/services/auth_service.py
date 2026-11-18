"""Local dashboard account authentication (M7): password hashing, login,
and server-side session lifecycle for human users of the web dashboard.

This is a deliberately separate concern from ``api_key_service.py`` /
``auth.py``'s ``AuthContext``: a :class:`User` authenticates a *person* into
the dashboard, while an :class:`ApiKey` continues to authenticate the
*programmatic* callers (the SDK, and the dashboard's own server-side calls to
this API) that every tenant-scoped resource endpoint still requires via
``AuthContext``. Nothing here is consulted by ``tenant_scope.py``, and no
resource endpoint's authorization changes.

Passwords use Argon2id (``argon2-cffi``) because, unlike an ApiKey's 256-bit
random token, a password is a low-entropy, human-chosen secret - see
``api_key_service.py``'s module docstring for the contrasting case. Session
tokens are high-entropy random values and are hashed with SHA-256 and looked
up via a non-secret prefix, exactly like ApiKey.
"""

import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DBSession

from agentops_api.config import get_settings
from agentops_api.models.core import Organization, Project, User, UserSession


TOKEN_LABEL = "asess"
PREFIX_RANDOM_BYTES = 4  # -> 8 hex characters
PREFIX_LENGTH = len(TOKEN_LABEL) + 1 + PREFIX_RANDOM_BYTES * 2
SECRET_BYTES = 32  # 256 bits of entropy

MAX_GENERATION_ATTEMPTS = 5

# Mirrors api_key_service.touch_last_used's throttle rationale: a session
# validated on every page/data request should not write to the database on
# every single one.
LAST_SEEN_THROTTLE_SECONDS = 60

_password_hasher = PasswordHasher()


class AuthServiceError(Exception):
    pass


class UserAlreadyExistsError(AuthServiceError):
    pass


class UserValidationError(AuthServiceError):
    pass


def hash_password(raw_password: str) -> str:
    return _password_hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, raw_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def count_users(db: DBSession) -> int:
    return len(db.execute(select(User.id)).scalars().all())


def create_user(
    db: DBSession,
    *,
    organization_id: UUID,
    email: str,
    password: str,
    project_id: UUID | None = None,
    role: str = "admin",
) -> User:
    """Create a local dashboard account. Used only by the ``bootstrap_admin``
    CLI script - there is deliberately no HTTP endpoint for this, the same
    reasoning as ``provision_api_key.py``'s module docstring: minting a
    dashboard account must never be reachable over the network without an
    existing credential."""
    organization = db.get(Organization, organization_id)

    if organization is None:
        raise UserValidationError("Organization not found")

    if project_id is not None:
        project = db.get(Project, project_id)

        if project is None:
            raise UserValidationError("Project not found")

        if project.organization_id != organization_id:
            raise UserValidationError(
                "Project does not belong to the specified organization"
            )

    normalized_email = _normalize_email(email)

    existing = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if existing is not None:
        raise UserAlreadyExistsError(
            f"A user with email {normalized_email!r} already exists"
        )

    user = User(
        organization_id=organization_id,
        project_id=project_id,
        email=normalized_email,
        password_hash=hash_password(password),
        role=role,
        status="active",
    )

    db.add(user)
    db.flush()

    return user


# --- Login rate limiting -----------------------------------------------
#
# In-memory, per-process sliding window keyed by normalized email. This is a
# deliberate, narrowly-scoped choice for a single-process local deployment:
# it needs no new infrastructure (no Redis - see the M7 report's note on
# Redis not actually being wired into this repository), at the cost of not
# sharing state across multiple worker processes and resetting on restart,
# which is an accepted limitation for "local" scope (documented in
# docs/architecture/m7-dashboard-and-auth.md).

_login_attempts: dict[str, list[float]] = {}
_login_attempts_lock = threading.Lock()


def _is_rate_limited(email: str) -> bool:
    settings = get_settings()
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - settings.login_rate_limit_window_seconds

    with _login_attempts_lock:
        attempts = [t for t in _login_attempts.get(email, []) if t >= window_start]
        _login_attempts[email] = attempts
        return len(attempts) >= settings.login_rate_limit_max_attempts


def _record_failed_attempt(email: str) -> None:
    now = datetime.now(timezone.utc).timestamp()

    with _login_attempts_lock:
        _login_attempts.setdefault(email, []).append(now)


def _clear_failed_attempts(email: str) -> None:
    with _login_attempts_lock:
        _login_attempts.pop(email, None)


def reset_rate_limiter_for_tests() -> None:
    with _login_attempts_lock:
        _login_attempts.clear()


class LoginRateLimitedError(AuthServiceError):
    pass


def authenticate(db: DBSession, email: str, password: str) -> User:
    """Verify credentials and return the matching active User.

    Raises AuthServiceError (never returns None) for every failure mode -
    unknown email, wrong password, inactive account, or rate limiting - with
    no way for a caller to distinguish them, so a login failure can never be
    used to enumerate which emails have accounts.
    """
    normalized_email = _normalize_email(email)

    if _is_rate_limited(normalized_email):
        raise LoginRateLimitedError("Too many login attempts. Try again later.")

    user = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if (
        user is None
        or user.status != "active"
        or not verify_password(password, user.password_hash)
    ):
        _record_failed_attempt(normalized_email)
        raise AuthServiceError("Invalid email or password")

    _clear_failed_attempts(normalized_email)

    user.last_login_at = datetime.now(timezone.utc)
    db.flush()

    return user


# --- Session lifecycle ---------------------------------------------------


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_raw_token() -> tuple[str, str]:
    token_prefix = f"{TOKEN_LABEL}_{secrets.token_hex(PREFIX_RANDOM_BYTES)}"
    secret = secrets.token_urlsafe(SECRET_BYTES)
    return f"{token_prefix}_{secret}", token_prefix


def create_session(db: DBSession, user: User) -> tuple[UserSession, str]:
    """Create a new server-side session for ``user``. Returns (record,
    raw_token); the raw token is returned only here and is never stored or
    retrievable again, exactly like create_api_key."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_minutes)

    for _ in range(MAX_GENERATION_ATTEMPTS):
        raw_token, token_prefix = _generate_raw_token()

        record = UserSession(
            user_id=user.id,
            token_prefix=token_prefix,
            token_hash=_hash_token(raw_token),
            expires_at=expires_at,
        )

        db.add(record)

        try:
            db.flush()
        except Exception:
            db.rollback()
            continue

        return record, raw_token

    raise RuntimeError("Could not generate a unique session token after several attempts")


def validate_session(db: DBSession, raw_token: str) -> tuple[User, UserSession] | None:
    """Look up and verify a raw session token.

    Returns None for every failure reason (not found, wrong secret, revoked,
    expired, or the owning user no longer active) - callers must not
    distinguish these cases, mirroring verify_api_key's rationale.
    """
    if not raw_token or len(raw_token) <= PREFIX_LENGTH:
        return None

    token_prefix = raw_token[:PREFIX_LENGTH]

    record = db.execute(
        select(UserSession).where(UserSession.token_prefix == token_prefix)
    ).scalar_one_or_none()

    if record is None:
        return None

    if not hmac.compare_digest(_hash_token(raw_token), record.token_hash):
        return None

    if record.revoked_at is not None:
        return None

    if record.expires_at <= datetime.now(timezone.utc):
        return None

    user = db.get(User, record.user_id)

    if user is None or user.status != "active":
        return None

    _touch_last_seen(db, record.id)

    return user, record


def _touch_last_seen(db: DBSession, session_id: UUID) -> None:
    """Throttled, best-effort update - see LAST_SEEN_THROTTLE_SECONDS."""
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=LAST_SEEN_THROTTLE_SECONDS)

    db.execute(
        update(UserSession)
        .where(
            UserSession.id == session_id,
            (UserSession.last_seen_at.is_(None)) | (UserSession.last_seen_at < stale_before),
        )
        .values(last_seen_at=now)
    )


def revoke_session(db: DBSession, raw_token: str) -> bool:
    """Revoke the session identified by ``raw_token``, if any. Returns True
    if a session was found and revoked (idempotent: revoking an
    already-revoked or unknown token is not an error)."""
    if not raw_token or len(raw_token) <= PREFIX_LENGTH:
        return False

    token_prefix = raw_token[:PREFIX_LENGTH]

    record = db.execute(
        select(UserSession).where(UserSession.token_prefix == token_prefix)
    ).scalar_one_or_none()

    if record is None or record.revoked_at is not None:
        return False

    record.revoked_at = datetime.now(timezone.utc)
    db.flush()

    return True
