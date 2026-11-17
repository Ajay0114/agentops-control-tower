from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest

from agentops_sdk.async_transport import AsyncTelemetryTransport
from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.exceptions import (
    AgentOpsAuthenticationError,
    AgentOpsNotFoundError,
    AgentOpsTransportError,
)


@pytest.fixture
def transport():
    config = AgentOpsConfig(
        endpoint="http://localhost:8010",
        api_key="test-api-key",
        max_retries=2,
    )
    t = AsyncTelemetryTransport(config)
    yield t


@pytest.fixture(autouse=True)
async def _close_after(transport):
    yield
    await transport.close()


def mock_response(status_code, json_data=None, text=""):
    return Mock(status_code=status_code, json=lambda: json_data or {}, text=text)


async def test_get_agent_success(transport):
    agent_id = uuid4()
    with patch.object(
        transport._client, "request",
        new=AsyncMock(return_value=mock_response(200, {"id": str(agent_id)})),
    ):
        result = await transport.get_agent(agent_id)

    assert result["id"] == str(agent_id)


async def test_get_agent_not_found(transport):
    with patch.object(
        transport._client, "request",
        new=AsyncMock(return_value=mock_response(404, text="not found")),
    ):
        with pytest.raises(AgentOpsNotFoundError):
            await transport.get_agent(uuid4())


async def test_authentication_failure(transport):
    with patch.object(
        transport._client, "request", new=AsyncMock(return_value=mock_response(401))
    ):
        with pytest.raises(AgentOpsAuthenticationError):
            await transport.get_agent(uuid4())


async def test_create_session_sends_expected_payload(transport):
    project_id, environment_id = uuid4(), uuid4()

    mock_request = AsyncMock(return_value=mock_response(201, {"id": str(uuid4())}))

    with patch.object(transport._client, "request", new=mock_request):
        await transport.create_session(
            project_id=project_id,
            environment_id=environment_id,
            external_session_id="conversation-1",
        )

    sent_json = mock_request.call_args.kwargs["json"]
    assert sent_json == {
        "project_id": str(project_id),
        "environment_id": str(environment_id),
        "external_session_id": "conversation-1",
    }


async def test_create_execution_and_update_status_round_trip(transport):
    execution_id = uuid4()

    with patch.object(
        transport._client, "request",
        new=AsyncMock(return_value=mock_response(201, {"id": str(execution_id)})),
    ):
        created = await transport.create_execution(
            session_id=uuid4(),
            agent_id=uuid4(),
            agent_version_id=None,
            external_execution_id="exec-1",
        )

    assert created["id"] == str(execution_id)

    with patch.object(
        transport._client, "request",
        new=AsyncMock(return_value=mock_response(200, {"id": str(execution_id), "status": "running"})),
    ):
        updated = await transport.update_execution_status(execution_id, status="running")

    assert updated["status"] == "running"


async def test_retries_transient_failure_without_blocking(transport):
    responses = [
        mock_response(503, text="unavailable"),
        mock_response(200, {"id": str(uuid4())}),
    ]
    mock_request = AsyncMock(side_effect=responses)

    with patch.object(transport._client, "request", new=mock_request), \
         patch("agentops_sdk.async_transport.asyncio.sleep", new=AsyncMock()):
        result = await transport.get_agent(uuid4())

    assert mock_request.call_count == 2
    assert "id" in result


async def test_does_not_retry_permanent_errors(transport):
    mock_request = AsyncMock(return_value=mock_response(404, text="nope"))

    with patch.object(transport._client, "request", new=mock_request):
        with pytest.raises(AgentOpsNotFoundError):
            await transport.get_agent(uuid4())

    assert mock_request.call_count == 1


async def test_gives_up_after_max_retries(transport):
    mock_request = AsyncMock(return_value=mock_response(500, text="down"))

    with patch.object(transport._client, "request", new=mock_request), \
         patch("agentops_sdk.async_transport.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(AgentOpsTransportError):
            await transport.get_agent(uuid4())

    assert mock_request.call_count == 3


async def test_retries_on_connection_error(transport):
    mock_request = AsyncMock(
        side_effect=[httpx.ConnectError("refused"), mock_response(200, {"id": str(uuid4())})]
    )

    with patch.object(transport._client, "request", new=mock_request), \
         patch("agentops_sdk.async_transport.asyncio.sleep", new=AsyncMock()):
        result = await transport.get_agent(uuid4())

    assert mock_request.call_count == 2
    assert "id" in result


async def test_custom_http_client_is_used_without_mutating_its_shared_defaults():
    """See the sync equivalent in test_transport.py for the rationale: a
    shared client's own defaults must never be overwritten with AgentOps's
    auth header or base_url."""
    config = AgentOpsConfig(endpoint="http://localhost:8010", api_key="test-api-key")
    custom_client = httpx.AsyncClient(
        base_url="https://unrelated-service.example.com",
        headers={"Authorization": "Bearer unrelated-service-token"},
        timeout=httpx.Timeout(30.0),
    )

    transport = AsyncTelemetryTransport(config, http_client=custom_client)

    try:
        assert transport._client is custom_client
        assert custom_client.base_url == httpx.URL("https://unrelated-service.example.com")
        assert custom_client.headers["Authorization"] == "Bearer unrelated-service-token"

        agent_id = uuid4()
        mock_request = AsyncMock(return_value=mock_response(200, {"id": str(agent_id)}))

        with patch.object(custom_client, "request", new=mock_request):
            await transport.get_agent(agent_id)

        called_url = mock_request.call_args.args[1]
        assert called_url == f"{config.endpoint}/api/v1/agents/{agent_id}"
        assert mock_request.call_args.kwargs["headers"]["Authorization"] == f"Bearer {config.api_key}"

        assert custom_client.base_url == httpx.URL("https://unrelated-service.example.com")
        assert custom_client.headers["Authorization"] == "Bearer unrelated-service-token"
    finally:
        await transport.close()
        await custom_client.aclose()


async def test_closing_transport_does_not_close_caller_supplied_client():
    config = AgentOpsConfig(endpoint="http://localhost:8010", api_key="test-api-key")
    custom_client = httpx.AsyncClient()
    transport = AsyncTelemetryTransport(config, http_client=custom_client)

    await transport.close()

    assert custom_client.is_closed is False
    await custom_client.aclose()
