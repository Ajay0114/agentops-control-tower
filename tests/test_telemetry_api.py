
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

    payload = telemetry_event_payload(context)

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["event_id"] == payload["event_id"]
    assert data["organization_id"] == str(context["organization"].id)
    assert data["event_type"] == "tool.call.completed"
    assert data["created"] is True
    assert data["id"] is not None
    assert data["received_at"] is not None


def test_identical_event_retry_returns_existing_record(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()

    payload = telemetry_event_payload(context)

    first_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
    )
    second_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
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

    payload = telemetry_event_payload(context)

    first_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
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
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_unknown_agent_returns_422(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()

    payload = telemetry_event_payload(context)
    payload["agent"]["id"] = str(uuid4())

    response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
    )

    assert response.status_code == 422
    assert "Agent not found" in response.json()["detail"]


def test_execution_must_belong_to_agent(client, db_session):
    context = create_telemetry_context(db_session)

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
    )

    assert response.status_code == 422
    assert "Execution must belong to the specified agent and session" in (
        response.json()["detail"]
    )


def test_agent_version_must_belong_to_agent(client, db_session):
    context = create_telemetry_context(db_session)

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

    payload = telemetry_event_payload(context)

    def submit_event():
        return client.post(
            "/api/v1/telemetry/events",
            json=payload,
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

    payloads = [
        telemetry_event_payload(context)
        for _ in range(3)
    ]

    for index, payload in enumerate(payloads):
        payload["occurred_at"] = f"2026-11-16T12:0{index}:00Z"
        response = client.post(
            "/api/v1/telemetry/events",
            json=payload,
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
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 2


def test_get_telemetry_event_by_id(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()

    payload = telemetry_event_payload(context)

    create_response = client.post(
        "/api/v1/telemetry/events",
        json=payload,
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/api/v1/telemetry/events/{payload['event_id']}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["event_id"] == payload["event_id"]
    assert data["agent_id"] == str(context["agent"].id)
    assert data["execution_id"] == str(context["execution"].id)
    assert data["event_type"] == "tool.call.completed"

    missing_response = client.get(
        f"/api/v1/telemetry/events/{uuid4()}"
    )

    assert missing_response.status_code == 404


def test_get_execution_and_trace_telemetry(client, db_session):
    context = create_telemetry_context(db_session)
    db_session.commit()

    first_payload = telemetry_event_payload(context)
    second_payload = telemetry_event_payload(context)

    for payload in (first_payload, second_payload):
        response = client.post(
            "/api/v1/telemetry/events",
            json=payload,
        )
        assert response.status_code == 201

    execution_response = client.get(
        f"/api/v1/telemetry/executions/{context['execution'].id}/events"
    )

    trace_response = client.get(
        f"/api/v1/telemetry/traces/{first_payload['context']['trace_id']}/events"
    )

    assert execution_response.status_code == 200
    assert trace_response.status_code == 200

    assert execution_response.json()["total"] == 2
    assert trace_response.json()["total"] == 2


def test_telemetry_query_validation(client):
    response = client.get(
        "/api/v1/telemetry/events",
        params={
            "start_time": "2026-11-17T12:00:00Z",
            "end_time": "2026-11-16T12:00:00Z",
        },
    )

    assert response.status_code == 422

    pagination_response = client.get(
        "/api/v1/telemetry/events",
        params={"page": 0},
    )

    assert pagination_response.status_code == 422

