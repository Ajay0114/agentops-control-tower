"""Trace/span identity, context propagation, and telemetry event construction.

Everything in this module is pure (no network I/O), so it is shared verbatim
by both the synchronous and asynchronous execution/span implementations in
``execution.py``.

Context propagation uses :mod:`contextvars`, which is the correct primitive
for this: a span opened inside one ``asyncio`` task is automatically visible
to code running later in that same task (including across ``await`` points),
while a new task created with ``asyncio.create_task`` receives its own copy
of the current context at creation time - so two concurrent tasks tracking
their own nested spans never see or clobber each other's current span. The
same isolation holds across threads, which is what makes a single
:class:`SpanContext` safe to share across the sync and async clients.
"""

from __future__ import annotations

import contextvars
import secrets
import uuid as uuid_module
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

OperationKind = Literal["agent", "llm", "tool", "workflow", "state"]
OperationStatus = Literal["started", "completed", "failed", "cancelled"]


def new_trace_id() -> str:
    """A fresh OpenTelemetry-compatible 32-character hex trace id."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """A fresh OpenTelemetry-compatible 16-character hex span id."""
    return secrets.token_hex(8)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SpanFrame:
    """One entry on the current-span stack for a single execution."""

    trace_id: str
    span_id: str
    parent_span_id: str | None


# A single, module-level ContextVar. Each Execution pushes its root frame
# when it starts and restores whatever was there before when it ends, so
# nested executions (or concurrent ones in different tasks/threads) never
# interfere with each other - contextvars isolate by task/thread, and the
# explicit push/pop here isolates by call stack within one task.
_current_span: contextvars.ContextVar[SpanFrame | None] = contextvars.ContextVar(
    "agentops_current_span", default=None
)


def current_span() -> SpanFrame | None:
    return _current_span.get()


def push_span(trace_id: str, span_id: str) -> contextvars.Token:
    """Make (trace_id, span_id) the current span for anything nested under
    it; the previous span (if any) becomes this one's parent."""
    parent = _current_span.get()
    parent_span_id = parent.span_id if parent is not None else None
    frame = SpanFrame(trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id)
    return _current_span.set(frame)


def pop_span(token: contextvars.Token) -> None:
    _current_span.reset(token)


@dataclass(frozen=True)
class AgentHandle:
    """Identifies an agent (and optionally a version/environment label) for
    use with :meth:`AgentOps.start_execution` / :meth:`AsyncAgentOps.start_execution`.

    Holds no transport or I/O state - it is plain data, safe to share across
    threads, tasks, and multiple executions. Returned by ``AgentOps.agent(...)``
    /``AsyncAgentOps.agent(...)``, which resolve ``environment_id`` (from the
    Agent Registry) and ``project_id`` (from that environment) once, so
    ``start_execution`` can create sessions without a further lookup.

    ``environment`` is a *different* thing: the free-text label stored in the
    telemetry contract's ``source.environment`` field (e.g. "production").
    It is metadata only and is never resolved against the registry's
    Environment table - do not confuse it with ``environment_id``.
    """

    agent_id: UUID
    environment_id: UUID
    project_id: UUID
    version: str | None = None
    version_id: UUID | None = None
    environment: str = "development"


def build_telemetry_event(
    *,
    event_type: str,
    agent: AgentHandle,
    session_id: UUID,
    execution_id: UUID,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    operation_name: str,
    operation_kind: OperationKind,
    operation_status: OperationStatus,
    service_name: str,
    duration_ms: int | None = None,
    workflow_id: str | None = None,
    model_usage: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    capture_mode: str = "metadata_only",
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one event dict matching the Telemetry Event Contract v1.0.0,
    ready to pass to :meth:`AgentOps.track`. Never includes raw prompts,
    completions, or chain-of-thought - callers only ever pass metadata here.
    """
    event: dict[str, Any] = {
        "schema_version": "1.0.0",
        "event_id": str(uuid_module.uuid4()),
        "event_type": event_type,
        "occurred_at": now_iso(),
        "source": {
            "platform": "custom-python",
            "service_name": service_name,
            "environment": agent.environment,
        },
        "agent": {
            "id": str(agent.agent_id),
            "version_id": str(agent.version_id) if agent.version_id else None,
            "version": agent.version,
        },
        "context": {
            "session_id": str(session_id),
            "execution_id": str(execution_id),
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
        },
        "operation": {
            "name": operation_name,
            "kind": operation_kind,
            "status": operation_status,
            "duration_ms": duration_ms,
        },
        # Never carries input_ref/output_ref: the SDK never captures raw
        # prompts, completions, or tool payloads, in any capture mode.
        "payload": {
            "capture_mode": capture_mode,
            "redacted": True,
        },
        "attributes": attributes or {},
    }

    if model_usage is not None:
        event["model_usage"] = model_usage

    if error is not None:
        event["error"] = error

    return event


def build_error_payload(exc: BaseException, *, retryable: bool = False) -> dict[str, Any]:
    """A safe, metadata-only error description for a telemetry event.

    Uses only the exception's type name and ``str(exc)`` - the SDK never
    inspects or transmits local variables, stack frames, or any other
    contents of the call site, so it cannot capture chain-of-thought or
    arguments the caller never explicitly handed it.
    """
    return {
        "type": type(exc).__name__,
        "message": str(exc) or type(exc).__name__,
        "retryable": retryable,
    }
