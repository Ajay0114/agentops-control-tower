
import logging
import random
import time
from uuid import UUID

import httpx

from agentops_sdk.config import AgentOpsConfig
from agentops_sdk.exceptions import (
    AgentOpsAuthenticationError,
    AgentOpsConflictError,
    AgentOpsNotFoundError,
    AgentOpsTransportError,
    AgentOpsValidationError,
)

logger = logging.getLogger(__name__)


def _raise_for_status(response: httpx.Response, *, action: str) -> None:
    """Map an AgentOps API error response to the SDK's exception hierarchy.
    Never includes the Authorization header or API key - only the response
    status and body AgentOps itself chose to return."""
    status_code = response.status_code

    if status_code in (200, 201):
        return

    if status_code in (401, 403):
        raise AgentOpsAuthenticationError("AgentOps authentication failed.")

    if status_code == 404:
        raise AgentOpsNotFoundError(f"{action} failed: not found - {response.text}")

    if status_code == 409:
        raise AgentOpsConflictError(f"{action} failed: conflict - {response.text}")

    if status_code == 422:
        raise AgentOpsValidationError(f"{action} failed: invalid request - {response.text}")

    raise AgentOpsTransportError(
        f"{action} failed: HTTP {status_code} - {response.text}",
        retryable=status_code == 429 or status_code >= 500,
    )


class TelemetryTransport:
    """HTTP transport for AgentOps: telemetry ingestion plus the control-plane
    calls (agent/environment lookup, session/execution lifecycle) the
    high-level SDK needs. ``send_event`` is used by the background batch
    processor (which has its own retry loop); the control-plane methods here
    retry transient failures themselves, since their callers are waiting
    synchronously for a result.
    """

    def __init__(self, config: AgentOpsConfig, *, http_client: httpx.Client | None = None):
        self.config = config
        self._owns_client = http_client is None
        self._client = http_client if http_client is not None else httpx.Client(timeout=config.timeout)

        # Applied per-request (see _url/_headers below) rather than mutated
        # onto the client itself: a caller-supplied client may be shared with
        # other, unrelated HTTP calls, and setting default headers/base_url
        # on it would leak the AgentOps Authorization header - and redirect
        # relative-path requests - to whatever else that client is used for.
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.config.endpoint}{path}"

    def send_event(self, event: dict) -> dict:
        """Send one telemetry event to the ingestion API."""

        try:
            response = self._client.post(
                self._url("/api/v1/telemetry/events"),
                json=event,
                headers=self._headers,
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

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        action: str,
        json: dict | None = None,
    ) -> dict:
        """Issue one control-plane request, retrying only transient failures
        (connection errors, 429, 5xx) with exponential backoff and jitter.
        The same ``json`` payload is sent on every attempt, so retries of an
        idempotent call (e.g. create_execution with a stable
        external_execution_id) can never create a duplicate record.
        """
        attempts = self.config.max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                response = self._client.request(
                    method, self._url(url), json=json, headers=self._headers
                )
                _raise_for_status(response, action=action)
                return response.json()

            except (AgentOpsAuthenticationError, AgentOpsNotFoundError,
                    AgentOpsConflictError, AgentOpsValidationError):
                raise

            except AgentOpsTransportError as exc:
                last_exc = exc
                if not exc.retryable or attempt >= attempts - 1:
                    raise

            except httpx.HTTPError as exc:
                last_exc = AgentOpsTransportError(
                    f"Unable to communicate with AgentOps API: {exc}",
                    retryable=True,
                )
                if attempt >= attempts - 1:
                    raise last_exc from exc

            delay = min(2 ** attempt, 8) + random.uniform(0, 0.25)
            logger.warning(
                "%s failed (attempt %d/%d), retrying in %.2fs: %s",
                action, attempt + 1, attempts, delay, last_exc,
            )
            time.sleep(delay)

        # Unreachable in practice (the loop always returns or raises), but
        # keeps type-checkers happy and fails loudly instead of returning None.
        raise last_exc or AgentOpsTransportError(f"{action} failed for an unknown reason")

    def get_agent(self, agent_id: UUID) -> dict:
        return self._request_with_retry(
            "GET", f"/api/v1/agents/{agent_id}", action="Resolving agent"
        )

    def get_environment(self, environment_id: UUID) -> dict:
        return self._request_with_retry(
            "GET", f"/api/v1/environments/{environment_id}", action="Resolving environment"
        )

    def create_session(
        self, *, project_id: UUID, environment_id: UUID, external_session_id: str
    ) -> dict:
        return self._request_with_retry(
            "POST",
            "/api/v1/sessions",
            action="Creating session",
            json={
                "project_id": str(project_id),
                "environment_id": str(environment_id),
                "external_session_id": external_session_id,
            },
        )

    def create_execution(
        self,
        *,
        session_id: UUID,
        agent_id: UUID,
        agent_version_id: UUID | None,
        external_execution_id: str,
    ) -> dict:
        return self._request_with_retry(
            "POST",
            "/api/v1/executions",
            action="Creating execution",
            json={
                "session_id": str(session_id),
                "agent_id": str(agent_id),
                "agent_version_id": str(agent_version_id) if agent_version_id else None,
                "external_execution_id": external_execution_id,
            },
        )

    def update_execution_status(
        self,
        execution_id: UUID,
        *,
        status: str,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> dict:
        payload: dict = {"status": status}

        if error_type is not None:
            payload["error_type"] = error_type

        if error_message is not None:
            payload["error_message"] = error_message

        return self._request_with_retry(
            "PATCH",
            f"/api/v1/executions/{execution_id}/status",
            action="Updating execution status",
            json=payload,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool.

        A no-op if the client was supplied by the caller (via ``http_client``)
        rather than created by AgentOps - ownership, and therefore closing it,
        stays with whoever constructed it.
        """
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
