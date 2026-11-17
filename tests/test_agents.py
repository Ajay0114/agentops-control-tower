from uuid import uuid4

from agentops_api.models.core import Environment, Organization, Project


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


def test_create_agent_successfully(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    payload = {
        "environment_id": str(context["environment"].id),
        "name": "Customer Support Agent",
        "slug": f"support-{uuid4().hex[:8]}",
        "description": "Handles support tickets",
        "framework": "custom-python",
    }

    response = client.post("/api/v1/agents", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["environment_id"] == payload["environment_id"]
    assert data["name"] == payload["name"]
    assert data["framework"] == "custom-python"
    assert data["status"] == "registered"


def test_create_agent_missing_environment_returns_422(client, db_session):
    payload = {
        "environment_id": str(uuid4()),
        "name": "Customer Support Agent",
        "slug": f"support-{uuid4().hex[:8]}",
    }

    response = client.post("/api/v1/agents", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Environment not found"


def test_duplicate_agent_slug_returns_409(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    slug = f"support-{uuid4().hex[:8]}"
    payload = {
        "environment_id": str(context["environment"].id),
        "name": "Customer Support Agent",
        "slug": slug,
    }

    first_response = client.post("/api/v1/agents", json=payload)
    second_response = client.post("/api/v1/agents", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_list_agents_filtered_by_environment_and_status(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    create_response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
        },
    )
    agent_id = create_response.json()["id"]

    client.patch(f"/api/v1/agents/{agent_id}", json={"status": "active"})

    active_response = client.get(
        "/api/v1/agents",
        params={"environment_id": str(context["environment"].id), "status": "active"},
    )
    registered_response = client.get(
        "/api/v1/agents",
        params={
            "environment_id": str(context["environment"].id),
            "status": "registered",
        },
    )

    assert len(active_response.json()) == 1
    assert active_response.json()[0]["id"] == agent_id
    assert len(registered_response.json()) == 0


def test_get_agent_not_found_returns_404(client, db_session):
    response = client.get(f"/api/v1/agents/{uuid4()}")

    assert response.status_code == 404


def test_update_agent_successfully(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    create_response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
        },
    )
    agent_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Renamed Agent", "status": "inactive"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Renamed Agent"
    assert data["status"] == "inactive"


def test_update_agent_not_found_returns_404(client, db_session):
    response = client.patch(f"/api/v1/agents/{uuid4()}", json={"name": "X"})

    assert response.status_code == 404


def create_agent_via_api(client, db_session):
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

    return response.json()["id"]


def test_create_agent_version_successfully(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    payload = {
        "version": "1.0.0",
        "description": "Initial release",
        "configuration": {"temperature": 0.2},
    }

    response = client.post(f"/api/v1/agents/{agent_id}/versions", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["agent_id"] == agent_id
    assert data["version"] == "1.0.0"
    assert data["deployment_status"] == "draft"
    assert data["configuration"] == {"temperature": 0.2}


def test_create_agent_version_for_missing_agent_returns_404(client, db_session):
    response = client.post(
        f"/api/v1/agents/{uuid4()}/versions",
        json={"version": "1.0.0"},
    )

    assert response.status_code == 404


def test_duplicate_agent_version_returns_409(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    payload = {"version": "1.0.0"}

    first_response = client.post(f"/api/v1/agents/{agent_id}/versions", json=payload)
    second_response = client.post(f"/api/v1/agents/{agent_id}/versions", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_list_agent_versions(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    client.post(f"/api/v1/agents/{agent_id}/versions", json={"version": "1.0.0"})
    client.post(f"/api/v1/agents/{agent_id}/versions", json={"version": "1.1.0"})

    response = client.get(f"/api/v1/agents/{agent_id}/versions")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_agent_version_not_found_returns_404(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    response = client.get(f"/api/v1/agents/{agent_id}/versions/{uuid4()}")

    assert response.status_code == 404


def test_get_agent_version_under_wrong_agent_returns_404(client, db_session):
    agent_id = create_agent_via_api(client, db_session)
    other_agent_id = create_agent_via_api(client, db_session)

    version_response = client.post(
        f"/api/v1/agents/{agent_id}/versions", json={"version": "1.0.0"}
    )
    version_id = version_response.json()["id"]

    response = client.get(f"/api/v1/agents/{other_agent_id}/versions/{version_id}")

    assert response.status_code == 404


def test_create_agent_rejects_unexpected_field(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": str(context["environment"].id),
            "name": "Customer Support Agent",
            "slug": f"support-{uuid4().hex[:8]}",
            "status": "active",
        },
    )

    assert response.status_code == 422


def test_update_agent_rejects_explicit_null_name(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    response = client.patch(f"/api/v1/agents/{agent_id}", json={"name": None})

    assert response.status_code == 422


def test_update_agent_rejects_explicit_null_status(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    response = client.patch(f"/api/v1/agents/{agent_id}", json={"status": None})

    assert response.status_code == 422


def test_list_agents_respects_limit(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    for _ in range(3):
        client.post(
            "/api/v1/agents",
            json={
                "environment_id": str(context["environment"].id),
                "name": "Customer Support Agent",
                "slug": f"support-{uuid4().hex[:8]}",
            },
        )

    response = client.get(
        "/api/v1/agents",
        params={"environment_id": str(context["environment"].id), "limit": 2},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_agent_versions_respects_limit(client, db_session):
    agent_id = create_agent_via_api(client, db_session)

    for version in ("1.0.0", "1.1.0", "1.2.0"):
        client.post(f"/api/v1/agents/{agent_id}/versions", json={"version": version})

    response = client.get(
        f"/api/v1/agents/{agent_id}/versions", params={"limit": 2}
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
