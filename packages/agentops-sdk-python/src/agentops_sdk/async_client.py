"""Asynchronous twin of :class:`agentops_sdk.client.AgentOps`.

Telemetry delivery (``track``/``flush``/``shutdown``) reuses the exact same
thread-backed :class:`~agentops_sdk.batch_processor.BatchProcessor` and
:class:`~agentops_sdk.transport.TelemetryTransport` the sync client uses -
``submit()`` only ever queues an event in memory, so it never blocks the
event loop regardless of which client calls it. ``flush``/``shutdown`` do
block (they wait on a ``threading.Condition``), so here they run on a worker
thread via :func:`asyncio.to_thread` rather than blocking the loop directly.
Only the control-plane calls (agent/environment lookup, session/execution
lifecycle) use a genuinely async HTTP client, via :mod:`agentops_sdk.async_transport`.
"""

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

import httpx

from agentops_sdk.async_transport import AsyncTelemetryTransport
from agentops_sdk.batch_processor import BatchProcessor
from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.execution import AsyncExecution
from agentops_sdk.exceptions import AgentOpsShutdownError
from agentops_sdk.tracing import AgentHandle, new_trace_id
from agentops_sdk.transport import TelemetryTransport

logger = logging.getLogger(__name__)


class AsyncAgentOps:
    """Async public client for AgentOps telemetry and observability."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        agent_id: str | None = None,
        environment: str = "development",
        service_name: str | None = None,
        capture_mode: str = "metadata_only",
        batch_size: int = 50,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        timeout: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        config_kwargs: dict[str, Any] = dict(
            endpoint=endpoint,
            api_key=api_key,
            agent_id=agent_id,
            environment=environment,
            capture_mode=capture_mode,
            batch_size=batch_size,
            flush_interval=flush_interval,
            max_retries=max_retries,
            timeout=timeout,
        )

        if service_name is not None:
            config_kwargs["service_name"] = service_name

        self.config = AgentOpsConfig(**config_kwargs)

        self._shutdown = False

        # Telemetry delivery: thread-backed, shared mechanism (see module docstring).
        self._telemetry_transport = TelemetryTransport(self.config)
        self._processor = BatchProcessor(
            self._telemetry_transport,
            batch_size=self.config.batch_size,
            flush_interval=self.config.flush_interval,
            max_retries=self.config.max_retries,
        )

        # Control plane: genuinely async. ``http_client`` (if given) only
        # customizes this transport, not the thread-backed telemetry one
        # above, since it must be an httpx.AsyncClient.
        self._transport = AsyncTelemetryTransport(self.config, http_client=http_client)

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    def _ensure_active(self) -> None:
        if self._shutdown:
            raise AgentOpsShutdownError(
                "AgentOps client has already been shut down."
            )

    def track(self, event: dict[str, Any]) -> bool:
        """Submit a telemetry event for asynchronous delivery. Never blocks
        the event loop - safe to call without awaiting."""
        self._ensure_active()

        try:
            return self._processor.submit(event)

        except Exception:
            logger.exception("Unable to queue AgentOps telemetry event")
            return False

    async def flush(self, timeout: float | None = None) -> bool:
        """Wait until pending telemetry events are processed, without
        blocking the event loop."""
        self._ensure_active()

        try:
            return await asyncio.to_thread(self._processor.flush, timeout=timeout)

        except Exception:
            logger.exception("AgentOps telemetry flush failed")
            return False

    async def shutdown(self, timeout: float | None = None) -> bool:
        """Flush pending telemetry and close both transports."""
        if self._shutdown:
            return True

        try:
            stopped = await asyncio.to_thread(self._processor.shutdown, timeout=timeout)

            if not stopped:
                logger.warning(
                    "AgentOps processor did not stop within the timeout. "
                    "HTTP transport remains open."
                )
                return False

            self._telemetry_transport.close()
            await self._transport.close()
            self._shutdown = True

            return True

        except Exception:
            logger.exception("AgentOps shutdown failed")
            return False

    async def agent(
        self,
        agent_id: str | UUID | None = None,
        *,
        version: str | None = None,
        version_id: str | UUID | None = None,
        environment: str | None = None,
    ) -> AgentHandle:
        """Async twin of :meth:`AgentOps.agent` - see its docstring."""
        self._ensure_active()

        resolved_id = agent_id if agent_id is not None else self.config.agent_id

        if resolved_id is None:
            raise ValueError(
                "agent_id is required (pass it to agent(...) or to AsyncAgentOps(...))"
            )

        agent_uuid = UUID(str(resolved_id))

        agent_data = await self._transport.get_agent(agent_uuid)
        environment_uuid = UUID(str(agent_data["environment_id"]))
        environment_data = await self._transport.get_environment(environment_uuid)

        return AgentHandle(
            agent_id=agent_uuid,
            environment_id=environment_uuid,
            project_id=UUID(str(environment_data["project_id"])),
            version=version,
            version_id=UUID(str(version_id)) if version_id is not None else None,
            environment=environment if environment is not None else self.config.environment,
        )

    async def start_execution(
        self,
        *,
        agent: AgentHandle,
        session_id: str,
        name: str = "agent_execution",
        external_execution_id: str | None = None,
    ) -> AsyncExecution:
        """Async twin of :meth:`AgentOps.start_execution` - see its docstring.

        This method itself must be awaited (it makes two control-plane
        calls); use the ``AsyncExecution`` it returns as an async context
        manager separately::

            execution = await agentops.start_execution(agent=agent, session_id=session_id)
            async with execution:
                ...
        """
        self._ensure_active()

        session_data = await self._transport.create_session(
            project_id=agent.project_id,
            environment_id=agent.environment_id,
            external_session_id=str(session_id),
        )

        execution_data = await self._transport.create_execution(
            session_id=UUID(session_data["id"]),
            agent_id=agent.agent_id,
            agent_version_id=agent.version_id,
            external_execution_id=external_execution_id or f"sdk-{uuid4().hex}",
        )

        return AsyncExecution(
            self,
            agent=agent,
            session_id=UUID(session_data["id"]),
            execution_id=UUID(execution_data["id"]),
            trace_id=new_trace_id(),
            service_name=self.config.service_name,
            capture_mode=self.config.capture_mode,
            operation_name=name,
        )

    async def __aenter__(self):
        self._ensure_active()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.shutdown()
        return False
