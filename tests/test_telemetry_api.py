
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import func, select

from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Execution,
    Organization,
    Project,
    Session,
    TelemetryEventRecord,
)
from agentops_api.services.api_key_service import create_api_key


def create_telemetry_context(db_session):
    organization = Organization(
        name="Telemetry API Test Organization",
        slug=f"telemetry-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Telemetry API Test Project",
        slug=f"telemetry-project-{uuid4().hex[:8]}",
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

    agent = Agent(
        environment_id=environment.id,
        name="Telemetry API Test Agent",
        slug=f"agent-{uuid4().hex[:8]}",
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
    db_session.flush()

    session = Session(
        project_id=project.id,
        environment_id=environment.id,
        external_session_id=f"session-{uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(session)
    db_session.flush()

    execution = Execution(
        session_id=session.id,
        agent_id=agent.id,
        agent_version_id=version.id,
        external_execution_id=f"execution-{uuid4().hex[:8]}",
        status="running",
    )
    db_session.add(execution)
    db_session.flush()

    return {
        "organization": organization,
        "project": project,
        "environment": environment,
        "agent": agent,
        "version": version,
        "session": session,
        "execution": execution,
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


def telemetry_event_payload(context):
    return {
        "event_id": str(uuid4()),
        "event_type": "tool.call.completed",
        "occurred_at": "2026-11-16T12:00:00Z",
        "source": {
            "platform": "custom-python",
            "service_name": "customer-support",
            "environment": "development",
        },
        "agent": {
            "id": str(context["agent"].id),
            "version_id": str(context["version"].id),
            "version": "1.0.0",
        },
        "context": {
            "session_id": str(context["session"].id),
            "execution_id": str(context["execution"].id),
            "workflow_id": "workflow-test-001",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7",
            "parent_span_id": "b7ad6b7169203331",
        },
        "operation": {
            "name": "product_lookup",
            "kind": "tool",
            "status": "completed",
            "duration_ms": 520,
        },
        "payload": {
            "capture_mode": "metadata_only",
            "redacted": True,
        },
        "attributes": {
            "http.response.status_code": 200,
        },
    }


def test_ingest_telemetry_event_successfully(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = telemetry_event_payload(context)

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["event_id"] == payload["event_id"]
    assert data["organization_id"] == str(context["organization"].id)
    assert data["event_type"] == "tool.call.completed"
    assert data["created"] is True
    assert data["id"] is not None
    assert data["received_at"] is not None


def test_ingest_telemetry_event_without_auth_returns_401(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()

    response = client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context),
    )

    assert response.status_code == 401


def test_identical_event_retry_returns_existing_record(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = telemetry_event_payload(context)

    first_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_data = first_response.json()
    second_data = second_response.json()

    assert first_data["id"] == second_data["id"]
    assert first_data["event_id"] == second_data["event_id"]
    assert first_data["created"] is True
    assert second_data["created"] is False


def test_same_event_id_with_different_content_returns_409(
    client,
    db_session,
):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = telemetry_event_payload(context)

    first_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    conflicting_payload = {
        **payload,
        "attributes": {
            "http.response.status_code": 503,
        },
    }

    second_response = client.post(
        "/api/v1/telemetry/events",
        json=conflicting_payload,
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_unknown_agent_returns_404(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = telemetry_event_payload(context)
    payload["agent"]["id"] = str(uuid4())

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 404
    assert "Agent not found" in response.json()["detail"]


def test_execution_must_belong_to_agent(client, db_session):
    context = create_telemetry_context(db_session)
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

    another_execution = Execution(
        session_id=context["session"].id,
        agent_id=another_agent.id,
        status="running",
    )
    db_session.add(another_execution)
    db_session.commit()

    payload = telemetry_event_payload(context)
    payload["context"]["execution_id"] = str(another_execution.id)

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422
    assert "Execution must belong to the specified agent and session" in (
        response.json()["detail"]
    )


def test_agent_version_must_belong_to_agent(client, db_session):
    context = create_telemetry_context(db_session)
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
        version="2.0.0",
        configuration={},
        deployment_status="draft",
    )
    db_session.add(another_version)
    db_session.commit()

    payload = telemetry_event_payload(context)
    payload["agent"]["version_id"] = str(another_version.id)

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422
    assert "Agent version does not belong to the specified agent" in (
        response.json()["detail"]
    )


def test_concurrent_identical_events_create_one_record(
    client,
    db_session,
):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = telemetry_event_payload(context)

    def submit_event():
        return client.post(
            "/api/v1/telemetry/events",
            json=payload,
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(
            executor.map(
                lambda _: submit_event(),
                range(5),
            )
        )

    status_codes = sorted(response.status_code for response in responses)

    assert status_codes == [200, 200, 200, 200, 201]

    response_ids = {
        response.json()["id"]
        for response in responses
    }

    assert len(response_ids) == 1

    db_session.expire_all()

    event_count = db_session.scalar(
        select(func.count())
        .select_from(TelemetryEventRecord)
        .where(
            TelemetryEventRecord.organization_id
            == context["organization"].id,
            TelemetryEventRecord.event_id == payload["event_id"],
        )
    )

    assert event_count == 1


def test_list_telemetry_events_with_filters_and_pagination(
    client,
    db_session,
):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payloads = [
        telemetry_event_payload(context)
        for _ in range(3)
    ]

    for index, payload in enumerate(payloads):
        payload["occurred_at"] = f"2026-11-16T12:0{index}:00Z"
        response = client.post(
            "/api/v1/telemetry/events",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/telemetry/events",
        params={
            "agent_id": str(context["agent"].id),
            "event_type": "tool.call.completed",
            "page": 1,
            "page_size": 2,
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 2


def test_list_telemetry_events_without_auth_returns_401(client, db_session):
    response = client.get("/api/v1/telemetry/events")
    assert response.status_code == 401


def test_get_telemetry_event_by_id(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    payload = telemetry_event_payload(context)

    create_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
        headers=headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/api/v1/telemetry/events/{payload['event_id']}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["event_id"] == payload["event_id"]
    assert data["agent_id"] == str(context["agent"].id)
    assert data["execution_id"] == str(context["execution"].id)
    assert data["event_type"] == "tool.call.completed"

    missing_response = client.get(
        f"/api/v1/telemetry/events/{uuid4()}",
        headers=headers,
    )

    assert missing_response.status_code == 404


def test_get_execution_and_trace_telemetry(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    first_payload = telemetry_event_payload(context)
    second_payload = telemetry_event_payload(context)

    for payload in (first_payload, second_payload):
        response = client.post(
            "/api/v1/telemetry/events",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 201

    execution_response = client.get(
        f"/api/v1/telemetry/executions/{context['execution'].id}/events",
        headers=headers,
    )

    trace_response = client.get(
        f"/api/v1/telemetry/traces/{first_payload['context']['trace_id']}/events",
        headers=headers,
    )

    assert execution_response.status_code == 200
    assert trace_response.status_code == 200

    assert execution_response.json()["total"] == 2
    assert trace_response.json()["total"] == 2


def test_telemetry_query_validation(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.get(
        "/api/v1/telemetry/events",
        params={
            "start_time": "2026-11-17T12:00:00Z",
            "end_time": "2026-11-16T12:00:00Z",
        },
        headers=headers,
    )

    assert response.status_code == 422

    pagination_response = client.get(
        "/api/v1/telemetry/events",
        params={"page": 0},
        headers=headers,
    )

    assert pagination_response.status_code == 422


# ---------------------------------------------------------------------------
# Cross-tenant ingestion isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_ingest_referencing_other_organization_agent(
    client, db_session
):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_b)
    payload["agent"]["id"] = str(context_a["agent"].id)
    payload["agent"]["version_id"] = str(context_a["version"].id)

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers_b
    )

    assert response.status_code == 404
    assert "Agent not found" in response.json()["detail"]


def test_cross_tenant_cannot_ingest_referencing_other_organization_agent_version(
    client, db_session
):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_b)
    payload["agent"]["version_id"] = str(context_a["version"].id)
    payload["agent"].pop("version")

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers_b
    )

    assert response.status_code == 404
    assert "Agent version not found" in response.json()["detail"]


def test_cross_tenant_cannot_ingest_referencing_other_organization_session(
    client, db_session
):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_b)
    payload["context"]["session_id"] = str(context_a["session"].id)

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers_b
    )

    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_cross_tenant_cannot_ingest_referencing_other_organization_execution(
    client, db_session
):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_b)
    payload["context"]["execution_id"] = str(context_a["execution"].id)

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers_b
    )

    assert response.status_code == 404
    assert "Execution not found" in response.json()["detail"]


def test_project_restricted_key_cannot_ingest_for_other_project(client, db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()

    # A key restricted to project A, used to submit an event entirely about
    # project B's own resources.
    headers = auth_headers(
        db_session, context_a["organization"].id, project_id=context_a["project"].id
    )

    payload = telemetry_event_payload(context_b)

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers
    )

    assert response.status_code == 404


def test_environment_restricted_key_cannot_ingest_for_other_environment(
    client, db_session
):
    context = create_telemetry_context(db_session)
    db_session.commit()

    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()

    other_agent = Agent(
        environment_id=other_environment.id,
        name="Staging Agent",
        slug=f"staging-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(other_agent)
    db_session.flush()
    db_session.commit()

    headers = auth_headers(
        db_session, context["organization"].id, environment_id=context["environment"].id
    )

    payload = telemetry_event_payload(context)
    payload["agent"]["id"] = str(other_agent.id)
    payload["agent"].pop("version_id")
    payload["agent"].pop("version")

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers
    )

    assert response.status_code == 404


def test_rejected_cross_tenant_ingestion_creates_no_record(client, db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_b)
    payload["agent"]["id"] = str(context_a["agent"].id)
    payload["agent"]["version_id"] = str(context_a["version"].id)

    response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers_b
    )
    assert response.status_code == 404

    db_session.expire_all()
    count = db_session.scalar(
        select(func.count())
        .select_from(TelemetryEventRecord)
        .where(TelemetryEventRecord.event_id == payload["event_id"])
    )
    assert count == 0


# ---------------------------------------------------------------------------
# Cross-tenant event retrieval isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_get_other_organization_event_by_id(client, db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_a)
    create_response = client.post(
        "/api/v1/telemetry/events", json=payload, headers=headers_a
    )
    assert create_response.status_code == 201

    response = client.get(
        f"/api/v1/telemetry/events/{payload['event_id']}", headers=headers_b
    )

    assert response.status_code == 404


def test_cross_tenant_list_never_returns_other_organization_events(client, db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context_a),
        headers=headers_a,
    )

    response = client.get("/api/v1/telemetry/events", headers=headers_b)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_project_restricted_key_cannot_retrieve_events_from_other_project(
    client, db_session
):
    organization = Organization(
        name="Project Scope Org", slug=f"project-scope-org-{uuid4().hex[:8]}"
    )
    db_session.add(organization)
    db_session.flush()

    project_a = Project(
        organization_id=organization.id,
        name="Project A",
        slug=f"project-a-{uuid4().hex[:8]}",
    )
    project_b = Project(
        organization_id=organization.id,
        name="Project B",
        slug=f"project-b-{uuid4().hex[:8]}",
    )
    db_session.add_all([project_a, project_b])
    db_session.flush()

    def build_full_context(project):
        environment = Environment(
            project_id=project.id, name="Dev", slug=f"dev-{uuid4().hex[:8]}"
        )
        db_session.add(environment)
        db_session.flush()

        agent = Agent(
            environment_id=environment.id,
            name="Agent",
            slug=f"agent-{uuid4().hex[:8]}",
            framework="custom-python",
            status="registered",
        )
        db_session.add(agent)
        db_session.flush()

        version = AgentVersion(
            agent_id=agent.id, version="1.0.0", configuration={}, deployment_status="draft"
        )
        db_session.add(version)
        db_session.flush()

        session = Session(
            project_id=project.id,
            environment_id=environment.id,
            external_session_id=f"session-{uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(session)
        db_session.flush()

        execution = Execution(
            session_id=session.id,
            agent_id=agent.id,
            agent_version_id=version.id,
            external_execution_id=f"execution-{uuid4().hex[:8]}",
            status="running",
        )
        db_session.add(execution)
        db_session.flush()

        return {
            "organization": organization,
            "project": project,
            "environment": environment,
            "agent": agent,
            "version": version,
            "session": session,
            "execution": execution,
        }

    context_a = build_full_context(project_a)
    context_b = build_full_context(project_b)
    db_session.commit()

    full_access_headers = auth_headers(db_session, organization.id)
    client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context_a),
        headers=full_access_headers,
    )
    client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context_b),
        headers=full_access_headers,
    )

    project_a_headers = auth_headers(
        db_session, organization.id, project_id=project_a.id
    )

    response = client.get("/api/v1/telemetry/events", headers=project_a_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_environment_restricted_key_cannot_retrieve_events_from_other_environment(
    client, db_session
):
    context = create_telemetry_context(db_session)
    db_session.commit()
    full_headers = auth_headers(db_session, context["organization"].id)

    client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context),
        headers=full_headers,
    )

    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()
    db_session.commit()

    scoped_headers = auth_headers(
        db_session, context["organization"].id, environment_id=other_environment.id
    )

    response = client.get("/api/v1/telemetry/events", headers=scoped_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 0


# ---------------------------------------------------------------------------
# Execution-specific event query isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_retrieve_events_for_other_organization_execution(
    client, db_session
):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context_a),
        headers=headers_a,
    )

    response = client.get(
        f"/api/v1/telemetry/executions/{context_a['execution'].id}/events",
        headers=headers_b,
    )

    assert response.status_code == 404


