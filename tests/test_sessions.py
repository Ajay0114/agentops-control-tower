from uuid import uuid4

from agentops_api.models.core import Environment, Organization, Project
from agentops_api.services.api_key_service import create_api_key


def create_environment_context(db_session):
    organization = Organization(
        name="Sessions Test Organization",
        slug=f"sessions-test-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Sessions Test Project",
        slug=f"sessions-test-project-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()

    environment = Environment(
        project_id=project.id,
        name="Development",
        slug=f"dev-{uuid4().hex[:8]}",
    )
    db_session.add(environment)
    db_session.flush()

    return {"organization": organization, "project": project, "environment": environment}


def auth_headers(db_session, organization_id, *, project_id=None, environment_id=None):
    _, raw_key = create_api_key(
        db_session,
        organization_id=organization_id,
        name="Test key",
        project_id=project_id,
        environment_id=environment_id,
    )
    db_session.commit()
    return {"Authorization": f"Bearer {raw_key}"}


def session_payload(context, external_session_id):
    return {
        "project_id": str(context["project"].id),
        "environment_id": str(context["environment"].id),
        "external_session_id": external_session_id,
    }


def test_create_session_successfully(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = session_payload(context, f"conversation-{uuid4().hex[:8]}")

    response = client.post("/api/v1/sessions", json=payload, headers=headers)

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == payload["project_id"]
    assert data["environment_id"] == payload["environment_id"]
    assert data["external_session_id"] == payload["external_session_id"]
    assert data["status"] == "active"
    assert data["ended_at"] is None


def test_create_session_without_auth_returns_401(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/sessions", json=session_payload(context, "no-auth")
    )

    assert response.status_code == 401


def test_create_session_missing_environment_returns_404(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = session_payload(context, "conversation-missing-env")
    payload["environment_id"] = str(uuid4())

    response = client.post("/api/v1/sessions", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Environment not found"


def test_create_session_cross_project_mismatch_returns_422(client, db_session):
    context = create_environment_context(db_session)
    other_project = Project(
        organization_id=context["organization"].id,
        name="Other Project",
        slug=f"other-project-{uuid4().hex[:8]}",
    )
    db_session.add(other_project)
    db_session.flush()
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    # environment belongs to context["project"], but the caller claims it
    # belongs to a different project (both in-scope, just inconsistent).
    payload = session_payload(context, "conversation-cross-project")
    payload["project_id"] = str(other_project.id)

    response = client.post("/api/v1/sessions", json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Environment does not belong to the specified project"
    )


def test_identical_session_request_returns_existing_session(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = session_payload(context, f"conversation-{uuid4().hex[:8]}")

    first_response = client.post("/api/v1/sessions", json=payload, headers=headers)
    second_response = client.post("/api/v1/sessions", json=payload, headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert first_response.json()["id"] == second_response.json()["id"]


def test_same_external_id_allowed_in_different_environment(client, db_session):
    context = create_environment_context(db_session)
    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    external_id = f"conversation-{uuid4().hex[:8]}"

    first_response = client.post(
        "/api/v1/sessions", json=session_payload(context, external_id), headers=headers
    )
    second_response = client.post(
        "/api/v1/sessions",
        json={
            "project_id": str(context["project"].id),
            "environment_id": str(other_environment.id),
            "external_session_id": external_id,
        },
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] != second_response.json()["id"]


def test_list_sessions_filtered_by_project_and_environment(client, db_session):
    organization = Organization(
        name="Filter Test Org", slug=f"filter-org-{uuid4().hex[:8]}"
    )
    db_session.add(organization)
    db_session.flush()

    project_a = Project(
        organization_id=organization.id, name="Project A", slug=f"project-a-{uuid4().hex[:8]}"
    )
    project_b = Project(
        organization_id=organization.id, name="Project B", slug=f"project-b-{uuid4().hex[:8]}"
    )
    db_session.add_all([project_a, project_b])
    db_session.flush()

    environment_a = Environment(
        project_id=project_a.id, name="Dev A", slug=f"dev-a-{uuid4().hex[:8]}"
    )
    environment_b = Environment(
        project_id=project_b.id, name="Dev B", slug=f"dev-b-{uuid4().hex[:8]}"
    )
    db_session.add_all([environment_a, environment_b])
    db_session.flush()
    db_session.commit()

    headers = auth_headers(db_session, organization.id)
    context_a = {"project": project_a, "environment": environment_a}
    context_b = {"project": project_b, "environment": environment_b}

    client.post(
        "/api/v1/sessions", json=session_payload(context_a, "session-a"), headers=headers
    )
    client.post(
        "/api/v1/sessions", json=session_payload(context_b, "session-b"), headers=headers
    )

    response = client.get(
        "/api/v1/sessions",
        params={"project_id": str(project_a.id)},
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["external_session_id"] == "session-a"


def test_get_session_not_found_returns_404(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.get(f"/api/v1/sessions/{uuid4()}", headers=headers)

    assert response.status_code == 404


def test_create_session_rejects_unexpected_field(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = session_payload(context, f"conversation-{uuid4().hex[:8]}")
    payload["status"] = "active"

    response = client.post("/api/v1/sessions", json=payload, headers=headers)

    assert response.status_code == 422


def test_list_sessions_respects_limit(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    for i in range(3):
        client.post(
            "/api/v1/sessions",
            json=session_payload(context, f"session-{i}"),
            headers=headers,
        )

    response = client.get(
        "/api/v1/sessions",
        params={"project_id": str(context["project"].id), "limit": 2},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_create_session_in_other_organization_environment(
    client, db_session
):
    context_a = create_environment_context(db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.post(
        "/api/v1/sessions",
        json=session_payload(context_a, "hijack-attempt"),
        headers=headers_b,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Environment not found"


def test_cross_tenant_cannot_list_other_organization_sessions(client, db_session):
    context_a = create_environment_context(db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    client.post(
        "/api/v1/sessions",
        json=session_payload(context_a, "session-a"),
        headers=headers_a,
    )

    response = client.get("/api/v1/sessions", headers=headers_b)

    assert response.status_code == 200
    assert response.json() == []


def test_cross_tenant_cannot_get_other_organization_session(client, db_session):
    context_a = create_environment_context(db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    create_response = client.post(
        "/api/v1/sessions",
        json=session_payload(context_a, "session-a"),
        headers=headers_a,
    )
    session_id = create_response.json()["id"]

    response = client.get(f"/api/v1/sessions/{session_id}", headers=headers_b)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Project- and environment-restricted API keys
# ---------------------------------------------------------------------------


def test_project_restricted_key_can_create_session_in_its_project(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(
        db_session, context["organization"].id, project_id=context["project"].id
    )

    response = client.post(
        "/api/v1/sessions",
        json=session_payload(context, f"conversation-{uuid4().hex[:8]}"),
        headers=headers,
    )

    assert response.status_code == 201


def test_project_restricted_key_cannot_create_session_in_sibling_project(
    client, db_session
):
    context = create_environment_context(db_session)
    other_project = Project(
        organization_id=context["organization"].id,
        name="Sibling Project",
        slug=f"sibling-project-{uuid4().hex[:8]}",
    )
    db_session.add(other_project)
    db_session.flush()

    other_environment = Environment(
        project_id=other_project.id,
        name="Sibling Environment",
        slug=f"sibling-env-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(
        db_session, context["organization"].id, project_id=context["project"].id
    )

    response = client.post(
        "/api/v1/sessions",
        json={
            "project_id": str(other_project.id),
            "environment_id": str(other_environment.id),
            "external_session_id": "should-not-be-created",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_environment_restricted_key_can_create_session_in_its_environment(
    client, db_session
):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(
        db_session,
        context["organization"].id,
        environment_id=context["environment"].id,
    )

    response = client.post(
        "/api/v1/sessions",
        json=session_payload(context, f"conversation-{uuid4().hex[:8]}"),
        headers=headers,
    )

    assert response.status_code == 201


def test_environment_restricted_key_cannot_create_session_in_sibling_environment(
    client, db_session
):
    context = create_environment_context(db_session)
    sibling_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(sibling_environment)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(
        db_session,
        context["organization"].id,
        environment_id=context["environment"].id,
    )

    response = client.post(
        "/api/v1/sessions",
        json={
            "project_id": str(context["project"].id),
            "environment_id": str(sibling_environment.id),
            "external_session_id": "should-not-be-created",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_environment_restricted_key_cannot_access_session_in_sibling_environment(
    client, db_session
):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    create_response = client.post(
        "/api/v1/sessions",
        json=session_payload(context, f"conversation-{uuid4().hex[:8]}"),
        headers=headers,
    )
    session_id = create_response.json()["id"]

    sibling_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(sibling_environment)
    db_session.flush()
    db_session.commit()

    scoped_headers = auth_headers(
        db_session, context["organization"].id, environment_id=sibling_environment.id
    )

    response = client.get(f"/api/v1/sessions/{session_id}", headers=scoped_headers)

    assert response.status_code == 404
