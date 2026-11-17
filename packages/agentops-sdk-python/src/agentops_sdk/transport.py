
import httpx

from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.exceptions import (
    AgentOpsAuthenticationError,
    AgentOpsTransportError,
)


class TelemetryTransport:
    """HTTP transport for sending telemetry to AgentOps."""

    def __init__(self, config: AgentOpsConfig):
        self.config = config
        self._client = httpx.Client(
            base_url=config.endpoint,
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )

    def send_event(self, event: dict) -> dict:
        """Send one telemetry event to the ingestion API."""

        try:
            response = self._client.post(
                "/api/v1/telemetry/events",
                json=event,
            )

            if response.status_code in (200, 201):
                return response.json()

            if response.status_code in (401, 403):
                raise AgentOpsAuthenticationError(
                    "AgentOps authentication failed."
                )

            status_code = response.status_code

            raise AgentOpsTransportError(
                f"Telemetry ingestion failed: HTTP {status_code} - {response.text}",
                retryable=status_code == 429 or status_code >= 500,
            )

        except AgentOpsAuthenticationError:
            raise

        except AgentOpsTransportError:
            raise

        except httpx.HTTPError as exc:
            raise AgentOpsTransportError(
                f"Unable to communicate with AgentOps API: {exc}",
                retryable=True,
            ) from exc

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
