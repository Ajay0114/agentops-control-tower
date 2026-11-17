import asyncio
from unittest.mock import Mock
from uuid import uuid4

import pytest

from agentops_sdk.execution import AsyncExecution, Execution
from agentops_sdk.tracing import AgentHandle, current_span, new_trace_id


def make_agent():
    return AgentHandle(
        agent_id=uuid4(),
        environment_id=uuid4(),
        project_id=uuid4(),
        version="1.0.0",
        version_id=uuid4(),
        environment="development",
    )


def make_execution(client, agent=None):
    return Execution(
        client,
        agent=agent or make_agent(),
        session_id=uuid4(),
        execution_id=uuid4(),
        trace_id=new_trace_id(),
        service_name="test-service",
        capture_mode="metadata_only",
        operation_name="agent_execution",
    )


@pytest.fixture
def mock_client():
    client = Mock()
    client.track = Mock(return_value=True)
    client._transport = Mock()
    client._transport.update_execution_status = Mock(return_value={})
    return client


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_enter_transitions_to_running_and_emits_started_event(mock_client):
    execution = make_execution(mock_client)

    with execution:
        pass

    running_calls = [
        call for call in mock_client._transport.update_execution_status.call_args_list
        if call.kwargs.get("status") == "running"
    ]
    assert len(running_calls) == 1

    started_events = [
        call.args[0] for call in mock_client.track.call_args_list
        if call.args[0]["event_type"] == "agent.execution.started"
    ]
    assert len(started_events) == 1
    assert started_events[0]["operation"]["status"] == "started"


def test_normal_exit_transitions_to_completed(mock_client):
    execution = make_execution(mock_client)

    with execution:
        pass

    completed_calls = [
        call for call in mock_client._transport.update_execution_status.call_args_list
        if call.kwargs.get("status") == "completed"
    ]
    assert len(completed_calls) == 1

    completed_events = [
        call.args[0] for call in mock_client.track.call_args_list
        if call.args[0]["event_type"] == "agent.execution.completed"
    ]
    assert len(completed_events) == 1


def test_exception_transitions_to_failed_and_is_reraised(mock_client):
    execution = make_execution(mock_client)

    with pytest.raises(ValueError, match="boom"):
        with execution:
            raise ValueError("boom")

    failed_calls = [
        call for call in mock_client._transport.update_execution_status.call_args_list
        if call.kwargs.get("status") == "failed"
    ]
    assert len(failed_calls) == 1
    assert failed_calls[0].kwargs["error_type"] == "ValueError"
    assert failed_calls[0].kwargs["error_message"] == "boom"

    failed_events = [
        call.args[0] for call in mock_client.track.call_args_list
        if call.args[0]["event_type"] == "agent.execution.failed"
    ]
    assert len(failed_events) == 1
    assert failed_events[0]["error"]["type"] == "ValueError"


def test_cancel_transitions_to_cancelled_and_prevents_exit_from_also_transitioning(
    mock_client,
):
    execution = make_execution(mock_client)

    with execution:
        execution.cancel()

    cancel_calls = [
        call for call in mock_client._transport.update_execution_status.call_args_list
        if call.kwargs.get("status") == "cancelled"
    ]
    assert len(cancel_calls) == 1

    # __exit__ must not also transition it to "completed" after cancel().
    completed_calls = [
        call for call in mock_client._transport.update_execution_status.call_args_list
        if call.kwargs.get("status") == "completed"
    ]
    assert len(completed_calls) == 0

    # No agent.execution.completed/failed telemetry event either - only the
    # started event (cancellation has no corresponding event type).
    terminal_events = [
        call.args[0] for call in mock_client.track.call_args_list
        if call.args[0]["event_type"] in ("agent.execution.completed", "agent.execution.failed")
    ]
    assert len(terminal_events) == 0


def test_cancel_is_idempotent(mock_client):
    execution = make_execution(mock_client)

    with execution:
        execution.cancel()
        execution.cancel()

    cancel_calls = [
        call for call in mock_client._transport.update_execution_status.call_args_list
        if call.kwargs.get("status") == "cancelled"
    ]
    assert len(cancel_calls) == 1


