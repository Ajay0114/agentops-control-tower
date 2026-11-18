"""Administrative CLI for bootstrapping the first local dashboard account (M7).

There is no HTTP endpoint for this, for the same reason provision_api_key.py
has none: creating a dashboard account must never be reachable over the
network without an existing credential, and this is the only intended way to
create one. It talks to the database directly, the same way
provision_api_key.py and the project's own test fixtures already do.

By default this refuses to run if ANY user already exists, so it is safe to
re-run accidentally (e.g. from a setup script executed more than once) - it
will never silently create a second administrator or reset an existing one.
Pass --force only if you specifically intend to create an additional account.

The password is never written to a file or log. Supply it via the
BOOTSTRAP_ADMIN_PASSWORD environment variable, or omit --password/the env
var entirely to be prompted interactively (recommended - this keeps it out
of shell history).

Usage (run from the repository root, with the backend's virtualenv active):

    python apps/api/scripts/bootstrap_admin.py \\
        --organization-id <uuid> --email admin@example.com [--project-id <uuid>]

    # Or entirely from environment variables (e.g. in a setup script):
    BOOTSTRAP_ADMIN_ORGANIZATION_ID=<uuid> \\
    BOOTSTRAP_ADMIN_EMAIL=admin@example.com \\
    BOOTSTRAP_ADMIN_PASSWORD=<password> \\
        python apps/api/scripts/bootstrap_admin.py
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentops_api.db import SessionLocal  # noqa: E402
from agentops_api.services.auth_service import (  # noqa: E402
    UserAlreadyExistsError,
    UserValidationError,
    count_users,
    create_user,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--organization-id",
        default=os.environ.get("BOOTSTRAP_ADMIN_ORGANIZATION_ID"),
        help="Existing organization this account belongs to (or $BOOTSTRAP_ADMIN_ORGANIZATION_ID)",
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get("BOOTSTRAP_ADMIN_PROJECT_ID"),
        help="Optional: narrow the account to one existing project (or $BOOTSTRAP_ADMIN_PROJECT_ID)",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("BOOTSTRAP_ADMIN_EMAIL"),
        help="Login email (or $BOOTSTRAP_ADMIN_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD"),
        help="Login password (or $BOOTSTRAP_ADMIN_PASSWORD). If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create this account even if one or more users already exist.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.organization_id:
        print("error: --organization-id (or $BOOTSTRAP_ADMIN_ORGANIZATION_ID) is required", file=sys.stderr)
        sys.exit(1)

    if not args.email:
        print("error: --email (or $BOOTSTRAP_ADMIN_EMAIL) is required", file=sys.stderr)
        sys.exit(1)

    password = args.password

    if not password:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("error: passwords did not match", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("error: password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    with SessionLocal() as db:
        existing_count = count_users(db)

        if existing_count > 0 and not args.force:
            print(
                f"error: {existing_count} user(s) already exist. "
                "Refusing to bootstrap another admin without --force.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            user = create_user(
                db,
                organization_id=UUID(args.organization_id),
                project_id=UUID(args.project_id) if args.project_id else None,
                email=args.email,
                password=password,
            )
        except (UserValidationError, UserAlreadyExistsError) as exc:
            db.rollback()
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)

        db.commit()

        print("Local administrator created.")
        print(f"user_id: {user.id}")
        print(f"email: {user.email}")
        print(f"organization_id: {user.organization_id}")
        print(f"project_id: {user.project_id}")


if __name__ == "__main__":
    main()
