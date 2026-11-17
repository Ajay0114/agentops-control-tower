
import logging
from typing import Any

from agentops_sdk.batch_processor import BatchProcessor
from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.exceptions import AgentOpsShutdownError
from agentops_sdk.transport import TelemetryTransport


logger = logging.getLogger(__name__)


class AgentOps:
    """Public client for AgentOps telemetry and observability."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        agent_id: str,
        environment: str = "development",
        capture_mode: str = "metadata_only",
        batch_size: int = 50,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        timeout: float = 5.0,
    ):
        self.config = AgentOpsConfig(
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

        self._shutdown = False

        self._transport = TelemetryTransport(self.config)

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

    def __enter__(self):
        self._ensure_active()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()
        return False
