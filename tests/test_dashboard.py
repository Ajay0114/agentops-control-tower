from datetime import datetime, timezone
from uuid import uuid4

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


def create_test_context(db_session):
    organization = Organization(name="Test Organization", slug=f"test-org-{uuid4().hex[:8]}")
    db_session.add(organization)
    db_session.flush()

    project = Project(organization_id=organization.id, name="Test Project", slug=f"test-project-{uuid4().hex[:8]}")
    db_session.add(project)
    db_session.flush()

    environment = Environment(project_id=project.id, name="Test Environment", slug=f"test-env-{uuid4().hex[:8]}")
    db_session.add(environment)
    db_session.flush()

    agent = Agent(
        environment_id=environment.id,
        name="Support Agent",
        slug=f"support-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db_session.add(agent)
    db_session.flush()

    version = AgentVersion(agent_id=agent.id, version="1.0.0", configuration={}, deployment_status="draft")
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


def make_execution(db_session, context, status, *, external_id=None):
    execution = Execution(
        session_id=context["session"].id,
        agent_id=context["agent"].id,
        agent_version_id=context["version"].id,
        external_execution_id=external_id or f"exec-{uuid4().hex[:8]}",
        status=status,
    )
    db_session.add(execution)
    db_session.flush()
    return execution


def test_overview_with_no_data_distinguishes_unavailable_from_zero(client, db_session):
    context = create_test_context(db_session)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.get("/api/v1/dashboard/overview", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["total_executions"] == 0
    assert body["total_agents"] == 1
    # No completed/failed executions yet -> no basis for a rate, not 0%.
    assert body["success_rate"] is None
    # No telemetry events at all -> unavailable, not a genuine 0 tokens.
    assert body["total_tokens_used"] is None
    assert body["recent_executions"] == []
    assert len(body["execution_trend"]) == 7


def test_overview_counts_executions_by_status(client, db_session):
    context = create_test_context(db_session)
    make_execution(db_session, context, "completed")
    make_execution(db_session, context, "completed")
    make_execution(db_session, context, "failed")
    make_execution(db_session, context, "running")
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.get("/api/v1/dashboard/overview", headers=headers)
    body = response.json()

    assert body["total_executions"] == 4
    assert body["completed_executions"] == 2
    assert body["failed_executions"] == 1
    assert body["running_executions"] == 1
    assert body["success_rate"] == 2 / 3


def test_overview_sums_token_usage_from_telemetry(client, db_session):
    context = create_test_context(db_session)
    execution = make_execution(db_session, context, "completed")

    event = TelemetryEventRecord(
        organization_id=context["organization"].id,
        event_id=uuid4(),
        schema_version="1.0.0",
        event_type="llm.request.completed",
        occurred_at=datetime.now(timezone.utc),
        agent_id=context["agent"].id,
        agent_version_id=context["version"].id,
        session_id=context["session"].id,
        execution_id=execution.id,
        source_platform="custom-python",
        service_name="svc",
        environment="development",
        operation_name="gpt-4",
        operation_kind="llm",
        operation_status="completed",
        trace_id="a" * 32,
        span_id="b" * 16,
        model_usage={"provider": "openai", "model": "gpt-4", "total_tokens": 150},
        attributes={},
        event_data={},
    )
    db_session.add(event)
    db_session.commit()
    headers = auth_headers(db_session, context["organization"].id)

    response = client.get("/api/v1/dashboard/overview", headers=headers)
    body = response.json()

    assert body["total_tokens_used"] == 150


def test_overview_is_tenant_scoped(client, db_session):
    context_a = create_test_context(db_session)
    make_execution(db_session, context_a, "completed")
    context_b = create_test_context(db_session)
    make_execution(db_session, context_b, "completed")
    make_execution(db_session, context_b, "completed")
    db_session.commit()

    headers_a = auth_headers(db_session, context_a["organization"].id)

    response = client.get("/api/v1/dashboard/overview", headers=headers_a)
    body = response.json()

    assert body["total_executions"] == 1
    assert body["total_agents"] == 1


def test_overview_requires_authentication(client, db_session):
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401
