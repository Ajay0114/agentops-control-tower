from uuid import uuid4

from agentops_api.models.core import Environment, Organization, Project
from agentops_api.services.api_key_service import create_api_key


def create_org_and_project(db_session):
    organization = Organization(
        name="Environments Test Organization",
        slug=f"env-test-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Environments Test Project",
        slug=f"env-test-project-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()

    return organization, project


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


def test_create_environment_successfully(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, project.organization_id)

    payload = {
        "project_id": str(project.id),
        "name": "Development",
        "slug": f"dev-{uuid4().hex[:8]}",
        "description": "Local development environment",
    }

    response = client.post("/api/v1/environments", json=payload, headers=headers)

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == payload["project_id"]
    assert data["name"] == "Development"
    assert data["slug"] == payload["slug"]
    assert data["description"] == "Local development environment"


def test_create_environment_without_auth_returns_401(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/environments",
        json={"project_id": str(project.id), "name": "Development", "slug": "dev"},
    )

    assert response.status_code == 401


def test_create_environment_missing_project_returns_404(client, db_session):
    organization, _ = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, organization.id)

    payload = {
        "project_id": str(uuid4()),
        "name": "Development",
        "slug": f"dev-{uuid4().hex[:8]}",
    }

    response = client.post("/api/v1/environments", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_duplicate_environment_slug_returns_409(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, project.organization_id)

    slug = f"dev-{uuid4().hex[:8]}"
    payload = {"project_id": str(project.id), "name": "Development", "slug": slug}

    first_response = client.post("/api/v1/environments", json=payload, headers=headers)
    second_response = client.post("/api/v1/environments", json=payload, headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_same_slug_allowed_across_different_projects(client, db_session):
    _, project_a = create_org_and_project(db_session)
    _, project_b = create_org_and_project(db_session)
    db_session.commit()

    slug = f"dev-{uuid4().hex[:8]}"

    response_a = client.post(
        "/api/v1/environments",
        json={"project_id": str(project_a.id), "name": "Development", "slug": slug},
        headers=auth_headers(db_session, project_a.organization_id),
    )
    response_b = client.post(
        "/api/v1/environments",
        json={"project_id": str(project_b.id), "name": "Development", "slug": slug},
        headers=auth_headers(db_session, project_b.organization_id),
    )

    assert response_a.status_code == 201
    assert response_b.status_code == 201
    assert response_a.json()["id"] != response_b.json()["id"]


def test_list_environments_filtered_by_project(client, db_session):
    organization, project_a = create_org_and_project(db_session)
    project_b = Project(
        organization_id=organization.id,
        name="Second Project",
        slug=f"env-test-project-{uuid4().hex[:8]}",
    )
    db_session.add(project_b)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(db_session, organization.id)

    client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_a.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_b.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    response = client.get(
        "/api/v1/environments",
        params={"project_id": str(project_a.id)},
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["project_id"] == str(project_a.id)


def test_get_environment_not_found_returns_404(client, db_session):
    organization, _ = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, organization.id)

    response = client.get(f"/api/v1/environments/{uuid4()}", headers=headers)

    assert response.status_code == 404


def test_update_environment_successfully(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, project.organization_id)

    create_response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    environment_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/environments/{environment_id}",
        json={"name": "Staging", "description": "Renamed environment"},
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Staging"
    assert data["description"] == "Renamed environment"


def test_update_environment_not_found_returns_404(client, db_session):
    organization, _ = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, organization.id)

    response = client.patch(
        f"/api/v1/environments/{uuid4()}",
        json={"name": "Staging"},
        headers=headers,
    )

    assert response.status_code == 404


def test_create_environment_rejects_unexpected_field(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, project.organization_id)

    response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
            "organization_id": str(uuid4()),
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_update_environment_rejects_explicit_null_name(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, project.organization_id)

    create_response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    environment_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/environments/{environment_id}",
        json={"name": None},
        headers=headers,
    )

    assert response.status_code == 422


def test_list_environments_respects_limit(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, project.organization_id)

    for _ in range(3):
        client.post(
            "/api/v1/environments",
            json={
                "project_id": str(project.id),
                "name": "Development",
                "slug": f"dev-{uuid4().hex[:8]}",
            },
            headers=headers,
        )

    response = client.get(
        "/api/v1/environments",
        params={"project_id": str(project.id), "limit": 2},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_list_other_organization_environments(client, db_session):
    org_a, project_a = create_org_and_project(db_session)
    org_b, _ = create_org_and_project(db_session)
    db_session.commit()

    headers_a = auth_headers(db_session, org_a.id)
    headers_b = auth_headers(db_session, org_b.id)

    client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_a.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers_a,
    )

    response = client.get("/api/v1/environments", headers=headers_b)

    assert response.status_code == 200
    assert response.json() == []


