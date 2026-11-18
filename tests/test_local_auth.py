from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from agentops_api.models.core import Organization, Project, UserSession
from agentops_api.services.auth_service import (
    LoginRateLimitedError,
    UserAlreadyExistsError,
    UserValidationError,
    authenticate,
    count_users,
    create_session,
    create_user,
    hash_password,
    reset_rate_limiter_for_tests,
    revoke_session,
    validate_session,
    verify_password,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    reset_rate_limiter_for_tests()
    yield
    reset_rate_limiter_for_tests()


def make_org(db_session):
    organization = Organization(name="Test Org", slug=f"test-org-{uuid4().hex[:8]}")
    db_session.add(organization)
    db_session.flush()
    return organization


# --- Password hashing -----------------------------------------------------


def test_hash_password_produces_argon2id_hash():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert "correct horse battery staple" not in hashed


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_password_rejects_garbage_hash_without_raising():
    assert verify_password("anything", "not-a-real-hash") is False


# --- User creation / bootstrap ---------------------------------------------


def test_create_user_success(db_session):
    organization = make_org(db_session)

    user = create_user(
        db_session,
        organization_id=organization.id,
        email="Admin@Example.com",
        password="supersecret1",
    )
    db_session.commit()

    assert user.email == "admin@example.com"  # normalized lowercase
    assert user.password_hash != "supersecret1"
    assert user.role == "admin"
    assert user.status == "active"
    assert count_users(db_session) == 1


def test_create_user_rejects_unknown_organization(db_session):
    with pytest.raises(UserValidationError):
        create_user(db_session, organization_id=uuid4(), email="a@example.com", password="x12345678")


def test_create_user_rejects_project_from_another_organization(db_session):
    organization = make_org(db_session)
    other_organization = make_org(db_session)
    project = Project(organization_id=other_organization.id, name="P", slug=f"p-{uuid4().hex[:8]}")
    db_session.add(project)
    db_session.flush()

    with pytest.raises(UserValidationError):
        create_user(
            db_session,
            organization_id=organization.id,
            project_id=project.id,
            email="a@example.com",
            password="x12345678",
        )


def test_create_user_rejects_duplicate_email(db_session):
    organization = make_org(db_session)
    create_user(db_session, organization_id=organization.id, email="dup@example.com", password="x12345678")
    db_session.commit()

    with pytest.raises(UserAlreadyExistsError):
        create_user(db_session, organization_id=organization.id, email="DUP@example.com", password="y12345678")


# --- authenticate() ---------------------------------------------------------


def test_authenticate_success(db_session):
    organization = make_org(db_session)
    create_user(db_session, organization_id=organization.id, email="login@example.com", password="x12345678")
    db_session.commit()

    user = authenticate(db_session, "login@example.com", "x12345678")
    assert user.email == "login@example.com"
    assert user.last_login_at is not None


def test_authenticate_rejects_wrong_password(db_session):
    organization = make_org(db_session)
    create_user(db_session, organization_id=organization.id, email="login2@example.com", password="x12345678")
    db_session.commit()

    with pytest.raises(Exception):
        authenticate(db_session, "login2@example.com", "wrong-password")


def test_authenticate_rejects_unknown_email_with_same_error_as_wrong_password(db_session):
    """Both failure modes must be indistinguishable to the caller."""
    with pytest.raises(Exception) as unknown_exc:
        authenticate(db_session, "nobody@example.com", "whatever12")

    organization = make_org(db_session)
    create_user(db_session, organization_id=organization.id, email="known@example.com", password="x12345678")
    db_session.commit()

    with pytest.raises(Exception) as wrong_pw_exc:
        authenticate(db_session, "known@example.com", "wrong-password")

    assert str(unknown_exc.value) == str(wrong_pw_exc.value)


def test_authenticate_rejects_inactive_user(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="inactive@example.com", password="x12345678")
    user.status = "disabled"
    db_session.commit()

    with pytest.raises(Exception):
        authenticate(db_session, "inactive@example.com", "x12345678")


def test_authenticate_rate_limits_after_repeated_failures(db_session):
    organization = make_org(db_session)
    create_user(db_session, organization_id=organization.id, email="ratelimit@example.com", password="x12345678")
    db_session.commit()

    for _ in range(5):
        with pytest.raises(Exception):
            authenticate(db_session, "ratelimit@example.com", "wrong-password")

    with pytest.raises(LoginRateLimitedError):
        authenticate(db_session, "ratelimit@example.com", "x12345678")  # even the correct password is blocked


def test_successful_login_clears_failed_attempt_counter(db_session):
    organization = make_org(db_session)
    create_user(db_session, organization_id=organization.id, email="clears@example.com", password="x12345678")
    db_session.commit()

    for _ in range(4):
        with pytest.raises(Exception):
            authenticate(db_session, "clears@example.com", "wrong-password")

    authenticate(db_session, "clears@example.com", "x12345678")

    # Counter was reset, so 4 more failures (rather than needing just 1 more
    # to hit the limit of 5) are tolerated afterward.
    for _ in range(4):
        with pytest.raises(Exception):
            authenticate(db_session, "clears@example.com", "wrong-password")

    authenticate(db_session, "clears@example.com", "x12345678")


# --- Session lifecycle --------------------------------------------------


def test_create_and_validate_session(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="session@example.com", password="x12345678")
    db_session.commit()

    _record, raw_token = create_session(db_session, user)
    db_session.commit()

    result = validate_session(db_session, raw_token)
    db_session.commit()

    assert result is not None
    validated_user, _session = result
    assert validated_user.id == user.id


def test_validate_session_rejects_garbage_token(db_session):
    assert validate_session(db_session, "not-a-real-token") is None


def test_validate_session_rejects_tampered_token(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="tamper@example.com", password="x12345678")
    db_session.commit()

    _record, raw_token = create_session(db_session, user)
    db_session.commit()

    tampered = raw_token[:-1] + ("a" if raw_token[-1] != "a" else "b")
    assert validate_session(db_session, tampered) is None


def test_validate_session_rejects_expired_session(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="expired@example.com", password="x12345678")
    db_session.commit()

    record, raw_token = create_session(db_session, user)
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    assert validate_session(db_session, raw_token) is None


def test_revoke_session_invalidates_it(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="revoke@example.com", password="x12345678")
    db_session.commit()

    _record, raw_token = create_session(db_session, user)
    db_session.commit()

    assert revoke_session(db_session, raw_token) is True
    db_session.commit()

    assert validate_session(db_session, raw_token) is None


def test_revoke_session_is_idempotent(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="idempotent@example.com", password="x12345678")
    db_session.commit()

    _record, raw_token = create_session(db_session, user)
    db_session.commit()

    assert revoke_session(db_session, raw_token) is True
    db_session.commit()
    assert revoke_session(db_session, raw_token) is False  # already revoked


def test_revoke_unknown_session_returns_false(db_session):
    assert revoke_session(db_session, "asess_deadbeef_not-a-real-token") is False


def test_validate_session_rejects_session_of_disabled_user(db_session):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email="disable-after@example.com", password="x12345678")
    db_session.commit()

    _record, raw_token = create_session(db_session, user)
    db_session.commit()

    user.status = "disabled"
    db_session.commit()

    assert validate_session(db_session, raw_token) is None
