from uuid import uuid4

import pytest

from agentops_api.models.core import Organization, Project
from agentops_api.services.api_key_service import create_api_key
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


def login_and_get_token(client, email, password="x12345678"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["session_token"]


def create_logged_in_user(client, db_session, *, project_id=None):
    organization = make_org(db_session)
    email = f"admin-{uuid4().hex[:8]}@example.com"
    create_user(
        db_session,
        organization_id=organization.id,
        project_id=project_id,
        email=email,
        password="x12345678",
    )
    db_session.commit()

    token = login_and_get_token(client, email)
    return organization, {"x-session-token": token}


def test_create_integration_key_requires_a_session(client, db_session):
    response = client.post("/api/v1/auth/api-keys", json={"name": "my key"})
    assert response.status_code == 401


def test_create_list_and_revoke_integration_key(client, db_session):
    organization, headers = create_logged_in_user(client, db_session)

    create_response = client.post(
        "/api/v1/auth/api-keys", json={"name": "CI key"}, headers=headers
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()

    # The raw key is shown exactly once, in this response only.
    assert body["raw_key"].startswith("aops_")
    assert body["api_key"]["name"] == "CI key"
    assert body["api_key"]["status"] == "active"
    assert "raw_key" not in body["api_key"]
    assert "key_hash" not in body["api_key"]

    key_id = body["api_key"]["id"]

    list_response = client.get("/api/v1/auth/api-keys", headers=headers)
    assert list_response.status_code == 200
    listed_ids = {item["id"] for item in list_response.json()}
    assert key_id in listed_ids
    # The list response never carries the raw key either.
    assert all("raw_key" not in item for item in list_response.json())

    revoke_response = client.post(f"/api/v1/auth/api-keys/{key_id}/revoke", headers=headers)
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"

    # Revoking an already-revoked key is idempotent (matches
    # api_key_service.revoke_api_key's own design) - a no-op 200, not an error.
    second_revoke = client.post(f"/api/v1/auth/api-keys/{key_id}/revoke", headers=headers)
    assert second_revoke.status_code == 200
    assert second_revoke.json()["status"] == "revoked"


def test_list_is_scoped_to_the_callers_own_organization(client, db_session):
    _org_a, headers_a = create_logged_in_user(client, db_session)
    _org_b, headers_b = create_logged_in_user(client, db_session)

    create_response = client.post(
        "/api/v1/auth/api-keys", json={"name": "org-a-key"}, headers=headers_a
    )
    key_id = create_response.json()["api_key"]["id"]

    list_as_b = client.get("/api/v1/auth/api-keys", headers=headers_b)
    assert key_id not in {item["id"] for item in list_as_b.json()}


def test_cannot_revoke_another_organizations_key(client, db_session):
    _org_a, headers_a = create_logged_in_user(client, db_session)
    _org_b, headers_b = create_logged_in_user(client, db_session)

    create_response = client.post(
        "/api/v1/auth/api-keys", json={"name": "org-a-key"}, headers=headers_a
    )
    key_id = create_response.json()["api_key"]["id"]

    revoke_as_b = client.post(f"/api/v1/auth/api-keys/{key_id}/revoke", headers=headers_b)
    assert revoke_as_b.status_code == 404

    # Confirm the hijack attempt genuinely did not revoke it.
    still_listed = client.get("/api/v1/auth/api-keys", headers=headers_a)
    matching = next(item for item in still_listed.json() if item["id"] == key_id)
    assert matching["status"] == "active"


def test_internal_dashboard_key_is_never_listed_or_revocable(client, db_session):
    organization, headers = create_logged_in_user(client, db_session)

    _record, _raw = create_api_key(
        db_session,
        organization_id=organization.id,
        name="__internal_dashboard_key__",
        key_type="internal",
    )
    db_session.commit()

    list_response = client.get("/api/v1/auth/api-keys", headers=headers)
    assert all(item["name"] != "__internal_dashboard_key__" for item in list_response.json())

    internal_key_id = _record.id
    revoke_response = client.post(
        f"/api/v1/auth/api-keys/{internal_key_id}/revoke", headers=headers
    )
    assert revoke_response.status_code == 404


def test_browser_supplied_organization_id_is_ignored(client, db_session):
    """The create-key request schema has no organization_id field at all -
    this proves the server can't be tricked into using one even if a client
    tried to send it, since FastAPI/Pydantic rejects unknown fields."""
    _organization, headers = create_logged_in_user(client, db_session)
    other_org = make_org(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "sneaky key", "organization_id": str(other_org.id)},
        headers=headers,
    )
    assert response.status_code == 422  # extra="forbid" on the schema


def test_project_scoped_user_can_only_create_keys_for_their_own_project(client, db_session):
    organization = make_org(db_session)
    project = Project(organization_id=organization.id, name="P", slug=f"p-{uuid4().hex[:8]}")
    db_session.add(project)
    db_session.flush()

    other_project = Project(
        organization_id=organization.id, name="Other", slug=f"other-{uuid4().hex[:8]}"
    )
    db_session.add(other_project)
    db_session.flush()

    email = f"scoped-{uuid4().hex[:8]}@example.com"
    create_user(
        db_session,
        organization_id=organization.id,
        project_id=project.id,
        email=email,
        password="x12345678",
    )
    db_session.commit()

    token = login_and_get_token(client, email)
    headers = {"x-session-token": token}

    # Even asking for the OTHER project is silently overridden to the
    # user's own fixed project - never trusted from the request.
    response = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "scoped key", "project_id": str(other_project.id)},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["api_key"]["project_id"] == str(project.id)


def test_key_management_also_works_via_the_tenant_api_key_not_only_a_session(client, db_session):
    """This is what keeps the API Keys UI usable when the frontend's local-
    auth bypass is active: no session exists in that mode, so the dashboard
    falls back to the one AGENTOPS_API_KEY it already uses for everything
    else."""
    organization = make_org(db_session)
    _record, raw_api_key = create_api_key(
        db_session, organization_id=organization.id, name="internal-ish key for this test"
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {raw_api_key}"}

    create_response = client.post(
        "/api/v1/auth/api-keys", json={"name": "created via api key"}, headers=headers
    )
    assert create_response.status_code == 201, create_response.text
    key_id = create_response.json()["api_key"]["id"]

    list_response = client.get("/api/v1/auth/api-keys", headers=headers)
    assert key_id in {item["id"] for item in list_response.json()}

    revoke_response = client.post(f"/api/v1/auth/api-keys/{key_id}/revoke", headers=headers)
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"


def test_key_management_prefers_a_session_over_an_api_key_when_both_are_sent(client, db_session):
    organization_a, headers_a = create_logged_in_user(client, db_session)
    organization_b = make_org(db_session)
    _record, raw_api_key_b = create_api_key(
        db_session, organization_id=organization_b.id, name="org-b-key"
    )
    db_session.commit()

    # Session (org A) takes priority over the Authorization header (org B).
    combined_headers = {**headers_a, "Authorization": f"Bearer {raw_api_key_b}"}

    create_response = client.post(
        "/api/v1/auth/api-keys", json={"name": "which org"}, headers=combined_headers
    )
    assert create_response.status_code == 201

    list_as_a = client.get("/api/v1/auth/api-keys", headers=headers_a)
    assert create_response.json()["api_key"]["id"] in {item["id"] for item in list_as_a.json()}
