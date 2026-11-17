
import logging
from typing import Any
from uuid import UUID, uuid4

import httpx

from agentops_sdk.batch_processor import BatchProcessor
from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.execution import Execution
from agentops_sdk.exceptions import AgentOpsShutdownError
from agentops_sdk.tracing import AgentHandle, new_trace_id
from agentops_sdk.transport import TelemetryTransport


logger = logging.getLogger(__name__)


class AgentOps:
    """Public client for AgentOps telemetry and observability."""

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
        http_client: httpx.Client | None = None,
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

        self._transport = TelemetryTransport(self.config, http_client=http_client)

        self._processor = BatchProcessor(
            self._transport,
            batch_size=self.config.batch_size,
            flush_interval=self.config.flush_interval,
            max_retries=self.config.max_retries,
        )

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    def _ensure_active(self) -> None:
        if self._shutdown:
            raise AgentOpsShutdownError(
                "AgentOps client has already been shut down."
            )

    def track(self, event: dict[str, Any]) -> bool:
        """
        Submit a telemetry event for asynchronous delivery.

        Returns True when queued successfully, False when dropped.
        """

        self._ensure_active()

        try:
            return self._processor.submit(event)

        except Exception:
            logger.exception("Unable to queue AgentOps telemetry event")
            return False

    def flush(self, timeout: float | None = None) -> bool:
        """Wait until pending telemetry events are processed."""

        self._ensure_active()

        try:
            return self._processor.flush(timeout=timeout)

        except Exception:
            logger.exception("AgentOps telemetry flush failed")
            return False

    def shutdown(self, timeout: float | None = None) -> bool:
        """Flush pending telemetry and close the HTTP transport."""

        if self._shutdown:
            return True

        try:
            stopped = self._processor.shutdown(timeout=timeout)

            if not stopped:
                logger.warning(
                    "AgentOps processor did not stop within the timeout. "
                    "HTTP transport remains open."
                )
                return False

            self._transport.close()
            self._shutdown = True

            return True

        except Exception:
            logger.exception("AgentOps shutdown failed")
            return False

    def agent(
        self,
        agent_id: str | UUID | None = None,
        *,
        version: str | None = None,
        version_id: str | UUID | None = None,
        environment: str | None = None,
    ) -> AgentHandle:
        """Identify an existing registered agent.

        Resolves and caches the agent's environment/project so that
        :meth:`start_execution` can create sessions and executions without
        a further lookup. The agent must already be registered through the
        existing Agent Registry API - the SDK never creates one on the fly.

        ``agent_id`` defaults to the id passed to the client's constructor,
        if any, for backward compatibility with the original single-agent
        client shape.
        """
        self._ensure_active()

        resolved_id = agent_id if agent_id is not None else self.config.agent_id

        if resolved_id is None:
            raise ValueError(
                "agent_id is required (pass it to agent(...) or to AgentOps(...))"
            )

        agent_uuid = UUID(str(resolved_id))

        agent_data = self._transport.get_agent(agent_uuid)
        environment_uuid = UUID(str(agent_data["environment_id"]))
        environment_data = self._transport.get_environment(environment_uuid)

        return AgentHandle(
            agent_id=agent_uuid,
            environment_id=environment_uuid,
            project_id=UUID(str(environment_data["project_id"])),
            version=version,
            version_id=UUID(str(version_id)) if version_id is not None else None,
            environment=environment if environment is not None else self.config.environment,
        )

    def start_execution(
        self,
        *,
        agent: AgentHandle,
        session_id: str,
        name: str = "agent_execution",
        external_execution_id: str | None = None,
    ) -> Execution:
        """Start tracking one execution of ``agent`` within a session.

        ``session_id`` is your own external identifier (e.g. a conversation
        or request id); it is created on first use and reused on every
        subsequent call with the same value, matching the backend's
        idempotent session semantics. If ``external_execution_id`` is not
        given, a random one is generated for this call - retries *within*
        this call never duplicate the execution, but if your own code calls
        start_execution() again for what is logically the same execution,
        pass a stable external_execution_id yourself so the backend's
        idempotency check can recognize it.

        Use as a context manager: entering transitions the execution to
        "running" and exiting transitions it to "completed" or "failed"
        (any exception raised inside the block is always re-raised).
        """
        self._ensure_active()

        session_data = self._transport.create_session(
            project_id=agent.project_id,
            environment_id=agent.environment_id,
            external_session_id=str(session_id),
        )

        execution_data = self._transport.create_execution(
            session_id=UUID(session_data["id"]),
            agent_id=agent.agent_id,
            agent_version_id=agent.version_id,
            external_execution_id=external_execution_id or f"sdk-{uuid4().hex}",
        )

        return Execution(
            self,
            agent=agent,
            session_id=UUID(session_data["id"]),
            execution_id=UUID(execution_data["id"]),
            trace_id=new_trace_id(),
            service_name=self.config.service_name,
            capture_mode=self.config.capture_mode,
            operation_name=name,
        )

    def __enter__(self):
        self._ensure_active()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()
        return False
