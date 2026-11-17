"""Execution lifecycle, and the Span/LLMCall/ToolCall instrumentation built on
top of it.

``Execution`` (and its async twin ``AsyncExecution``) own the two network
calls a running execution needs - transitioning its backend status and
emitting its start/end telemetry. ``Span``/``LLMCall``/``ToolCall`` need
neither: emitting a telemetry event only ever queues it on the existing
background batch processor (never blocking), so one implementation of each
supports both ``with`` and ``async with`` unchanged.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

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

if TYPE_CHECKING:
    from agentops_sdk.async_client import AsyncAgentOps
    from agentops_sdk.client import AgentOps


logger = logging.getLogger(__name__)


class _SpanBase:
    """Shared logic for Span/LLMCall/ToolCall - see module docstring."""

    _operation_kind = "workflow"
    _event_prefix = "workflow"

    def __init__(self, execution: "Execution | AsyncExecution", name: str):
        self._execution = execution
        self._name = name
        self._span_id = new_span_id()
        self._token = None
        self._started_at = 0.0
        self.attributes: dict[str, Any] = {}
        self.model_usage: dict[str, Any] | None = None
        self._explicit_failure: BaseException | None = None

    def fail(self, error: BaseException | str) -> None:
        """Mark this span as failed without raising - for calls that report
        failure through a return value or status field rather than an
        exception."""
        self._explicit_failure = (
            error if isinstance(error, BaseException) else RuntimeError(str(error))
        )

    def _do_enter(self) -> None:
        self._started_at = time.monotonic()
        self._token = push_span(self._execution.trace_id, self._span_id)

    def _do_exit(self, exc_value: BaseException | None) -> None:
        duration_ms = int((time.monotonic() - self._started_at) * 1000)

        error = None
        status = "completed"

        failure = exc_value or self._explicit_failure

        if failure is not None:
            status = "failed"
            error = build_error_payload(failure)

        frame = current_span()
        parent_span_id = frame.parent_span_id if frame else None

        event = build_telemetry_event(
            event_type=f"{self._event_prefix}.{status}",
            agent=self._execution.agent,
            session_id=self._execution.session_id,
            execution_id=self._execution.execution_id,
            trace_id=self._execution.trace_id,
            span_id=self._span_id,
            parent_span_id=parent_span_id,
            operation_name=self._name,
            operation_kind=self._operation_kind,
            operation_status=status,
            service_name=self._execution.service_name,
            duration_ms=duration_ms,
            model_usage=self.model_usage,
            error=error,
            capture_mode=self._execution.capture_mode,
            attributes=self.attributes,
        )
        self._execution._track(event)

        if self._token is not None:
            pop_span(self._token)

    def __enter__(self):
        self._do_enter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self._do_exit(exc_value)
        return False  # never suppress the caller's exception

    async def __aenter__(self):
        self._do_enter()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        self._do_exit(exc_value)
        return False


class Span(_SpanBase):
    """A generic workflow/process span: ``with execution.trace(name): ...``."""

    _operation_kind = "workflow"
    _event_prefix = "workflow"


class LLMCall(_SpanBase):
    """An LLM request span: ``with execution.llm_call(model=..., provider=...): ...``.

    Captures only structured usage metrics - never raw prompts or completions.
    """

    _operation_kind = "llm"
    _event_prefix = "llm.request"

    def __init__(self, execution: "Execution | AsyncExecution", *, model: str, provider: str):
        super().__init__(execution, name=model)
        self.attributes = {"model": model, "provider": provider}
        self.model_usage = {"provider": provider, "model": model}

    def set_usage(
        self,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Record token usage (and optionally cost) for this call. Only
        meaningful, caller-supplied values are recorded - the SDK never
        estimates or guesses usage or pricing on its own."""
        usage = self.model_usage or {}

        if input_tokens is not None:
            usage["input_tokens"] = input_tokens

        if output_tokens is not None:
            usage["output_tokens"] = output_tokens

        if total_tokens is not None:
            usage["total_tokens"] = total_tokens
        elif input_tokens is not None and output_tokens is not None:
            usage["total_tokens"] = input_tokens + output_tokens

        if cost_usd is not None:
            usage["cost_usd"] = cost_usd

        self.model_usage = usage


