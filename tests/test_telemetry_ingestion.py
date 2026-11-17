from uuid import uuid4

import pytest

from agentops_api.auth import AuthContext
from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Execution,
    Session,
)
from agentops_api.schemas.telemetry import TelemetryEvent
from agentops_api.services.telemetry_service import (
    TelemetryIdempotencyConflictError,
    TelemetryNotFoundError,
    TelemetryValidationError,
    ingest_telemetry_event,
)


def create_telemetry_context(db_session):
    from agentops_api.models.core import Organization, Project

    organization = Organization(
        name="Telemetry Test Organization",
        slug=f"telemetry-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Telemetry Test Project",
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
        name="Telemetry Test Agent",
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


def auth_context_for(context, *, project_id=None, environment_id=None):
    """These tests call the service layer directly, not via HTTP, so a real
    minted API key isn't needed - an AuthContext can be constructed inline."""
    return AuthContext(
        api_key_id=uuid4(),
        organization_id=context["organization"].id,
        project_id=project_id,
        environment_id=environment_id,
    )


def telemetry_event_data(context):
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


def test_ingest_valid_telemetry_event(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)
    event = TelemetryEvent.model_validate(
        telemetry_event_data(context)
    )

    record, created = ingest_telemetry_event(db_session, event, auth)

    assert created is True
    assert record.event_id == event.event_id
    assert record.organization_id == context["organization"].id
    assert record.agent_id == context["agent"].id
    assert record.session_id == context["session"].id
    assert record.execution_id == context["execution"].id
    assert record.event_type == "tool.call.completed"
    assert record.operation_name == "product_lookup"
    assert record.event_data["event_id"] == str(event.event_id)


def test_identical_event_retry_returns_existing_record(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)
    event = TelemetryEvent.model_validate(
        telemetry_event_data(context)
    )

    first_record, first_created = ingest_telemetry_event(
        db_session, event, auth
    )
    second_record, second_created = ingest_telemetry_event(
        db_session, event, auth
    )

    assert first_created is True
    assert second_created is False
    assert first_record.id == second_record.id


def test_same_event_id_with_different_content_conflicts(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)
    data = telemetry_event_data(context)

    event = TelemetryEvent.model_validate(data)
    ingest_telemetry_event(db_session, event, auth)

    conflicting_data = {
        **data,
        "attributes": {
            "http.response.status_code": 503,
        },
    }
    conflicting_event = TelemetryEvent.model_validate(
        conflicting_data
    )

    with pytest.raises(TelemetryIdempotencyConflictError):
        ingest_telemetry_event(db_session, conflicting_event, auth)


def test_unknown_agent_is_rejected(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)
    data = telemetry_event_data(context)
    data["agent"]["id"] = str(uuid4())

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(
        TelemetryNotFoundError,
        match="Agent not found",
    ):
        ingest_telemetry_event(db_session, event, auth)


def test_execution_must_belong_to_agent(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)

    another_agent = Agent(
        environment_id=context["environment"].id,
        name="Another Agent",
        slug=f"another-agent-{uuid4().hex[:8]}",
        framework="custom-python",
    )
    db_session.add(another_agent)
    db_session.flush()

    another_execution = Execution(
        session_id=context["session"].id,
        agent_id=another_agent.id,
        status="running",
    )
    db_session.add(another_execution)
    db_session.flush()

    data = telemetry_event_data(context)
    data["context"]["execution_id"] = str(another_execution.id)

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(
        TelemetryValidationError,
        match="Execution must belong to the specified agent and session",
    ):
        ingest_telemetry_event(db_session, event, auth)


def test_agent_version_must_belong_to_agent(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)

    another_agent = Agent(
        environment_id=context["environment"].id,
        name="Another Agent",
        slug=f"another-agent-{uuid4().hex[:8]}",
        framework="custom-python",
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

    data = telemetry_event_data(context)
    data["agent"]["version_id"] = str(another_version.id)

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(
        TelemetryValidationError,
        match="Agent version does not belong to the specified agent",
    ):
        ingest_telemetry_event(db_session, event, auth)


def test_session_must_belong_to_agent_environment(db_session):
    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)

    another_environment = Environment(
        project_id=context["project"].id,
        name="Testing",
        slug=f"test-{uuid4().hex[:8]}",
    )
    db_session.add(another_environment)
    db_session.flush()

    another_session = Session(
        project_id=context["project"].id,
        environment_id=another_environment.id,
        external_session_id=f"session-{uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(another_session)
    db_session.flush()

    data = telemetry_event_data(context)
    data["context"]["session_id"] = str(another_session.id)

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(
        TelemetryValidationError,
        match="Agent and session must belong to the same project and environment",
    ):
        ingest_telemetry_event(db_session, event, auth)


# ---------------------------------------------------------------------------
# Cross-tenant and scope-restriction isolation (service-level)
# ---------------------------------------------------------------------------


def test_cross_tenant_cannot_ingest_referencing_other_organization_agent(db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    auth_b = auth_context_for(context_b)

    # Use org B's own session/execution, but reference org A's agent.
    data = telemetry_event_data(context_b)
    data["agent"]["id"] = str(context_a["agent"].id)
    data["agent"]["version_id"] = str(context_a["version"].id)

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(TelemetryNotFoundError, match="Agent not found"):
        ingest_telemetry_event(db_session, event, auth_b)


def test_cross_tenant_cannot_ingest_referencing_other_organization_session(db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    auth_b = auth_context_for(context_b)

    data = telemetry_event_data(context_b)
    data["context"]["session_id"] = str(context_a["session"].id)

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(TelemetryNotFoundError, match="Session not found"):
        ingest_telemetry_event(db_session, event, auth_b)


def test_cross_tenant_cannot_ingest_referencing_other_organization_execution(db_session):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    auth_b = auth_context_for(context_b)

    data = telemetry_event_data(context_b)
    data["context"]["execution_id"] = str(context_a["execution"].id)

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(TelemetryNotFoundError, match="Execution not found"):
        ingest_telemetry_event(db_session, event, auth_b)


def test_cross_tenant_cannot_ingest_referencing_other_organization_agent_version(
    db_session,
):
    context_a = create_telemetry_context(db_session)
    context_b = create_telemetry_context(db_session)
    auth_b = auth_context_for(context_b)

    data = telemetry_event_data(context_b)
    data["agent"]["version_id"] = str(context_a["version"].id)
    data["agent"].pop("version")

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(TelemetryNotFoundError, match="Agent version not found"):
        ingest_telemetry_event(db_session, event, auth_b)


def test_environment_restricted_key_cannot_ingest_for_other_environment(db_session):
    context = create_telemetry_context(db_session)

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

    # Restricted to the ORIGINAL environment, but the event references the
    # staging agent (in a different environment of the same org).
    auth = auth_context_for(context, environment_id=context["environment"].id)

    data = telemetry_event_data(context)
    data["agent"]["id"] = str(other_agent.id)
    data["agent"].pop("version_id")
    data["agent"].pop("version")

    event = TelemetryEvent.model_validate(data)

    with pytest.raises(TelemetryNotFoundError, match="Agent not found"):
        ingest_telemetry_event(db_session, event, auth)


def test_rejected_ingestion_creates_no_database_record(db_session):
    from sqlalchemy import func, select

    from agentops_api.models.core import TelemetryEventRecord

    context = create_telemetry_context(db_session)
    auth = auth_context_for(context)
    data = telemetry_event_data(context)
    data["agent"]["id"] = str(uuid4())
    event = TelemetryEvent.model_validate(data)

    with pytest.raises(TelemetryNotFoundError):
        ingest_telemetry_event(db_session, event, auth)

    count = db_session.scalar(
        select(func.count())
        .select_from(TelemetryEventRecord)
        .where(TelemetryEventRecord.event_id == event.event_id)
    )
    assert count == 0
