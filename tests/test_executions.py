from uuid import uuid4

from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Organization,
    Project,
    Session,
)


def create_test_context(db_session):
    organization = Organization(
        name="Test Organization",
        slug=f"test-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Test Project",
        slug=f"test-project-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()

    environment = Environment(
        project_id=project.id,
        name="Test Environment",
        slug=f"test-env-{uuid4().hex[:8]}",
    )
    db_session.add(environment)
    db_session.flush()

    agent = Agent(
        environment_id=environment.id,
        name="Customer Support Agent",
        slug=f"support-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(agent)
    db_session.flush()

    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        configuration={},
        deployment_status="draft",
    )
    db_session.add(version)

    session = Session(
        project_id=project.id,
        environment_id=environment.id,
        external_session_id=f"test-session-{uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(session)
    db_session.flush()

    return {
        "organization": organization,
        "project": project,
        "environment": environment,
        "agent": agent,
        "version": version,
        "session": session,
    }


def execution_payload(context, external_execution_id):
    return {
        "session_id": str(context["session"].id),
        "agent_id": str(context["agent"].id),
        "agent_version_id": str(context["version"].id),
        "external_execution_id": external_execution_id,
    }


def test_create_execution_successfully(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    payload = execution_payload(context, "test-execution-001")

    response = client.post("/api/v1/executions", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["session_id"] == payload["session_id"]
    assert data["agent_id"] == payload["agent_id"]
    assert data["agent_version_id"] == payload["agent_version_id"]
    assert data["external_execution_id"] == "test-execution-001"
    assert data["status"] == "queued"


def test_identical_request_returns_existing_execution(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    payload = execution_payload(context, "test-idempotency-001")

    first_response = client.post("/api/v1/executions", json=payload)
    second_response = client.post("/api/v1/executions", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    assert first_response.json()["id"] == second_response.json()["id"]


def test_conflicting_request_returns_409(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    payload = execution_payload(context, "test-idempotency-conflict-001")

    first_response = client.post("/api/v1/executions", json=payload)

    conflicting_payload = {
        **payload,
        "agent_version_id": str(uuid4()),
    }

    second_response = client.post(
        "/api/v1/executions",
        json=conflicting_payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_missing_session_returns_422(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()

    payload = execution_payload(context, "test-missing-session-001")
    payload["session_id"] = str(uuid4())

    response = client.post("/api/v1/executions", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Session not found"


def test_agent_version_must_belong_to_agent(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()

    another_agent = Agent(
        environment_id=context["environment"].id,
        name="Another Agent",
        slug=f"another-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(another_agent)
    db_session.flush()

    another_version = AgentVersion(
        agent_id=another_agent.id,
        version="1.0.0",
        configuration={},
        deployment_status="draft",
    )
    db_session.add(another_version)
    db_session.flush()
    db_session.commit()

    payload = execution_payload(context, "test-invalid-version-001")
    payload["agent_version_id"] = str(another_version.id)

    response = client.post("/api/v1/executions", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Agent version does not belong to the specified agent"
    )


def create_execution_via_api(client, db_session, external_id):
    context = create_test_context(db_session)
    db_session.commit()

    payload = execution_payload(context, external_id)
    response = client.post("/api/v1/executions", json=payload)

    assert response.status_code == 201

    return response.json()["id"]


def test_execution_queued_to_running_to_completed(client, db_session):
    execution_id = create_execution_via_api(
        client, db_session, "test-lifecycle-completed-001"
    )

    running_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
    )

    assert running_response.status_code == 200
    assert running_response.json()["status"] == "running"
    assert running_response.json()["started_at"] is not None

    completed_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "completed"},
    )

    assert completed_response.status_code == 200

    data = completed_response.json()

    assert data["status"] == "completed"
    assert data["started_at"] is not None
    assert data["ended_at"] is not None
    assert data["duration_ms"] is not None
    assert data["duration_ms"] >= 0


def test_execution_failure_stores_error_details(client, db_session):
    execution_id = create_execution_via_api(
        client, db_session, "test-lifecycle-failed-001"
    )

    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
    )

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={
            "status": "failed",
            "error_type": "ToolExecutionTimeout",
            "error_message": "Product lookup API timed out",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "failed"
    assert data["error_type"] == "ToolExecutionTimeout"
    assert data["error_message"] == "Product lookup API timed out"
    assert data["ended_at"] is not None
    assert data["duration_ms"] is not None


def test_execution_rejects_invalid_transition(client, db_session):
    execution_id = create_execution_via_api(
        client, db_session, "test-lifecycle-invalid-001"
    )

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "completed"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Transition from 'queued' to 'completed' is not allowed"
    )


def test_terminal_execution_cannot_transition_again(client, db_session):
    execution_id = create_execution_via_api(
        client, db_session, "test-lifecycle-terminal-001"
    )

    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
    )

    completed_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "completed"},
    )

    assert completed_response.status_code == 200

    invalid_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
    )

    assert invalid_response.status_code == 409
    assert invalid_response.json()["detail"] == (
        "Transition from 'completed' to 'running' is not allowed"
    )


def test_failed_transition_requires_error_type(client, db_session):
    execution_id = create_execution_via_api(
        client, db_session, "test-lifecycle-validation-001"
    )

    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
    )

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={
            "status": "failed",
            "error_message": "Tool call failed",
        },
    )

    assert response.status_code == 422


from concurrent.futures import ThreadPoolExecutor


def test_concurrent_idempotent_creation_creates_one_execution(
    client, db_session
):
    context = create_test_context(db_session)
    db_session.commit()

    payload = execution_payload(
        context,
        "test-concurrent-idempotency-001",
    )

    def create_execution_request():
        return client.post("/api/v1/executions", json=payload)

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(
            executor.map(
                lambda _: create_execution_request(),
                range(5),
            )
        )

    status_codes = sorted(response.status_code for response in responses)

    assert status_codes == [200, 200, 200, 200, 201]

    execution_ids = {
        response.json()["id"]
        for response in responses
    }

    assert len(execution_ids) == 1

    execution_count = db_session.query(
        __import__(
            "agentops_api.models.core",
            fromlist=["Execution"],
        ).Execution
    ).filter_by(
        session_id=context["session"].id,
        external_execution_id="test-concurrent-idempotency-001",
    ).count()

    assert execution_count == 1


def test_concurrent_lifecycle_transition_applies_once(
    client, db_session
):
    execution_id = create_execution_via_api(
        client,
        db_session,
        "test-concurrent-transition-001",
    )

    def transition_request():
        return client.patch(
            f"/api/v1/executions/{execution_id}/status",
            json={"status": "running"},
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(
            executor.map(
                lambda _: transition_request(),
                range(5),
            )
        )

    status_codes = sorted(response.status_code for response in responses)

    assert status_codes == [200, 409, 409, 409, 409]

    successful_responses = [
        response for response in responses
        if response.status_code == 200
    ]

    assert successful_responses[0].json()["status"] == "running"