class ToolCall(_SpanBase):
    """A tool-call span: ``with execution.tool_call(name): ...``.

    ``set_input``/``set_output`` record only safe, non-sensitive metadata
    (the argument's type and size) - never its contents - matching the
    metadata-only privacy default.
    """

    _operation_kind = "tool"
    _event_prefix = "tool.call"

    def set_input(self, value: Any) -> None:
        self.attributes["input"] = self._safe_metadata(value)

    def set_output(self, value: Any) -> None:
        self.attributes["output"] = self._safe_metadata(value)

    @staticmethod
    def _safe_metadata(value: Any) -> dict[str, Any]:
        metadata: dict[str, Any] = {"type": type(value).__name__}

        try:
            metadata["size"] = len(value)
        except TypeError:
            pass

        return metadata


class _ExecutionBase:
    """Shared, non-I/O state and span-factory methods for Execution/AsyncExecution."""

    def __init__(
        self,
        *,
        agent: AgentHandle,
        session_id: UUID,
        execution_id: UUID,
        trace_id: str,
        service_name: str,
        capture_mode: str,
        operation_name: str,
    ):
        self.agent = agent
        self.session_id = session_id
        self.execution_id = execution_id
        self.trace_id = trace_id
        self.service_name = service_name
        self.capture_mode = capture_mode
        self.operation_name = operation_name

        self._root_span_id = new_span_id()
        self._root_token = None
        self._finished = False
        self.output: Any = None

    def set_output(self, output: Any) -> None:
        """Local bookkeeping only (e.g. for your own logging) - never
        transmitted. Use a ToolCall's set_output if you want the fact that
        output was produced reflected in telemetry, as safe metadata."""
        self.output = output

    def trace(self, name: str) -> Span:
        return Span(self, name)

    def llm_call(self, *, model: str, provider: str) -> LLMCall:
        return LLMCall(self, model=model, provider=provider)

    def tool_call(self, name: str) -> ToolCall:
        return ToolCall(self, name)

    def state_changed(self, label: str, **attributes: Any) -> None:
        self._emit_state_event("agent.state.changed", label, attributes)

    def context_updated(self, label: str, **attributes: Any) -> None:
        self._emit_state_event("agent.context.updated", label, attributes)

    def _emit_state_event(self, event_type: str, label: str, attributes: dict[str, Any]) -> None:
        frame = current_span()
        event = build_telemetry_event(
            event_type=event_type,
            agent=self.agent,
            session_id=self.session_id,
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            span_id=new_span_id(),
            parent_span_id=frame.span_id if frame else self._root_span_id,
            operation_name=label,
            operation_kind="state",
            operation_status="completed",
            service_name=self.service_name,
            capture_mode=self.capture_mode,
            attributes=attributes,
        )
        self._track(event)

    def _started_event(self) -> dict[str, Any]:
        return build_telemetry_event(
            event_type="agent.execution.started",
            agent=self.agent,
            session_id=self.session_id,
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            span_id=self._root_span_id,
            parent_span_id=None,
            operation_name=self.operation_name,
            operation_kind="agent",
            operation_status="started",
            service_name=self.service_name,
            capture_mode=self.capture_mode,
        )

    def _terminal_event(self, status: str, error: dict[str, Any] | None) -> dict[str, Any]:
        return build_telemetry_event(
            event_type=f"agent.execution.{status}",
            agent=self.agent,
            session_id=self.session_id,
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            span_id=self._root_span_id,
            parent_span_id=None,
            operation_name=self.operation_name,
            operation_kind="agent",
            operation_status=status,
            service_name=self.service_name,
            capture_mode=self.capture_mode,
            error=error,
        )

    def _track(self, event: dict[str, Any]) -> None:
        raise NotImplementedError