def test_cross_tenant_cannot_get_other_organization_environment(client, db_session):
    org_a, project_a = create_org_and_project(db_session)
    org_b, _ = create_org_and_project(db_session)
    db_session.commit()

    headers_a = auth_headers(db_session, org_a.id)
    headers_b = auth_headers(db_session, org_b.id)

    create_response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_a.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers_a,
    )
    environment_id = create_response.json()["id"]

    response = client.get(f"/api/v1/environments/{environment_id}", headers=headers_b)

    assert response.status_code == 404


def test_cross_tenant_cannot_update_other_organization_environment(client, db_session):
    org_a, project_a = create_org_and_project(db_session)
    org_b, _ = create_org_and_project(db_session)
    db_session.commit()

    headers_a = auth_headers(db_session, org_a.id)
    headers_b = auth_headers(db_session, org_b.id)

    create_response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_a.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers_a,
    )
    environment_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/environments/{environment_id}",
        json={"name": "Hijacked"},
        headers=headers_b,
    )

    assert response.status_code == 404


def test_cross_tenant_cannot_create_environment_in_other_organization_project(
    client, db_session
):
    org_a, project_a = create_org_and_project(db_session)
    org_b, _ = create_org_and_project(db_session)
    db_session.commit()

    headers_b = auth_headers(db_session, org_b.id)

    response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_a.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers_b,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


# ---------------------------------------------------------------------------
# Project- and environment-restricted API keys
# ---------------------------------------------------------------------------


def test_project_restricted_key_can_create_environment_in_its_project(client, db_session):
    organization, project = create_org_and_project(db_session)
    db_session.commit()
    headers = auth_headers(db_session, organization.id, project_id=project.id)

    response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    assert response.status_code == 201


def test_project_restricted_key_cannot_create_environment_in_sibling_project(
    client, db_session
):
    organization, project_a = create_org_and_project(db_session)
    project_b = Project(
        organization_id=organization.id,
        name="Sibling Project",
        slug=f"sibling-project-{uuid4().hex[:8]}",
    )
    db_session.add(project_b)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(db_session, organization.id, project_id=project_a.id)

    response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_b.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_environment_restricted_key_cannot_create_environment(client, db_session):
    """Mandatory M5-D1 requirement: a key confined to one environment must not
    be able to create a sibling environment, even inside its own project."""
    organization, project = create_org_and_project(db_session)
    db_session.commit()

    environment = Environment(
        project_id=project.id,
        name="A1",
        slug=f"a1-{uuid4().hex[:8]}",
    )
    db_session.add(environment)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(db_session, organization.id, environment_id=environment.id)

    response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "A2",
            "slug": f"a2-{uuid4().hex[:8]}",
        },
        headers=headers,
    )

    assert response.status_code == 404

    remaining = client.get(
        "/api/v1/environments",
        params={"project_id": str(project.id)},
        headers=auth_headers(db_session, organization.id),
    ).json()
    assert len(remaining) == 1  # only the original A1 - nothing was created


def test_environment_restricted_key_can_access_its_own_environment(client, db_session):
    organization, project = create_org_and_project(db_session)
    db_session.commit()

    environment = Environment(
        project_id=project.id,
        name="A1",
        slug=f"a1-{uuid4().hex[:8]}",
    )
    db_session.add(environment)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(db_session, organization.id, environment_id=environment.id)

    response = client.get(f"/api/v1/environments/{environment.id}", headers=headers)

    assert response.status_code == 200


def test_environment_restricted_key_cannot_access_sibling_environment(client, db_session):
    organization, project = create_org_and_project(db_session)
    db_session.commit()

    environment_a1 = Environment(
        project_id=project.id, name="A1", slug=f"a1-{uuid4().hex[:8]}"
    )
    environment_a2 = Environment(
        project_id=project.id, name="A2", slug=f"a2-{uuid4().hex[:8]}"
    )
    db_session.add_all([environment_a1, environment_a2])
    db_session.flush()
    db_session.commit()

    headers = auth_headers(
        db_session, organization.id, environment_id=environment_a1.id
    )

    response = client.get(f"/api/v1/environments/{environment_a2.id}", headers=headers)

    assert response.status_code == 404
