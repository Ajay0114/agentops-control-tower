from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Execution,
    Organization,
    Project,
    Session,
)
from agentops_api.services.api_key_service import create_api_key


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
    headers = auth_headers(db_session, context["organization"].id)
    payload = execution_payload(context, "test-execution-001")

    response = client.post("/api/v1/executions", json=payload, headers=headers)

    assert response.status_code == 201

    data = response.json()

    assert data["session_id"] == payload["session_id"]
    assert data["agent_id"] == payload["agent_id"]
    assert data["agent_version_id"] == payload["agent_version_id"]
    assert data["external_execution_id"] == "test-execution-001"
    assert data["status"] == "queued"


def test_create_execution_without_auth_returns_401(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/executions", json=execution_payload(context, "no-auth")
    )

    assert response.status_code == 401


def test_identical_request_returns_existing_execution(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)
    payload = execution_payload(context, "test-idempotency-001")

    first_response = client.post("/api/v1/executions", json=payload, headers=headers)
    second_response = client.post("/api/v1/executions", json=payload, headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    assert first_response.json()["id"] == second_response.json()["id"]


def test_conflicting_request_returns_409(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)
    payload = execution_payload(context, "test-idempotency-conflict-001")

    first_response = client.post("/api/v1/executions", json=payload, headers=headers)

    conflicting_payload = {
        **payload,
        "agent_version_id": str(uuid4()),
    }

    second_response = client.post(
        "/api/v1/executions",
        json=conflicting_payload,
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_missing_session_returns_404(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = execution_payload(context, "test-missing-session-001")
    payload["session_id"] = str(uuid4())

    response = client.post("/api/v1/executions", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_agent_version_must_belong_to_agent(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

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

    response = client.post("/api/v1/executions", json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Agent version does not belong to the specified agent"
    )


def test_agent_and_session_in_different_environments_returns_422(client, db_session):
    """Agent and Session each individually resolve within the caller's own
    scope, but live in different environments - a self-consistency problem
    (422), not a scope problem (404). No execution may be created."""
    context = create_test_context(db_session)

    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()

    other_environment_agent = Agent(
        environment_id=other_environment.id,
        name="Staging Agent",
        slug=f"staging-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(other_environment_agent)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(db_session, context["organization"].id)

    # The session stays in context["environment"]; the agent lives in a
    # different environment of the same (authenticated) organization.
    payload = execution_payload(context, "cross-environment-execution")
    payload["agent_id"] = str(other_environment_agent.id)

    response = client.post("/api/v1/executions", json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Agent and session must belong to the same environment"
    )

    execution_count = db_session.query(Execution).filter_by(
        session_id=context["session"].id,
        external_execution_id="cross-environment-execution",
    ).count()
    assert execution_count == 0


def create_execution_via_api(client, db_session, external_id):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = execution_payload(context, external_id)
    response = client.post("/api/v1/executions", json=payload, headers=headers)

    assert response.status_code == 201

    return response.json()["id"], headers, context


def test_execution_queued_to_running_to_completed(client, db_session):
    execution_id, headers, _ = create_execution_via_api(
        client, db_session, "test-lifecycle-completed-001"
    )

    running_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers,
    )

    assert running_response.status_code == 200
    assert running_response.json()["status"] == "running"
    assert running_response.json()["started_at"] is not None

    completed_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "completed"},
        headers=headers,
    )

    assert completed_response.status_code == 200

    data = completed_response.json()

    assert data["status"] == "completed"
    assert data["started_at"] is not None
    assert data["ended_at"] is not None
    assert data["duration_ms"] is not None
    assert data["duration_ms"] >= 0


def test_execution_failure_stores_error_details(client, db_session):
    execution_id, headers, _ = create_execution_via_api(
        client, db_session, "test-lifecycle-failed-001"
    )

    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={
            "status": "failed",
            "error_type": "ToolExecutionTimeout",
            "error_message": "Product lookup API timed out",
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "failed"
    assert data["error_type"] == "ToolExecutionTimeout"
    assert data["error_message"] == "Product lookup API timed out"
    assert data["ended_at"] is not None
    assert data["duration_ms"] is not None


def test_execution_rejects_invalid_transition(client, db_session):
    execution_id, headers, _ = create_execution_via_api(
        client, db_session, "test-lifecycle-invalid-001"
    )

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "completed"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Transition from 'queued' to 'completed' is not allowed"
    )


def test_terminal_execution_cannot_transition_again(client, db_session):
    execution_id, headers, _ = create_execution_via_api(
        client, db_session, "test-lifecycle-terminal-001"
    )

    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers,
    )

    completed_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "completed"},
        headers=headers,
    )

    assert completed_response.status_code == 200

    invalid_response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers,
    )

    assert invalid_response.status_code == 409
    assert invalid_response.json()["detail"] == (
        "Transition from 'completed' to 'running' is not allowed"
    )


