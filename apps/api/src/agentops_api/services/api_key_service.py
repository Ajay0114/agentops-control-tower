"""API key generation, hashing, verification, and lifecycle management.

Key format: ``aops_<8 hex chars>_<43-char urlsafe secret>``.

The leading ``aops_<8 hex chars>`` segment (``PREFIX_LENGTH`` characters, fixed)
is stored in plaintext as ``key_prefix`` and is never secret on its own — it only
gives an indexed O(1) lookup. All security comes from the SHA-256 hash of the
*entire* raw key, compared with a constant-time comparison.

Why SHA-256 and not bcrypt/argon2: those exist to slow down brute-forcing a
low-entropy, human-chosen secret (a password). An API key here is 256 bits of
``secrets`` (CSPRNG) output — there is no dictionary to run against it, and the
search space is computationally unbrute-forceable regardless of hash speed.
A deliberately slow hash would only add latency to every authenticated request
for no security benefit. SHA-256 is the right tool for high-entropy token
hashing; bcrypt/argon2 remain the right tool if this platform ever adds
human-chosen password login.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import ApiKey, Environment, Organization, Project


KEY_LABEL = "aops"
PREFIX_RANDOM_BYTES = 4  # -> 8 hex characters
PREFIX_LENGTH = len(KEY_LABEL) + 1 + PREFIX_RANDOM_BYTES * 2  # "aops_" + 8 hex = 13
SECRET_BYTES = 32  # 256 bits of entropy

MAX_GENERATION_ATTEMPTS = 5

# Only write last_used_at when it is missing or older than this, so a key used
# on every request does not cause a database write on every request.
LAST_USED_THROTTLE_SECONDS = 60


class ApiKeyValidationError(Exception):
    pass


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_raw_key() -> tuple[str, str]:
    """Generate a new raw API key. Returns (raw_key, key_prefix)."""
    key_prefix = f"{KEY_LABEL}_{secrets.token_hex(PREFIX_RANDOM_BYTES)}"
    secret = secrets.token_urlsafe(SECRET_BYTES)

    return f"{key_prefix}_{secret}", key_prefix


def create_api_key(
    db: DBSession,
    *,
    organization_id: UUID,
    name: str,
    project_id: UUID | None = None,
    environment_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create a new API key record. Returns (record, raw_key).

    The raw key is returned ONLY here and is never stored or retrievable again.
    Callers (routers, CLI scripts) must display or hand back ``raw_key`` to the
    operator immediately and never log it.
    """
    organization = db.get(Organization, organization_id)

    if organization is None:
        raise ApiKeyValidationError("Organization not found")

    project: Project | None = None

    if project_id is not None:
        project = db.get(Project, project_id)

        if project is None:
            raise ApiKeyValidationError("Project not found")

        if project.organization_id != organization_id:
            raise ApiKeyValidationError(
                "Project does not belong to the specified organization"
            )

    if environment_id is not None:
        environment = db.get(Environment, environment_id)

        if environment is None:
            raise ApiKeyValidationError("Environment not found")

        if project_id is not None:
            if environment.project_id != project_id:
                raise ApiKeyValidationError(
                    "Environment does not belong to the specified project"
                )
        else:
            owning_project = db.get(Project, environment.project_id)

            if owning_project is None or owning_project.organization_id != organization_id:
                raise ApiKeyValidationError(
                    "Environment does not belong to the specified organization"
                )

    for _ in range(MAX_GENERATION_ATTEMPTS):
        raw_key, key_prefix = generate_raw_key()

        record = ApiKey(
            organization_id=organization_id,
            project_id=project_id,
            environment_id=environment_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=_hash_key(raw_key),
            expires_at=expires_at,
        )

        db.add(record)

        try:
            db.flush()
        except IntegrityError:
            # key_prefix collision: astronomically unlikely (1 in 2^32), but
            # retried defensively with a freshly generated key rather than failing.
            db.rollback()
            continue

        return record, raw_key

    raise RuntimeError(
        "Could not generate a unique API key prefix after several attempts"
    )


def verify_api_key(db: DBSession, raw_key: str) -> ApiKey | None:
    """Look up and verify a raw API key.

    Returns the record only if it exists, the secret matches, it is active, and
    it has not expired. Returns None for every other reason (not found, wrong
    secret, revoked, expired) — callers must not distinguish these cases in the
    response, to avoid confirming whether a given key ever existed.
    """
    if not raw_key or len(raw_key) <= PREFIX_LENGTH:
        return None

    key_prefix = raw_key[:PREFIX_LENGTH]

    record = db.execute(
        select(ApiKey).where(ApiKey.key_prefix == key_prefix)
    ).scalar_one_or_none()

    if record is None:
        return None

    if not hmac.compare_digest(_hash_key(raw_key), record.key_hash):
        return None

    if record.status != "active":
        return None

    if record.expires_at is not None and record.expires_at <= datetime.now(timezone.utc):
        return None

    return record


def revoke_api_key(db: DBSession, api_key: ApiKey) -> ApiKey:
    if api_key.status != "revoked":
        api_key.status = "revoked"
        api_key.revoked_at = datetime.now(timezone.utc)
        db.flush()

    return api_key


def get_api_key(db: DBSession, api_key_id: UUID) -> ApiKey | None:
    return db.get(ApiKey, api_key_id)


def list_api_keys(db: DBSession, organization_id: UUID) -> list[ApiKey]:
    statement = (
        select(ApiKey)
        .where(ApiKey.organization_id == organization_id)
        .order_by(ApiKey.created_at.desc())
    )

    return list(db.execute(statement).scalars().all())


def touch_last_used(db: DBSession, api_key_id: UUID) -> None:
    """Best-effort, throttled update of ``last_used_at``.

    Safe to call on every authenticated request: the UPDATE only takes effect
    when the stored value is missing or older than ``LAST_USED_THROTTLE_SECONDS``,
    so a key used continuously still causes at most one write per throttle
    window rather than one write per request. The WHERE-guarded UPDATE makes the
    check-and-write atomic, with no separate read step.

    Must be called with a database session that is independent of the request's
    own session — e.g. a fresh ``SessionLocal()`` opened inside a
    ``BackgroundTasks`` callback after the response is being sent. A request-scoped
    session must never be reused after the response has started.
    """
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=LAST_USED_THROTTLE_SECONDS)

    db.execute(
        update(ApiKey)
        .where(
            ApiKey.id == api_key_id,
            or_(ApiKey.last_used_at.is_(None), ApiKey.last_used_at < stale_before),
        )
        .values(last_used_at=now)
    )
    db.commit()
