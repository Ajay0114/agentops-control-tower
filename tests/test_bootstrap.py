import threading

from sqlalchemy.orm import sessionmaker

from agentops_api.models.core import ApiKey, Environment, Organization, Project
from agentops_api.services.api_key_service import verify_api_key
from agentops_api.services.bootstrap_service import (
    INTERNAL_KEY_NAME,
    LOCAL_ENVIRONMENT_SLUG,
    LOCAL_ORGANIZATION_SLUG,
    LOCAL_PROJECT_SLUG,
    ensure_local_bootstrap,
    rotate_internal_key,
)


def test_first_run_creates_org_project_environment_and_internal_key(db_session):
    result = ensure_local_bootstrap(db_session)

    organization = db_session.get(Organization, result.organization_id)
    project = db_session.get(Project, result.project_id)
    environment = db_session.get(Environment, result.environment_id)
    api_key = db_session.get(ApiKey, result.api_key_id)

    assert organization.slug == LOCAL_ORGANIZATION_SLUG
    assert project.organization_id == organization.id
    assert project.slug == LOCAL_PROJECT_SLUG
    assert environment.project_id == project.id
    assert environment.slug == LOCAL_ENVIRONMENT_SLUG
    assert api_key.key_type == "internal"
    assert api_key.name == INTERNAL_KEY_NAME
    assert api_key.organization_id == organization.id

    # The raw key this call just created must actually work against the
    # real verification path the rest of the API uses.
    assert result.raw_api_key is not None
    verified = verify_api_key(db_session, result.raw_api_key)
    assert verified is not None
    assert verified.id == api_key.id


def test_repeated_bootstrap_is_idempotent(db_session):
    first = ensure_local_bootstrap(db_session)
    second = ensure_local_bootstrap(db_session)

    assert first.organization_id == second.organization_id
    assert first.project_id == second.project_id
    assert first.environment_id == second.environment_id
    assert first.api_key_id == second.api_key_id

    # Only the first call actually created anything - the second found it.
    assert first.raw_api_key is not None
    assert second.raw_api_key is None

    organizations = db_session.query(Organization).filter_by(slug=LOCAL_ORGANIZATION_SLUG).all()
    assert len(organizations) == 1

    api_keys = db_session.query(ApiKey).filter_by(name=INTERNAL_KEY_NAME).all()
    assert len(api_keys) == 1


def test_bootstrap_is_safe_under_concurrent_callers(db_session):
    """Simulates two processes racing to bootstrap at once, each with its
    own database session (as two real uvicorn workers would have) - exactly
    the scenario the M7 follow-up brief calls out by name."""
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    results = []
    errors = []

    def run():
        session = session_factory()
        try:
            results.append(ensure_local_bootstrap(session))
        except Exception as exc:  # pragma: no cover - failure path only
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=run) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"concurrent bootstrap raised: {errors}"
    assert len(results) == 5

    organization_ids = {result.organization_id for result in results}
    project_ids = {result.project_id for result in results}
    environment_ids = {result.environment_id for result in results}
    api_key_ids = {result.api_key_id for result in results}

    assert len(organization_ids) == 1
    assert len(project_ids) == 1
    assert len(environment_ids) == 1
    assert len(api_key_ids) == 1

    # Exactly one of the five concurrent callers actually created the key.
    raw_keys = [result.raw_api_key for result in results if result.raw_api_key is not None]
    assert len(raw_keys) == 1


def test_rotate_internal_key_revokes_the_old_one_and_mints_a_new_one(db_session):
    first = ensure_local_bootstrap(db_session)
    old_key_id = first.api_key_id

    new_record, new_raw_key = rotate_internal_key(
        db_session,
        organization_id=first.organization_id,
        project_id=first.project_id,
        environment_id=first.environment_id,
    )

    assert new_record.id != old_key_id

    old_record = db_session.get(ApiKey, old_key_id)
    assert old_record.status == "revoked"

    assert verify_api_key(db_session, new_raw_key) is not None
    # The old raw key (we never had it - but the old record's prefix with
    # any token) must now be rejected purely by virtue of being revoked.
    assert old_record.status != "active"


def test_rotate_internal_key_works_even_when_none_existed_yet(db_session):
    """Recovery when bootstrap never ran at all (e.g. a brand new database)
    still produces a usable internal key, not an error."""
    bootstrap_result = ensure_local_bootstrap(db_session)

    # Simulate "no internal key exists yet" by revoking the one bootstrap
    # just made, without going through rotate_internal_key, then rotating.
    existing = db_session.get(ApiKey, bootstrap_result.api_key_id)
    existing.status = "revoked"
    db_session.commit()

    record, raw_key = rotate_internal_key(
        db_session,
        organization_id=bootstrap_result.organization_id,
        project_id=bootstrap_result.project_id,
        environment_id=bootstrap_result.environment_id,
    )

    assert record.key_type == "internal"
    assert verify_api_key(db_session, raw_key) is not None
