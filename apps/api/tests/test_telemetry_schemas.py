from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentops_api.schemas.telemetry import TelemetryEvent


def valid_event_data():
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
            "id": str(uuid4()),
            "version_id": str(uuid4()),
            "version": "1.0.0",
        },
        "context": {
            "session_id": str(uuid4()),
            "execution_id": str(uuid4()),
            "workflow_id": "workflow-001",
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


def test_valid_telemetry_event():
    event = TelemetryEvent.model_validate(valid_event_data())

    assert event.event_type == "tool.call.completed"
    assert event.operation.name == "product_lookup"
    assert event.operation.duration_ms == 520


def test_event_timestamp_is_normalized_to_utc():
    data = valid_event_data()
    data["occurred_at"] = "2026-11-16T17:30:00+05:30"

    event = TelemetryEvent.model_validate(data)

    assert event.occurred_at == datetime(
        2026, 11, 16, 12, 0, tzinfo=timezone.utc
    )


def test_event_rejects_timestamp_without_timezone():
    data = valid_event_data()
    data["occurred_at"] = "2026-11-16T12:00:00"

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_invalid_trace_id():
    data = valid_event_data()
    data["context"]["trace_id"] = "invalid-trace-id"

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_all_zero_trace_id():
    data = valid_event_data()
    data["context"]["trace_id"] = "0" * 32

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_all_zero_span_id():
    data = valid_event_data()
    data["context"]["span_id"] = "0" * 16

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_failed_event_requires_error_details():
    data = valid_event_data()
    data["event_type"] = "tool.call.failed"
    data["operation"]["status"] = "failed"

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_failed_event_accepts_error_details():
    data = valid_event_data()
    data["event_type"] = "tool.call.failed"
    data["operation"]["status"] = "failed"
    data["error"] = {
        "type": "TimeoutError",
        "code": "API_TIMEOUT",
        "message": "Product lookup service timed out",
        "retryable": True,
    }

    event = TelemetryEvent.model_validate(data)

    assert event.error.type == "TimeoutError"
    assert event.error.retryable is True


def test_non_failed_event_rejects_error_details():
    data = valid_event_data()
    data["error"] = {
        "type": "TimeoutError",
        "message": "Unexpected error",
    }

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_negative_duration():
    data = valid_event_data()
    data["operation"]["duration_ms"] = -1

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_negative_token_count():
    data = valid_event_data()
    data["model_usage"] = {
        "provider": "openrouter",
        "model": "example-model",
        "input_tokens": -10,
        "output_tokens": 20,
        "total_tokens": 10,
    }

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_metadata_only_capture_rejects_payload_references():
    data = valid_event_data()
    data["payload"]["input_ref"] = "payloads/input-001.json"

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_redacted_capture_requires_redacted_flag():
    data = valid_event_data()
    data["payload"] = {
        "capture_mode": "redacted",
        "redacted": False,
    }

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_unsupported_schema_version():
    data = valid_event_data()
    data["schema_version"] = "2.0.0"

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)


def test_event_rejects_unknown_top_level_fields():
    data = valid_event_data()
    data["organization_id"] = str(uuid4())

    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate(data)