def test_environment_restricted_key_cannot_retrieve_execution_events_in_sibling_environment(
    client, db_session
):
    context = create_telemetry_context(db_session)
    db_session.commit()
    full_headers = auth_headers(db_session, context["organization"].id)

    client.post(
        "/api/v1/telemetry/events",
        json=telemetry_event_payload(context),
        headers=full_headers,
    )

    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()
    db_session.commit()

    scoped_headers = auth_headers(
        db_session, context["organization"].id, environment_id=other_environment.id
    )

    response = client.get(
        f"/api/v1/telemetry/executions/{context['execution'].id}/events",
        headers=scoped_headers,
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Trace isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_retrieve_other_organization_trace(client, db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    payload = telemetry_event_payload(context_a)
    client.post("/api/v1/telemetry/events", json=payload, headers=headers_a)

    response = client.get(
        f"/api/v1/telemetry/traces/{payload['context']['trace_id']}/events",
        headers=headers_b,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_trace_shared_across_organizations_only_returns_callers_events(
    client, db_session
):
    """Two different organizations happen to produce events carrying the same
    trace_id (e.g. a collision, or a trace replayed across environments). A
    scoped trace query must return only the caller's own matching events."""
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    db_session.commit()
    headers_a = auth_headers(db_session, context_a["organization"].id)
    headers_b = auth_headers(db_session, context_b["organization"].id)

    shared_trace_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    payload_a = telemetry_event_payload(context_a)
    payload_a["context"]["trace_id"] = shared_trace_id
    payload_b = telemetry_event_payload(context_b)
    payload_b["context"]["trace_id"] = shared_trace_id
    payload_b["context"]["span_id"] = "1111111111111111"

    client.post("/api/v1/telemetry/events", json=payload_a, headers=headers_a)
    client.post("/api/v1/telemetry/events", json=payload_b, headers=headers_b)

    response_a = client.get(
        f"/api/v1/telemetry/traces/{shared_trace_id}/events", headers=headers_a
    )
    response_b = client.get(
        f"/api/v1/telemetry/traces/{shared_trace_id}/events", headers=headers_b
    )

    assert response_a.json()["total"] == 1
    assert response_a.json()["items"][0]["event_id"] == payload_a["event_id"]

    assert response_b.json()["total"] == 1
    assert response_b.json()["items"][0]["event_id"] == payload_b["event_id"]


def test_project_restricted_key_cannot_retrieve_other_project_trace(client, db_session):
    organization = Organization(
        name="Trace Project Org", slug=f"trace-project-org-{uuid4().hex[:8]}"
    )
    db_session.add(organization)
    db_session.flush()

    project_a = Project(
        organization_id=organization.id, name="Project A", slug=f"trace-proj-a-{uuid4().hex[:8]}"
    )
    project_b = Project(
        organization_id=organization.id, name="Project B", slug=f"trace-proj-b-{uuid4().hex[:8]}"
    )
    db_session.add_all([project_a, project_b])
    db_session.flush()

    def build_context(project):
        environment = Environment(
            project_id=project.id, name="Dev", slug=f"dev-{uuid4().hex[:8]}"
        )
        db_session.add(environment)
        db_session.flush()
        agent = Agent(
            environment_id=environment.id,
            name="Agent",
            slug=f"agent-{uuid4().hex[:8]}",
            framework="custom-python",
            status="registered",
        )
        db_session.add(agent)
        db_session.flush()
        version = AgentVersion(
            agent_id=agent.id, version="1.0.0", configuration={}, deployment_status="draft"
        )
        db_session.add(version)
        db_session.flush()
        session = Session(
            project_id=project.id,
            environment_id=environment.id,
            external_session_id=f"session-{uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(session)
        db_session.flush()
        execution = Execution(
            session_id=session.id,
            agent_id=agent.id,
            agent_version_id=version.id,
            external_execution_id=f"execution-{uuid4().hex[:8]}",
            status="running",
        )
        db_session.add(execution)
        db_session.flush()
        return {
            "organization": organization,
            "project": project,
            "environment": environment,
            "agent": agent,
            "version": version,
            "session": session,
            "execution": execution,
        }

    context_a = build_context(project_a)
    context_b = build_context(project_b)
    db_session.commit()

    full_headers = auth_headers(db_session, organization.id)

    shared_trace_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    payload_a = telemetry_event_payload(context_a)
    payload_a["context"]["trace_id"] = shared_trace_id
    payload_b = telemetry_event_payload(context_b)
    payload_b["context"]["trace_id"] = shared_trace_id
    payload_b["context"]["span_id"] = "2222222222222222"

    client.post("/api/v1/telemetry/events", json=payload_a, headers=full_headers)
    client.post("/api/v1/telemetry/events", json=payload_b, headers=full_headers)

    project_a_headers = auth_headers(
        db_session, organization.id, project_id=project_a.id
    )

    response = client.get(
        f"/api/v1/telemetry/traces/{shared_trace_id}/events",
        headers=project_a_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["event_id"] == payload_a["event_id"]


def test_environment_restricted_key_cannot_retrieve_other_environment_trace(
    client, db_session
):
    context = create_telemetry_context(db_session)
    db_session.commit()

    other_environment = Environment(
        project_id=context["project"].id,
        name="Staging",
        slug=f"staging-{uuid4().hex[:8]}",
    )
    db_session.add(other_environment)
    db_session.flush()

    other_agent = Agent(
        environment_id=other_environment.id,
        name="Staging Agent",
        slug=f"staging-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(other_agent)
    db_session.flush()

    other_version = AgentVersion(
        agent_id=other_agent.id, version="1.0.0", configuration={}, deployment_status="draft"
    )
    db_session.add(other_version)
    db_session.flush()

    other_session = Session(
        project_id=context["project"].id,
        environment_id=other_environment.id,
        external_session_id=f"session-{uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(other_session)
    db_session.flush()

    other_execution = Execution(
        session_id=other_session.id,
        agent_id=other_agent.id,
        agent_version_id=other_version.id,
        external_execution_id=f"execution-{uuid4().hex[:8]}",
        status="running",
    )
    db_session.add(other_execution)
    db_session.flush()
    db_session.commit()

    other_context = {
        "organization": context["organization"],
        "project": context["project"],
        "environment": other_environment,
        "agent": other_agent,
        "version": other_version,
        "session": other_session,
        "execution": other_execution,
    }

    full_headers = auth_headers(db_session, context["organization"].id)

    shared_trace_id = "cccccccccccccccccccccccccccccccc"
    payload_original = telemetry_event_payload(context)
    payload_original["context"]["trace_id"] = shared_trace_id
    payload_other = telemetry_event_payload(other_context)
    payload_other["context"]["trace_id"] = shared_trace_id
    payload_other["context"]["span_id"] = "3333333333333333"

    client.post(
        "/api/v1/telemetry/events", json=payload_original, headers=full_headers
    )
    client.post(
        "/api/v1/telemetry/events", json=payload_other, headers=full_headers
    )

    scoped_headers = auth_headers(
        db_session, context["organization"].id, environment_id=context["environment"].id
    )

    response = client.get(
        f"/api/v1/telemetry/traces/{shared_trace_id}/events",
        headers=scoped_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["event_id"] == payload_original["event_id"]
