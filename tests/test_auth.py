import logging
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import agentops_api.auth as auth_module
from agentops_api.auth import AuthContext, get_auth_context
from agentops_api.config import get_settings
from agentops_api.db import get_db
from agentops_api.models.core import Environment, Organization, Project
from agentops_api.services.api_key_service import (
    create_api_key,
    get_api_key,
    revoke_api_key,
    touch_last_used,
)


# A dedicated engine/session bound to the same isolated test database used by
# the rest of the suite, so anything that opens its OWN session (the auth
# module's background task, deliberately independent of the request session)
# still reads and writes test data rather than the real dev database.
_database_url = make_url(get_settings().database_url).set(database="agentops_test")
_auth_test_engine = create_engine(_database_url, pool_pre_ping=True)
AuthTestSessionLocal = sessionmaker(bind=_auth_test_engine, autoflush=False, autocommit=False)


@pytest.fixture
def patch_auth_session(monkeypatch):
    """Redirect the auth module's independent background-task session to the test DB."""
    monkeypatch.setattr(auth_module, "SessionLocal", AuthTestSessionLocal)


def create_org_project_environment(db_session):
    organization = Organization(
        name="Auth Test Organization",
        slug=f"auth-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="Auth Test Project",
        slug=f"auth-project-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()

    environment = Environment(
        project_id=project.id,
        name="Development",
        slug=f"dev-{uuid4().hex[:8]}",
    )
    db_session.add(environment)
    db_session.flush()

    return {"organization": organization, "project": project, "environment": environment}


# ---------------------------------------------------------------------------
# Direct dependency tests
# ---------------------------------------------------------------------------


def test_missing_authorization_header_raises_401(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(
            background_tasks=BackgroundTasks(), authorization=None, db=db_session
        )

    assert exc_info.value.status_code == 401


@pytest.mark.parametrize(
    "header_value",
    [
        "NotBearer sometoken",
        "Bearer",
        "Bearer ",
        "justatoken",
        "",
    ],
)
def test_malformed_or_empty_header_raises_401(db_session, header_value):
    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(
            background_tasks=BackgroundTasks(),
            authorization=header_value,
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_invalid_api_key_raises_401(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(
            background_tasks=BackgroundTasks(),
            authorization="Bearer aops_00000000_doesnotexist",
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_expired_api_key_raises_401(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    _, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Expired key",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(
            background_tasks=BackgroundTasks(),
            authorization=f"Bearer {raw_key}",
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_revoked_api_key_raises_401(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Revoked key"
    )
    revoke_api_key(db_session, record)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(
            background_tasks=BackgroundTasks(),
            authorization=f"Bearer {raw_key}",
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_valid_api_key_returns_auth_context(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Valid key",
        project_id=context["project"].id,
        environment_id=context["environment"].id,
    )
    db_session.commit()

    auth = get_auth_context(
        background_tasks=BackgroundTasks(),
        authorization=f"Bearer {raw_key}",
        db=db_session,
    )

    assert isinstance(auth, AuthContext)
    assert auth.api_key_id == record.id
    assert auth.organization_id == context["organization"].id
    assert auth.project_id == context["project"].id
    assert auth.environment_id == context["environment"].id


def test_auth_context_reflects_unrestricted_key(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    _, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Org-wide key"
    )
    db_session.commit()

    auth = get_auth_context(
        background_tasks=BackgroundTasks(),
        authorization=f"Bearer {raw_key}",
        db=db_session,
    )

    assert auth.organization_id == context["organization"].id
    assert auth.project_id is None
    assert auth.environment_id is None


def test_auth_context_is_immutable(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    _, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Immutable key"
    )
    db_session.commit()

    auth = get_auth_context(
        background_tasks=BackgroundTasks(),
        authorization=f"Bearer {raw_key}",
        db=db_session,
    )

    with pytest.raises(FrozenInstanceError):
        auth.organization_id = uuid4()


def test_unauthorized_detail_is_generic_and_identical_across_failures(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    revoked_record, revoked_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Revoked"
    )
    revoke_api_key(db_session, revoked_record)

    _, expired_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Expired",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.commit()

    failing_headers = [
        None,
        "Malformed",
        "Bearer unknown_key_xyz",
        f"Bearer {revoked_key}",
        f"Bearer {expired_key}",
    ]

    details = set()
    statuses = set()

    for header in failing_headers:
        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                background_tasks=BackgroundTasks(), authorization=header, db=db_session
            )

        details.add(exc_info.value.detail)
        statuses.add(exc_info.value.status_code)

    assert statuses == {401}
    assert len(details) == 1  # every failure reason produces the exact same message


def test_no_raw_key_in_logs_on_failure(db_session, caplog):
    secret_marker = "totally-not-a-real-secret-marker"

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(HTTPException):
            get_auth_context(
                background_tasks=BackgroundTasks(),
                authorization=f"Bearer {secret_marker}",
                db=db_session,
            )

    assert secret_marker not in caplog.text


# ---------------------------------------------------------------------------
# Background last_used_at update: scheduling, independent session, throttling
# ---------------------------------------------------------------------------


def test_valid_auth_schedules_last_used_background_task(db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Scheduled key"
    )
    db_session.commit()

    background_tasks = BackgroundTasks()

    get_auth_context(
        background_tasks=background_tasks,
        authorization=f"Bearer {raw_key}",
        db=db_session,
    )

    assert len(background_tasks.tasks) == 1
    scheduled = background_tasks.tasks[0]
    assert scheduled.func is auth_module._run_touch_last_used
    assert scheduled.args == (record.id,)


def test_run_touch_last_used_uses_independent_session(
    db_session, patch_auth_session
):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, _ = create_api_key(
        db_session, organization_id=context["organization"].id, name="Background key"
    )
    db_session.commit()

    assert record.last_used_at is None

    auth_module._run_touch_last_used(record.id)

    # _run_touch_last_used wrote through a different session/connection;
    # db_session's identity map still holds the pre-update object, so it must
    # be expired explicitly to observe the other session's committed change.
    db_session.expire_all()

    refreshed = get_api_key(db_session, record.id)
    assert refreshed.last_used_at is not None


def test_run_touch_last_used_is_throttled(db_session, patch_auth_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, _ = create_api_key(
        db_session, organization_id=context["organization"].id, name="Throttled key"
    )
    db_session.commit()

    auth_module._run_touch_last_used(record.id)
    db_session.expire_all()
    first_value = get_api_key(db_session, record.id).last_used_at

    auth_module._run_touch_last_used(record.id)
    db_session.expire_all()
    second_value = get_api_key(db_session, record.id).last_used_at

    assert first_value is not None
    assert first_value == second_value


def test_run_touch_last_used_never_raises(monkeypatch, caplog):
    def boom(db, api_key_id):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(auth_module, "touch_last_used", boom)

    with caplog.at_level(logging.ERROR):
        auth_module._run_touch_last_used(uuid4())  # must not raise

    assert "simulated failure" in caplog.text


# ---------------------------------------------------------------------------
# Full-stack integration: isolated test-only endpoint (no production route
# is touched - tenant-scoped wiring into real endpoints is Milestone 5-D)
# ---------------------------------------------------------------------------


def _build_probe_app() -> FastAPI:
    app = FastAPI()

    @app.get("/__probe_auth__")
    def probe(auth: AuthContext = Depends(get_auth_context)):
        return {
            "api_key_id": str(auth.api_key_id),
            "organization_id": str(auth.organization_id),
            "project_id": str(auth.project_id) if auth.project_id else None,
            "environment_id": str(auth.environment_id) if auth.environment_id else None,
        }

    return app


@pytest.fixture
def probe_client():
    app = _build_probe_app()

    def override_get_db():
        db = AuthTestSessionLocal()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_probe_endpoint_rejects_missing_header(probe_client):
    response = probe_client.get("/__probe_auth__")

    assert response.status_code == 401
    assert response.json()["detail"] == auth_module.AUTHENTICATION_ERROR_DETAIL


def test_probe_endpoint_rejects_invalid_key(probe_client):
    response = probe_client.get(
        "/__probe_auth__", headers={"Authorization": "Bearer not_a_real_key"}
    )

    assert response.status_code == 401


def test_probe_endpoint_accepts_valid_key_and_returns_context(
    probe_client, db_session
):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Probe key",
        project_id=context["project"].id,
    )
    db_session.commit()

    response = probe_client.get(
        "/__probe_auth__", headers={"Authorization": f"Bearer {raw_key}"}
    )

    assert response.status_code == 200

    body = response.json()
    assert body["api_key_id"] == str(record.id)
    assert body["organization_id"] == str(context["organization"].id)
    assert body["project_id"] == str(context["project"].id)
    assert body["environment_id"] is None


def test_probe_endpoint_runs_background_last_used_update(
    probe_client, db_session, patch_auth_session
):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Probe bg key"
    )
    db_session.commit()

    response = probe_client.get(
        "/__probe_auth__", headers={"Authorization": f"Bearer {raw_key}"}
    )

    assert response.status_code == 200

    db_session.expire_all()
    refreshed = get_api_key(db_session, record.id)
    assert refreshed.last_used_at is not None
