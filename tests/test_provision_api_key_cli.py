import argparse
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from agentops_api.config import get_settings
from agentops_api.models.core import Organization, Project

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "apps" / "api" / "scripts" / "provision_api_key.py"
)

# A dedicated engine/session pointed at the same isolated test database the
# rest of the suite uses, so the CLI module (which opens its own sessions,
# independent of the request-scoped fixtures) reads and writes the same data.
_database_url = make_url(get_settings().database_url).set(database="agentops_test")
_cli_test_engine = create_engine(_database_url, pool_pre_ping=True)
CliSessionLocal = sessionmaker(bind=_cli_test_engine, autoflush=False, autocommit=False)


@pytest.fixture
def cli(monkeypatch):
    spec = importlib.util.spec_from_file_location("provision_api_key_cli", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "SessionLocal", CliSessionLocal)

    return module


def create_org_and_project(db_session):
    organization = Organization(
        name="CLI Test Organization",
        slug=f"cli-org-{uuid4().hex[:8]}",
    )
    db_session.add(organization)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        name="CLI Test Project",
        slug=f"cli-project-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()

    return organization, project


def extract_field(output: str, label: str) -> str:
    for line in output.splitlines():
        if line.startswith(f"{label}: "):
            return line[len(label) + 2 :]

    raise AssertionError(f"'{label}:' not found in output:\n{output}")


def test_cli_bootstrap_org_creates_organization_and_project(cli, capsys):
    args = argparse.Namespace(
        name="Bootstrap Org",
        slug=f"bootstrap-{uuid4().hex[:8]}",
        project_name="Default",
        project_slug=f"default-{uuid4().hex[:8]}",
    )

    cli.cmd_bootstrap_org(args)

    output = capsys.readouterr().out
    assert "organization_id:" in output
    assert "project_id:" in output


def test_cli_bootstrap_org_without_project(cli, capsys):
    args = argparse.Namespace(
        name="Org Only",
        slug=f"org-only-{uuid4().hex[:8]}",
        project_name=None,
        project_slug=None,
    )

    cli.cmd_bootstrap_org(args)

    output = capsys.readouterr().out
    assert "organization_id:" in output
    assert "project_id:" not in output


def test_cli_create_key_prints_raw_key_once(cli, db_session, capsys):
    organization, _ = create_org_and_project(db_session)
    db_session.commit()

    args = argparse.Namespace(
        organization_id=str(organization.id),
        name="Test key",
        project_id=None,
        environment_id=None,
        expires_days=None,
    )

    cli.cmd_create_key(args)

    output = capsys.readouterr().out
    raw_key = extract_field(output, "api_key")

    assert raw_key.startswith("aops_")
    assert output.count("api_key:") == 1


def test_cli_create_key_rejects_unknown_organization(cli, capsys):
    args = argparse.Namespace(
        organization_id=str(uuid4()),
        name="Test key",
        project_id=None,
        environment_id=None,
        expires_days=None,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_create_key(args)

    assert exc_info.value.code == 1
    assert "Organization not found" in capsys.readouterr().err


def test_cli_list_keys_never_prints_raw_key(cli, db_session, capsys):
    organization, _ = create_org_and_project(db_session)
    db_session.commit()

    create_args = argparse.Namespace(
        organization_id=str(organization.id),
        name="Listed key",
        project_id=None,
        environment_id=None,
        expires_days=None,
    )
    cli.cmd_create_key(create_args)
    raw_key = extract_field(capsys.readouterr().out, "api_key")

    list_args = argparse.Namespace(organization_id=str(organization.id))
    cli.cmd_list_keys(list_args)

    list_output = capsys.readouterr().out
    assert raw_key not in list_output
    assert "Listed key" in list_output


def test_cli_revoke_key_disables_authentication(cli, db_session, capsys):
    organization, _ = create_org_and_project(db_session)
    db_session.commit()

    create_args = argparse.Namespace(
        organization_id=str(organization.id),
        name="Revocable key",
        project_id=None,
        environment_id=None,
        expires_days=None,
    )
    cli.cmd_create_key(create_args)
    output = capsys.readouterr().out
    raw_key = extract_field(output, "api_key")
    api_key_id = extract_field(output, "api_key_id")

    cli.cmd_revoke_key(argparse.Namespace(api_key_id=api_key_id))

    from agentops_api.services.api_key_service import verify_api_key

    assert verify_api_key(db_session, raw_key) is None
