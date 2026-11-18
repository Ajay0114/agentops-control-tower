"""add key_type to api_keys

Revision ID: b2c7e8f1a3d5
Revises: 8f3a2c1d9e4b
Create Date: 2026-11-19 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c7e8f1a3d5'
down_revision: Union[str, Sequence[str], None] = '8f3a2c1d9e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'api_keys',
        sa.Column('key_type', sa.String(length=20), server_default='integration', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('api_keys', 'key_type')
