"""enforce at most one internal api key per organization

Revision ID: c4d9f2a6b8e1
Revises: b2c7e8f1a3d5
Create Date: 2026-11-19 10:00:00.000000

A partial unique index, not a blanket one: integration keys (the vast
majority of rows, and the only kind a platform user creates) keep allowing
duplicate names - API key names are just labels, not identifiers, and
tools like this commonly let you create two keys called "CI key". Only
*active* key_type='internal' rows are constrained to one per organization
(the predicate includes status='active', not just key_type='internal' -
otherwise rotate_internal_key's revoke-then-create recovery path could
never create a replacement, since the just-revoked row would still count
toward the uniqueness check). This is what actually needs to be true for
bootstrap_service.py's concurrent-safety guarantee to hold at the database
level rather than just in application code.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4d9f2a6b8e1'
down_revision: Union[str, Sequence[str], None] = 'b2c7e8f1a3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'uq_api_keys_one_internal_per_organization',
        'api_keys',
        ['organization_id'],
        unique=True,
        postgresql_where="key_type = 'internal' AND status = 'active'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_api_keys_one_internal_per_organization', table_name='api_keys')
