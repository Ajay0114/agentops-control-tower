"""Async HTTP transport for the control-plane calls (agent/environment
lookup, session/execution lifecycle) that :class:`AsyncAgentOps` must await
without blocking the event loop.

Telemetry event delivery does not need an async transport: the existing
:class:`~agentops_sdk.batch_processor.BatchProcessor` already runs on a
background thread, so ``submit()`` never blocks regardless of whether the
caller is sync or async code - both clients share it unchanged.
"""

import asyncio
import logging
import random
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
from agentops_sdk.transport import _raise_for_status

logger = logging.getLogger(__name__)


class AsyncTelemetryTransport:
    """Async twin of the control-plane portion of :class:`TelemetryTransport`."""

    def __init__(self, config: AgentOpsConfig, *, http_client: httpx.AsyncClient | None = None):
        self.config = config
        self._owns_client = http_client is None
        self._client = (
            http_client if http_client is not None else httpx.AsyncClient(timeout=config.timeout)
        )

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

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        action: str,
        json: dict | None = None,
    ) -> dict:
        attempts = self.config.max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await self._client.request(
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
            await asyncio.sleep(delay)

        raise last_exc or AgentOpsTransportError(f"{action} failed for an unknown reason")

    async def get_agent(self, agent_id: UUID) -> dict:
        return await self._request_with_retry(
            "GET", f"/api/v1/agents/{agent_id}", action="Resolving agent"
        )

    async def get_environment(self, environment_id: UUID) -> dict:
        return await self._request_with_retry(
            "GET", f"/api/v1/environments/{environment_id}", action="Resolving environment"
        )

    async def create_session(
        self, *, project_id: UUID, environment_id: UUID, external_session_id: str
    ) -> dict:
        return await self._request_with_retry(
            "POST",
            "/api/v1/sessions",
            action="Creating session",
            json={
                "project_id": str(project_id),
                "environment_id": str(environment_id),
                "external_session_id": external_session_id,
            },
        )

    async def create_execution(
        self,
        *,
        session_id: UUID,
        agent_id: UUID,
        agent_version_id: UUID | None,
        external_execution_id: str,
    ) -> dict:
        return await self._request_with_retry(
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

    async def update_execution_status(
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

        return await self._request_with_retry(
            "PATCH",
            f"/api/v1/executions/{execution_id}/status",
            action="Updating execution status",
            json=payload,
        )

    async def close(self) -> None:
        """A no-op if the client was supplied by the caller - see
        :meth:`TelemetryTransport.close` for the ownership rationale."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()
        return False