def test_set_output_is_local_only_and_never_tracked(mock_client):
    execution = make_execution(mock_client)

    with execution:
        execution.set_output({"secret": "value"})

    assert execution.output == {"secret": "value"}

    for call in mock_client.track.call_args_list:
        assert "secret" not in str(call.args[0])


def test_root_span_is_cleared_after_exit(mock_client):
    execution = make_execution(mock_client)

    assert current_span() is None

    with execution:
        assert current_span() is not None

    assert current_span() is None


# ---------------------------------------------------------------------------
# Span / LLMCall / ToolCall - parent-child relationships
# ---------------------------------------------------------------------------


def test_trace_span_is_child_of_execution_root(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.trace("process_request") as span:
            root_span_id = execution._root_span_id
            child_span_id = span._span_id

    events = [call.args[0] for call in mock_client.track.call_args_list]
    workflow_event = next(e for e in events if e["event_type"] == "workflow.completed")

    assert workflow_event["context"]["span_id"] == child_span_id
    assert workflow_event["context"]["parent_span_id"] == root_span_id
    assert workflow_event["context"]["trace_id"] == execution.trace_id


def test_nested_spans_chain_parent_ids_correctly(mock_client):
    execution = make_execution(mock_client)
    outer_id = None
    inner_id = None

    with execution:
        with execution.trace("outer") as outer:
            outer_id = outer._span_id
            with execution.tool_call("inner_tool") as inner:
                inner_id = inner._span_id

    events = [call.args[0] for call in mock_client.track.call_args_list]
    tool_event = next(e for e in events if e["event_type"] == "tool.call.completed")
    outer_event = next(e for e in events if e["event_type"] == "workflow.completed")

    assert tool_event["context"]["span_id"] == inner_id
    assert tool_event["context"]["parent_span_id"] == outer_id
    assert outer_event["context"]["parent_span_id"] == execution._root_span_id


def test_llm_call_captures_usage(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.llm_call(model="gpt-4.1", provider="openai") as call:
            call.set_usage(input_tokens=500, output_tokens=200)

    events = [call.args[0] for call in mock_client.track.call_args_list]
    llm_event = next(e for e in events if e["event_type"] == "llm.request.completed")

    assert llm_event["model_usage"]["provider"] == "openai"
    assert llm_event["model_usage"]["model"] == "gpt-4.1"
    assert llm_event["model_usage"]["input_tokens"] == 500
    assert llm_event["model_usage"]["output_tokens"] == 200
    assert llm_event["model_usage"]["total_tokens"] == 700


def test_llm_call_respects_explicit_total_tokens(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.llm_call(model="m", provider="p") as call:
            call.set_usage(input_tokens=10, output_tokens=5, total_tokens=999)

    events = [call.args[0] for call in mock_client.track.call_args_list]
    llm_event = next(e for e in events if e["event_type"] == "llm.request.completed")
    assert llm_event["model_usage"]["total_tokens"] == 999


def test_llm_call_never_captures_raw_prompt_or_completion(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.llm_call(model="m", provider="p") as call:
            call.set_usage(input_tokens=1, output_tokens=1)

    for call_args in mock_client.track.call_args_list:
        event = call_args.args[0]
        assert "prompt" not in str(event).lower()
        assert "completion" not in str(event).lower()
        assert "model_usage" not in event or set(event.get("model_usage", {})) <= {
            "provider", "model", "input_tokens", "output_tokens", "total_tokens", "cost_usd"
        }


def test_tool_call_set_output_captures_only_safe_metadata(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.tool_call("search_customer") as tool:
            tool.set_output({"customer_id": "secret-12345", "name": "Jane Doe"})

    events = [call.args[0] for call in mock_client.track.call_args_list]
    tool_event = next(e for e in events if e["event_type"] == "tool.call.completed")

    output_metadata = tool_event["attributes"]["output"]
    assert output_metadata["type"] == "dict"
    assert output_metadata["size"] == 2
    assert "secret-12345" not in str(tool_event)
    assert "Jane Doe" not in str(tool_event)


def test_tool_call_set_input_captures_only_safe_metadata(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.tool_call("search_customer") as tool:
            tool.set_input("jane.doe@example.com")

    events = [call.args[0] for call in mock_client.track.call_args_list]
    tool_event = next(e for e in events if e["event_type"] == "tool.call.completed")

    assert tool_event["attributes"]["input"]["type"] == "str"
    assert "jane.doe@example.com" not in str(tool_event)


def test_span_captures_exception_as_failed(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with pytest.raises(RuntimeError):
            with execution.tool_call("flaky_tool"):
                raise RuntimeError("tool exploded")

    events = [call.args[0] for call in mock_client.track.call_args_list]
    tool_event = next(e for e in events if e["event_type"] == "tool.call.failed")
    assert tool_event["error"]["type"] == "RuntimeError"
    assert tool_event["error"]["message"] == "tool exploded"


def test_span_fail_marks_failed_without_raising(mock_client):
    execution = make_execution(mock_client)

    with execution:
        with execution.llm_call(model="m", provider="p") as call:
            call.fail("provider returned an error response")

    events = [call.args[0] for call in mock_client.track.call_args_list]
    llm_event = next(e for e in events if e["event_type"] == "llm.request.failed")
    assert llm_event["error"]["message"] == "provider returned an error response"


def test_state_changed_and_context_updated_emit_state_events(mock_client):
    execution = make_execution(mock_client)

    with execution:
        execution.state_changed("dialog_step", step="collect_name")
        execution.context_updated("entities", name="Jane")

    events = [call.args[0] for call in mock_client.track.call_args_list]
    state_event = next(e for e in events if e["event_type"] == "agent.state.changed")
    context_event = next(e for e in events if e["event_type"] == "agent.context.updated")

    assert state_event["attributes"] == {"step": "collect_name"}
    assert context_event["attributes"] == {"name": "Jane"}


# ---------------------------------------------------------------------------
# Async execution + concurrent executions / context isolation
# ---------------------------------------------------------------------------


def make_async_mock_client():
    client = Mock()
    client.track = Mock(return_value=True)
    client._transport = Mock()

    async def _update_status(*args, **kwargs):
        return {}

    client._transport.update_execution_status = Mock(side_effect=_update_status)
    return client


def make_async_execution(client, agent=None):
    return AsyncExecution(
        client,
        agent=agent or make_agent(),
        session_id=uuid4(),
        execution_id=uuid4(),
        trace_id=new_trace_id(),
        service_name="test-service",
        capture_mode="metadata_only",
        operation_name="agent_execution",
    )


@pytest.mark.asyncio
async def test_async_execution_lifecycle():
    client = make_async_mock_client()
    execution = make_async_execution(client)

    async with execution:
        async with execution.tool_call("lookup") as tool:
            tool.set_output([1, 2, 3])

    events = [call.args[0] for call in client.track.call_args_list]
    assert any(e["event_type"] == "agent.execution.started" for e in events)
    assert any(e["event_type"] == "agent.execution.completed" for e in events)
    assert any(e["event_type"] == "tool.call.completed" for e in events)


@pytest.mark.asyncio
async def test_async_execution_captures_exception_as_failed():
    client = make_async_mock_client()
    execution = make_async_execution(client)

    with pytest.raises(ValueError):
        async with execution:
            raise ValueError("async failure")

    events = [call.args[0] for call in client.track.call_args_list]
    failed = next(e for e in events if e["event_type"] == "agent.execution.failed")
    assert failed["error"]["type"] == "ValueError"


@pytest.mark.asyncio
async def test_concurrent_async_executions_do_not_share_span_context():
    """Two concurrent tasks, each with their own Execution and nested span,
    must never see each other's current span - contextvars isolate per task."""
    client = make_async_mock_client()

    observed = {}

    async def run(label):
        execution = make_async_execution(client)
        async with execution:
            async with execution.trace(f"span-{label}"):
                await asyncio.sleep(0.01)
                observed[label] = current_span().trace_id
                await asyncio.sleep(0.01)
                # Still ours after the second await, not clobbered by the
                # other concurrently-running task.
                assert current_span().trace_id == observed[label]

    await asyncio.gather(run("a"), run("b"))

    assert observed["a"] != observed["b"]


@pytest.mark.asyncio
async def test_async_cancel_prevents_terminal_event():
    client = make_async_mock_client()
    execution = make_async_execution(client)

    async with execution:
        await execution.cancel()

    events = [call.args[0] for call in client.track.call_args_list]
    assert not any(
        e["event_type"] in ("agent.execution.completed", "agent.execution.failed")
        for e in events
    )
