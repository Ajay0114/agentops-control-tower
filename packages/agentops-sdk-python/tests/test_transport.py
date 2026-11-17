
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
