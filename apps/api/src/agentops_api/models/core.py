
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import foreign, Mapped, mapped_column, relationship

from agentops_api.models.base import Base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import (
    BigInteger,
    and_,
    ForeignKeyConstraint,
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class Project(Base):
    __tablename__ = "projects"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_projects_organization_slug",
        ),
        Index("ix_projects_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(
        back_populates="projects",
    )

    environments: Mapped[list["Environment"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    integrations: Mapped[list["Integration"]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
    )

    sessions: Mapped[list["Session"]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
    )


class Environment(Base):
    __tablename__ = "environments"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "slug",
            name="uq_environments_project_slug",
        ),
        Index("ix_environments_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    agents: Mapped[list["Agent"]] = relationship(
    back_populates="environment",
    cascade="all, delete-orphan",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(
        back_populates="environments",
    )

    integrations: Mapped[list["Integration"]] = relationship(
    back_populates="environment",
    )

    sessions: Mapped[list["Session"]] = relationship(
    back_populates="environment",
    cascade="all, delete-orphan",
    )



class Agent(Base):
    __tablename__ = "agents"

    __table_args__ = (
        UniqueConstraint(
            "environment_id",
            "slug",
            name="uq_agents_environment_slug",
        ),
        Index("ix_agents_environment_id", "environment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    environment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    framework: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="registered",
        server_default="registered",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    environment: Mapped["Environment"] = relationship(
        back_populates="agents",
    )

    versions: Mapped[list["AgentVersion"]] = relationship(
    back_populates="agent",
    cascade="all, delete-orphan",
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "version",
            name="uq_agent_versions_agent_version",
        ),
        UniqueConstraint(
            "id",
            "agent_id",
            name="uq_agent_versions_id_agent_id",
        ),
        Index("ix_agent_versions_agent_id", "agent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    configuration: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    deployment_status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        server_default="draft",
        nullable=False,
    )

    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(
        back_populates="versions",
    )


class Integration(Base):
    __tablename__ = "integrations"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            name="uq_integrations_project_name",
        ),
        Index("ix_integrations_project_id", "project_id"),
        Index("ix_integrations_environment_id", "environment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    integration_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    configuration: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(
        back_populates="integrations",
    )

    environment: Mapped["Environment | None"] = relationship(
        back_populates="integrations",
    )



class Session(Base):
    __tablename__ = "sessions"

    __table_args__ = (
        UniqueConstraint(
            "environment_id",
            "external_session_id",
            name="uq_sessions_environment_external_id",
        ),
        Index("ix_sessions_project_id", "project_id"),
        Index("ix_sessions_environment_id", "environment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    environment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )

    external_session_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        server_default="active",
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(
        back_populates="sessions",
    )

    environment: Mapped["Environment"] = relationship(
        back_populates="sessions",
    )

    executions: Mapped[list["Execution"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Execution(Base):
    __tablename__ = "executions"

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "external_execution_id",
            name="uq_executions_session_external_id",
        ),
        ForeignKeyConstraint(
            ["agent_version_id", "agent_id"],
            ["agent_versions.id", "agent_versions.agent_id"],
            name="fk_executions_version_agent",
            ondelete="RESTRICT",
        ),
        Index("ix_executions_session_id", "session_id"),
        Index("ix_executions_agent_id", "agent_id"),
        Index("ix_executions_agent_version_id", "agent_version_id"),
        Index("ix_executions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
    nullable=True,
    )

    external_execution_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="queued",
        server_default="queued",
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    error_type: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session: Mapped["Session"] = relationship(
        back_populates="executions",
    )

    agent: Mapped["Agent"] = relationship(
        foreign_keys=[agent_id],
    )

    agent_version: Mapped["AgentVersion | None"] = relationship(
        primaryjoin=lambda: and_(
            AgentVersion.id == foreign(Execution.agent_version_id),
            AgentVersion.agent_id == Execution.agent_id,
        ),
        foreign_keys=lambda: [Execution.agent_version_id],
    )


class TelemetryEventRecord(Base):
    __tablename__ = "telemetry_events"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "event_id",
            name="uq_telemetry_events_organization_event",
        ),
        ForeignKeyConstraint(
            ["agent_version_id", "agent_id"],
            ["agent_versions.id", "agent_versions.agent_id"],
            name="fk_telemetry_events_version_agent",
            ondelete="RESTRICT",
        ),
        Index("ix_telemetry_events_agent_id", "agent_id"),
        Index("ix_telemetry_events_session_id", "session_id"),
        Index("ix_telemetry_events_execution_id", "execution_id"),
        Index("ix_telemetry_events_event_type", "event_type"),
        Index("ix_telemetry_events_trace_id", "trace_id"),
        Index("ix_telemetry_events_occurred_at", "occurred_at"),
        Index("ix_telemetry_events_organization_occurred", "organization_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
    )

    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_platform: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    service_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    operation_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    operation_kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    operation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    trace_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    span_id: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    parent_span_id: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    model_usage: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    error: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    attributes: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )

    event_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    __table_args__ = (
        Index("ix_api_keys_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional narrowing: null means "any project/environment in the organization".
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )

    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # Non-secret, indexed lookup value: the first characters of the raw key.
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    # SHA-256 hex digest of the full raw key. Never store the raw key itself.
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        server_default="active",
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship()
    project: Mapped["Project | None"] = relationship()
    environment: Mapped["Environment | None"] = relationship()


class User(Base):
    """A local dashboard account (M7). Entirely separate from ApiKey: a User
    authenticates a human into the dashboard via the browser-facing session
    mechanism below, while ApiKey continues to authenticate programmatic
    callers (the SDK, and the dashboard's own server-side backend calls) via
    AuthContext. A User's organization_id/project_id are never consulted by
    AuthContext or tenant_scope.py - they exist only so the dashboard layer
    can resolve and display which tenant this person belongs to; the actual
    authorization for every data request still flows through the existing
    API-key AuthContext mechanism, unchanged."""

    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional narrowing, mirroring ApiKey: null means "the whole organization".
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Stored lowercased; uniqueness is case-insensitive by construction.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # Argon2id hash (via argon2-cffi), never the raw password.
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="admin",
        server_default="admin",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        server_default="active",
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship()
    project: Mapped["Project | None"] = relationship()


class UserSession(Base):
    """A server-side dashboard session (M7). Mirrors ApiKey's prefix+hash
    pattern: the raw session token is returned to the caller (here, the
    Next.js server layer) exactly once at creation and is never stored -
    only its SHA-256 hash is persisted, looked up via the non-secret
    token_prefix. SHA-256 is appropriate here for the same reason it is for
    ApiKey: the token is 256 bits of secrets.token_urlsafe output, not a
    human-chosen secret - see api_key_service.py's module docstring."""

    __tablename__ = "user_sessions"

    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    token_prefix: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship()

