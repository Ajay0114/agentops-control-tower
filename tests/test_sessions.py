from uuid import uuid4

from agentops_api.models.core import Environment, Organization, Project


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


def session_payload(context, external_session_id):
    return {
        "project_id": str(context["project"].id),
        "environment_id": str(context["environment"].id),
        "external_session_id": external_session_id,
    }


def test_create_session_successfully(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    payload = session_payload(context, f"conversation-{uuid4().hex[:8]}")

    response = client.post("/api/v1/sessions", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == payload["project_id"]
    assert data["environment_id"] == payload["environment_id"]
    assert data["external_session_id"] == payload["external_session_id"]
    assert data["status"] == "active"
    assert data["ended_at"] is None


def test_create_session_missing_environment_returns_422(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    payload = session_payload(context, "conversation-missing-env")
    payload["environment_id"] = str(uuid4())

    response = client.post("/api/v1/sessions", json=payload)

    assert response.status_code == 422
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

    # environment belongs to context["project"], but the caller claims it
    # belongs to a different project.
    payload = session_payload(context, "conversation-cross-project")
    payload["project_id"] = str(other_project.id)

    response = client.post("/api/v1/sessions", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Environment does not belong to the specified project"
    )


def test_identical_session_request_returns_existing_session(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    payload = session_payload(context, f"conversation-{uuid4().hex[:8]}")

    first_response = client.post("/api/v1/sessions", json=payload)
    second_response = client.post("/api/v1/sessions", json=payload)

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

    external_id = f"conversation-{uuid4().hex[:8]}"

    first_response = client.post(
        "/api/v1/sessions", json=session_payload(context, external_id)
    )
    second_response = client.post(
        "/api/v1/sessions",
        json={
            "project_id": str(context["project"].id),
            "environment_id": str(other_environment.id),
            "external_session_id": external_id,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] != second_response.json()["id"]


def test_list_sessions_filtered_by_project_and_environment(client, db_session):
    context_a = create_environment_context(db_session)
    context_b = create_environment_context(db_session)
    db_session.commit()

    client.post("/api/v1/sessions", json=session_payload(context_a, "session-a"))
    client.post("/api/v1/sessions", json=session_payload(context_b, "session-b"))

    response = client.get(
        "/api/v1/sessions", params={"project_id": str(context_a["project"].id)}
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["external_session_id"] == "session-a"


def test_get_session_not_found_returns_404(client, db_session):
    response = client.get(f"/api/v1/sessions/{uuid4()}")

    assert response.status_code == 404


def test_create_session_rejects_unexpected_field(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    payload = session_payload(context, f"conversation-{uuid4().hex[:8]}")
    payload["status"] = "active"

    response = client.post("/api/v1/sessions", json=payload)

    assert response.status_code == 422


def test_list_sessions_respects_limit(client, db_session):
    context = create_environment_context(db_session)
    db_session.commit()

    for i in range(3):
        client.post(
            "/api/v1/sessions", json=session_payload(context, f"session-{i}")
        )

    response = client.get(
        "/api/v1/sessions",
        params={"project_id": str(context["project"].id), "limit": 2},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
