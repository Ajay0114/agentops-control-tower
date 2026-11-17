from uuid import uuid4

from agentops_api.models.core import Environment, Organization, Project
from agentops_api.services.api_key_service import create_api_key


def create_environment_context(db_session):
    organization = Organization(
        name="Agents Test Organization",
        slug=f"agents-test-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Agents Test Project",
        slug=f"agents-test-project-{uuid4().hex[:8]}",
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


def test_create_agent_successfully(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = {
        "environment_id": str(context["environment"].id),
        "name": "Customer Support Agent",
        "slug": f"support-{uuid4().hex[:8]}",
        "description": "Handles support tickets",
        "framework": "custom-python",
    }

    response = client.post("/api/v1/agents", json=payload, headers=headers)

    assert response.status_code == 201

    data = response.json()

    assert data["environment_id"] == payload["environment_id"]
    assert data["name"] == payload["name"]
    assert data["framework"] == "custom-python"
    assert data["status"] == "registered"


def test_create_agent_without_auth_returns_401(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
        },
    )

    assert response.status_code == 401


def test_create_agent_missing_environment_returns_404(client, db_session):
    organization = Organization(name="Solo Org", slug=f"solo-org-{uuid4().hex[:8]}")
    db_session.add(organization)
    db_session.flush()
    db_session.commit()
    headers = auth_headers(db_session, organization.id)

    payload = {
        "environment_id": str(uuid4()),
        "name": "Customer Support Agent",
        "slug": f"support-{uuid4().hex[:8]}",
    }

    response = client.post("/api/v1/agents", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Environment not found"


def test_duplicate_agent_slug_returns_409(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    slug = f"support-{uuid4().hex[:8]}"
    payload = {
        "environment_id": str(context["environment"].id),
        "name": "Customer Support Agent",
        "slug": slug,
    }

    first_response = client.post("/api/v1/agents", json=payload, headers=headers)
    second_response = client.post("/api/v1/agents", json=payload, headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_list_agents_filtered_by_environment_and_status(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    create_response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    agent_id = create_response.json()["id"]

    client.patch(
        f"/api/v1/agents/{agent_id}", json={"status": "active"}, headers=headers
    )

    active_response = client.get(
        "/api/v1/agents",
        params={"environment_id": str(context["environment"].id), "status": "active"},
        headers=headers,
    )
    registered_response = client.get(
        "/api/v1/agents",
        params={
            "environment_id": str(context["environment"].id),
            "status": "registered",
        },
        headers=headers,
    )

    assert len(active_response.json()) == 1
    assert active_response.json()[0]["id"] == agent_id
    assert len(registered_response.json()) == 0


def test_get_agent_not_found_returns_404(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.get(f"/api/v1/agents/{uuid4()}", headers=headers)

    assert response.status_code == 404


def test_update_agent_successfully(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    create_response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    agent_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Renamed Agent", "status": "inactive"},
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Renamed Agent"
    assert data["status"] == "inactive"


def test_update_agent_not_found_returns_404(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.patch(
        f"/api/v1/agents/{uuid4()}", json={"name": "X"}, headers=headers
    )

    assert response.status_code == 404


def create_agent_via_api(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    return response.json()["id"], headers, context


def test_create_agent_version_successfully(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    payload = {
        "version": "1.0.0",
        "description": "Initial release",
        "configuration": {"temperature": 0.2},
    }

    response = client.post(
        f"/api/v1/agents/{agent_id}/versions", json=payload, headers=headers
    )

    assert response.status_code == 201

    data = response.json()

    assert data["agent_id"] == agent_id
    assert data["version"] == "1.0.0"
    assert data["deployment_status"] == "draft"
    assert data["configuration"] == {"temperature": 0.2}


def test_create_agent_version_for_missing_agent_returns_404(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.post(
        f"/api/v1/agents/{uuid4()}/versions",
        json={"version": "1.0.0"},
        headers=headers,
    )

    assert response.status_code == 404


def test_duplicate_agent_version_returns_409(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    payload = {"version": "1.0.0"}

    first_response = client.post(
        f"/api/v1/agents/{agent_id}/versions", json=payload, headers=headers
    )
    second_response = client.post(
        f"/api/v1/agents/{agent_id}/versions", json=payload, headers=headers
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_list_agent_versions(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"version": "1.0.0"},
        headers=headers,
    )
    client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"version": "1.1.0"},
        headers=headers,
    )

    response = client.get(f"/api/v1/agents/{agent_id}/versions", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_agent_version_not_found_returns_404(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    response = client.get(
        f"/api/v1/agents/{agent_id}/versions/{uuid4()}", headers=headers
    )

    assert response.status_code == 404


def test_get_agent_version_under_wrong_agent_returns_404(client, db_session):
    agent_id, headers, context = create_agent_via_api(client, db_session)

    other_agent_response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Another Agent",
            "slug": f"another-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    other_agent_id = other_agent_response.json()["id"]

    version_response = client.post(
        f"/api/v1/agents/{agent_id}/versions", json={"version": "1.0.0"}, headers=headers
    )
    version_id = version_response.json()["id"]

    response = client.get(
        f"/api/v1/agents/{other_agent_id}/versions/{version_id}", headers=headers
    )

    assert response.status_code == 404


def test_create_agent_rejects_unexpected_field(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
            "status": "active",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_update_agent_rejects_explicit_null_name(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    response = client.patch(
        f"/api/v1/agents/{agent_id}", json={"name": None}, headers=headers
    )

    assert response.status_code == 422


def test_update_agent_rejects_explicit_null_status(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    response = client.patch(
        f"/api/v1/agents/{agent_id}", json={"status": None}, headers=headers
    )

    assert response.status_code == 422


def test_list_agents_respects_limit(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    for _ in range(3):
        client.post(
            "/api/v1/agents",
            json={
                "environment_id": str(context["environment"].id),
                "name": "Customer Support Agent",
                "slug": f"support-{uuid4().hex[:8]}",
            },
            headers=headers,
        )

    response = client.get(
        "/api/v1/agents",
        params={"environment_id": str(context["environment"].id), "limit": 2},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_agent_versions_respects_limit(client, db_session):
    agent_id, headers, _ = create_agent_via_api(client, db_session)

    for version in ("1.0.0", "1.1.0", "1.2.0"):
        client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={"version": version},
            headers=headers,
        )

    response = client.get(
        f"/api/v1/agents/{agent_id}/versions", params={"limit": 2}, headers=headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_list_other_organization_agents(client, db_session):
    context_a = create_environment_context(db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()

    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context_a["environment"].id),
            "name": "Org A Agent",
            "slug": f"org-a-agent-{uuid4().hex[:8]}",
        },
        headers=headers_a,
    )

    response = client.get("/api/v1/agents", headers=headers_b)

    assert response.status_code == 200
    assert response.json() == []


def test_cross_tenant_cannot_get_other_organization_agent(client, db_session):
    agent_id, headers_a, context_a = create_agent_via_api(client, db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.get(f"/api/v1/agents/{agent_id}", headers=headers_b)

    assert response.status_code == 404


def test_cross_tenant_cannot_update_other_organization_agent(client, db_session):
    agent_id, headers_a, context_a = create_agent_via_api(client, db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.patch(
        f"/api/v1/agents/{agent_id}", json={"name": "Hijacked"}, headers=headers_b
    )

    assert response.status_code == 404


def test_cross_tenant_cannot_create_agent_in_other_organization_environment(
    client, db_session
):
    context_a = create_environment_context(db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context_a["environment"].id),
            "name": "Hijack Attempt",
            "slug": f"hijack-{uuid4().hex[:8]}",
        },
        headers=headers_b,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Environment not found"


def test_cross_tenant_cannot_access_other_organization_agent_version(client, db_session):
    agent_id, headers_a, _ = create_agent_via_api(client, db_session)
    version_response = client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"version": "1.0.0"},
        headers=headers_a,
    )
    version_id = version_response.json()["id"]

    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.get(
        f"/api/v1/agents/{agent_id}/versions/{version_id}", headers=headers_b
    )

    assert response.status_code == 404


def test_cross_tenant_cannot_create_version_for_other_organization_agent(
    client, db_session
):
    agent_id, _, _ = create_agent_via_api(client, db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"version": "1.0.0"},
        headers=headers_b,
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Environment-restricted API keys
# ---------------------------------------------------------------------------


def test_environment_restricted_key_can_create_agent_in_its_environment(
    client, db_session
):
    context = create_environment_context(db_session)
    db_session.commit()
    headers = auth_headers(
        db_session, context["organization"].id, environment_id=context["environment"].id
    )

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Scoped Agent",
            "slug": f"scoped-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    assert response.status_code == 201


def test_environment_restricted_key_cannot_create_agent_in_sibling_environment(
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
        db_session, context["organization"].id, environment_id=context["environment"].id
    )

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(sibling_environment.id),
            "name": "Should Not Be Created",
            "slug": f"nope-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_environment_restricted_key_cannot_access_agent_in_sibling_environment(
    client, db_session
):
    agent_id, headers, context = create_agent_via_api(client, db_session)

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

    response = client.get(f"/api/v1/agents/{agent_id}", headers=scoped_headers)

    assert response.status_code == 404