class Execution(_ExecutionBase):
    """Synchronous execution lifecycle. Created by :meth:`AgentOps.start_execution`.

    Entering the ``with`` block transitions the backend execution from
    "queued" to "running" and emits ``agent.execution.started``; exiting
    transitions it to "completed" or "failed" (capturing any exception raised
    in the block, which is always re-raised, never swallowed) and emits the
    matching terminal telemetry event. Calling :meth:`cancel` inside the
    block transitions it to "cancelled" instead - the contract has no
    ``agent.execution.cancelled`` event type, so no terminal telemetry event
    is emitted for a cancellation, only the registry status change.
    """

    def __init__(self, client: "AgentOps", **kwargs: Any):
        super().__init__(**kwargs)
        self._client = client

    def _track(self, event: dict[str, Any]) -> None:
        self._client.track(event)

    def cancel(self) -> None:
        if self._finished:
            return

        try:
            self._client._transport.update_execution_status(
                self.execution_id, status="cancelled"
            )
        except Exception:
            logger.exception(
                "Failed to transition execution %s to cancelled", self.execution_id
            )

        self._finished = True

    def __enter__(self) -> "Execution":
        self._root_token = push_span(self.trace_id, self._root_span_id)

        try:
            self._client._transport.update_execution_status(
                self.execution_id, status="running"
            )
        except Exception:
            logger.exception(
                "Failed to transition execution %s to running", self.execution_id
            )

        self._track(self._started_event())
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if not self._finished:
            status = "failed" if exc_value is not None else "completed"
            error = build_error_payload(exc_value) if exc_value is not None else None

            try:
                self._client._transport.update_execution_status(
                    self.execution_id,
                    status=status,
                    error_type=error["type"] if error else None,
                    error_message=error["message"] if error else None,
                )
            except Exception:
                logger.exception(
                    "Failed to update execution status for %s", self.execution_id
                )

            self._track(self._terminal_event(status, error))
            self._finished = True

        if self._root_token is not None:
            pop_span(self._root_token)

        return False


class AsyncExecution(_ExecutionBase):
    """Asynchronous twin of :class:`Execution`. Created by
    :meth:`AsyncAgentOps.start_execution`. Identical lifecycle semantics,
    using ``async with`` and awaited transport calls instead."""

    def __init__(self, client: "AsyncAgentOps", **kwargs: Any):
        super().__init__(**kwargs)
        self._client = client

    def _track(self, event: dict[str, Any]) -> None:
        self._client.track(event)

    async def cancel(self) -> None:
        if self._finished:
            return

        try:
            await self._client._transport.update_execution_status(
                self.execution_id, status="cancelled"
            )
        except Exception:
            logger.exception(
                "Failed to transition execution %s to cancelled", self.execution_id
            )

        self._finished = True

    async def __aenter__(self) -> "AsyncExecution":
        self._root_token = push_span(self.trace_id, self._root_span_id)

        try:
            await self._client._transport.update_execution_status(
                self.execution_id, status="running"
            )
        except Exception:
            logger.exception(
                "Failed to transition execution %s to running", self.execution_id
            )

        self._track(self._started_event())
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        if not self._finished:
            status = "failed" if exc_value is not None else "completed"
            error = build_error_payload(exc_value) if exc_value is not None else None

            try:
                await self._client._transport.update_execution_status(
                    self.execution_id,
                    status=status,
                    error_type=error["type"] if error else None,
                    error_message=error["message"] if error else None,
                )
            except Exception:
                logger.exception(
                    "Failed to update execution status for %s", self.execution_id
                )

            self._track(self._terminal_event(status, error))
            self._finished = True

        if self._root_token is not None:
            pop_span(self._root_token)

        return False
