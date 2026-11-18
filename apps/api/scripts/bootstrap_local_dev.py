"""Explicit, idempotent local-development bootstrap.

The backend's own startup (see main.py's lifespan, gated on APP_ENV=local)
already runs this automatically - a first-time user does not need to run
this script just to use the dashboard. It exists for the cases where that
automatic path can't reach apps/frontend/.env.local (a different working
directory layout, a container without the frontend mounted, etc.) or where
you want to re-run it explicitly - e.g. to confirm the current state, or to
recover a lost internal key with --rotate.

Never prints the raw key to the terminal in the normal path; it writes
straight to apps/frontend/.env.local, the same way the backend's own
startup hook does. Pass --print-key only if you specifically need to see it
(e.g. no frontend checkout is present) - it is still never logged anywhere.

Usage (run from the repository root, with the backend's virtualenv active):

    python apps/api/scripts/bootstrap_local_dev.py
    python apps/api/scripts/bootstrap_local_dev.py --rotate   # lost-key recovery
    python apps/api/scripts/bootstrap_local_dev.py --print-key
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentops_api.db import SessionLocal  # noqa: E402
from agentops_api.services.bootstrap_service import (  # noqa: E402
    ensure_local_bootstrap,
    rotate_internal_key,
    try_write_frontend_env_local,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Revoke the current internal key and mint a fresh one (lost-key recovery).",
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8010",
        help="Value to write as BACKEND_API_URL (default: http://localhost:8010).",
    )
    parser.add_argument(
        "--print-key",
        action="store_true",
        help="Print the raw key to stdout instead of writing apps/frontend/.env.local. "
        "Use only if that file truly can't be written for you.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        result = ensure_local_bootstrap(db)

        raw_key = result.raw_api_key

        if args.rotate:
            print("Rotating the internal dashboard key (the old one is being revoked)...")
            _, raw_key = rotate_internal_key(
                db,
                organization_id=result.organization_id,
                project_id=result.project_id,
                environment_id=result.environment_id,
            )

    print(f"organization_id: {result.organization_id}")
    print(f"project_id: {result.project_id}")
    print(f"environment_id: {result.environment_id}")
    print(f"internal_api_key_id: {result.api_key_id}")

    if raw_key is None:
        print(
            "An internal key already exists and --rotate was not passed - "
            "nothing new to provision. apps/frontend/.env.local should "
            "already have a working AGENTOPS_API_KEY."
        )
        return

    if args.print_key:
        print("\nThis is the ONLY time the raw key is shown. Store it securely.")
        print(f"AGENTOPS_API_KEY={raw_key}")
        print(f"BACKEND_API_URL={args.backend_url}")
        return

    written = try_write_frontend_env_local(raw_key, args.backend_url)

    if written:
        print("Wrote AGENTOPS_API_KEY and BACKEND_API_URL into apps/frontend/.env.local.")
    else:
        print(
            "Could not locate/write apps/frontend/.env.local automatically. "
            "Re-run with --print-key and add the two lines yourself.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
