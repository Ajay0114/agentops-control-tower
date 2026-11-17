"""Tenant-scoping helpers shared by every protected resource.

Every function here takes the caller's :class:`~agentops_api.auth.AuthContext`
(the only trusted source of tenant identity) and enforces all three scope
dimensions together:

- ``organization_id``: always required.
- ``project_id``: only when the authenticated key is restricted to one
  project (``auth.project_id is not None``).
- ``environment_id``: only when the key is restricted to one environment
  (``auth.environment_id is not None``).

Scoping is join-based against the existing Organization -> Project ->
Environment -> Agent chain (and Session's own direct ``project_id`` /
``environment_id`` columns), per the Milestone 5-A decision: no
``organization_id`` column is added to any table that doesn't already have
one.

A resource that exists but is outside the caller's scope is indistinguishable
from one that does not exist at all - every function here returns
``None`` (single fetch) or an empty result (list) for both cases. Callers
must turn that into an HTTP 404, never a 403, so a resource ID can never be
used to probe for another organization's data.
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import (
    Agent,
    AgentVersion,
    Environment,
    Execution,
    Project,
    Session,
    TelemetryEventRecord,
)


def _scope_project(statement: Select, auth: AuthContext) -> Select:
    statement = statement.where(Project.organization_id == auth.organization_id)

    if auth.project_id is not None:
        statement = statement.where(Project.id == auth.project_id)

    return statement


def get_scoped_project(db: DBSession, project_id: UUID, auth: AuthContext) -> Project | None:
    """Internal use only (e.g. validating a project_id referenced during
    Environment creation) - there is no public Project API."""
    statement = _scope_project(select(Project).where(Project.id == project_id), auth)
    return db.execute(statement).scalar_one_or_none()


def _scope_environment(statement: Select, auth: AuthContext) -> Select:
    statement = statement.join(
        Project, Environment.project_id == Project.id
    ).where(Project.organization_id == auth.organization_id)

    if auth.project_id is not None:
        statement = statement.where(Environment.project_id == auth.project_id)

    if auth.environment_id is not None:
        statement = statement.where(Environment.id == auth.environment_id)

    return statement


def get_scoped_environment(
    db: DBSession, environment_id: UUID, auth: AuthContext
) -> Environment | None:
    statement = _scope_environment(
        select(Environment).where(Environment.id == environment_id), auth
    )
    return db.execute(statement).scalar_one_or_none()


def scope_environment_list(statement: Select, auth: AuthContext) -> Select:
    return _scope_environment(statement, auth)


def _scope_agent(statement: Select, auth: AuthContext) -> Select:
    statement = (
        statement.join(Environment, Agent.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .where(Project.organization_id == auth.organization_id)
    )

    if auth.project_id is not None:
        statement = statement.where(Environment.project_id == auth.project_id)

    if auth.environment_id is not None:
        statement = statement.where(Agent.environment_id == auth.environment_id)

    return statement


def get_scoped_agent(db: DBSession, agent_id: UUID, auth: AuthContext) -> Agent | None:
    statement = _scope_agent(select(Agent).where(Agent.id == agent_id), auth)
    return db.execute(statement).scalar_one_or_none()


def scope_agent_list(statement: Select, auth: AuthContext) -> Select:
    return _scope_agent(statement, auth)


def _scope_agent_version(statement: Select, auth: AuthContext) -> Select:
    statement = (
        statement.join(Agent, AgentVersion.agent_id == Agent.id)
        .join(Environment, Agent.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .where(Project.organization_id == auth.organization_id)
    )

    if auth.project_id is not None:
        statement = statement.where(Environment.project_id == auth.project_id)

    if auth.environment_id is not None:
        statement = statement.where(Agent.environment_id == auth.environment_id)

    return statement


def get_scoped_agent_version(
    db: DBSession, agent_id: UUID, version_id: UUID, auth: AuthContext
) -> AgentVersion | None:
    statement = _scope_agent_version(
        select(AgentVersion).where(
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent_id,
        ),
        auth,
    )
    return db.execute(statement).scalar_one_or_none()


def get_scoped_agent_version_by_id(
    db: DBSession, version_id: UUID, auth: AuthContext
) -> AgentVersion | None:
    """Resolve a version by its own id alone, with no agent_id pre-constraint.

    Used where the version is one of several independently-resolved
    references in a request body (e.g. Execution creation's agent_version_id)
    and must be looked up on its own merits before being cross-checked for
    consistency against the other references.
    """
    statement = _scope_agent_version(
        select(AgentVersion).where(AgentVersion.id == version_id), auth
    )
    return db.execute(statement).scalar_one_or_none()


def scope_agent_version_list(statement: Select, auth: AuthContext) -> Select:
    return _scope_agent_version(statement, auth)


def _scope_session(statement: Select, auth: AuthContext) -> Select:
    statement = statement.join(
        Project, Session.project_id == Project.id
    ).where(Project.organization_id == auth.organization_id)

    if auth.project_id is not None:
        statement = statement.where(Session.project_id == auth.project_id)

    if auth.environment_id is not None:
        statement = statement.where(Session.environment_id == auth.environment_id)

    return statement


def get_scoped_session(db: DBSession, session_id: UUID, auth: AuthContext) -> Session | None:
    statement = _scope_session(select(Session).where(Session.id == session_id), auth)
    return db.execute(statement).scalar_one_or_none()


def scope_session_list(statement: Select, auth: AuthContext) -> Select:
    return _scope_session(statement, auth)


def _scope_execution(statement: Select, auth: AuthContext) -> Select:
    statement = statement.join(
        Session, Execution.session_id == Session.id
    ).join(Project, Session.project_id == Project.id).where(
        Project.organization_id == auth.organization_id
    )

    if auth.project_id is not None:
        statement = statement.where(Session.project_id == auth.project_id)

    if auth.environment_id is not None:
        statement = statement.where(Session.environment_id == auth.environment_id)

    return statement


def get_scoped_execution(db: DBSession, execution_id: UUID, auth: AuthContext) -> Execution | None:
    statement = _scope_execution(select(Execution).where(Execution.id == execution_id), auth)
    return db.execute(statement).scalar_one_or_none()


def scope_execution_list(statement: Select, auth: AuthContext) -> Select:
    return _scope_execution(statement, auth)


def _scope_telemetry_event(statement: Select, auth: AuthContext) -> Select:
    # TelemetryEventRecord already has organization_id directly - no join
    # needed for the primary tenant check. The Agent/Environment join is only
    # added when the key is further restricted to one project or environment,
    # so the common org-wide-key case stays a single-table filter.
    statement = statement.where(
        TelemetryEventRecord.organization_id == auth.organization_id
    )

    if auth.project_id is not None or auth.environment_id is not None:
        statement = statement.join(
            Agent, TelemetryEventRecord.agent_id == Agent.id
        )

        if auth.environment_id is not None:
            statement = statement.where(Agent.environment_id == auth.environment_id)
        else:
            statement = statement.join(
                Environment, Agent.environment_id == Environment.id
            ).where(Environment.project_id == auth.project_id)

    return statement


def get_scoped_telemetry_event(
    db: DBSession, event_id: UUID, auth: AuthContext
) -> TelemetryEventRecord | None:
    statement = _scope_telemetry_event(
        select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == event_id),
        auth,
    )
    return db.execute(statement).scalar_one_or_none()


def scope_telemetry_event_list(statement: Select, auth: AuthContext) -> Select:
    return _scope_telemetry_event(statement, auth)
