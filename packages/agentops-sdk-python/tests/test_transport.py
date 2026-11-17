
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest

from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.exceptions import (
    AgentOpsAuthenticationError,
    AgentOpsTransportError,
)
from agentops_sdk.transport import TelemetryTransport


@pytest.fixture
def config():
    return AgentOpsConfig(
        endpoint="http://localhost:8010",
        api_key="test-api-key",
        agent_id=uuid4(),
    )


def test_send_event_success(config):
    transport = TelemetryTransport(config)

    try:
        with patch.object(
            transport._client,
            "post",
            return_value=Mock(
                status_code=201,
                json=lambda: {"status": "accepted"},
            ),
        ):
            result = transport.send_event({"event_id": str(uuid4())})

        assert result["status"] == "accepted"
    finally:
        transport.close()


def test_authentication_failure(config):
    transport = TelemetryTransport(config)

    try:
        with patch.object(
            transport._client,
            "post",
            return_value=Mock(status_code=401),
        ):
            with pytest.raises(AgentOpsAuthenticationError):
                transport.send_event({})
    finally:
        transport.close()


def test_http_failure(config):
    transport = TelemetryTransport(config)

    try:
        with patch.object(
            transport._client,
            "post",
            return_value=Mock(
                status_code=500,
                text="Internal Server Error",
            ),
        ):
            with pytest.raises(AgentOpsTransportError):
                transport.send_event({})
    finally:
        transport.close()


def test_connection_failure(config):
    transport = TelemetryTransport(config)

    try:
        with patch.object(
            transport._client,
            "post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(AgentOpsTransportError):
                transport.send_event({})
    finally:
        transport.close()


def test_custom_http_client_is_used_without_mutating_its_shared_defaults(config):
    """A caller-supplied client may be shared with unrelated HTTP calls, so
    AgentOps must apply auth/base-url per-request rather than overwriting the
    client's own default headers/base_url - otherwise the AgentOps API key
    would leak into the caller's other, unrelated requests through the same
    client, and the caller's own base_url would be silently hijacked."""
    custom_client = httpx.Client(
        base_url="https://unrelated-service.example.com",
        headers={"Authorization": "Bearer unrelated-service-token"},
        timeout=httpx.Timeout(30.0),
    )

    transport = TelemetryTransport(config, http_client=custom_client)

    try:
        assert transport._client is custom_client
        # The caller's own defaults are untouched.
        assert custom_client.base_url == httpx.URL("https://unrelated-service.example.com")
        assert custom_client.headers["Authorization"] == "Bearer unrelated-service-token"

        agent_id = uuid4()

        with patch.object(
            custom_client, "request",
            return_value=Mock(status_code=200, json=lambda: {"id": str(agent_id)}),
        ) as mock_request:
            transport.get_agent(agent_id)

        called_url = mock_request.call_args.args[1]
        assert called_url == f"{config.endpoint}/api/v1/agents/{agent_id}"
        assert mock_request.call_args.kwargs["headers"]["Authorization"] == f"Bearer {config.api_key}"

        # Still untouched after a real request was made through it.
        assert custom_client.base_url == httpx.URL("https://unrelated-service.example.com")
        assert custom_client.headers["Authorization"] == "Bearer unrelated-service-token"
    finally:
        transport.close()
        custom_client.close()


def test_closing_transport_does_not_close_caller_supplied_client(config):
    custom_client = httpx.Client()
    transport = TelemetryTransport(config, http_client=custom_client)

    transport.close()

    assert custom_client.is_closed is False
    custom_client.close()


def test_closing_transport_closes_its_own_default_client(config):
    transport = TelemetryTransport(config)

    transport.close()

    assert transport._client.is_closed is True
