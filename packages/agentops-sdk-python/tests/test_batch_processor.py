
import threading
from unittest.mock import Mock

import queue
from unittest.mock import patch

from agentops_sdk.batch_processor import BatchProcessor
from agentops_sdk.exceptions import AgentOpsTransportError


def test_submit_and_flush():
    transport = Mock()
    transport.send_event.return_value = {"status": "accepted"}

    processor = BatchProcessor(
        transport,
        batch_size=2,
        flush_interval=10,
    )

    assert processor.submit({"event_id": "1"})
    assert processor.submit({"event_id": "2"})

    assert processor.flush(timeout=2)
    assert transport.send_event.call_count == 2

    assert processor.shutdown(timeout=2)


def test_retry_transient_failure():
    transport = Mock()

    transport.send_event.side_effect = [
        AgentOpsTransportError("Temporary failure", retryable=True),
        {"status": "accepted"},
    ]

    processor = BatchProcessor(
        transport,
        batch_size=1,
        flush_interval=10,
        max_retries=2,
        retry_backoff=0,
    )

    processor.submit({"event_id": "retry-test"})

    assert processor.flush(timeout=2)
    assert transport.send_event.call_count == 2

    assert processor.shutdown(timeout=2)


def test_non_retryable_failure_is_not_retried():
    transport = Mock()

    transport.send_event.side_effect = AgentOpsTransportError(
        "Invalid request",
        retryable=False,
    )

    processor = BatchProcessor(
        transport,
        batch_size=1,
        flush_interval=10,
        max_retries=3,
    )

    processor.submit({"event_id": "invalid-test"})

    assert processor.flush(timeout=2)
    assert transport.send_event.call_count == 1

    assert processor.shutdown(timeout=2)


def test_queue_full_drops_event():
    transport = Mock()
    dropped = []

    processor = BatchProcessor(
        transport,
        batch_size=100,
        flush_interval=10,
        queue_capacity=1,
        on_drop=dropped.append,
    )

    try:
        with patch.object(
            processor._queue,
            "put_nowait",
            side_effect=queue.Full,
        ):
            result = processor.submit({"event_id": "overflow"})

        assert result is False
        assert len(dropped) == 1
        assert dropped[0]["event_id"] == "overflow"

    finally:
        assert processor.shutdown(timeout=2)
