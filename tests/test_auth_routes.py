from uuid import uuid4

import pytest

from agentops_api.models.core import Organization
from agentops_api.services.auth_service import create_user, reset_rate_limiter_for_tests


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


def make_user(db_session, email="admin@example.com", password="x12345678"):
    organization = make_org(db_session)
    user = create_user(db_session, organization_id=organization.id, email=email, password=password)
    db_session.commit()
    return user


def test_login_success_returns_session_token(client, db_session):
    make_user(db_session, "login@example.com", "x12345678")

    response = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "x12345678"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_token"]
    assert body["user"]["email"] == "login@example.com"
    # The password hash must never leave the server.
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_login_failure_generic_message(client, db_session):
    make_user(db_session, "fail@example.com", "x12345678")

    response = client.post(
        "/api/v1/auth/login", json={"email": "fail@example.com", "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_same_status_and_message_as_wrong_password(client, db_session):
    unknown_response = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )

    make_user(db_session, "real@example.com", "x12345678")
    wrong_pw_response = client.post(
        "/api/v1/auth/login", json={"email": "real@example.com", "password": "wrong"}
    )

    assert unknown_response.status_code == wrong_pw_response.status_code == 401
    assert unknown_response.json() == wrong_pw_response.json()


def test_login_rate_limited_after_repeated_failures(client, db_session):
    make_user(db_session, "limited@example.com", "x12345678")

    for _ in range(5):
        client.post(
            "/api/v1/auth/login", json={"email": "limited@example.com", "password": "wrong"}
        )

    response = client.post(
        "/api/v1/auth/login", json={"email": "limited@example.com", "password": "x12345678"}
    )

    assert response.status_code == 429


def test_me_requires_session_header(client, db_session):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_session(client, db_session):
    response = client.get("/api/v1/auth/me", headers={"x-session-token": "not-a-real-token"})
    assert response.status_code == 401


def test_me_returns_current_user_for_valid_session(client, db_session):
    make_user(db_session, "me@example.com", "x12345678")
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "me@example.com", "password": "x12345678"}
    )
    token = login_response.json()["session_token"]

    response = client.get("/api/v1/auth/me", headers={"x-session-token": token})

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_logout_revokes_session(client, db_session):
    make_user(db_session, "logout@example.com", "x12345678")
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "logout@example.com", "password": "x12345678"}
    )
    token = login_response.json()["session_token"]

    logout_response = client.post("/api/v1/auth/logout", json={"session_token": token})
    assert logout_response.status_code == 204

    me_response = client.get("/api/v1/auth/me", headers={"x-session-token": token})
    assert me_response.status_code == 401


def test_logout_is_idempotent_and_never_errors_on_unknown_token(client, db_session):
    response = client.post("/api/v1/auth/logout", json={"session_token": "asess_deadbeef_bogus"})
    assert response.status_code == 204


def test_existing_api_key_authentication_is_unaffected_by_local_auth_routes(client, db_session):
    """Regression guard: adding the user-session auth system must not touch
    AuthContext/get_auth_context at all - the existing API-key-protected
    endpoints must behave exactly as before."""
    response = client.get("/api/v1/agents")  # no Authorization header at all
    assert response.status_code == 401
