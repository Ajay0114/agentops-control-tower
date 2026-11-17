from uuid import uuid4

from agentops_sdk.tracing import (
    AgentHandle,
    build_error_payload,
    build_telemetry_event,
    current_span,
    new_span_id,
    new_trace_id,
    pop_span,
    push_span,
)


def test_new_trace_id_is_32_hex_chars():
    trace_id = new_trace_id()
    assert len(trace_id) == 32
    int(trace_id, 16)  # raises if not valid hex


def test_new_span_id_is_16_hex_chars():
    span_id = new_span_id()
    assert len(span_id) == 16
    int(span_id, 16)


def test_trace_and_span_ids_are_unique():
    assert new_trace_id() != new_trace_id()
    assert new_span_id() != new_span_id()


def test_current_span_is_none_outside_any_span():
    assert current_span() is None


def test_push_span_sets_current_span_with_no_parent_at_root():
    token = push_span("trace-1", "span-1")
    try:
        frame = current_span()
        assert frame.trace_id == "trace-1"
        assert frame.span_id == "span-1"
        assert frame.parent_span_id is None
    finally:
        pop_span(token)

    assert current_span() is None


def test_nested_push_span_sets_parent_to_enclosing_span():
    root_token = push_span("trace-1", "root-span")
    try:
        child_token = push_span("trace-1", "child-span")
        try:
            frame = current_span()
            assert frame.span_id == "child-span"
            assert frame.parent_span_id == "root-span"
        finally:
            pop_span(child_token)

        # Popping the child restores the root as current.
        frame = current_span()
        assert frame.span_id == "root-span"
    finally:
        pop_span(root_token)


def test_deeply_nested_spans_chain_parents_correctly():
    tokens = []
    tokens.append(push_span("trace-1", "a"))
    tokens.append(push_span("trace-1", "b"))
    tokens.append(push_span("trace-1", "c"))

    frame = current_span()
    assert frame.span_id == "c"
    assert frame.parent_span_id == "b"

    for token in reversed(tokens):
        pop_span(token)

    assert current_span() is None


def test_build_telemetry_event_matches_contract_shape():
    agent = AgentHandle(
        agent_id=uuid4(),
        environment_id=uuid4(),
        project_id=uuid4(),
        version="1.0.0",
        version_id=uuid4(),
        environment="development",
    )
    session_id = uuid4()
    execution_id = uuid4()

    event = build_telemetry_event(
        event_type="tool.call.completed",
        agent=agent,
        session_id=session_id,
        execution_id=execution_id,
        trace_id=new_trace_id(),
        span_id=new_span_id(),
        parent_span_id=None,
        operation_name="search_customer",
        operation_kind="tool",
        operation_status="completed",
        service_name="my-service",
        duration_ms=120,
        attributes={"x": 1},
    )

    assert event["schema_version"] == "1.0.0"
    assert event["event_type"] == "tool.call.completed"
    assert event["source"]["service_name"] == "my-service"
    assert event["source"]["environment"] == "development"
    assert event["agent"]["id"] == str(agent.agent_id)
    assert event["agent"]["version_id"] == str(agent.version_id)
    assert event["agent"]["version"] == "1.0.0"
    assert event["context"]["session_id"] == str(session_id)
    assert event["context"]["execution_id"] == str(execution_id)
    assert event["operation"]["name"] == "search_customer"
    assert event["operation"]["kind"] == "tool"
    assert event["operation"]["status"] == "completed"
    assert event["operation"]["duration_ms"] == 120
    assert event["payload"]["capture_mode"] == "metadata_only"
    assert event["payload"]["redacted"] is True
    assert event["attributes"] == {"x": 1}
    assert "model_usage" not in event
    assert "error" not in event


def test_build_telemetry_event_never_includes_input_output_refs():
    agent = AgentHandle(agent_id=uuid4(), environment_id=uuid4(), project_id=uuid4())

    event = build_telemetry_event(
        event_type="workflow.completed",
        agent=agent,
        session_id=uuid4(),
        execution_id=uuid4(),
        trace_id=new_trace_id(),
        span_id=new_span_id(),
        parent_span_id=None,
        operation_name="process",
        operation_kind="workflow",
        operation_status="completed",
        service_name="svc",
    )

    assert "input_ref" not in event["payload"] or event["payload"].get("input_ref") is None
    assert "output_ref" not in event["payload"] or event["payload"].get("output_ref") is None


def test_build_telemetry_event_includes_error_only_when_given():
    agent = AgentHandle(agent_id=uuid4(), environment_id=uuid4(), project_id=uuid4())

    event = build_telemetry_event(
        event_type="tool.call.failed",
        agent=agent,
        session_id=uuid4(),
        execution_id=uuid4(),
        trace_id=new_trace_id(),
        span_id=new_span_id(),
        parent_span_id=None,
        operation_name="x",
        operation_kind="tool",
        operation_status="failed",
        service_name="svc",
        error={"type": "ValueError", "message": "bad input", "retryable": False},
    )

    assert event["error"] == {"type": "ValueError", "message": "bad input", "retryable": False}


def test_build_error_payload_captures_only_type_and_message():
    try:
        raise ValueError("something went wrong")
    except ValueError as exc:
        payload = build_error_payload(exc)

    assert payload["type"] == "ValueError"
    assert payload["message"] == "something went wrong"
    assert payload["retryable"] is False


def test_build_error_payload_falls_back_to_type_name_when_no_message():
    try:
        raise RuntimeError()
    except RuntimeError as exc:
        payload = build_error_payload(exc)

    assert payload["message"] == "RuntimeError"


def test_build_error_payload_respects_retryable_flag():
    payload = build_error_payload(ValueError("x"), retryable=True)
    assert payload["retryable"] is True
