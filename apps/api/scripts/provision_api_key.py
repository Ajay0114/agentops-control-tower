"""Administrative CLI for organization bootstrap and API key provisioning.

There is no HTTP endpoint for any of this on purpose: minting an API key or
creating an organization must never be reachable over the network without an
existing credential, and Milestone 5 does not add a user-login system to guard
such an endpoint. This script is the only way to provision the first key for
an organization; it talks to the database directly, the same way the project's
own test fixtures and the Milestone 1 verification script already do.

The raw API key is printed to stdout exactly once, at creation time, and is
never written to a log file or any other file. There is no way to recover it
later - only ``key_prefix`` and metadata are ever stored.

Usage (run from the repository root, with the backend's virtualenv active):

    python apps/api/scripts/provision_api_key.py bootstrap-org \\
        --name "Acme Corp" --slug acme [--project-name "Default" --project-slug default]

    python apps/api/scripts/provision_api_key.py create-key \\
        --organization-id <uuid> --name "Marina prod agent" \\
        [--project-id <uuid>] [--environment-id <uuid>] [--expires-days 90]

    python apps/api/scripts/provision_api_key.py list-keys --organization-id <uuid>

    python apps/api/scripts/provision_api_key.py revoke-key --api-key-id <uuid>
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentops_api.db import SessionLocal  # noqa: E402
from agentops_api.models.core import Organization, Project  # noqa: E402
from agentops_api.services.api_key_service import (  # noqa: E402
    ApiKeyValidationError,
    create_api_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
)


def cmd_bootstrap_org(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        organization = Organization(name=args.name, slug=args.slug)
        db.add(organization)
        db.flush()

        project = None

        if args.project_name:
            if not args.project_slug:
                print("error: --project-slug is required with --project-name", file=sys.stderr)
                sys.exit(1)

            project = Project(
                organization_id=organization.id,
                name=args.project_name,
                slug=args.project_slug,
            )
            db.add(project)
            db.flush()

        db.commit()

        print(f"organization_id: {organization.id}")
        print(f"organization_slug: {organization.slug}")

        if project is not None:
            print(f"project_id: {project.id}")
            print(f"project_slug: {project.slug}")


def cmd_create_key(args: argparse.Namespace) -> None:
    expires_at = None

    if args.expires_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_days)

    with SessionLocal() as db:
        try:
            record, raw_key = create_api_key(
                db,
                organization_id=UUID(args.organization_id),
                name=args.name,
                project_id=UUID(args.project_id) if args.project_id else None,
                environment_id=UUID(args.environment_id) if args.environment_id else None,
                expires_at=expires_at,
            )
        except ApiKeyValidationError as exc:
            db.rollback()
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)

        db.commit()

        print("API key created. This is the ONLY time the raw key is shown.")
        print("Store it securely now - it cannot be retrieved again.")
        print()
        print(f"api_key_id: {record.id}")
        print(f"key_prefix: {record.key_prefix}")
        print(f"api_key: {raw_key}")


def cmd_list_keys(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        records = list_api_keys(db, UUID(args.organization_id))

        if not records:
            print("No API keys found for this organization.")
            return

        for record in records:
            print(
                f"{record.id}  {record.key_prefix}  status={record.status}  "
                f"name={record.name!r}  project_id={record.project_id}  "
                f"environment_id={record.environment_id}  "
                f"expires_at={record.expires_at}  last_used_at={record.last_used_at}"
            )


def cmd_revoke_key(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        record = get_api_key(db, UUID(args.api_key_id))

        if record is None:
            print("error: API key not found", file=sys.stderr)
            sys.exit(1)

        revoke_api_key(db, record)
        db.commit()

        print(f"api_key_id {record.id} revoked")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap-org", help="Create a new organization (and optionally its first project)"
    )
    bootstrap.add_argument("--name", required=True)
    bootstrap.add_argument("--slug", required=True)
    bootstrap.add_argument("--project-name")
    bootstrap.add_argument("--project-slug")
    bootstrap.set_defaults(func=cmd_bootstrap_org)

    create_key = subparsers.add_parser("create-key", help="Provision a new API key")
    create_key.add_argument("--organization-id", required=True)
    create_key.add_argument("--name", required=True)
    create_key.add_argument("--project-id")
    create_key.add_argument("--environment-id")
    create_key.add_argument("--expires-days", type=int)
    create_key.set_defaults(func=cmd_create_key)

    list_keys = subparsers.add_parser("list-keys", help="List API keys for an organization")
    list_keys.add_argument("--organization-id", required=True)
    list_keys.set_defaults(func=cmd_list_keys)

    revoke_key = subparsers.add_parser("revoke-key", help="Revoke an API key")
    revoke_key.add_argument("--api-key-id", required=True)
    revoke_key.set_defaults(func=cmd_revoke_key)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
