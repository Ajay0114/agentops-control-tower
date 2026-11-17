from uuid import uuid4

from agentops_api.models.core import Organization, Project


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


def test_create_environment_successfully(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    payload = {
        "project_id": str(project.id),
        "name": "Development",
        "slug": f"dev-{uuid4().hex[:8]}",
        "description": "Local development environment",
    }

    response = client.post("/api/v1/environments", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == payload["project_id"]
    assert data["name"] == "Development"
    assert data["slug"] == payload["slug"]
    assert data["description"] == "Local development environment"


def test_create_environment_missing_project_returns_422(client, db_session):
    payload = {
        "project_id": str(uuid4()),
        "name": "Development",
        "slug": f"dev-{uuid4().hex[:8]}",
    }

    response = client.post("/api/v1/environments", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Project not found"


def test_duplicate_environment_slug_returns_409(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    slug = f"dev-{uuid4().hex[:8]}"
    payload = {"project_id": str(project.id), "name": "Development", "slug": slug}

    first_response = client.post("/api/v1/environments", json=payload)
    second_response = client.post("/api/v1/environments", json=payload)

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
    )
    response_b = client.post(
        "/api/v1/environments",
        json={"project_id": str(project_b.id), "name": "Development", "slug": slug},
    )

    assert response_a.status_code == 201
    assert response_b.status_code == 201
    assert response_a.json()["id"] != response_b.json()["id"]


def test_list_environments_filtered_by_project(client, db_session):
    _, project_a = create_org_and_project(db_session)
    _, project_b = create_org_and_project(db_session)
    db_session.commit()

    client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_a.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
    )
    client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project_b.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
    )

    response = client.get(
        "/api/v1/environments", params={"project_id": str(project_a.id)}
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["project_id"] == str(project_a.id)


def test_get_environment_not_found_returns_404(client, db_session):
    response = client.get(f"/api/v1/environments/{uuid4()}")

    assert response.status_code == 404


def test_update_environment_successfully(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    create_response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
    )
    environment_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/environments/{environment_id}",
        json={"name": "Staging", "description": "Renamed environment"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Staging"
    assert data["description"] == "Renamed environment"


def test_update_environment_not_found_returns_404(client, db_session):
    response = client.patch(
        f"/api/v1/environments/{uuid4()}",
        json={"name": "Staging"},
    )

    assert response.status_code == 404


def test_create_environment_rejects_unexpected_field(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
            "organization_id": str(uuid4()),
        },
    )

    assert response.status_code == 422


def test_update_environment_rejects_explicit_null_name(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    create_response = client.post(
        "/api/v1/environments",
        json={
            "project_id": str(project.id),
            "name": "Development",
            "slug": f"dev-{uuid4().hex[:8]}",
        },
    )
    environment_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/environments/{environment_id}",
        json={"name": None},
    )

    assert response.status_code == 422


def test_list_environments_respects_limit(client, db_session):
    _, project = create_org_and_project(db_session)
    db_session.commit()

    for _ in range(3):
        client.post(
            "/api/v1/environments",
            json={
                "project_id": str(project.id),
                "name": "Development",
                "slug": f"dev-{uuid4().hex[:8]}",
            },
        )

    response = client.get(
        "/api/v1/environments",
        params={"project_id": str(project.id), "limit": 2},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
