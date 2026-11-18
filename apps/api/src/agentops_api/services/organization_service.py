"""Self-service organization/project creation for the customer-onboarding
flow (signup -> organization -> project -> environment -> integration key).

Reuses the exact ``Organization``/``Project`` models and uniqueness
constraints the existing ``provision_api_key.py bootstrap-org`` CLI command
already relies on (see its module docstring) - this module is simply that
same creation logic, made safe to call from an HTTP request (auto-deriving
a URL-safe slug from the human-entered name, with a bounded retry on a
collision, rather than requiring the caller to invent one) and, for
projects, scoped by the caller's own verified :class:`AuthContext` so a
customer can only ever create a project inside their own organization.
"""

import re
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import Organization, Project


MAX_SLUG_ATTEMPTS = 5
SLUG_SUFFIX_BYTES = 3  # -> 6 hex characters, only appended on a collision


class OrganizationValidationError(Exception):
    pass


def slugify(name: str) -> str:
    """Derives a URL-safe, lowercase slug from a human-entered name.

    Not cryptographic and not required to be reversible - just a readable
    default so a first-time customer is never asked to invent a slug
    themselves. A name with no alphanumeric characters at all falls back to
    "org"/"project" (callers pass that in), never an empty string, since
    every slug column here is non-nullable.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "org"


def create_organization(db: DBSession, *, name: str) -> Organization:
    """Creates a brand-new organization for a self-service signup.

    Unlike ``bootstrap_service.py``'s ``_get_or_create_organization``, this
    always creates a *new* row - a signup is, by definition, a new tenant,
    never a lookup of an existing one. The slug collision retry exists only
    because the slug is derived from free-text input, not because two
    signups for the same organization name should ever be merged.
    """
    base_slug = slugify(name)

    for attempt in range(MAX_SLUG_ATTEMPTS):
        slug = base_slug if attempt == 0 else f"{base_slug}-{secrets.token_hex(SLUG_SUFFIX_BYTES)}"

        organization = Organization(name=name, slug=slug)
        db.add(organization)

        try:
            db.flush()
            return organization
        except IntegrityError:
            db.rollback()

    raise OrganizationValidationError(
        "Could not generate a unique organization slug after several attempts"
    )


def create_project(db: DBSession, *, name: str, auth: AuthContext) -> Project:
    """Creates a new project inside the caller's own organization.

    ``auth.organization_id`` - never anything the request body could supply
    - is the only source of which organization this project belongs to,
    the same rule every other tenant-scoped write in this codebase follows
    (see tenant_scope.py's module docstring). Rejected if the caller's own
    identity is already narrowed to one specific project or environment:
    such a caller has no standing to create a sibling, mirroring
    environment_service.create_environment's identical check.
    """
    if auth.project_id is not None or auth.environment_id is not None:
        raise OrganizationValidationError("Organization not found")

    base_slug = slugify(name)

    for attempt in range(MAX_SLUG_ATTEMPTS):
        slug = base_slug if attempt == 0 else f"{base_slug}-{secrets.token_hex(SLUG_SUFFIX_BYTES)}"

        project = Project(organization_id=auth.organization_id, name=name, slug=slug)
        db.add(project)

        try:
            db.flush()
            return project
        except IntegrityError:
            db.rollback()

    raise OrganizationValidationError(
        "Could not generate a unique project slug after several attempts"
    )
