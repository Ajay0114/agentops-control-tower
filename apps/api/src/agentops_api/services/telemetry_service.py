from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Project,
    TelemetryEventRecord,
)
from agentops_api.schemas.telemetry import TelemetryEvent
from agentops_api.services.tenant_scope import (
    get_scoped_agent_version_by_id,
    get_scoped_execution,
    get_scoped_session,
    scope_telemetry_event_list,
)


class TelemetryNotFoundError(Exception):
    """A referenced resource does not exist, or is outside the authenticated
    key's scope (404)."""


class TelemetryValidationError(Exception):
    """The request body is self-contradictory (422) - independently valid,
    in-scope references that don't actually relate to each other."""


class TelemetryIdempotencyConflictError(Exception):
    pass


def resolve_agent_ownership(
    db: DBSession,
    agent_id: UUID,
    auth: AuthContext,
):
    statement = (
        select(Agent, Environment, Project)
        .join(Environment, Agent.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .where(
            Agent.id == agent_id,
            Project.organization_id == auth.organization_id,
        )
    )

    if auth.project_id is not None:
        statement = statement.where(Environment.project_id == auth.project_id)

    if auth.environment_id is not None:
        statement = statement.where(Agent.environment_id == auth.environment_id)

    result = db.execute(statement).one_or_none()

    if result is None:
        raise TelemetryNotFoundError("Agent not found")

    return result


def validate_event_associations(
    db: DBSession,
    data: TelemetryEvent,
    auth: AuthContext,
):
    agent, environment, project = resolve_agent_ownership(
        db,
        data.agent.id,
        auth,
    )

    session = get_scoped_session(db, data.context.session_id, auth)

    if session is None:
        raise TelemetryNotFoundError("Session not found")

    if (
        session.environment_id != environment.id
        or session.project_id != project.id
    ):
        raise TelemetryValidationError(
            "Agent and session must belong to the same project and environment"
        )

    execution = get_scoped_execution(db, data.context.execution_id, auth)

    if execution is None:
        raise TelemetryNotFoundError("Execution not found")

    if (
        execution.agent_id != agent.id
        or execution.session_id != session.id
    ):
        raise TelemetryValidationError(
            "Execution must belong to the specified agent and session"
        )

    version_id = data.agent.version_id

    if version_id is not None:
        version = get_scoped_agent_version_by_id(db, version_id, auth)

        if version is None:
            raise TelemetryNotFoundError("Agent version not found")

        if version.agent_id != agent.id:
            raise TelemetryValidationError(
                "Agent version does not belong to the specified agent"
            )

        if data.agent.version is not None and (
            data.agent.version != version.version
        ):
            raise TelemetryValidationError(
                "Agent version label does not match the registered version"
            )

    elif data.agent.version is not None:
        # agent.id here is already the tenant-scoped agent resolved above, not
        # a raw external identifier, so no further scoping is needed on this
        # lookup - any AgentVersion matching it is already within scope.
        version = db.execute(
            select(AgentVersion).where(
                AgentVersion.agent_id == agent.id,
                AgentVersion.version == data.agent.version,
            )
        ).scalar_one_or_none()

        if version is None:
            raise TelemetryNotFoundError(
                "Agent version does not exist for the specified agent"
            )

        version_id = version.id

    return agent, project, version_id


def find_existing_telemetry_event(
    db: DBSession,
    auth: AuthContext,
    event_id: UUID,
) -> TelemetryEventRecord | None:
    statement = scope_telemetry_event_list(
        select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == event_id),
        auth,
    )
    return db.execute(statement).scalar_one_or_none()


def validate_idempotent_telemetry_event(
    existing: TelemetryEventRecord,
    event_data: dict,
) -> None:
    if existing.event_data != event_data:
        raise TelemetryIdempotencyConflictError(
            "This event ID is already registered with different event content"
        )


def ingest_telemetry_event(
    db: DBSession,
    data: TelemetryEvent,
    auth: AuthContext,
) -> tuple[TelemetryEventRecord, bool]:
    agent, project, version_id = validate_event_associations(
        db,
        data,
        auth,
    )

    # Always the authenticated caller's own organization - never derived from
    # request payload data, even though project.organization_id is (after the
    # scoping above) guaranteed to be the same value.
    organization_id = auth.organization_id

    # Serialize the complete validated event into JSON-compatible values.
    event_data = data.model_dump(mode="json")

    # Check for an existing event before inserting.
    existing = find_existing_telemetry_event(
        db,
        auth,
        data.event_id,
    )

    if existing is not None:
        validate_idempotent_telemetry_event(existing, event_data)
        return existing, False

    record = TelemetryEventRecord(
        organization_id=organization_id,
        event_id=data.event_id,
        schema_version=data.schema_version,
        event_type=data.event_type,
        occurred_at=data.occurred_at,
        agent_id=agent.id,
        agent_version_id=version_id,
        session_id=data.context.session_id,
        execution_id=data.context.execution_id,
        source_platform=data.source.platform,
        service_name=data.source.service_name,
        environment=data.source.environment,
        operation_name=data.operation.name,
        operation_kind=data.operation.kind,
        operation_status=data.operation.status,
        duration_ms=data.operation.duration_ms,
        trace_id=data.context.trace_id.lower(),
        span_id=data.context.span_id.lower(),
        parent_span_id=(
            data.context.parent_span_id.lower()
            if data.context.parent_span_id is not None
            else None
        ),
        model_usage=(
            data.model_usage.model_dump(mode="json")
            if data.model_usage is not None
            else None
        ),
        error=(
            data.error.model_dump(mode="json")
            if data.error is not None
            else None
        ),
        payload=(
            data.payload.model_dump(mode="json")
            if data.payload is not None
            else None
        ),
        attributes=data.attributes,
        event_data=event_data,
    )

    db.add(record)
    db.flush()

    return record, True
