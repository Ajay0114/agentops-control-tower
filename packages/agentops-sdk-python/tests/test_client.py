
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from agentops_sdk import AgentOps
from agentops_sdk.exceptions import AgentOpsShutdownError


@pytest.fixture
def client():
    with patch("agentops_sdk.client.TelemetryTransport") as transport_class:
        transport = transport_class.return_value

        with patch("agentops_sdk.client.BatchProcessor") as processor_class:
            processor = processor_class.return_value

            instance = AgentOps(
                endpoint="http://localhost:8010",
                api_key="test-api-key",
                agent_id=str(uuid4()),
            )

            yield instance, transport, processor


def test_client_initialization(client):
    instance, transport, processor = client

    assert instance.is_shutdown is False
    assert instance.config.environment == "development"
    assert instance.config.capture_mode == "metadata_only"

    assert instance._transport is transport
    assert instance._processor is processor


def test_endpoint_normalization(client):
    instance, _, _ = client

    assert instance.config.endpoint == "http://localhost:8010"


def test_track_event(client):
    instance, _, processor = client

    event = {"event_id": str(uuid4())}
    processor.submit.return_value = True

    result = instance.track(event)

    assert result is True
    processor.submit.assert_called_once_with(event)


def test_track_returns_false_when_queue_rejects_event(client):
    instance, _, processor = client
    processor.submit.return_value = False

    result = instance.track({"event_id": str(uuid4())})

    assert result is False


def test_flush_pending_events(client):
    instance, _, processor = client
    processor.flush.return_value = True

    assert instance.flush(timeout=2) is True

    processor.flush.assert_called_once_with(timeout=2)


def test_client_shutdown(client):
    instance, transport, processor = client
    processor.shutdown.return_value = True

    result = instance.shutdown(timeout=2)

    assert result is True
    assert instance.is_shutdown is True

    processor.shutdown.assert_called_once_with(timeout=2)
    transport.close.assert_called_once()


def test_shutdown_is_idempotent(client):
    instance, transport, processor = client
    processor.shutdown.return_value = True

    assert instance.shutdown() is True
    assert instance.shutdown() is True

    assert processor.shutdown.call_count == 1
    assert transport.close.call_count == 1


def test_client_context_manager():
    with patch("agentops_sdk.client.TelemetryTransport"), \
         patch("agentops_sdk.client.BatchProcessor") as processor_class:

        processor_class.return_value.shutdown.return_value = True

        with AgentOps(
            endpoint="http://localhost:8010",
            api_key="test-api-key",
            agent_id=str(uuid4()),
        ) as instance:
            assert instance.is_shutdown is False

        assert instance.is_shutdown is True


def test_track_after_shutdown_raises(client):
    instance, _, processor = client
    processor.shutdown.return_value = True

    instance.shutdown()

    with pytest.raises(AgentOpsShutdownError):
        instance.track({"event_id": str(uuid4())})


def test_shutdown_timeout_keeps_transport_open(client):
    instance, transport, processor = client
    processor.shutdown.return_value = False

    result = instance.shutdown(timeout=0.01)

    assert result is False
    assert instance.is_shutdown is False
    transport.close.assert_not_called()


def test_processor_initialization_uses_config(client):
    instance, _, _ = client

    assert instance._processor is not None
    assert instance.config.batch_size == 50
    assert instance.config.flush_interval == 5.0
    assert instance.config.max_retries == 3
