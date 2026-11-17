import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from agentops_api.models.core import Environment, Organization, Project
from agentops_api.services import api_key_service
from agentops_api.services.api_key_service import (
    ApiKeyValidationError,
    PREFIX_LENGTH,
    create_api_key,
    generate_raw_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
    touch_last_used,
    verify_api_key,
)


def create_org_project_environment(db_session):
    organization = Organization(
        name="API Key Test Organization",
        slug=f"apikey-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="API Key Test Project",
        slug=f"apikey-project-{uuid4().hex[:8]}",
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


def test_create_api_key_returns_record_and_raw_key(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Test key",
        project_id=context["project"].id,
        environment_id=context["environment"].id,
    )
    db_session.commit()

    assert record.organization_id == context["organization"].id
    assert record.project_id == context["project"].id
    assert record.environment_id == context["environment"].id
    assert record.status == "active"
    assert record.revoked_at is None
    assert raw_key.startswith(record.key_prefix)
    assert raw_key.startswith("aops_")


def test_raw_key_is_never_stored(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Test key",
    )
    db_session.commit()

    assert record.key_hash != raw_key
    assert record.key_hash == hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    assert not hasattr(record, "raw_key")
    assert not hasattr(record, "api_key")


def test_create_api_key_missing_organization_raises(client, db_session):
    with pytest.raises(ApiKeyValidationError, match="Organization not found"):
        create_api_key(db_session, organization_id=uuid4(), name="Test key")


def test_create_api_key_project_outside_organization_raises(client, db_session):
    context_a = create_org_project_environment(db_session)
    context_b = create_org_project_environment(db_session)
    db_session.commit()

    with pytest.raises(ApiKeyValidationError, match="Project does not belong"):
        create_api_key(
            db_session,
            organization_id=context_a["organization"].id,
            name="Test key",
            project_id=context_b["project"].id,
        )


def test_create_api_key_environment_outside_project_raises(client, db_session):
    context = create_org_project_environment(db_session)
    other_project = Project(
        organization_id=context["organization"].id,
        name="Other Project",
        slug=f"other-project-{uuid4().hex[:8]}",
    )
    db_session.add(other_project)
    db_session.flush()
    db_session.commit()

    with pytest.raises(ApiKeyValidationError, match="does not belong to the specified project"):
        create_api_key(
            db_session,
            organization_id=context["organization"].id,
            name="Test key",
            project_id=other_project.id,
            environment_id=context["environment"].id,
        )


def test_create_api_key_environment_outside_organization_raises(client, db_session):
    context_a = create_org_project_environment(db_session)
    context_b = create_org_project_environment(db_session)
    db_session.commit()

    with pytest.raises(ApiKeyValidationError, match="does not belong to the specified organization"):
        create_api_key(
            db_session,
            organization_id=context_a["organization"].id,
            name="Test key",
            environment_id=context_b["environment"].id,
        )


def test_verify_api_key_success(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Test key"
    )
    db_session.commit()

    verified = verify_api_key(db_session, raw_key)

    assert verified is not None
    assert verified.id == record.id


def test_verify_api_key_wrong_secret_fails(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    _, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Test key"
    )
    db_session.commit()

    tampered = raw_key[:-1] + ("a" if raw_key[-1] != "a" else "b")

    assert verify_api_key(db_session, tampered) is None


def test_verify_api_key_unknown_prefix_fails(client, db_session):
    assert verify_api_key(db_session, "aops_00000000_doesnotexist") is None


def test_verify_api_key_malformed_or_short_fails(client, db_session):
    assert verify_api_key(db_session, "") is None
    assert verify_api_key(db_session, "short") is None
    assert verify_api_key(db_session, None) is None


def test_verify_api_key_revoked_fails(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Test key"
    )
    db_session.commit()

    revoke_api_key(db_session, record)
    db_session.commit()

    assert verify_api_key(db_session, raw_key) is None


def test_verify_api_key_expired_fails(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    _, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Test key",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.commit()

    assert verify_api_key(db_session, raw_key) is None


def test_verify_api_key_not_yet_expired_succeeds(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    _, raw_key = create_api_key(
        db_session,
        organization_id=context["organization"].id,
        name="Test key",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.commit()

    assert verify_api_key(db_session, raw_key) is not None


def test_revoke_api_key_sets_status_and_timestamp(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, _ = create_api_key(
        db_session, organization_id=context["organization"].id, name="Test key"
    )
    db_session.commit()

    revoke_api_key(db_session, record)
    db_session.commit()

    assert record.status == "revoked"
    first_revoked_at = record.revoked_at
    assert first_revoked_at is not None

    # Revoking an already-revoked key is a no-op, not an error.
    revoke_api_key(db_session, record)
    db_session.commit()

    assert record.revoked_at == first_revoked_at


def test_list_api_keys_filters_by_organization(client, db_session):
    context_a = create_org_project_environment(db_session)
    context_b = create_org_project_environment(db_session)
    db_session.commit()

    create_api_key(db_session, organization_id=context_a["organization"].id, name="Key A")
    create_api_key(db_session, organization_id=context_b["organization"].id, name="Key B")
    db_session.commit()

    keys_a = list_api_keys(db_session, context_a["organization"].id)

    assert len(keys_a) == 1
    assert keys_a[0].name == "Key A"


def test_touch_last_used_sets_when_null(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, _ = create_api_key(
        db_session, organization_id=context["organization"].id, name="Test key"
    )
    db_session.commit()

    assert record.last_used_at is None

    touch_last_used(db_session, record.id)

    refreshed = get_api_key(db_session, record.id)
    assert refreshed.last_used_at is not None


def test_touch_last_used_is_throttled(client, db_session):
    context = create_org_project_environment(db_session)
    db_session.commit()

    record, _ = create_api_key(
        db_session, organization_id=context["organization"].id, name="Test key"
    )
    db_session.commit()

    touch_last_used(db_session, record.id)
    first_value = get_api_key(db_session, record.id).last_used_at

    # Called again immediately: within the throttle window, so no write happens.
    touch_last_used(db_session, record.id)
    second_value = get_api_key(db_session, record.id).last_used_at

    assert first_value == second_value


def test_create_api_key_retries_on_prefix_collision(client, db_session, monkeypatch):
    context = create_org_project_environment(db_session)
    db_session.commit()

    # Pre-insert a key, then force the next generated prefix to collide with it
    # once before succeeding, to exercise the retry-on-collision path.
    create_api_key(db_session, organization_id=context["organization"].id, name="Existing key")
    db_session.commit()

    existing_prefix = list_api_keys(db_session, context["organization"].id)[0].key_prefix

    attempts = iter([(f"{existing_prefix}_collide", existing_prefix), generate_raw_key()])
    monkeypatch.setattr(api_key_service, "generate_raw_key", lambda: next(attempts))

    record, raw_key = create_api_key(
        db_session, organization_id=context["organization"].id, name="Retried key"
    )
    db_session.commit()

    assert record.name == "Retried key"
    assert verify_api_key(db_session, raw_key) is not None