def test_failed_transition_requires_error_type(client, db_session):
    execution_id, headers, _ = create_execution_via_api(
        client, db_session, "test-lifecycle-validation-001"
    )

    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={
            "status": "failed",
            "error_message": "Tool call failed",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_concurrent_idempotent_creation_creates_one_execution(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = execution_payload(
        context,
        "test-concurrent-idempotency-001",
    )

    def create_execution_request():
        return client.post("/api/v1/executions", json=payload, headers=headers)

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

    execution_count = db_session.query(Execution).filter_by(
        session_id=context["session"].id,
        external_execution_id="test-concurrent-idempotency-001",
    ).count()

    assert execution_count == 1


def test_concurrent_lifecycle_transition_applies_once(client, db_session):
    execution_id, headers, _ = create_execution_via_api(
        client,
        db_session,
        "test-concurrent-transition-001",
    )

    def transition_request():
        return client.patch(
            f"/api/v1/executions/{execution_id}/status",
            json={"status": "running"},
            headers=headers,
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


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_create_execution_with_other_organization_session(
    client, db_session
):
    context_a = create_test_context(db_session)
    context_b = create_test_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.post(
        "/api/v1/executions",
        json=execution_payload(context_a, "hijack-attempt"),
        headers=headers_b,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_cross_tenant_cannot_list_other_organization_executions(client, db_session):
    _, headers_a, context_a = create_execution_via_api(
        client, db_session, "org-a-execution"
    )
    context_b = create_test_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.get("/api/v1/executions", headers=headers_b)

    assert response.status_code == 200
    assert response.json() == []


def test_cross_tenant_cannot_get_other_organization_execution(client, db_session):
    execution_id, headers_a, context_a = create_execution_via_api(
        client, db_session, "org-a-execution-get"
    )
    context_b = create_test_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.get(f"/api/v1/executions/{execution_id}", headers=headers_b)

    assert response.status_code == 404


def test_cross_tenant_cannot_transition_other_organization_execution(client, db_session):
    execution_id, headers_a, context_a = create_execution_via_api(
        client, db_session, "org-a-execution-transition"
    )
    context_b = create_test_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    response = client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers_b,
    )

    assert response.status_code == 404

    # Confirm the hijack attempt genuinely did not mutate the execution.
    unaffected = client.get(f"/api/v1/executions/{execution_id}", headers=headers_a)
    assert unaffected.json()["status"] == "queued"


def test_cross_tenant_cannot_create_execution_with_other_organization_agent(
    client, db_session
):
    context_a = create_test_context(db_session)
    context_b = create_test_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    # Use org B's own session but reference org A's agent.
    payload = execution_payload(context_b, "cross-tenant-agent")
    payload["agent_id"] = str(context_a["agent"].id)

    response = client.post("/api/v1/executions", json=payload, headers=headers_b)

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


# ---------------------------------------------------------------------------
# Project- and environment-restricted API keys
# ---------------------------------------------------------------------------


def test_environment_restricted_key_can_create_execution_in_its_environment(
    client, db_session
):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(
        db_session,
        context["organization"].id,
        environment_id=context["environment"].id,
    )

    response = client.post(
        "/api/v1/executions",
        json=execution_payload(context, "scoped-execution"),
        headers=headers,
    )

    assert response.status_code == 201


def test_environment_restricted_key_cannot_access_execution_in_sibling_environment(
    client, db_session
):
    execution_id, _, context = create_execution_via_api(
        client, db_session, "sibling-env-execution"
    )

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

    response = client.get(f"/api/v1/executions/{execution_id}", headers=scoped_headers)

    assert response.status_code == 404


# --- M7: additional list filters (environment_id, time range, id search) and
# the X-Total-Count header, added for the dashboard's executions page. The
# response body stays a bare list (see the cross-tenant test above asserting
# response.json() == []) so these are purely additive.


def test_list_executions_returns_total_count_header(client, db_session):
    create_execution_via_api(client, db_session, "count-header-001")
    execution_id_2, headers, context = create_execution_via_api(
        client, db_session, "count-header-002"
    )

    # Re-use the same org via a fresh key scoped the same way isn't possible
    # across two independent contexts, so just verify against the second
    # context's own single execution for a precise count.
    response = client.get("/api/v1/executions", headers=headers)

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "1"
    assert len(response.json()) == 1


def test_list_executions_filters_by_environment_id(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = execution_payload(context, "env-filter-match")
    client.post("/api/v1/executions", json=payload, headers=headers)

    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()
    other_session = Session(
        project_id=context["project"].id,
        environment_id=other_environment.id,
        external_session_id=f"other-session-{uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(other_session)
    db_session.flush()
    db_session.commit()

    other_payload = {
        "session_id": str(other_session.id),
        "agent_id": str(context["agent"].id),
        "agent_version_id": str(context["version"].id),
        "external_execution_id": "env-filter-no-match",
    }
    # The agent belongs to the original environment, so creating an execution
    # against a session in a different environment is rejected - which is
    # exactly why this filter is meaningful: we instead register a second
    # agent in the other environment to produce a genuinely different-
    # environment execution.
    other_agent = Agent(
        environment_id=other_environment.id,
        name="Other Env Agent",
        slug=f"other-env-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(other_agent)
    db_session.flush()
    other_payload["agent_id"] = str(other_agent.id)
    other_payload["agent_version_id"] = None
    db_session.commit()

    client.post("/api/v1/executions", json=other_payload, headers=headers)

    response = client.get(
        "/api/v1/executions",
        params={"environment_id": str(context["environment"].id)},
        headers=headers,
    )

    assert response.status_code == 200
    ids = {item["external_execution_id"] for item in response.json()}
    assert ids == {"env-filter-match"}


def test_list_executions_filters_by_execution_id_search(client, db_session):
    execution_id, headers, _ = create_execution_via_api(client, db_session, "search-target")

    response = client.get(
        "/api/v1/executions", params={"execution_id": execution_id}, headers=headers
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == execution_id


def test_list_executions_filters_by_started_after_and_before(client, db_session):
    execution_id, headers, _ = create_execution_via_api(client, db_session, "time-range-001")
    client.patch(
        f"/api/v1/executions/{execution_id}/status",
        json={"status": "running"},
        headers=headers,
    )

    far_future = "2999-01-01T00:00:00Z"
    far_past = "1999-01-01T00:00:00Z"

    too_late = client.get(
        "/api/v1/executions", params={"started_after": far_future}, headers=headers
    )
    assert too_late.json() == []

    too_early = client.get(
        "/api/v1/executions", params={"started_before": far_past}, headers=headers
    )
    assert too_early.json() == []

    in_range = client.get(
        "/api/v1/executions",
        params={"started_after": far_past, "started_before": far_future},
        headers=headers,
    )
    assert len(in_range.json()) == 1
    assert in_range.json()[0]["id"] == execution_id
