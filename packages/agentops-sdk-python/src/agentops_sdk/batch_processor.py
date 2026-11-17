
import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from agentops_sdk.exceptions import (
    AgentOpsAuthenticationError,
    AgentOpsTransportError,
)
from agentops_sdk.transport import TelemetryTransport


logger = logging.getLogger(__name__)


class BatchProcessor:
    """Background telemetry batching and delivery."""

    def __init__(
        self,
        transport: TelemetryTransport,
        *,
        batch_size: int = 50,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        queue_capacity: int = 5000,
        retry_backoff: float = 0.5,
        on_drop: Callable[[dict[str, Any]], None] | None = None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if flush_interval <= 0:
            raise ValueError("flush_interval must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if queue_capacity < 1:
            raise ValueError("queue_capacity must be at least 1")

        self.transport = transport
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.on_drop = on_drop

        self._queue: queue.Queue = queue.Queue(maxsize=queue_capacity)
        self._condition = threading.Condition()
        self._pending = 0
        self._stopping = False

        self._worker = threading.Thread(
            target=self._run,
            name="agentops-batch-processor",
            daemon=True,
        )
        self._worker.start()

    def submit(self, event: dict[str, Any]) -> bool:
        """Queue an event without waiting for network delivery."""

        with self._condition:
            if self._stopping:
                return False

            self._pending += 1

        try:
            self._queue.put_nowait(event)
            return True

        except queue.Full:
            with self._condition:
                self._pending -= 1
                self._condition.notify_all()

            logger.warning("AgentOps telemetry queue is full; event dropped")
            self._notify_drop(event)
            return False

    def flush(self, timeout: float | None = None) -> bool:
        """Wait until all queued events have been processed."""

        deadline = (
            None if timeout is None else time.monotonic() + timeout
        )

        with self._condition:
            while self._pending > 0:
                if deadline is None:
                    self._condition.wait()
                    continue

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    return False

                self._condition.wait(remaining)

        return True

    def shutdown(self, timeout: float | None = None) -> bool:
        """Stop the worker after processing pending events."""

        with self._condition:
            self._stopping = True
            self._condition.notify_all()

        flushed = self.flush(timeout=timeout)

        self._worker.join(timeout=timeout)

        return flushed and not self._worker.is_alive()

    def _run(self) -> None:
        batch: list[dict[str, Any]] = []
        last_flush = time.monotonic()

        while True:
            with self._condition:
                stopping = self._stopping

            if stopping and self._queue.empty():
                if batch:
                    self._deliver_batch(batch)
                return

            elapsed = time.monotonic() - last_flush
            remaining = max(0.0, self.flush_interval - elapsed)

            # Wake periodically so shutdown does not wait for the
            # entire flush interval.
            wait_time = min(remaining, 0.1)

            try:
                event = self._queue.get(timeout=wait_time)
                batch.append(event)
            except queue.Empty:
                pass

            should_flush = (
                len(batch) >= self.batch_size
                or (
                    batch
                    and time.monotonic() - last_flush >= self.flush_interval
                )
            )

            if should_flush:
                self._deliver_batch(batch)
                batch = []
                last_flush = time.monotonic()

    def _deliver_batch(self, batch: list[dict[str, Any]]) -> None:
        for event in batch:
            try:
                delivered = self._deliver_event(event)

                if not delivered:
                    self._notify_drop(event)

            finally:
                self._queue.task_done()

                with self._condition:
                    self._pending -= 1
                    self._condition.notify_all()

    def _deliver_event(self, event: dict[str, Any]) -> bool:
        for attempt in range(self.max_retries + 1):
            try:
                self.transport.send_event(event)
                return True

            except AgentOpsAuthenticationError:
                logger.error("AgentOps authentication failed; event dropped")
                return False

            except AgentOpsTransportError as exc:
                if not exc.retryable:
                    logger.warning("Non-retryable telemetry error: %s", exc)
                    return False

                if attempt >= self.max_retries:
                    logger.error(
                        "Telemetry delivery retries exhausted: %s", exc
                    )
                    return False

                delay = self.retry_backoff * (2 ** attempt)
                time.sleep(delay)

            except Exception:
                logger.exception("Unexpected telemetry delivery error")
                return False

        return False

    def _notify_drop(self, event: dict[str, Any]) -> None:
        if self.on_drop is None:
            return

        try:
            self.on_drop(event)
        except Exception:
            logger.exception("Telemetry drop callback failed")
