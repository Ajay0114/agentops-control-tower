from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Execution,
    Project,
    Session,
    TelemetryEventRecord,
)
from agentops_api.schemas.telemetry import TelemetryEvent


class TelemetryValidationError(Exception):
    pass


class TelemetryIdempotencyConflictError(Exception):
    pass


def resolve_agent_ownership(
    db: DBSession,
    agent_id: UUID,
):
    result = db.execute(
        select(Agent, Environment, Project)
        .join(Environment, Agent.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .where(Agent.id == agent_id)
    ).one_or_none()

    if result is None:
        raise TelemetryValidationError("Agent not found")

    return result


def validate_event_associations(
    db: DBSession,
    data: TelemetryEvent,
):
    agent, environment, project = resolve_agent_ownership(
        db,
        data.agent.id,
    )

    session = db.get(Session, data.context.session_id)

    if session is None:
        raise TelemetryValidationError("Session not found")

    if (
        session.environment_id != environment.id
        or session.project_id != project.id
    ):
        raise TelemetryValidationError(
            "Agent and session must belong to the same project and environment"
        )

    execution = db.get(Execution, data.context.execution_id)

    if execution is None:
        raise TelemetryValidationError("Execution not found")

    if (
        execution.agent_id != agent.id
        or execution.session_id != session.id
    ):
        raise TelemetryValidationError(
            "Execution must belong to the specified agent and session"
        )

    version_id = data.agent.version_id

    if version_id is not None:
        version = db.get(AgentVersion, version_id)

        if version is None:
            raise TelemetryValidationError("Agent version not found")

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
        version = db.execute(
            select(AgentVersion).where(
                AgentVersion.agent_id == agent.id,
                AgentVersion.version == data.agent.version,
            )
        ).scalar_one_or_none()

        if version is None:
            raise TelemetryValidationError(
                "Agent version does not exist for the specified agent"
            )

        version_id = version.id

    return agent, project, version_id


def find_existing_telemetry_event(
    db: DBSession,
    organization_id: UUID,
    event_id: UUID,
) -> TelemetryEventRecord | None:
    return db.execute(
        select(TelemetryEventRecord).where(
            TelemetryEventRecord.organization_id == organization_id,
            TelemetryEventRecord.event_id == event_id,
        )
    ).scalar_one_or_none()


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
) -> tuple[TelemetryEventRecord, bool]:
    agent, project, version_id = validate_event_associations(
        db,
        data,
    )

    organization_id = project.organization_id

    # Serialize the complete validated event into JSON-compatible values.
    event_data = data.model_dump(mode="json")

    # Check for an existing event before inserting.
    existing = find_existing_telemetry_event(
        db,
        organization_id,
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
