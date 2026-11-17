from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from agentops_sdk import AsyncAgentOps
from agentops_sdk.execution import AsyncExecution


@pytest.fixture
def client():
    with patch("agentops_sdk.async_client.TelemetryTransport"), \
         patch("agentops_sdk.async_client.BatchProcessor") as processor_class, \
         patch("agentops_sdk.async_client.AsyncTelemetryTransport") as async_transport_class:

        processor = processor_class.return_value
        async_transport = async_transport_class.return_value
        async_transport.close = AsyncMock()

        instance = AsyncAgentOps(
            endpoint="http://localhost:8010",
            api_key="test-api-key",
        )

        yield instance, async_transport, processor


def test_initialization(client):
    instance, transport, processor = client

    assert instance.is_shutdown is False
    assert instance.config.environment == "development"
    assert instance._transport is transport
    assert instance._processor is processor


def test_custom_http_client_is_forwarded_to_async_transport():
    custom_client = Mock()

    with patch("agentops_sdk.async_client.TelemetryTransport"), \
         patch("agentops_sdk.async_client.BatchProcessor"), \
         patch("agentops_sdk.async_client.AsyncTelemetryTransport") as async_transport_class:
        AsyncAgentOps(
            endpoint="http://localhost:8010",
            api_key="test-api-key",
            http_client=custom_client,
        )

    assert async_transport_class.call_args.kwargs["http_client"] is custom_client


def test_track_never_blocks_and_does_not_need_awaiting(client):
    instance, _, processor = client
    processor.submit.return_value = True

    result = instance.track({"event_id": str(uuid4())})

    assert result is True
    processor.submit.assert_called_once()


async def test_flush_runs_off_the_event_loop(client):
    instance, _, processor = client
    processor.flush.return_value = True

    result = await instance.flush(timeout=2)

    assert result is True
    processor.flush.assert_called_once_with(timeout=2)


async def test_shutdown_closes_both_transports(client):
    instance, async_transport, processor = client
    processor.shutdown.return_value = True

    result = await instance.shutdown(timeout=2)

    assert result is True
    assert instance.is_shutdown is True
    async_transport.close.assert_awaited_once()


async def test_shutdown_is_idempotent(client):
    instance, async_transport, processor = client
    processor.shutdown.return_value = True

    assert await instance.shutdown() is True
    assert await instance.shutdown() is True

    assert processor.shutdown.call_count == 1
    assert async_transport.close.await_count == 1


async def test_context_manager_shuts_down_on_exit(client):
    instance, _, processor = client
    processor.shutdown.return_value = True

    async with instance:
        assert instance.is_shutdown is False

    assert instance.is_shutdown is True


async def test_agent_resolves_environment_and_project(client):
    instance, transport, _ = client
    agent_id, environment_id, project_id = uuid4(), uuid4(), uuid4()

    transport.get_agent = AsyncMock(
        return_value={"id": str(agent_id), "environment_id": str(environment_id)}
    )
    transport.get_environment = AsyncMock(
        return_value={"id": str(environment_id), "project_id": str(project_id)}
    )

    handle = await instance.agent(agent_id, version="2.0.0")

    assert handle.agent_id == agent_id
    assert handle.environment_id == environment_id
    assert handle.project_id == project_id
    assert handle.version == "2.0.0"


async def test_start_execution_returns_async_execution(client):
    instance, transport, _ = client
    agent_id, environment_id, project_id = uuid4(), uuid4(), uuid4()

    transport.get_agent = AsyncMock(
        return_value={"id": str(agent_id), "environment_id": str(environment_id)}
    )
    transport.get_environment = AsyncMock(
        return_value={"id": str(environment_id), "project_id": str(project_id)}
    )
    agent = await instance.agent(agent_id)

    session_id, execution_id = uuid4(), uuid4()
    transport.create_session = AsyncMock(return_value={"id": str(session_id)})
    transport.create_execution = AsyncMock(return_value={"id": str(execution_id)})

    execution = await instance.start_execution(agent=agent, session_id="conv-1")

    assert isinstance(execution, AsyncExecution)
    assert execution.session_id == session_id
    assert execution.execution_id == execution_id


async def test_concurrent_start_execution_calls_do_not_interfere(client):
    """Two concurrent start_execution() calls for the same agent must each
    get their own, independent execution/session resolution - each call's
    create_execution request is matched back to its own session_id, with no
    shared mutable state between the two concurrent tasks."""
    import asyncio

    instance, transport, _ = client
    agent_id, environment_id, project_id = uuid4(), uuid4(), uuid4()

    transport.get_agent = AsyncMock(
        return_value={"id": str(agent_id), "environment_id": str(environment_id)}
    )
    transport.get_environment = AsyncMock(
        return_value={"id": str(environment_id), "project_id": str(project_id)}
    )
    agent = await instance.agent(agent_id)

    session_ids = {"a": uuid4(), "b": uuid4()}
    execution_ids_by_session = {
        session_ids["a"]: uuid4(),
        session_ids["b"]: uuid4(),
    }

    async def create_session(**kwargs):
        label = kwargs["external_session_id"]
        return {"id": str(session_ids[label])}

    async def create_execution(**kwargs):
        # Deterministic: looked up from this call's own session_id argument,
        # never from shared state another concurrent task could mutate.
        session_id = kwargs["session_id"]
        return {"id": str(execution_ids_by_session[session_id])}

    transport.create_session = AsyncMock(side_effect=create_session)
    transport.create_execution = AsyncMock(side_effect=create_execution)

    results = await asyncio.gather(
        instance.start_execution(agent=agent, session_id="a"),
        instance.start_execution(agent=agent, session_id="b"),
    )

    result_by_session = {r.session_id: r.execution_id for r in results}
    assert result_by_session[session_ids["a"]] == execution_ids_by_session[session_ids["a"]]
    assert result_by_session[session_ids["b"]] == execution_ids_by_session[session_ids["b"]]
