"""End-to-end integration tests: the real agentops_sdk package talking over
real HTTP to a real (locally running) agentops_api instance, backed by the
same isolated test Postgres database the rest of the suite uses.

This is deliberately separate from the SDK package's own test suite (which
is all mocked, for fast deterministic unit coverage) - these tests prove the
SDK's request/response shapes are actually compatible with the committed
backend, not just with what the SDK itself assumes.
"""

import socket
import threading
import time
from contextlib import closing
from uuid import uuid4

import pytest
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from agentops_api.config import get_settings
from agentops_api.db import get_db
from agentops_api.main import app
from agentops_api.models.core import Agent, AgentVersion, Environment, Organization, Project
from agentops_api.services.api_key_service import create_api_key

from agentops_sdk import AgentOps, AsyncAgentOps


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """A real uvicorn server for the real agentops_api app, pointed at the
    same agentops_test database the rest of the suite uses via the identical
    dependency-override pattern as tests/conftest.py's ``client`` fixture -
    the only difference is that requests arrive over real HTTP from an
    actual SDK client instead of FastAPI's in-process TestClient."""
    test_url = make_url(get_settings().database_url).set(database="agentops_test")
    engine = create_engine(test_url, pool_pre_ping=True)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Live test server did not start in time")

    yield {
        "base_url": f"http://127.0.0.1:{port}",
        "session_local": session_local,
    }

    server.should_exit = True
    thread.join(timeout=5)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def backend_context(live_server):
    """Seed an organization/project/environment/agent/version and a real,
    live-DB-backed API key - everything the SDK needs, created exactly the
    way the admin CLI / registry API would."""
    db = live_server["session_local"]()

    organization = Organization(name="SDK IT Org", slug=f"sdk-it-org-{uuid4().hex[:8]}")
    db.add(organization)
    db.flush()

    project = Project(
        organization_id=organization.id, name="SDK IT Project", slug=f"sdk-it-project-{uuid4().hex[:8]}"
    )
    db.add(project)
    db.flush()

    environment = Environment(
        project_id=project.id, name="Development", slug=f"dev-{uuid4().hex[:8]}"
    )
    db.add(environment)
    db.flush()

    agent = Agent(
        environment_id=environment.id,
        name="SDK IT Agent",
        slug=f"sdk-it-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db.add(agent)
    db.flush()

    version = AgentVersion(agent_id=agent.id, version="1.0.0", configuration={}, deployment_status="draft")
    db.add(version)
    db.flush()

    _, raw_key = create_api_key(db, organization_id=organization.id, name="SDK IT key")
    db.commit()

    yield {
        "base_url": live_server["base_url"],
        "api_key": raw_key,
        "agent_id": str(agent.id),
        "version_id": str(version.id),
        "session_local": live_server["session_local"],
    }

    db.close()


def test_sync_sdk_full_lifecycle_against_real_backend(backend_context):
    agentops = AgentOps(
        endpoint=backend_context["base_url"],
        api_key=backend_context["api_key"],
        timeout=10,
    )

    try:
        agent = agentops.agent(backend_context["agent_id"], version="1.0.0")

        with agentops.start_execution(agent=agent, session_id="integration-session-1") as execution:
            with execution.llm_call(model="gpt-4.1", provider="openai") as call:
                call.set_usage(input_tokens=100, output_tokens=50)

            with execution.tool_call("lookup_order") as tool:
                tool.set_output({"order_id": "123"})

        assert agentops.flush(timeout=10) is True
    finally:
        agentops.shutdown(timeout=10)

    # Verify against the real database: the execution reached "completed",
    # and both spans arrived as real, correctly-linked telemetry rows.
    from agentops_api.models.core import Execution as ExecutionModel, TelemetryEventRecord

    db = backend_context["session_local"]()
    try:
        db_execution = db.get(ExecutionModel, execution.execution_id)
        assert db_execution is not None
        assert db_execution.status == "completed"
        assert db_execution.duration_ms is not None

        events = (
            db.query(TelemetryEventRecord)
            .filter(TelemetryEventRecord.execution_id == execution.execution_id)
            .order_by(TelemetryEventRecord.occurred_at)
            .all()
        )
        event_types = {e.event_type for e in events}
        assert "agent.execution.started" in event_types
        assert "agent.execution.completed" in event_types
        assert "llm.request.completed" in event_types
        assert "tool.call.completed" in event_types

        llm_event = next(e for e in events if e.event_type == "llm.request.completed")
        assert llm_event.model_usage["input_tokens"] == 100
        assert llm_event.model_usage["total_tokens"] == 150
        assert llm_event.trace_id == execution.trace_id

        root_event = next(e for e in events if e.event_type == "agent.execution.started")
        assert llm_event.parent_span_id == root_event.span_id
    finally:
        db.close()


def test_sync_sdk_failure_path_against_real_backend(backend_context):
    agentops = AgentOps(
        endpoint=backend_context["base_url"],
        api_key=backend_context["api_key"],
        timeout=10,
    )

    try:
        agent = agentops.agent(backend_context["agent_id"], version="1.0.0")

        with pytest.raises(ValueError):
            with agentops.start_execution(agent=agent, session_id="integration-session-2") as execution:
                raise ValueError("simulated agent failure")

        agentops.flush(timeout=10)
    finally:
        agentops.shutdown(timeout=10)

    from agentops_api.models.core import Execution as ExecutionModel, TelemetryEventRecord

    db = backend_context["session_local"]()
    try:
        db_execution = db.get(ExecutionModel, execution.execution_id)
        assert db_execution.status == "failed"
        assert db_execution.error_type == "ValueError"

        failed_event = (
            db.query(TelemetryEventRecord)
            .filter(
                TelemetryEventRecord.execution_id == execution.execution_id,
                TelemetryEventRecord.event_type == "agent.execution.failed",
            )
            .one_or_none()
        )
        assert failed_event is not None
        assert failed_event.error["type"] == "ValueError"
    finally:
        db.close()


def test_sync_sdk_rejects_cross_tenant_agent(backend_context):
    """A second organization's agent_id must not be resolvable or usable by
    this API key - the SDK surfaces the backend's own tenant isolation."""
    from agentops_sdk.exceptions import AgentOpsNotFoundError

    db = backend_context["session_local"]()
    other_org = Organization(name="Other Org", slug=f"other-org-{uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    other_project = Project(organization_id=other_org.id, name="Other", slug=f"other-proj-{uuid4().hex[:8]}")
    db.add(other_project)
    db.flush()
    other_environment = Environment(project_id=other_project.id, name="Dev", slug=f"other-dev-{uuid4().hex[:8]}")
    db.add(other_environment)
    db.flush()
    other_agent = Agent(
        environment_id=other_environment.id,
        name="Other Agent",
        slug=f"other-agent-{uuid4().hex[:8]}",
        framework="custom-python",
        status="registered",
    )
    db.add(other_agent)
    db.commit()
    other_agent_id = str(other_agent.id)
    db.close()

    agentops = AgentOps(
        endpoint=backend_context["base_url"], api_key=backend_context["api_key"], timeout=10
    )
    try:
        with pytest.raises(AgentOpsNotFoundError):
            agentops.agent(other_agent_id)
    finally:
        agentops.shutdown(timeout=10)


@pytest.mark.asyncio
async def test_async_sdk_full_lifecycle_against_real_backend(backend_context):
    agentops = AsyncAgentOps(
        endpoint=backend_context["base_url"],
        api_key=backend_context["api_key"],
        timeout=10,
    )

    try:
        agent = await agentops.agent(backend_context["agent_id"], version="1.0.0")

        execution = await agentops.start_execution(
            agent=agent, session_id="integration-session-async-1"
        )
        async with execution:
            async with execution.trace("process_request"):
                pass

        assert await agentops.flush(timeout=10) is True
    finally:
        await agentops.shutdown(timeout=10)

    from agentops_api.models.core import Execution as ExecutionModel

    db = backend_context["session_local"]()
    try:
        db_execution = db.get(ExecutionModel, execution.execution_id)
        assert db_execution is not None
        assert db_execution.status == "completed"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_async_sdk_concurrent_executions_against_real_backend(backend_context):
    import asyncio

    agentops = AsyncAgentOps(
        endpoint=backend_context["base_url"], api_key=backend_context["api_key"], timeout=10
    )

    try:
        agent = await agentops.agent(backend_context["agent_id"], version="1.0.0")

        async def run(label):
            execution = await agentops.start_execution(
                agent=agent, session_id=f"integration-concurrent-{label}"
            )
            async with execution:
                async with execution.tool_call(f"tool-{label}"):
                    await asyncio.sleep(0.01)
                return execution.execution_id

        execution_ids = await asyncio.gather(run("a"), run("b"), run("c"))
        await agentops.flush(timeout=10)
    finally:
        await agentops.shutdown(timeout=10)

    assert len(set(execution_ids)) == 3

    from agentops_api.models.core import Execution as ExecutionModel

    db = backend_context["session_local"]()
    try:
        for execution_id in execution_ids:
            db_execution = db.get(ExecutionModel, execution_id)
            assert db_execution.status == "completed"
    finally:
        db.close()
