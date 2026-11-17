from unittest.mock import patch
from uuid import uuid4

import pytest

from agentops_sdk import AgentOps
from agentops_sdk.execution import Execution


@pytest.fixture
def client():
    with patch("agentops_sdk.client.TelemetryTransport") as transport_class:
        transport = transport_class.return_value

        with patch("agentops_sdk.client.BatchProcessor"):
            instance = AgentOps(
                endpoint="http://localhost:8010",
                api_key="test-api-key",
            )
            yield instance, transport


def test_agent_requires_an_id_when_none_configured(client):
    instance, _ = client

    with pytest.raises(ValueError):
        instance.agent()


def test_agent_resolves_environment_and_project(client):
    instance, transport = client
    agent_id = uuid4()
    environment_id = uuid4()
    project_id = uuid4()

    transport.get_agent.return_value = {
        "id": str(agent_id),
        "environment_id": str(environment_id),
        "name": "Support Agent",
        "status": "registered",
    }
    transport.get_environment.return_value = {
        "id": str(environment_id),
        "project_id": str(project_id),
    }

    handle = instance.agent(agent_id, version="1.0.0", environment="production")

    transport.get_agent.assert_called_once_with(agent_id)
    transport.get_environment.assert_called_once_with(environment_id)

    assert handle.agent_id == agent_id
    assert handle.environment_id == environment_id
    assert handle.project_id == project_id
    assert handle.version == "1.0.0"
    assert handle.environment == "production"


def test_agent_falls_back_to_configured_agent_id(client):
    instance, transport = client
    configured_agent_id = uuid4()
    instance.config = instance.config.model_copy(update={"agent_id": configured_agent_id})

    transport.get_agent.return_value = {
        "id": str(configured_agent_id),
        "environment_id": str(uuid4()),
    }
    transport.get_environment.return_value = {"id": str(uuid4()), "project_id": str(uuid4())}

    instance.agent()

    transport.get_agent.assert_called_once_with(configured_agent_id)


def test_agent_raises_not_found_propagated_from_transport(client):
    from agentops_sdk.exceptions import AgentOpsNotFoundError

    instance, transport = client
    transport.get_agent.side_effect = AgentOpsNotFoundError("Agent not found")

    with pytest.raises(AgentOpsNotFoundError):
        instance.agent(uuid4())


def _make_resolved_agent(instance, transport):
    agent_id, environment_id, project_id = uuid4(), uuid4(), uuid4()
    transport.get_agent.return_value = {"id": str(agent_id), "environment_id": str(environment_id)}
    transport.get_environment.return_value = {"id": str(environment_id), "project_id": str(project_id)}
    return instance.agent(agent_id, version="1.0.0")


def test_start_execution_creates_session_and_execution(client):
    instance, transport = client
    agent = _make_resolved_agent(instance, transport)

    session_id = uuid4()
    execution_id = uuid4()
    transport.create_session.return_value = {"id": str(session_id)}
    transport.create_execution.return_value = {"id": str(execution_id)}

    execution = instance.start_execution(agent=agent, session_id="conversation-123")

    assert isinstance(execution, Execution)
    assert execution.session_id == session_id
    assert execution.execution_id == execution_id

    transport.create_session.assert_called_once_with(
        project_id=agent.project_id,
        environment_id=agent.environment_id,
        external_session_id="conversation-123",
    )
    transport.create_execution.assert_called_once()
    call_kwargs = transport.create_execution.call_args.kwargs
    assert call_kwargs["session_id"] == session_id
    assert call_kwargs["agent_id"] == agent.agent_id
    assert call_kwargs["agent_version_id"] == agent.version_id
    assert call_kwargs["external_execution_id"].startswith("sdk-")


def test_start_execution_uses_caller_supplied_external_id_for_idempotency(client):
    instance, transport = client
    agent = _make_resolved_agent(instance, transport)

    transport.create_session.return_value = {"id": str(uuid4())}
    transport.create_execution.return_value = {"id": str(uuid4())}

    instance.start_execution(
        agent=agent, session_id="s1", external_execution_id="my-stable-id"
    )

    assert transport.create_execution.call_args.kwargs["external_execution_id"] == "my-stable-id"


def test_start_execution_without_explicit_id_generates_a_fresh_one_each_call(client):
    """Without a caller-supplied id, repeated logical calls get different
    ids (idempotency across retries is the caller's responsibility unless
    they pass their own id) - but within one call it's used consistently."""
    instance, transport = client
    agent = _make_resolved_agent(instance, transport)
    transport.create_session.return_value = {"id": str(uuid4())}
    transport.create_execution.return_value = {"id": str(uuid4())}

    instance.start_execution(agent=agent, session_id="s1")
    first_id = transport.create_execution.call_args.kwargs["external_execution_id"]

    instance.start_execution(agent=agent, session_id="s1")
    second_id = transport.create_execution.call_args.kwargs["external_execution_id"]

    assert first_id != second_id
