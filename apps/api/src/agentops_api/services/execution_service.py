
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import Execution
from agentops_api.schemas.execution import ExecutionCreate, ExecutionTransition
from agentops_api.services.tenant_scope import (
    get_scoped_agent,
    get_scoped_agent_version_by_id,
    get_scoped_session,
    scope_execution_list,
)


ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class ExecutionNotFoundError(Exception):
    """The execution itself, or a referenced resource, does not exist or is
    outside the authenticated key's scope (404)."""


class ExecutionValidationError(Exception):
    """The request body is self-contradictory (422) - independently valid,
    in-scope references that don't actually relate to each other."""


class ExecutionIdempotencyConflictError(Exception):
    pass


class InvalidExecutionTransitionError(Exception):
    pass


def find_existing_execution(
    db: DBSession,
    session_id: UUID,
    external_execution_id: str,
    auth: AuthContext,
) -> Execution | None:
    """Tenant-scoped on its own merits - does not rely on the caller having
    already validated session_id's ownership before calling this."""
    statement = scope_execution_list(
        select(Execution).where(
            Execution.session_id == session_id,
            Execution.external_execution_id == external_execution_id,
        ),
        auth,
    )
    return db.execute(statement).scalar_one_or_none()


def validate_idempotent_request(
    existing: Execution,
    data: ExecutionCreate,
) -> None:
    if (
        existing.agent_id != data.agent_id
        or existing.agent_version_id != data.agent_version_id
    ):
        raise ExecutionIdempotencyConflictError(
            "This external execution ID is already associated "
            "with a different agent or agent version"
        )


def create_execution(
    db: DBSession,
    data: ExecutionCreate,
    auth: AuthContext,
) -> tuple[Execution, bool]:

    session = get_scoped_session(db, data.session_id, auth)

    if session is None:
        raise ExecutionNotFoundError("Session not found")

    # Check for an existing execution before inserting.
    if data.external_execution_id is not None:
        existing = find_existing_execution(
            db,
            data.session_id,
            data.external_execution_id,
            auth,
        )

        if existing is not None:
            validate_idempotent_request(existing, data)
            return existing, False

    agent = get_scoped_agent(db, data.agent_id, auth)

    if agent is None:
        raise ExecutionNotFoundError("Agent not found")

    if session.environment_id != agent.environment_id:
        raise ExecutionValidationError(
            "Agent and session must belong to the same environment"
        )

    if data.agent_version_id is not None:
        version = get_scoped_agent_version_by_id(db, data.agent_version_id, auth)

        if version is None:
            raise ExecutionNotFoundError("Agent version not found")

        if version.agent_id != agent.id:
            raise ExecutionValidationError(
                "Agent version does not belong to the specified agent"
            )

    execution = Execution(
        session_id=session.id,
        agent_id=agent.id,
        agent_version_id=data.agent_version_id,
        external_execution_id=data.external_execution_id,
        status="queued",
    )

    db.add(execution)
    db.flush()

    return execution, True


def transition_execution(
    db: DBSession,
    execution_id: UUID,
    data: ExecutionTransition,
    auth: AuthContext,
) -> Execution:

    statement = scope_execution_list(
        select(Execution).where(Execution.id == execution_id), auth
    ).with_for_update(of=Execution)

    execution = db.execute(statement).scalar_one_or_none()

    if execution is None:
        raise ExecutionNotFoundError("Execution not found")

    allowed = ALLOWED_TRANSITIONS.get(execution.status, set())

    if data.status not in allowed:
        raise InvalidExecutionTransitionError(
            f"Transition from '{execution.status}' "
            f"to '{data.status}' is not allowed"
        )

    now = datetime.now(timezone.utc)

    if data.status == "running":
        execution.started_at = now

    if data.status in {"completed", "failed", "cancelled"}:
        execution.ended_at = now

        if execution.started_at is not None:
            duration = now - execution.started_at
            execution.duration_ms = max(
                0,
                int(duration.total_seconds() * 1000),
            )

    if data.status == "failed":
        execution.error_type = data.error_type
        execution.error_message = data.error_message

    execution.status = data.status

    db.flush()

    return execution
