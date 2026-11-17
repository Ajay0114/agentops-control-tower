from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest

from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.exceptions import (
    AgentOpsAuthenticationError,
    AgentOpsConflictError,
    AgentOpsNotFoundError,
    AgentOpsTransportError,
    AgentOpsValidationError,
)
from agentops_sdk.transport import TelemetryTransport


@pytest.fixture
def transport():
    config = AgentOpsConfig(
        endpoint="http://localhost:8010",
        api_key="test-api-key",
        max_retries=2,
    )
    t = TelemetryTransport(config)
    yield t
    t.close()


def mock_response(status_code, json_data=None, text=""):
    return Mock(status_code=status_code, json=lambda: json_data or {}, text=text)


def test_get_agent_success(transport):
    agent_id = uuid4()
    with patch.object(
        transport._client, "request",
        return_value=mock_response(200, {"id": str(agent_id), "environment_id": str(uuid4())}),
    ) as mock_request:
        result = transport.get_agent(agent_id)

    assert result["id"] == str(agent_id)
    mock_request.assert_called_once()
    assert mock_request.call_args.args[0] == "GET"
    assert f"/api/v1/agents/{agent_id}" in mock_request.call_args.args[1]


def test_get_agent_not_found_raises_not_found_error(transport):
    with patch.object(
        transport._client, "request",
        return_value=mock_response(404, text='{"detail": "Agent not found"}'),
    ):
        with pytest.raises(AgentOpsNotFoundError):
            transport.get_agent(uuid4())


def test_get_agent_auth_failure_raises_authentication_error(transport):
    with patch.object(transport._client, "request", return_value=mock_response(401)):
        with pytest.raises(AgentOpsAuthenticationError):
            transport.get_agent(uuid4())


def test_create_session_sends_expected_payload(transport):
    project_id, environment_id = uuid4(), uuid4()

    with patch.object(
        transport._client, "request",
        return_value=mock_response(201, {"id": str(uuid4())}),
    ) as mock_request:
        transport.create_session(
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


def test_create_session_idempotent_response_returns_existing(transport):
    """A 200 (idempotent re-create) is treated the same as a 201."""
    existing_id = str(uuid4())

    with patch.object(
        transport._client, "request",
        return_value=mock_response(200, {"id": existing_id}),
    ):
        result = transport.create_session(
            project_id=uuid4(), environment_id=uuid4(), external_session_id="x"
        )

    assert result["id"] == existing_id


def test_create_execution_conflict_raises_conflict_error(transport):
    with patch.object(
        transport._client, "request",
        return_value=mock_response(409, text='{"detail": "conflict"}'),
    ):
        with pytest.raises(AgentOpsConflictError):
            transport.create_execution(
                session_id=uuid4(),
                agent_id=uuid4(),
                agent_version_id=None,
                external_execution_id="exec-1",
            )


def test_create_execution_validation_error_raises_validation_error(transport):
    with patch.object(
        transport._client, "request",
        return_value=mock_response(422, text='{"detail": "invalid"}'),
    ):
        with pytest.raises(AgentOpsValidationError):
            transport.create_execution(
                session_id=uuid4(),
                agent_id=uuid4(),
                agent_version_id=None,
                external_execution_id="exec-1",
            )


def test_update_execution_status_sends_error_fields_only_when_given(transport):
    execution_id = uuid4()

    with patch.object(
        transport._client, "request",
        return_value=mock_response(200, {"id": str(execution_id)}),
    ) as mock_request:
        transport.update_execution_status(execution_id, status="running")

    assert mock_request.call_args.kwargs["json"] == {"status": "running"}

    with patch.object(
        transport._client, "request",
        return_value=mock_response(200, {"id": str(execution_id)}),
    ) as mock_request:
        transport.update_execution_status(
            execution_id, status="failed", error_type="ValueError", error_message="bad"
        )

    assert mock_request.call_args.kwargs["json"] == {
        "status": "failed",
        "error_type": "ValueError",
        "error_message": "bad",
    }


def test_control_plane_retries_transient_5xx_then_succeeds(transport):
    responses = [
        mock_response(503, text="unavailable"),
        mock_response(200, {"id": str(uuid4())}),
    ]

    with patch.object(transport._client, "request", side_effect=responses) as mock_request, \
         patch("agentops_sdk.transport.time.sleep"):
        result = transport.get_agent(uuid4())

    assert mock_request.call_count == 2
    assert "id" in result


def test_control_plane_does_not_retry_404(transport):
    with patch.object(
        transport._client, "request",
        return_value=mock_response(404, text="not found"),
    ) as mock_request:
        with pytest.raises(AgentOpsNotFoundError):
            transport.get_agent(uuid4())

    assert mock_request.call_count == 1


def test_control_plane_does_not_retry_authentication_failure(transport):
    with patch.object(transport._client, "request", return_value=mock_response(401)) as mock_request:
        with pytest.raises(AgentOpsAuthenticationError):
            transport.get_agent(uuid4())

    assert mock_request.call_count == 1


def test_control_plane_gives_up_after_max_retries(transport):
    with patch.object(
        transport._client, "request",
        return_value=mock_response(500, text="still down"),
    ) as mock_request, patch("agentops_sdk.transport.time.sleep"):
        with pytest.raises(AgentOpsTransportError):
            transport.get_agent(uuid4())

    # max_retries=2 configured on the fixture -> 3 total attempts.
    assert mock_request.call_count == 3


def test_control_plane_retries_on_connection_error(transport):
    with patch.object(
        transport._client, "request",
        side_effect=[httpx.ConnectError("refused"), mock_response(200, {"id": str(uuid4())})],
    ) as mock_request, patch("agentops_sdk.transport.time.sleep"):
        result = transport.get_agent(uuid4())

    assert mock_request.call_count == 2
    assert "id" in result


def test_send_event_still_works_unchanged(transport):
    """Backward compatibility: send_event's own behavior is untouched."""
    with patch.object(
        transport._client, "post",
        return_value=mock_response(201, {"status": "accepted"}),
    ):
        result = transport.send_event({"event_id": str(uuid4())})

    assert result["status"] == "accepted"
